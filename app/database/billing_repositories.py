"""Billing, subscription, referral, and giveaway repositories."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    BillingSettings,
    Giveaway,
    GiveawayEntry,
    PaymentInvoice,
    PaymentStatus,
    User,
)


def _now() -> datetime:
    return datetime.now(tz=UTC)


async def get_billing_settings(session: AsyncSession) -> BillingSettings:
    result = await session.execute(select(BillingSettings).where(BillingSettings.id == 1))
    row = result.scalar_one_or_none()
    if row is None:
        row = BillingSettings(id=1)
        session.add(row)
        await session.commit()
        await session.refresh(row)
    return row


async def update_billing_settings(session: AsyncSession, **fields: object) -> BillingSettings:
    row = await get_billing_settings(session)
    for key, value in fields.items():
        setattr(row, key, value)
    await session.commit()
    await session.refresh(row)
    return row


def is_subscription_active(user: User, *, now: datetime | None = None) -> bool:
    if user.subscription_until is None:
        return False
    return user.subscription_until > (now or _now())


async def revoke_subscription(session: AsyncSession, user: User) -> User:
    user.subscription_until = None
    await session.commit()
    await session.refresh(user)
    return user


async def extend_subscription(session: AsyncSession, user: User, days: int) -> User:
    now = _now()
    base = user.subscription_until if user.subscription_until and user.subscription_until > now else now
    user.subscription_until = base + timedelta(days=days)
    await session.commit()
    await session.refresh(user)
    return user


async def get_user_by_referral_code(session: AsyncSession, code: str) -> User | None:
    result = await session.execute(select(User).where(User.referral_code == code))
    return result.scalar_one_or_none()


async def count_referrals(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(
        select(func.count(User.id)).where(User.referrer_id == user_id)
    )
    return int(result.scalar_one())


async def count_paid_referrals(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(
        select(func.count(User.id))
        .where(User.referrer_id == user_id)
        .where(User.subscription_until.is_not(None))
    )
    return int(result.scalar_one())


async def create_payment_invoice(
    session: AsyncSession,
    *,
    user_id: int,
    cryptopay_invoice_id: int,
    amount: str,
    asset: str,
    pay_url: str,
    payload: str,
) -> PaymentInvoice:
    invoice = PaymentInvoice(
        user_id=user_id,
        cryptopay_invoice_id=cryptopay_invoice_id,
        amount=amount,
        asset=asset,
        pay_url=pay_url,
        payload=payload,
    )
    session.add(invoice)
    await session.commit()
    await session.refresh(invoice)
    return invoice


async def get_payment_by_cryptopay_id(session: AsyncSession, invoice_id: int) -> PaymentInvoice | None:
    result = await session.execute(
        select(PaymentInvoice).where(PaymentInvoice.cryptopay_invoice_id == invoice_id)
    )
    return result.scalar_one_or_none()


async def list_pending_invoices(session: AsyncSession) -> list[PaymentInvoice]:
    result = await session.execute(
        select(PaymentInvoice).where(PaymentInvoice.status == PaymentStatus.PENDING.value)
    )
    return list(result.scalars().all())


async def mark_invoice_paid(session: AsyncSession, invoice: PaymentInvoice) -> PaymentInvoice:
    invoice.status = PaymentStatus.PAID.value
    invoice.paid_at = _now()
    await session.commit()
    await session.refresh(invoice)
    return invoice


async def mark_invoice_expired(session: AsyncSession, invoice: PaymentInvoice) -> None:
    invoice.status = PaymentStatus.EXPIRED.value
    await session.commit()


async def get_active_giveaway(session: AsyncSession) -> Giveaway | None:
    now = _now()
    result = await session.execute(
        select(Giveaway)
        .where(Giveaway.is_active.is_(True))
        .where(Giveaway.drawn_at.is_(None))
        .where(Giveaway.ends_at > now)
        .order_by(Giveaway.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def create_giveaway(
    session: AsyncSession,
    *,
    title: str,
    prize_days: int,
    winners_count: int,
    extra_discount_percent: float,
    duration_days: int,
) -> Giveaway:
    await deactivate_active_giveaways(session)
    row = Giveaway(
        title=title,
        prize_days=prize_days,
        winners_count=winners_count,
        extra_discount_percent=extra_discount_percent,
        ends_at=_now() + timedelta(days=duration_days),
        is_active=True,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def deactivate_active_giveaways(session: AsyncSession) -> None:
    result = await session.execute(select(Giveaway).where(Giveaway.is_active.is_(True)))
    for row in result.scalars().all():
        row.is_active = False
    await session.commit()


async def enter_giveaway(session: AsyncSession, giveaway: Giveaway, user: User) -> GiveawayEntry:
    existing = await session.execute(
        select(GiveawayEntry)
        .where(GiveawayEntry.giveaway_id == giveaway.id)
        .where(GiveawayEntry.user_id == user.id)
    )
    entry = existing.scalar_one_or_none()
    if entry:
        return entry
    entry = GiveawayEntry(giveaway_id=giveaway.id, user_id=user.id)
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    return entry


async def count_giveaway_entries(session: AsyncSession, giveaway_id: int) -> int:
    result = await session.execute(
        select(func.count(GiveawayEntry.id)).where(GiveawayEntry.giveaway_id == giveaway_id)
    )
    return int(result.scalar_one())


async def list_giveaway_entries(session: AsyncSession, giveaway_id: int) -> list[GiveawayEntry]:
    result = await session.execute(
        select(GiveawayEntry).where(GiveawayEntry.giveaway_id == giveaway_id)
    )
    return list(result.scalars().all())


async def finish_giveaway(session: AsyncSession, giveaway: Giveaway) -> Giveaway:
    giveaway.is_active = False
    giveaway.drawn_at = _now()
    await session.commit()
    await session.refresh(giveaway)
    return giveaway


def generate_referral_code() -> str:
    return secrets.token_hex(4)
