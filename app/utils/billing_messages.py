"""Billing and subscription message templates."""

from __future__ import annotations

from datetime import datetime

from app.database.billing_repositories import is_subscription_active
from app.database.models import BillingSettings, Giveaway, User
from app.utils.formatting import footer, header, kv, section


def format_subscription_page(
    user: User,
    billing: BillingSettings,
    *,
    price: float,
    bot_username: str,
    referral_stats: dict,
    giveaway_info: dict | None,
) -> str:
    if is_subscription_active(user):
        until = user.subscription_until.strftime("%d.%m.%Y %H:%M UTC") if user.subscription_until else "—"
        status = f"✅ Активна до <b>{until}</b>"
    else:
        status = "❌ Не активна — сигналы недоступны"

    asset = billing.subscription_asset
    lines = [
        f"{header('💎 Подписка', 'Доступ к торговым сигналам')}\n",
        f"{section('Статус')}\n{status}\n",
        f"{section('Тариф')}\n",
        f"{kv('Период', f'<b>{billing.subscription_days} дн.</b>')}\n",
        f"{kv('Цена', f'<b>{price:.2f} {asset}</b>')}\n",
    ]

    discounts = []
    if billing.discount_enabled and billing.discount_percent:
        discounts.append(f"−{billing.discount_percent:g}% общая скидка")
    if user.referrer_id and billing.referral_discount_percent:
        discounts.append(f"−{billing.referral_discount_percent:g}% по реф. ссылке")
    if giveaway_info and giveaway_info["giveaway"].extra_discount_percent:
        discounts.append(f"−{giveaway_info['giveaway'].extra_discount_percent:g}% розыгрыш")
    if discounts:
        lines.append(f"{kv('Скидки', ', '.join(discounts))}\n")

    code = user.referral_code or "—"
    link = f"https://t.me/{bot_username}?start=ref_{code}"
    lines.extend([
        f"{section('Реферальная программа')}\n",
        f"{kv('Приглашено', f'<b>{referral_stats["total"]}</b>')}\n",
        f"{kv('Оплатили', f'<b>{referral_stats["paid"]}</b>')}\n",
        f"{kv('Бонус', f'<b>+{billing.referral_bonus_days} дн.</b> за оплату друга')}\n",
        f"{kv('Ваша ссылка', f'<code>{link}</code>')}\n",
    ])

    if giveaway_info:
        g: Giveaway = giveaway_info["giveaway"]
        ends = g.ends_at.strftime("%d.%m.%Y %H:%M UTC")
        lines.extend([
            f"{section('🎁 Розыгрыш')}\n",
            f"{kv('Приз', f'<b>{g.prize_days} дн.</b> подписки · {g.winners_count} поб.')}\n",
            f"{kv('Участников', f'<b>{giveaway_info["entries"]}</b>')}\n",
            f"{kv('До', ends)}\n",
        ])

    lines.append(
        "\n<i>Оплата через Crypto Bot (@CryptoBot).\n"
        "После оплаты доступ открывается автоматически.</i>"
    )
    lines.append(footer())
    return "".join(lines)


def format_subscription_paywall() -> str:
    return (
        f"{header('🔒 Нужна подписка')}\n\n"
        f"Сигналы с Entry, Stop-Loss и Take-Profit\n"
        f"доступны только подписчикам.\n\n"
        f"Откройте раздел <b>💎 Подписка</b> для оплаты."
        f"{footer()}"
    )


def format_billing_admin(billing: BillingSettings, *, token_set: bool, giveaway: Giveaway | None) -> str:
    token_status = "✅ установлен" if token_set else "❌ не задан"
    discount = f"−{billing.discount_percent:g}%" if billing.discount_enabled else "выкл"
    giveaway_line = "нет активного"
    if giveaway:
        giveaway_line = (
            f"{giveaway.title} · {giveaway.winners_count} поб. · "
            f"{giveaway.prize_days} дн. · −{giveaway.extra_discount_percent:g}%"
        )
    return (
        f"{header('💎 Подписка', 'Crypto Pay · тариф · рефералы')}\n\n"
        f"{kv('Crypto Pay token', token_status)}\n"
        f"{kv('Testnet', '✅' if billing.cryptopay_testnet else '❌')}\n"
        f"{kv('Цена', f'<b>{billing.subscription_price:g} {billing.subscription_asset}</b>')}\n"
        f"{kv('Период', f'<b>{billing.subscription_days} дн.</b>')}\n"
        f"{kv('Скидка', discount)}\n"
        f"{kv('Реф. бонус', f'+{billing.referral_bonus_days} дн.')}\n"
        f"{kv('Реф. скидка', f'−{billing.referral_discount_percent:g}%')}\n"
        f"{kv('Сигналы только VIP', '✅' if billing.require_subscription_for_signals else '❌')}\n"
        f"{kv('Розыгрыш', giveaway_line)}\n"
    )
