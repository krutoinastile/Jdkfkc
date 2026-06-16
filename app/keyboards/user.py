from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.database.models import User


def main_menu_keyboard(*, is_admin: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="🏠  Дашборд", callback_data="menu:dashboard")],
        [
            InlineKeyboardButton(text="📊 Сигнал", callback_data="menu:signal"),
            InlineKeyboardButton(text="💹 Рынок", callback_data="menu:market"),
        ],
        [
            InlineKeyboardButton(text="📈 Статистика", callback_data="menu:stats"),
            InlineKeyboardButton(text="📜 История", callback_data="hist:all:0:0"),
        ],
        [
            InlineKeyboardButton(text="💰 Калькулятор", callback_data="menu:calculator"),
            InlineKeyboardButton(text="🔬 Бэктест", callback_data="menu:backtest"),
        ],
        [
            InlineKeyboardButton(text="💎 Подписка", callback_data="menu:subscription"),
            InlineKeyboardButton(text="🔔 Алерты", callback_data="menu:settings"),
        ],
        [
            InlineKeyboardButton(text="❓ Помощь", callback_data="menu:help"),
        ],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton(text="🛠  Админ-панель", callback_data="admin:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def backtest_period_keyboard() -> InlineKeyboardMarkup:
    from app.utils.backtest_ui import BACKTEST_PERIODS

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=f"📅 {label}", callback_data=f"backtest:period:{days}")
                for days, label in BACKTEST_PERIODS.items()
            ],
            [InlineKeyboardButton(text="◀️ Меню", callback_data="menu:home")],
        ]
    )


def backtest_trades_keyboard(days: int) -> InlineKeyboardMarkup:
    from app.utils.backtest_ui import BACKTEST_MAX_TRADES

    rows = [
        [
            InlineKeyboardButton(text=f"📊 {label}", callback_data=f"backtest:run:{days}:{max_per_day}")
            for max_per_day, label in list(BACKTEST_MAX_TRADES.items())[:3]
        ],
        [
            InlineKeyboardButton(text=f"📊 {label}", callback_data=f"backtest:run:{days}:{max_per_day}")
            for max_per_day, label in list(BACKTEST_MAX_TRADES.items())[3:]
        ],
        [
            InlineKeyboardButton(text="◀️ Период", callback_data="menu:backtest"),
            InlineKeyboardButton(text="🏠 Меню", callback_data="menu:home"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def backtest_result_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 Другой лимит", callback_data="menu:backtest"),
                InlineKeyboardButton(text="◀️ Меню", callback_data="menu:home"),
            ],
        ]
    )


def refresh_keyboard(refresh_data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Обновить", callback_data=refresh_data),
                InlineKeyboardButton(text="◀️ Меню", callback_data="menu:home"),
            ],
        ]
    )


