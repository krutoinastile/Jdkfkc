from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.database.models import Account


def admin_home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin:users:0")],
            [InlineKeyboardButton(text="💳 Оплата", callback_data="admin:payments")],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats")],
            [InlineKeyboardButton(text="◀️ Меню", callback_data="menu:home")],
        ]
    )


def admin_users_keyboard(accounts: list[Account], page: int, total: int, page_size: int = 10) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for account in accounts:
        label = account.username or account.first_name or str(account.tg_id)
        rows.append(
            [InlineKeyboardButton(text=f"👤 {label}", callback_data=f"admin:user:{account.tg_id}")]
        )

    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"admin:users:{page - 1}"))
    if (page + 1) * page_size < total:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"admin:users:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="◀️ Админ", callback_data="admin:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_user_actions_keyboard(tg_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="+7 дней", callback_data=f"admin:extend:{tg_id}:7"),
                InlineKeyboardButton(text="+30 дней", callback_data=f"admin:extend:{tg_id}:30"),
            ],
            [
                InlineKeyboardButton(text="Заблокировать", callback_data=f"admin:block:{tg_id}:1"),
                InlineKeyboardButton(text="Разблокировать", callback_data=f"admin:block:{tg_id}:0"),
            ],
            [InlineKeyboardButton(text="◀️ К списку", callback_data="admin:users:0")],
        ]
    )
