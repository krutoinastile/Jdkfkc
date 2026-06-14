from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.database.models import Application


def applications_keyboard(applications: list[Application]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for application in applications:
        user = application.user
        username = f"@{user.username}" if user.username else str(user.tg_id)
        builder.button(
            text=f"#{application.id} | {username} | UID {user.bingx_uid or '-'}",
            callback_data=f"admin:application:{application.id}:open",
        )
    builder.button(text="🔄 Обновить", callback_data="admin:applications:refresh")
    builder.adjust(1)
    return builder.as_markup()


def decision_keyboard(application_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Одобрить", callback_data=f"admin:application:{application_id}:approve")
    builder.button(text="❌ Отклонить", callback_data=f"admin:application:{application_id}:reject")
    builder.button(text="📝 Запросить повторно", callback_data=f"admin:application:{application_id}:resubmit")
    builder.button(text="🚫 Заблокировать", callback_data=f"admin:application:{application_id}:block")
    builder.button(text="⬅️ К списку", callback_data="admin:applications:refresh")
    builder.adjust(2, 1, 1, 1)
    return builder.as_markup()
