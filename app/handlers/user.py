from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.database.repositories import (
    get_or_create_user,
    get_statistics,
    list_open_signals,
    list_recent_signals,
    toggle_notifications,
)
from app.keyboards.user import back_keyboard, history_keyboard, main_menu_keyboard
from app.services.market_data import fetch_candles
from app.services.strategy import market_snapshot
from app.services.trade_tracker import format_signal_message

router = Router(name="user")

PAGE_SIZE = 5


def welcome_text() -> str:
    return (
        "<b>BTC Trading Bot</b>\n\n"
        "Бот анализирует Bitcoin (BTC/USDT) на таймфрейме 1H "
        "и выдаёт точки входа по стратегии:\n\n"
        "• Тренд: EMA55\n"
        "• Вход: пересечение EMA9 / EMA21\n"
        "• Фильтр: RSI\n"
        "• Stop-Loss / Take-Profit: на основе ATR\n\n"
        "⚠️ Это не финансовый совет. Торгуйте на свой риск."
    )


def format_stats(stats: dict) -> str:
    return (
        "<b>📈 Статистика сделок</b>\n\n"
        f"Всего сигналов: <b>{stats['total']}</b>\n"
        f"✅ Успешных: <b>{stats['wins']}</b>\n"
        f"❌ Неуспешных: <b>{stats['losses']}</b>\n"
        f"⏱ Истекло: <b>{stats['expired']}</b>\n"
        f"🔄 Открытых: <b>{stats['open']}</b>\n\n"
        f"Win Rate: <b>{stats['win_rate']}%</b>\n"
        f"Средний P&L: <b>{stats['avg_pnl']:+.2f}%</b>"
    )


@router.message(CommandStart())
async def start(message: Message, session: AsyncSession) -> None:
    if message.from_user is None:
        return
    await get_or_create_user(session, message.from_user.id, message.from_user.username)
    await message.answer(welcome_text(), reply_markup=main_menu_keyboard())


@router.callback_query(F.data == "menu:home")
async def menu_home(callback: CallbackQuery) -> None:
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.answer(welcome_text(), reply_markup=main_menu_keyboard())


@router.callback_query(F.data == "menu:signal")
async def menu_signal(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await callback.answer()
    if not isinstance(callback.message, Message):
        return

    open_signals = await list_open_signals(session)
    if open_signals:
        await callback.message.answer(
            format_signal_message(open_signals[0]),
            reply_markup=back_keyboard(),
        )
        return

    candles = await fetch_candles(settings.symbol, settings.timeframe)
    snap = market_snapshot(candles)
    await callback.message.answer(
        "Сейчас активного сигнала нет.\n\n"
        f"💰 BTC: <b>${snap['price']:,.2f}</b>\n"
        f"Тренд: {snap['trend']}\n"
        f"RSI: {snap['rsi']} | EMA9: ${snap['ema9']:,.0f} | EMA21: ${snap['ema21']:,.0f}\n\n"
        "Бот пришлёт уведомление, когда появится точка входа.",
        reply_markup=back_keyboard(),
    )


@router.callback_query(F.data == "menu:market")
async def menu_market(callback: CallbackQuery, settings: Settings) -> None:
    await callback.answer()
    if not isinstance(callback.message, Message):
        return

    candles = await fetch_candles(settings.symbol, settings.timeframe)
    snap = market_snapshot(candles)
    await callback.message.answer(
        f"<b>💹 BTC/USDT ({settings.timeframe})</b>\n\n"
        f"Цена: <b>${snap['price']:,.2f}</b>\n"
        f"Тренд: {snap['trend']}\n"
        f"RSI(14): {snap['rsi']}\n"
        f"EMA9: ${snap['ema9']:,.2f}\n"
        f"EMA21: ${snap['ema21']:,.2f}\n"
        f"EMA55: ${snap['ema55']:,.2f}",
        reply_markup=back_keyboard(),
    )


@router.callback_query(F.data == "menu:stats")
async def menu_stats(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    if not isinstance(callback.message, Message):
        return
    stats = await get_statistics(session)
    await callback.message.answer(format_stats(stats), reply_markup=back_keyboard())


@router.callback_query(F.data.regexp(r"^menu:history:\d+$"))
async def menu_history(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    if callback.data is None or not isinstance(callback.message, Message):
        return

    page = int(callback.data.rsplit(":", maxsplit=1)[-1])
    offset = page * PAGE_SIZE
    signals = await list_recent_signals(session, limit=PAGE_SIZE + 1)
    # Simple pagination on fetched list
    all_signals = await list_recent_signals(session, limit=50)
    chunk = all_signals[offset : offset + PAGE_SIZE]
    has_more = len(all_signals) > offset + PAGE_SIZE

    if not chunk:
        await callback.message.answer("История пуста.", reply_markup=back_keyboard())
        return

    lines = ["<b>📜 История сделок</b>\n"]
    for s in chunk:
        if s.status == "win":
            icon = "✅"
        elif s.status == "loss":
            icon = "❌"
        elif s.status == "open":
            icon = "🔄"
        else:
            icon = "⏱"
        pnl = f" ({s.pnl_percent:+.2f}%)" if s.pnl_percent is not None else ""
        lines.append(
            f"{icon} {s.direction.upper()} | ${s.entry_price:,.0f} → "
            f"{s.status.upper()}{pnl}"
        )

    await callback.message.answer(
        "\n".join(lines),
        reply_markup=history_keyboard(page, has_more),
    )


@router.callback_query(F.data == "menu:notify")
async def menu_notify(callback: CallbackQuery, session: AsyncSession) -> None:
    if callback.from_user is None:
        return
    user = await get_or_create_user(session, callback.from_user.id, callback.from_user.username)
    user = await toggle_notifications(session, user)
    state = "включены" if user.notify_signals else "выключены"
    await callback.answer(f"Уведомления {state}")
    if isinstance(callback.message, Message):
        await callback.message.answer(
            f"🔔 Уведомления о сигналах: <b>{state}</b>",
            reply_markup=main_menu_keyboard(),
        )


@router.message(Command("stats"))
async def stats_cmd(message: Message, session: AsyncSession) -> None:
    stats = await get_statistics(session)
    await message.answer(format_stats(stats), reply_markup=main_menu_keyboard())


@router.message(Command("signal"))
async def signal_cmd(message: Message, session: AsyncSession, settings: Settings) -> None:
    open_signals = await list_open_signals(session)
    if open_signals:
        await message.answer(format_signal_message(open_signals[0]))
    else:
        candles = await fetch_candles(settings.symbol, settings.timeframe)
        snap = market_snapshot(candles)
        await message.answer(
            f"Активного сигнала нет. BTC: ${snap['price']:,.2f}, тренд: {snap['trend']}"
        )
