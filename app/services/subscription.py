"""Subscription pricing, payments, referrals, and access control."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.database.billing_repositories import (
    count_giveaway_entries,
    count_paid_referrals,
    count_referrals,
    create_payment_invoice,
    extend_subscription,
    get_active_giveaway,
    get_billing_settings,
    get_payment_by_cryptopay_id,
    is_subscription_active,
    list_pending_invoices,
    mark_invoice_expired,
    mark_invoice_paid,
)
from app.database.models import PaymentStatus, User
from app.database.repositories import get_or_create_user, list_subscribed_users
from app.services.cryptopay import CryptoPayClient, CryptoPayError

from app.utils.datetime_utils import ensure_utc

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(tz=UTC)


def calculate_subscription_price(
    billing,
    *,
    has_referral: bool,
    giveaway=None,
) -> float:
    price = float(billing.subscription_price)
    if billing.discount_enabled and billing.discount_percent > 0:
        price *= 1 - billing.discount_percent / 100
    if has_referral and billing.referral_discount_percent > 0:
        price *= 1 - billing.referral_discount_percent / 100
    if giveaway and giveaway.extra_discount_percent > 0:
        price *= 1 - giveaway.extra_discount_percent / 100
    return round(max(price, 0.01), 2)


async def user_has_signal_access(session: AsyncSession, user: User, settings: Settings) -> bool:
    if user.tg_id in settings.parsed_admin_ids:
        return True
    billing = await get_billing_settings(session)
    if not billing.require_subscription_for_signals:
        return True
    return is_subscription_active(user)


async def list_premium_notify_users(session: AsyncSession, settings: Settings) -> list[User]:
    billing = await get_billing_settings(session)
    users = await list_subscribed_users(session)
    if not billing.require_subscription_for_signals:
        return users
    return [u for u in users if is_subscription_active(u)]


async def create_subscription_invoice(session: AsyncSession, user: User) -> tuple[str, int]:
    billing = await get_billing_settings(session)
    giveaway = await get_active_giveaway(session)
    has_referral = user.referrer_id is not None
    amount = calculate_subscription_price(billing, has_referral=has_referral, giveaway=giveaway)

    client = CryptoPayClient(billing.cryptopay_api_token, testnet=billing.cryptopay_testnet)
    payload = f"sub:{user.id}:{int(_now().timestamp())}"
    invoice = await client.create_invoice(
        asset=billing.subscription_asset,
        amount=f"{amount:.2f}",
        description=f"Подписка на сигналы · {billing.subscription_days} дн.",
        payload=payload,
    )
    await create_payment_invoice(
        session,
        user_id=user.id,
        cryptopay_invoice_id=invoice.invoice_id,
        amount=invoice.amount,
        asset=invoice.asset,
        pay_url=invoice.pay_url,
        payload=payload,
    )
    return invoice.pay_url, invoice.invoice_id


async def activate_subscription_payment(session: AsyncSession, user: User, billing) -> User:
    user = await extend_subscription(session, user, billing.subscription_days)
    if user.referrer_id:
        result = await session.get(User, user.referrer_id)
        if result and billing.referral_bonus_days > 0:
            await extend_subscription(session, result, billing.referral_bonus_days)
    return user


async def process_paid_invoice(session: AsyncSession, bot: Bot, invoice_id: int) -> bool:
    payment = await get_payment_by_cryptopay_id(session, invoice_id)
    if payment is None or payment.status == PaymentStatus.PAID.value:
        return False

    billing = await get_billing_settings(session)
    user = await session.get(User, payment.user_id)
    if user is None:
        return False

    await mark_invoice_paid(session, payment)
    user = await activate_subscription_payment(session, user, billing)

    try:
        until = user.subscription_until.strftime("%d.%m.%Y %H:%M UTC") if user.subscription_until else "—"
        await bot.send_message(
            user.tg_id,
            f"✅ <b>Оплата получена!</b>\n\n"
            f"Подписка активна до: <b>{until}</b>\n"
            f"Сигналы с Entry / SL / TP снова доступны.",
        )
    except Exception:
        logger.exception("Failed to notify user %s about payment", user.tg_id)

    if user.referrer_id:
        referrer = await session.get(User, user.referrer_id)
        if referrer and billing.referral_bonus_days > 0:
            try:
                ref_until = referrer.subscription_until.strftime("%d.%m.%Y") if referrer.subscription_until else "—"
                await bot.send_message(
                    referrer.tg_id,
                    f"🎁 <b>Реферальный бонус!</b>\n\n"
                    f"+{billing.referral_bonus_days} дн. подписки за оплату друга.\n"
                    f"Активна до: <b>{ref_until}</b>",
                )
            except Exception:
                logger.exception("Failed to notify referrer %s", referrer.tg_id)
    return True


async def poll_pending_invoices(session: AsyncSession, bot: Bot) -> None:
    billing = await get_billing_settings(session)
    if not billing.cryptopay_api_token:
        return

    pending = await list_pending_invoices(session)
    if not pending:
        return

    try:
        client = CryptoPayClient(billing.cryptopay_api_token, testnet=billing.cryptopay_testnet)
    except CryptoPayError:
        return

    for payment in pending:
        try:
            remote = await client.get_invoice(payment.cryptopay_invoice_id)
        except CryptoPayError:
            logger.exception("Failed to fetch invoice %s", payment.cryptopay_invoice_id)
            continue
        if remote is None:
            continue
        if remote.status == "paid":
            await process_paid_invoice(session, bot, payment.cryptopay_invoice_id)
        elif remote.status == "expired":
            await mark_invoice_expired(session, payment)


async def get_referral_stats(session: AsyncSession, user: User) -> dict:
    return {
        "total": await count_referrals(session, user.id),
        "paid": await count_paid_referrals(session, user.id),
    }


async def get_giveaway_stats(session: AsyncSession) -> dict | None:
    giveaway = await get_active_giveaway(session)
    if giveaway is None:
        return None
    return {
        "giveaway": giveaway,
        "entries": await count_giveaway_entries(session, giveaway.id),
    }


async def send_subscription_reminders(session: AsyncSession, bot: Bot) -> None:
    """Notify users whose subscription expires within 3 days."""
    from datetime import timedelta

    from sqlalchemy import select

    now = _now()
    window_end = now + timedelta(days=3)
    result = await session.execute(
        select(User).where(
            User.subscription_until.is_not(None),
            User.subscription_until > now,
            User.subscription_until <= window_end,
        )
    )
    users = list(result.scalars().all())
    for user in users:
        until = ensure_utc(user.subscription_until)
        if until is None:
            continue
        days_left = max(0, (until - now).days)
        until_text = until.strftime("%d.%m.%Y %H:%M UTC")
        try:
            await bot.send_message(
                user.tg_id,
                f"⏳ <b>Подписка скоро истекает</b>\n\n"
                f"Осталось: <b>{days_left} дн.</b> (до {until_text})\n"
                f"Продлите в разделе 💎 Подписка, чтобы не пропустить сигналы.",
            )
        except Exception:
            logger.exception("Subscription reminder failed for %s", user.tg_id)

