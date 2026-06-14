from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.database.models import Application, ApplicationDecision


PAGE_SIZE = 5

DECISION_LABELS = {
    ApplicationDecision.PENDING.value: "📥 Новые",
    ApplicationDecision.APPROVED.value: "✅ Одобрено",
    ApplicationDecision.REJECTED.value: "❌ Отклонено",
    ApplicationDecision.RESUBMIT.value: "📝 Повторно",
    ApplicationDecision.BLOCKED.value: "🚫 Заблокировано",
}

REASON_LABELS = {
    "bad_uid": "Неверный UID",
    "no_registration": "Нет/плохой скрин регистрации",
    "no_deposit": "Нет/плохой скрин пополнения",
    "not_referral": "Не видно регистрацию по реф-ссылке",
    "other": "Другая причина",
}


def dashboard_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📥 Новые заявки", callback_data="admin:list:pending:0")
    builder.button(text="✅ Одобрено", callback_data="admin:list:approved:0")
    builder.button(text="❌ Отклонено", callback_data="admin:list:rejected:0")
    builder.button(text="📝 Повторно", callback_data="admin:list:resubmit:0")
    builder.button(text="🚫 Заблокировано", callback_data="admin:list:blocked:0")
    builder.button(text="🔎 Поиск", callback_data="admin:search")
    builder.button(text="🔄 Обновить", callback_data="admin:menu")
    builder.adjust(1, 2, 2, 1, 1)
    return builder.as_markup()


def applications_keyboard(
    applications: list[Application],
    status: str,
    page: int,
    total: int,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for application in applications:
        user = application.user
        username = f"@{user.username}" if user.username else str(user.tg_id)
        builder.button(
            text=f"#{application.id} | {username} | UID {user.bingx_uid or '-'}",
            callback_data=f"admin:app:{application.id}:open",
        )

    last_page = max((total - 1) // PAGE_SIZE, 0)
    if page > 0:
        builder.button(text="⬅️ Назад", callback_data=f"admin:list:{status}:{page - 1}")
    if page < last_page:
        builder.button(text="➡️ Далее", callback_data=f"admin:list:{status}:{page + 1}")

    builder.button(text="🔄 Обновить", callback_data=f"admin:list:{status}:{page}")
    builder.button(text="🏠 Админ-панель", callback_data="admin:menu")
    builder.adjust(1)
    return builder.as_markup()


def decision_keyboard(application_id: int, can_decide: bool = True) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if can_decide:
        builder.button(text="✅ Одобрить", callback_data=f"admin:app:{application_id}:approve")
        builder.button(text="❌ Отклонить", callback_data=f"admin:reason:{application_id}:reject")
        builder.button(text="📝 Запросить повторно", callback_data=f"admin:reason:{application_id}:resubmit")
        builder.button(text="🚫 Заблокировать", callback_data=f"admin:reason:{application_id}:block")
    builder.button(text="⬅️ К новым", callback_data="admin:list:pending:0")
    builder.button(text="🏠 Админ-панель", callback_data="admin:menu")
    builder.adjust(2, 1, 1, 1)
    return builder.as_markup()


def reason_keyboard(application_id: int, action: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for code, label in REASON_LABELS.items():
        builder.button(
            text=label,
            callback_data=f"admin:setreason:{application_id}:{action}:{code}",
        )
    builder.button(text="⬅️ К заявке", callback_data=f"admin:app:{application_id}:open")
    builder.adjust(1)
    return builder.as_markup()


def search_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🏠 Админ-панель", callback_data="admin:menu")
    return builder.as_markup()


def search_results_keyboard(applications: list[Application]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for application in applications:
        user = application.user
        username = f"@{user.username}" if user.username else str(user.tg_id)
        builder.button(
            text=f"#{application.id} | {username} | {application.decision}",
            callback_data=f"admin:app:{application.id}:open",
        )
    builder.button(text="🔎 Новый поиск", callback_data="admin:search")
    builder.button(text="🏠 Админ-панель", callback_data="admin:menu")
    builder.adjust(1)
    return builder.as_markup()
