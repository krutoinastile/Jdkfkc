"""Format and send payment invoices."""

from __future__ import annotations

import uuid

from aiogram import Bot
from aiogram.types import LabeledPrice

from app.database.models import Account, PaymentSettings


def format_price(settings: PaymentSettings) -> str:
    if settings.currency == "XTR":
        return f"{settings.price_amount} ⭐"
    if settings.currency == "RUB":
        rubles = settings.price_amount / 100
        if settings.price_amount % 100 == 0:
            return f"{int(rubles)} ₽"
        return f"{rubles:.2f} ₽"
    return f"{settings.price_amount} {settings.currency}"


def mask_provider_token(token: str | None) -> str:
    if not token:
        return "не задан (Stars)"
    if len(token) <= 8:
        return "••••••••"
    return f"{'•' * (len(token) - 8)}{token[-8:]}"


def payment_settings_text(settings: PaymentSettings) -> str:
    status = "включена" if settings.is_enabled else "выключена"
    currency_label = "Telegram Stars" if settings.currency == "XTR" else settings.currency
    return (
        "<b>Настройки оплаты</b>\n\n"
        f"Статус: <b>{status}</b>\n"
        f"Цена: <b>{format_price(settings)}</b>\n"
        f"Валюта: <b>{currency_label}</b>\n"
        f"Дней подписки: <b>{settings.subscription_days}</b>\n"
        f"Provider token: <code>{mask_provider_token(settings.provider_token)}</code>\n"
        f"Товар: {settings.product_title}"
    )


def build_invoice_payload(account: Account) -> str:
    return f"subscription:{account.id}:{uuid.uuid4().hex}"


async def send_subscription_invoice(
    bot: Bot,
    chat_id: int,
    account: Account,
    settings: PaymentSettings,
) -> None:
    if not settings.is_enabled:
        raise ValueError("payments_disabled")
    if settings.currency != "XTR" and not settings.provider_token:
        raise ValueError("provider_token_required")

    provider_token = settings.provider_token or ""
    await bot.send_invoice(
        chat_id=chat_id,
        title=settings.product_title,
        description=(
            f"{settings.product_description}\n"
            f"Срок: {settings.subscription_days} дн."
        ),
        payload=build_invoice_payload(account),
        provider_token=provider_token,
        currency=settings.currency,
        prices=[LabeledPrice(label=settings.product_title, amount=settings.price_amount)],
    )
