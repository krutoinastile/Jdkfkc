from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.database.models import StrategySettings


def admin_home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats")],
            [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin:users:0")],
            [InlineKeyboardButton(text="⚙️ Стратегия", callback_data="admin:strategy")],
            [InlineKeyboardButton(text="🔍 Сканировать сейчас", callback_data="admin:scan")],
            [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin:broadcast")],
            [InlineKeyboardButton(text="🔄 Открытые сделки", callback_data="admin:open")],
            [InlineKeyboardButton(text="◀️ Меню", callback_data="menu:home")],
        ]
    )


def strategy_keyboard(cfg: StrategySettings) -> InlineKeyboardMarkup:
    scan_label = "🔴 Скан: ВЫКЛ" if not cfg.scanning_enabled else "🟢 Скан: ВКЛ"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=scan_label, callback_data="admin:strategy:toggle_scan")],
            [
                InlineKeyboardButton(text="TF: 1H", callback_data="admin:strategy:tf:1h"),
                InlineKeyboardButton(text="TF: 4H", callback_data="admin:strategy:tf:4h"),
            ],
            [
                InlineKeyboardButton(text="SL x1.5", callback_data="admin:strategy:sl:1.5"),
                InlineKeyboardButton(text="SL x2.0", callback_data="admin:strategy:sl:2.0"),
            ],
            [
                InlineKeyboardButton(text="TP x2.5", callback_data="admin:strategy:tp:2.5"),
                InlineKeyboardButton(text="TP x3.0", callback_data="admin:strategy:tp:3.0"),
                InlineKeyboardButton(text="TP x4.0", callback_data="admin:strategy:tp:4.0"),
            ],
            [
                InlineKeyboardButton(text=_toggle("MACD", cfg.use_macd_filter), callback_data="admin:strategy:toggle:macd"),
                InlineKeyboardButton(text=_toggle("Vol", cfg.use_volume_filter), callback_data="admin:strategy:toggle:vol"),
            ],
            [
                InlineKeyboardButton(text=_toggle("HTF 4H", cfg.use_higher_tf), callback_data="admin:strategy:toggle:htf"),
            ],
            [
                InlineKeyboardButton(text="Сила: 50", callback_data="admin:strategy:str:50"),
                InlineKeyboardButton(text="Сила: 60", callback_data="admin:strategy:str:60"),
                InlineKeyboardButton(text="Сила: 70", callback_data="admin:strategy:str:70"),
            ],
            [
                InlineKeyboardButton(text="1/день", callback_data="admin:strategy:daymax:1"),
                InlineKeyboardButton(text="2/день", callback_data="admin:strategy:daymax:2"),
                InlineKeyboardButton(text="Пауза 20ч", callback_data="admin:strategy:cooldown:20"),
            ],
            [
                InlineKeyboardButton(text="Пауза 24ч", callback_data="admin:strategy:cooldown:24"),
                InlineKeyboardButton(text="Пауза 12ч", callback_data="admin:strategy:cooldown:12"),
            ],
            [
                InlineKeyboardButton(
                    text=_toggle("Ликвидации", cfg.liquidations_enabled),
                    callback_data="admin:strategy:toggle:liq",
                ),
            ],
            [
                InlineKeyboardButton(text="Liq $50k", callback_data="admin:strategy:liqmin:50000"),
                InlineKeyboardButton(text="Liq $100k", callback_data="admin:strategy:liqmin:100000"),
                InlineKeyboardButton(text="Liq $250k", callback_data="admin:strategy:liqmin:250000"),
            ],
            [
                InlineKeyboardButton(
                    text=_toggle("Funding", cfg.funding_alerts_enabled),
                    callback_data="admin:strategy:toggle:funding",
                ),
            ],
            [
                InlineKeyboardButton(text="Fund 0.03%", callback_data="admin:strategy:fund:0.03"),
                InlineKeyboardButton(text="Fund 0.05%", callback_data="admin:strategy:fund:0.05"),
                InlineKeyboardButton(text="Fund 0.10%", callback_data="admin:strategy:fund:0.1"),
            ],
            [InlineKeyboardButton(text="◀️ Админ", callback_data="admin:home")],
        ]
    )


def _toggle(name: str, enabled: bool) -> str:
    return f"{name}: {'✅' if enabled else '❌'}"


def users_keyboard(page: int, total: int, page_size: int = 10) -> InlineKeyboardMarkup:
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"admin:users:{page - 1}"))
    if (page + 1) * page_size < total:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"admin:users:{page + 1}"))
    rows: list[list[InlineKeyboardButton]] = []
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="◀️ Админ", callback_data="admin:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
