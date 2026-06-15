from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.database.models import User


def main_menu_keyboard(*, is_admin: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="📊 Точка входа", callback_data="menu:signal")],
        [InlineKeyboardButton(text="💹 Рынок BTC", callback_data="menu:market")],
        [InlineKeyboardButton(text="📈 Статистика", callback_data="menu:stats")],
        [InlineKeyboardButton(text="📜 История сделок", callback_data="menu:history:0")],
        [InlineKeyboardButton(text="🔔 Уведомления", callback_data="menu:settings")],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton(text="🛠 Админ-панель", callback_data="admin:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def settings_keyboard(user: User) -> InlineKeyboardMarkup:
    def onoff(enabled: bool) -> str:
        return "✅" if enabled else "❌"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{onoff(user.notify_signals)} Торговые сигналы",
                callback_data="settings:toggle:notify_signals",
            )],
            [InlineKeyboardButton(
                text=f"{onoff(user.notify_liq_longs)} Ликвидации LONG",
                callback_data="settings:toggle:notify_liq_longs",
            )],
            [InlineKeyboardButton(
                text=f"{onoff(user.notify_liq_shorts)} Ликвидации SHORT",
                callback_data="settings:toggle:notify_liq_shorts",
            )],
            [InlineKeyboardButton(text="◀️ Меню", callback_data="menu:home")],
        ]
    )


def settings_text(user: User) -> str:
    return (
        "<b>🔔 Настройки уведомлений</b>\n\n"
        f"Торговые сигналы: <b>{'вкл' if user.notify_signals else 'выкл'}</b>\n"
        f"Ликвидации LONG: <b>{'вкл' if user.notify_liq_longs else 'выкл'}</b>\n"
        f"Ликвидации SHORT: <b>{'вкл' if user.notify_liq_shorts else 'выкл'}</b>\n\n"
        "<i>Ликвидации отслеживаются в реальном времени с Binance Futures.</i>"
    )


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
