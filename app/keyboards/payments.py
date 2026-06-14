from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.database.models import PaymentSettings
from app.services.payments import format_price


def subscription_keyboard(payment_settings: PaymentSettings | None) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if payment_settings and payment_settings.is_enabled:
        price = format_price(payment_settings)
        rows.append(
            [InlineKeyboardButton(text=f"💳 Оплатить {price}", callback_data="pay:subscription")]
        )
    rows.append([InlineKeyboardButton(text="◀️ Меню", callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_payment_keyboard(settings: PaymentSettings) -> InlineKeyboardMarkup:
    toggle_label = "🔴 Выключить оплату" if settings.is_enabled else "🟢 Включить оплату"
    currency_toggle = "💱 Переключить на RUB" if settings.currency == "XTR" else "💱 Переключить на Stars"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=toggle_label, callback_data="admin:payments:toggle")],
            [
                InlineKeyboardButton(text="✏️ Цена", callback_data="admin:payments:edit:price"),
                InlineKeyboardButton(text="📅 Дни", callback_data="admin:payments:edit:days"),
            ],
            [
                InlineKeyboardButton(text="🔑 Provider token", callback_data="admin:payments:edit:token"),
                InlineKeyboardButton(text=currency_toggle, callback_data="admin:payments:currency:toggle"),
            ],
            [InlineKeyboardButton(text="◀️ Админ", callback_data="admin:home")],
        ]
    )
