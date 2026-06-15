from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.database.models import User


def main_menu_keyboard(*, is_admin: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="🏠 Дашборд", callback_data="menu:dashboard")],
        [
            InlineKeyboardButton(text="📊 Сигнал", callback_data="menu:signal"),
            InlineKeyboardButton(text="💹 Рынок", callback_data="menu:market"),
        ],
        [
            InlineKeyboardButton(text="📈 Статистика", callback_data="menu:stats"),
            InlineKeyboardButton(text="📜 История", callback_data="menu:history:0"),
        ],
        [InlineKeyboardButton(text="🔔 Уведомления", callback_data="menu:settings")],
        [InlineKeyboardButton(text="❓ Помощь", callback_data="menu:help")],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton(text="🛠 Админ-панель", callback_data="admin:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def settings_keyboard(user: User) -> InlineKeyboardMarkup:
    def onoff(enabled: bool) -> str:
        return "🟢" if enabled else "⚫"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{onoff(user.notify_signals)} Сигналы входа",
                callback_data="settings:toggle:notify_signals",
            )],
            [
                InlineKeyboardButton(
                    text=f"{onoff(user.notify_liq_longs)} Liq LONG",
                    callback_data="settings:toggle:notify_liq_longs",
                ),
                InlineKeyboardButton(
                    text=f"{onoff(user.notify_liq_shorts)} Liq SHORT",
                    callback_data="settings:toggle:notify_liq_shorts",
                ),
            ],
            [InlineKeyboardButton(text="◀️ Меню", callback_data="menu:home")],
        ]
    )


def settings_text(user: User) -> str:
    from app.utils.formatting import header, section

    def state(on: bool) -> str:
        return "🟢 Включено" if on else "⚫ Выключено"

    return (
        f"{header('🔔 Уведомления', 'Нажмите кнопку для переключения')}\n"
        f"{section('Торговля')}\n"
        f"  Сигналы входа — {state(user.notify_signals)}\n"
        f"{section('Ликвидации')}\n"
        f"  LONG позиции — {state(user.notify_liq_longs)}\n"
        f"  SHORT позиции — {state(user.notify_liq_shorts)}\n\n"
        f"<i>Ликвидации — в реальном времени с Binance Futures</i>"
    )


def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="◀️ Меню", callback_data="menu:home")]]
    )


def history_keyboard(page: int, has_more: bool) -> InlineKeyboardMarkup:
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◬ Назад", callback_data=f"menu:history:{page - 1}"))
    if has_more:
        nav.append(InlineKeyboardButton(text="Вперёд ⬭", callback_data=f"menu:history:{page + 1}"))
    rows: list[list[InlineKeyboardButton]] = []
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="◀️ Меню", callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