def calculator_period_keyboard(counts: dict[int, int]) -> InlineKeyboardMarkup:
    from app.services.profit_calc import PERIOD_OPTIONS

    rows: list[list[InlineKeyboardButton]] = []
    period_keys = [7, 30, 90, 180, 0]
    for i in range(0, len(period_keys), 2):
        row = []
        for days in period_keys[i : i + 2]:
            label = PERIOD_OPTIONS[days]
            count = counts.get(days, 0)
            suffix = f" ({count})" if count else ""
            row.append(InlineKeyboardButton(
                text=f"📅 {label}{suffix}",
                callback_data=f"calc:period:{days}",
            ))
        rows.append(row)
    rows.append([InlineKeyboardButton(text="◀️ Меню", callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def calculator_amount_keyboard(days: int) -> InlineKeyboardMarkup:
    presets = [100, 500, 1000, 5000, 10000]
    rows = [
        [
            InlineKeyboardButton(text=f"💵 ${p:,}", callback_data=f"calc:run:{days}:{p}")
            for p in presets[:3]
        ],
        [
            InlineKeyboardButton(text=f"💵 ${p:,}", callback_data=f"calc:run:{days}:{p}")
            for p in presets[3:]
        ],
        [InlineKeyboardButton(text="✏️  Своя сумма", callback_data=f"calc:custom:{days}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="menu:calculator")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def calculator_keyboard() -> InlineKeyboardMarkup:
    """Legacy alias — use calculator_period_keyboard."""
    return calculator_period_keyboard({0: 0})


def calculator_result_keyboard(days: int, amount: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📅 Период", callback_data="menu:calculator"),
                InlineKeyboardButton(text="💵 Сумма", callback_data=f"calc:period:{days}"),
            ],
            [
                InlineKeyboardButton(text="🔬 Бэктест", callback_data="menu:backtest"),
                InlineKeyboardButton(text="◀️ Меню", callback_data="menu:home"),
            ],
        ]
    )


def stats_keyboard(*, has_equity: bool = False) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if has_equity:
        rows.append([InlineKeyboardButton(text="📈 Кривая капитала", callback_data="stats:equity")])
    rows.extend([
        [
            InlineKeyboardButton(text="💰 Калькулятор", callback_data="menu:calculator"),
            InlineKeyboardButton(text="🔬 Бэктест", callback_data="menu:backtest"),
        ],
        [InlineKeyboardButton(text="◀️ Меню", callback_data="menu:home")],
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def settings_keyboard(user: User) -> InlineKeyboardMarkup:
    def onoff(enabled: bool) -> str:
        return "🟢" if enabled else "⚫"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{onoff(user.notify_signals)}  Сигналы входа",
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
            [InlineKeyboardButton(
                text=f"{onoff(user.notify_funding)}  Funding Rate",
                callback_data="settings:toggle:notify_funding",
            )],
            [InlineKeyboardButton(text="◀️ Меню", callback_data="menu:home")],
        ]
    )


def settings_text(user: User) -> str:
    from app.utils.formatting import badge, footer, header, section

    return (
        f"{header('🔔 Уведомления', 'Нажмите для переключения')}\n"
        f"{section('Торговля')}\n"
        f"   {badge('Сигналы входа', style='on' if user.notify_signals else 'off')}\n"
        f"{section('Ликвидации')}\n"
        f"   {badge('LONG позиции', style='on' if user.notify_liq_longs else 'off')}\n"
        f"   {badge('SHORT позиции', style='on' if user.notify_liq_shorts else 'off')}\n"
        f"{section('Funding')}\n"
        f"   {badge('Экстремальный rate', style='on' if user.notify_funding else 'off')}\n\n"
        f"<i>Ликвидации — Binance Futures в реальном времени</i>"
        f"{footer()}"
    )


def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="◀️ Меню", callback_data="menu:home")]]
    )


def history_keyboard(
    *,
    page: int,
    has_more: bool,
    status_filter: str,
    days: int,
    signals: list | None = None,
) -> InlineKeyboardMarkup:
    from app.utils.history import HISTORY_FILTERS, HISTORY_PERIODS, history_callback

    rows: list[list[InlineKeyboardButton]] = []

    if signals:
        for s in signals:
            icon = {"win": "✅", "loss": "❌", "open": "🔄", "expired": "⏱"}.get(s.status, "·")
            d = "L" if s.direction == "long" else "S"
            rows.append([InlineKeyboardButton(
                text=f"{icon} #{s.id} {d} ${s.entry_price:,.0f}",
                callback_data=f"hist:detail:{s.id}",
            )])

    filter_row = []
    for key, label in HISTORY_FILTERS.items():
        mark = "• " if key == status_filter else ""
        filter_row.append(InlineKeyboardButton(
            text=f"{mark}{label}",
            callback_data=history_callback(key, days, 0),
        ))
    rows.append(filter_row[:2])
    rows.append(filter_row[2:])

    period_row = []
    for d, label in HISTORY_PERIODS.items():
        mark = "• " if d == days else ""
        period_row.append(InlineKeyboardButton(
            text=f"{mark}{label}",
            callback_data=history_callback(status_filter, d, 0),
        ))
    rows.append(period_row)

    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(
            text="◀️ Назад",
            callback_data=history_callback(status_filter, days, page - 1),
        ))
    if has_more:
        nav.append(InlineKeyboardButton(
            text="Вперёд ▶️",
            callback_data=history_callback(status_filter, days, page + 1),
        ))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="◀️ Меню", callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def history_detail_keyboard(signal_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="◀️ К истории", callback_data="hist:all:0:0")],
            [InlineKeyboardButton(text="◀️ Меню", callback_data="menu:home")],
        ]
    )
