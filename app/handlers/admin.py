"""Admin panel handlers."""

from aiogram import Bot, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.database.repositories import (
    count_users,
    get_statistics,
    get_strategy_settings,
    list_open_signals,
    list_users,
    update_strategy_settings,
)
from app.filters.admin import AdminFilter
from app.keyboards.admin import admin_home_keyboard, strategy_keyboard, users_keyboard
from app.services.trade_tracker import format_signal_message, run_market_scan
from app.states.admin import AdminStates

router = Router(name="admin")
router.message.filter(AdminFilter())
router.callback_query.filter(AdminFilter())

PAGE_SIZE = 10


def strategy_text(cfg) -> str:
    return (
        "<b>⚙️ Настройки стратегии v2</b>\n\n"
        f"Таймфрейм: <b>{cfg.timeframe}</b> | HTF: <b>{cfg.higher_tf}</b>\n"
        f"EMA: {cfg.ema_fast}/{cfg.ema_slow}/{cfg.ema_trend}\n"
        f"SL: <b>{cfg.atr_sl_mult}×ATR</b> | TP: <b>{cfg.atr_tp_mult}×ATR</b>\n"
        f"Мин. сила сигнала: <b>{cfg.min_signal_strength}/100</b>\n\n"
        f"MACD фильтр: {'✅' if cfg.use_macd_filter else '❌'}\n"
        f"Объём фильтр: {'✅' if cfg.use_volume_filter else '❌'}\n"
        f"HTF подтверждение: {'✅' if cfg.use_higher_tf else '❌'}\n"
        f"Автоскан: {'✅' if cfg.scanning_enabled else '❌'}\n\n"
        "<i>Стратегия: тренд EMA + пересечение/откат + MACD + объём + 4H</i>"
    )


@router.message(Command("admin"))
async def admin_cmd(message: Message) -> None:
    await message.answer("🛠 <b>Админ-панель</b>", reply_markup=admin_home_keyboard())


@router.callback_query(F.data == "admin:home")
async def admin_home(callback: CallbackQuery) -> None:
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.answer("🛠 <b>Админ-панель</b>", reply_markup=admin_home_keyboard())


