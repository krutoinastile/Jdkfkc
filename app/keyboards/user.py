from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.config import Settings


def main_menu_keyboard(settings: Settings) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🚀 Зарегистрироваться в BingX", url=settings.bingx_ref_link)
    builder.button(text="✅ Я зарегистрировался", callback_data="user:registered")
    builder.button(text="📩 Подать заявку", callback_data="application:start")
    builder.button(text="🔎 Проверить статус", callback_data="user:status")
    if settings.support_url:
        builder.button(text="💬 Поддержка", url=settings.support_url)
    else:
        builder.button(text="💬 Поддержка", callback_data="user:support")
    builder.adjust(1)
    return builder.as_markup()


def registered_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📩 Подать заявку", callback_data="application:start")
    builder.button(text="🏠 Главное меню", callback_data="user:menu")
    builder.adjust(1)
    return builder.as_markup()


def cancel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отменить", callback_data="application:cancel")
    return builder.as_markup()
