"""Crypto Pay payment processing."""

from __future__ import annotations

import logging

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import CryptoInvoice
from app.database.repositories import (
    create_payment_record,
    extend_subscription,
    get_account_by_id,
    get_crypto_invoice_by_crypto_id,
    get_payment_by_charge_id,
    get_payment_settings,
    mark_crypto_invoice_paid,
)
from app.services.cryptopay import CryptoPayClient, CryptoPayError
from app.services.payments import build_invoice_payload, format_price, mask_provider_token
from app.utils.text import subscription_status_text

logger = logging.getLogger(__name__)


def format_crypto_price(asset: str, amount: str) -> str:
    return f"{amount} {asset}"


def payment_method_label(currency: str) -> str:
    if currency == "XTR":
        return "Telegram Stars"
    if currency == "RUB":
        return "Рубли (Telegram Payments)"
    if currency == "CRYPTO":
        return "Crypto Pay"
    return currency


def payment_settings_text(settings) -> str:
    status = "включена" if settings.is_enabled else "выключена"
    lines = [
        "<b>Настройки оплаты</b>\n",
        f"Статус: <b>{status}</b>",
        f"Способ: <b>{payment_method_label(settings.currency)}</b>",
        f"Дней подписки: <b>{settings.subscription_days}</b>",
        f"Товар: {settings.product_title}",
    ]

    if settings.currency == "CRYPTO":
        lines.extend(
            [
                f"Цена: <b>{format_crypto_price(settings.crypto_asset, settings.crypto_amount)}</b>",
                f"Сеть: <b>{'Testnet' if settings.crypto_testnet else 'Mainnet'}</b>",
                f"Crypto Pay API: <code>{mask_provider_token(settings.crypto_pay_api_token)}</code>",
            ]
        )
    else:
        lines.extend(
            [
                f"Цена: <b>{format_price(settings)}</b>",
                f"Provider token: <code>{mask_provider_token(settings.provider_token)}</code>",
            ]
        )
    return "\n".join(lines)


async def create_crypto_subscription_invoice(session: AsyncSession, account, settings) -> CryptoInvoice:
    from app.database.repositories import create_crypto_invoice_record

    if not settings.crypto_pay_api_token:
        raise ValueError("crypto_token_required")

    payload = build_invoice_payload(account)
    client = CryptoPayClient(settings.crypto_pay_api_token, testnet=settings.crypto_testnet)
    try:
        result = await client.create_invoice(
            asset=settings.crypto_asset,
            amount=settings.crypto_amount,
            description=f"{settings.product_title} — {settings.subscription_days} дн.",
            payload=payload,
        )
    except CryptoPayError as exc:
        logger.exception("Crypto Pay createInvoice failed")
        raise ValueError("crypto_invoice_failed") from exc

    return await create_crypto_invoice_record(
        session,
        account_id=account.id,
        crypto_invoice_id=int(result["invoice_id"]),
        payload=payload,
        asset=settings.crypto_asset,
        amount=settings.crypto_amount,
        pay_url=result.get("bot_invoice_url") or result.get("pay_url"),
    )


async def process_paid_crypto_invoice(
    session: AsyncSession,
    bot: Bot,
    invoice: CryptoInvoice,
    *,
    notify_user: bool,
) -> bool:
    if invoice.status == "paid":
        return False

    settings = await get_payment_settings(session)
    if not settings.crypto_pay_api_token:
        return False

    client = CryptoPayClient(settings.crypto_pay_api_token, testnet=settings.crypto_testnet)
    try:
        remote = await client.get_invoice(invoice.crypto_invoice_id)
    except CryptoPayError:
        logger.exception("Crypto Pay getInvoices failed for %s", invoice.crypto_invoice_id)
        return False

    if remote is None or remote.get("status") != "paid":
        return False

    charge_id = f"crypto:{invoice.crypto_invoice_id}"
    if await get_payment_by_charge_id(session, charge_id):
        await mark_crypto_invoice_paid(session, invoice)
        return False

    await create_payment_record(
        session,
        account_id=invoice.account_id,
        telegram_payment_charge_id=charge_id,
        payload=invoice.payload,
        currency="CRYPTO",
        total_amount=0,
        subscription_days=settings.subscription_days,
    )
    await mark_crypto_invoice_paid(session, invoice)

    account = await get_account_by_id(session, invoice.account_id)
    if account is None:
        return False
    account = await extend_subscription(session, account, settings.subscription_days)

    if notify_user:
        try:
            await bot.send_message(
                chat_id=account.tg_id,
                text=(
                    "✅ <b>Крипто-оплата прошла успешно!</b>\n\n"
                    f"Подписка продлена на {settings.subscription_days} дн.\n"
                    f"{subscription_status_text(account)}"
                ),
            )
        except Exception:
            logger.exception("Failed to notify user %s about crypto payment", account.tg_id)
    return True


async def check_crypto_invoice_by_id(
    session: AsyncSession,
    bot: Bot,
    *,
    crypto_invoice_id: int,
    user_tg_id: int,
) -> str:
    invoice = await get_crypto_invoice_by_crypto_id(session, crypto_invoice_id)
    if invoice is None:
        return "not_found"
    if invoice.account.tg_id != user_tg_id:
        return "forbidden"
    if invoice.status == "paid":
        return "already_paid"

    paid = await process_paid_crypto_invoice(session, bot, invoice, notify_user=False)
    return "paid" if paid else "pending"