@router.callback_query(F.data == "admin:stats")
async def admin_stats(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    if not isinstance(callback.message, Message):
        return
    stats = await get_statistics(session)
    users = await count_users(session)
    await callback.message.answer(
        "<b>📊 Статистика</b>\n\n"
        f"Пользователей: <b>{users}</b>\n"
        f"Всего сигналов: <b>{stats['total']}</b>\n"
        f"✅ Успешных: <b>{stats['wins']}</b>\n"
        f"❌ Убыточных: <b>{stats['losses']}</b>\n"
        f"🔄 Открытых: <b>{stats['open']}</b>\n"
        f"Win Rate: <b>{stats['win_rate']}%</b>\n"
        f"Средний P&L: <b>{stats['avg_pnl']:+.2f}%</b>",
        reply_markup=admin_home_keyboard(),
    )


@router.callback_query(F.data.regexp(r"^admin:users:\d+$"))
async def admin_users(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    if callback.data is None or not isinstance(callback.message, Message):
        return
    page = int(callback.data.rsplit(":", maxsplit=1)[-1])
    total = await count_users(session)
    users = await list_users(session, limit=PAGE_SIZE, offset=page * PAGE_SIZE)
    lines = [f"<b>👥 Пользователи ({total})</b>\n"]
    for u in users:
        name = u.username or u.tg_id
        notify = "🔔" if u.notify_signals else "🔕"
        lines.append(f"{notify} {name} (<code>{u.tg_id}</code>)")
    await callback.message.answer(
        "\n".join(lines) if users else "Пользователей нет.",
        reply_markup=users_keyboard(page, total, PAGE_SIZE),
    )


@router.callback_query(F.data == "admin:strategy")
async def admin_strategy(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    if not isinstance(callback.message, Message):
        return
    cfg = await get_strategy_settings(session)
    await callback.message.answer(strategy_text(cfg), reply_markup=strategy_keyboard(cfg))


@router.callback_query(F.data == "admin:strategy:toggle_scan")
async def toggle_scan(callback: CallbackQuery, session: AsyncSession) -> None:
    cfg = await get_strategy_settings(session)
    cfg = await update_strategy_settings(session, scanning_enabled=not cfg.scanning_enabled)
    await callback.answer("Скан переключён")
    if isinstance(callback.message, Message):
        await callback.message.edit_text(strategy_text(cfg), reply_markup=strategy_keyboard(cfg))


@router.callback_query(F.data.regexp(r"^admin:strategy:toggle:(macd|vol|htf)$"))
async def toggle_filter(callback: CallbackQuery, session: AsyncSession) -> None:
    if callback.data is None:
        return
    key = callback.data.rsplit(":", maxsplit=1)[-1]
    field_map = {"macd": "use_macd_filter", "vol": "use_volume_filter", "htf": "use_higher_tf"}
    cfg = await get_strategy_settings(session)
    field = field_map[key]
    cfg = await update_strategy_settings(session, **{field: not getattr(cfg, field)})
    await callback.answer("Обновлено")
    if isinstance(callback.message, Message):
        await callback.message.edit_text(strategy_text(cfg), reply_markup=strategy_keyboard(cfg))


@router.callback_query(F.data.regexp(r"^admin:strategy:tf:(1h|4h)$"))
async def set_tf(callback: CallbackQuery, session: AsyncSession) -> None:
    if callback.data is None:
        return
    tf = callback.data.rsplit(":", maxsplit=1)[-1]
    cfg = await update_strategy_settings(session, timeframe=tf)
    await callback.answer(f"TF: {tf}")
    if isinstance(callback.message, Message):
        await callback.message.edit_text(strategy_text(cfg), reply_markup=strategy_keyboard(cfg))


@router.callback_query(F.data.regexp(r"^admin:strategy:sl:[\d.]+$"))
async def set_sl(callback: CallbackQuery, session: AsyncSession) -> None:
    if callback.data is None:
        return
    val = float(callback.data.rsplit(":", maxsplit=1)[-1])
    cfg = await update_strategy_settings(session, atr_sl_mult=val)
    await callback.answer(f"SL: {val}×ATR")
    if isinstance(callback.message, Message):
        await callback.message.edit_text(strategy_text(cfg), reply_markup=strategy_keyboard(cfg))


@router.callback_query(F.data.regexp(r"^admin:strategy:tp:[\d.]+$"))
async def set_tp(callback: CallbackQuery, session: AsyncSession) -> None:
    if callback.data is None:
        return
    val = float(callback.data.rsplit(":", maxsplit=1)[-1])
    cfg = await update_strategy_settings(session, atr_tp_mult=val)
    await callback.answer(f"TP: {val}×ATR")
    if isinstance(callback.message, Message):
        await callback.message.edit_text(strategy_text(cfg), reply_markup=strategy_keyboard(cfg))


@router.callback_query(F.data.regexp(r"^admin:strategy:str:\d+$"))
async def set_strength(callback: CallbackQuery, session: AsyncSession) -> None:
    if callback.data is None:
        return
    val = int(callback.data.rsplit(":", maxsplit=1)[-1])
    cfg = await update_strategy_settings(session, min_signal_strength=val)
    await callback.answer(f"Мин. сила: {val}")
    if isinstance(callback.message, Message):
        await callback.message.edit_text(strategy_text(cfg), reply_markup=strategy_keyboard(cfg))


@router.callback_query(F.data == "admin:scan")
async def admin_scan(callback: CallbackQuery, session: AsyncSession, settings: Settings, bot: Bot) -> None:
    await callback.answer("Сканирую...")
    if not isinstance(callback.message, Message):
        return
    signal = await run_market_scan(session, settings, bot, force=True)
    if signal:
        await callback.message.answer(format_signal_message(signal, is_new=True))
    else:
        await callback.message.answer("Сигнал не найден. Условия стратегии не выполнены.", reply_markup=admin_home_keyboard())


@router.callback_query(F.data == "admin:open")
async def admin_open(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    if not isinstance(callback.message, Message):
        return
    open_sigs = await list_open_signals(session)
    if not open_sigs:
        await callback.message.answer("Открытых сделок нет.", reply_markup=admin_home_keyboard())
        return
    for s in open_sigs:
        await callback.message.answer(format_signal_message(s))


@router.callback_query(F.data == "admin:broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(AdminStates.broadcast)
    if isinstance(callback.message, Message):
        await callback.message.answer("Отправьте текст рассылки всем пользователям.\n/cancel для отмены.")


@router.message(Command("cancel"), StateFilter(AdminStates))
async def admin_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Отменено.", reply_markup=admin_home_keyboard())


@router.message(StateFilter(AdminStates.broadcast))
async def admin_broadcast_send(message: Message, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
    if message.text is None:
        return
    users = await list_users(session, limit=1000)
    sent = 0
    for user in users:
        try:
            await bot.send_message(chat_id=user.tg_id, text=message.text)
            sent += 1
        except Exception:
            pass
    await state.clear()
    await message.answer(f"Рассылка отправлена: {sent}/{len(users)}", reply_markup=admin_home_keyboard())
