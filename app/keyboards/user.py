from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_keyboard(*, is_admin: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="📊 Точка входа", callback_data="menu:signal")],
        [InlineKeyboardButton(text="💹 Рынок BTC", callback_data="menu:market")],
        [InlineKeyboardButton(text="📈 Статистика", callback_data="menu:stats")],
        [InlineKeyboardButton(text="📜 История сделок", callback_data="menu:history:0")],
        [InlineKeyboardButton(text="🔔 Уведомления", callback_data="menu:notify")],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton(text="🛠 Админ-панель", callback_data="admin:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="◀️ Меню", callback_data="menu:home")]]
    )


def history_keyboard(page: int, has_more: bool) -> InlineKeyboardMarkup:
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"menu:history:{page - 1}"))
    if has_more:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"menu:history:{page + 1}"))
    rows: list[list[InlineKeyboardButton]] = []
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="◀️ Меню", callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
