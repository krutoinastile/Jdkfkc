from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.database.models import PaymentSettings
from app.services.payments import format_price


def subscription_keyboard(payment_settings: PaymentSettings | None) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if payment_settings and payment_settings.is_enabled:
        price = format_price(payment_settings)
        label = f"💳 Оплатить {price}"
        if payment_settings.currency == "CRYPTO":
            label = f"🪙 Оплатить {price}"
        rows.append([InlineKeyboardButton(text=label, callback_data="pay:subscription")])
    rows.append([InlineKeyboardButton(text="◀️ Меню", callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def crypto_pay_keyboard(pay_url: str, crypto_invoice_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🪙 Перейти к оплате", url=pay_url)],
            [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"pay:crypto:check:{crypto_invoice_id}")],
            [InlineKeyboardButton(text="◀️ Меню", callback_data="menu:home")],
        ]
    )


def admin_payment_keyboard(settings: PaymentSettings) -> InlineKeyboardMarkup:
    toggle_label = "🔴 Выключить оплату" if settings.is_enabled else "🟢 Включить оплату"
    method_labels = {"XTR": "Stars → RUB", "RUB": "RUB → Crypto", "CRYPTO": "Crypto → Stars"}
    method_toggle = method_labels.get(settings.currency, "Сменить способ")

    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text=toggle_label, callback_data="admin:payments:toggle")],
        [
            InlineKeyboardButton(text="✏️ Цена", callback_data="admin:payments:edit:price"),
            InlineKeyboardButton(text="📅 Дни", callback_data="admin:payments:edit:days"),
        ],
        [InlineKeyboardButton(text=f"💱 {method_toggle}", callback_data="admin:payments:method:next")],
    ]

    if settings.currency == "CRYPTO":
        rows.append(
            [
                InlineKeyboardButton(text="🔑 Crypto Pay API", callback_data="admin:payments:edit:crypto_token"),
                InlineKeyboardButton(text="🪙 Монета", callback_data="admin:payments:edit:crypto_asset"),
            ]
        )
        testnet_label = "🔬 Testnet: ВКЛ" if settings.crypto_testnet else "🔬 Testnet: ВЫКЛ"
        rows.append([InlineKeyboardButton(text=testnet_label, callback_data="admin:payments:crypto:testnet")])
    else:
        rows.append(
            [InlineKeyboardButton(text="🔑 Provider token", callback_data="admin:payments:edit:token")]
        )

    rows.append([InlineKeyboardButton(text="◀️ Админ", callback_data="admin:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


CRYPTO_ASSETS = ("USDT", "TON", "BTC", "ETH", "LTC", "BNB", "TRX", "USDC")


def admin_crypto_asset_keyboard(current: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for asset in CRYPTO_ASSETS:
        prefix = "✅ " if asset == current else ""
        row.append(InlineKeyboardButton(text=f"{prefix}{asset}", callback_data=f"admin:payments:asset:{asset}"))
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin:payments")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
