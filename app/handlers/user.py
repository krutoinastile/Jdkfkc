import asyncio

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.database.repositories import (
    get_or_create_user,
    get_statistics,
    get_strategy_settings,
    is_admin,
    list_open_signals,
    list_recent_signals,
    toggle_user_flag,
)
from app.keyboards.user import back_keyboard, history_keyboard, main_menu_keyboard, settings_keyboard, settings_text
from app.services.funding import fetch_funding_rate
from app.services.market_data import fetch_candles
from app.services.sentiment import fetch_fear_greed
from app.services.strategy import market_snapshot
from app.services.strategy_config import StrategyConfig
from app.services.trade_tracker import format_signal_message
from app.utils.messages import (
    format_dashboard,
    format_history,
    format_market,
    format_no_signal,
    format_stats,
    help_text,
    welcome_text,
)
from app.utils.telegram import answer_with_chart

router = Router(name="user")

PAGE_SIZE = 5


async def _cfg(session: AsyncSession) -> StrategyConfig:
    return StrategyConfig.from_db(await get_strategy_settings(session))


async def _market_context(session: AsyncSession, settings: Settings) -> tuple:
    cfg = await _cfg(session)
    candles, fear_greed, funding = await asyncio.gather(
        fetch_candles(settings.symbol, cfg.timeframe),
        fetch_fear_greed(),
        fetch_funding_rate(settings.symbol),
    )
    snap = market_snapshot(candles, cfg)
    return cfg, candles, snap, fear_greed, funding


@router.message(CommandStart())
async def start(message: Message, session: AsyncSession, settings: Settings) -> None:
    if message.from_user is None:
        return
    await get_or_create_user(session, message.from_user.id, message.from_user.username)
    admin = await is_admin(message.from_user.id, settings.parsed_admin_ids)
    await message.answer(welcome_text(), reply_markup=main_menu_keyboard(is_admin=admin))


@router.callback_query(F.data == "menu:home")
async def menu_home(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await callback.answer()
    if callback.from_user is None or not isinstance(callback.message, Message):
        return
    admin = await is_admin(callback.from_user.id, settings.parsed_admin_ids)
    await callback.message.answer(welcome_text(), reply_markup=main_menu_keyboard(is_admin=admin))


@router.callback_query(F.data == "menu:dashboard")
async def menu_dashboard(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await callback.answer("Загружаю...")
    if not isinstance(callback.message, Message):
        return

    cfg, candles, snap, fear_greed, funding = await _market_context(session, settings)
    stats = await get_statistics(session)
    open_signals = await list_open_signals(session)
    caption = format_dashboard(
        snap, stats, has_open=bool(open_signals), fear_greed=fear_greed, funding=funding,
    )
    await answer_with_chart(callback.message, caption, candles, cfg, reply_markup=back_keyboard())


@router.callback_query(F.data == "menu:help")
async def menu_help(callback: CallbackQuery) -> None:
    await callback.answer()
    if not isinstance(callback.message, Message):
        return
    await callback.message.answer(help_text(), reply_markup=back_keyboard())


@router.callback_query(F.data == "menu:signal")
async def menu_signal(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await callback.answer("Загружаю...")
    if not isinstance(callback.message, Message):
        return

    open_signals = await list_open_signals(session)
    cfg, candles, snap, _, _ = await _market_context(session, settings)

    if open_signals:
        signal = open_signals[0]
        await answer_with_chart(
            callback.message,
            format_signal_message(signal),
            candles,
            cfg,
            signal=signal,
            reply_markup=back_keyboard(),
        )
        return

    await answer_with_chart(
        callback.message,
        format_no_signal(snap),
        candles,
        cfg,
        reply_markup=back_keyboard(),
    )


@router.callback_query(F.data == "menu:market")
async def menu_market(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await callback.answer("Загружаю...")
    if not isinstance(callback.message, Message):
        return

    cfg, candles, snap, fear_greed, funding = await _market_context(session, settings)
    caption = format_market(snap, cfg.timeframe, fear_greed=fear_greed, funding=funding)
    await answer_with_chart(callback.message, caption, candles, cfg, reply_markup=back_keyboard())


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
    all_signals = await list_recent_signals(session, limit=50)
    chunk = all_signals[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]
    has_more = len(all_signals) > (page + 1) * PAGE_SIZE

    if not chunk:
        await callback.message.answer("История пуста.", reply_markup=back_keyboard())
        return

    await callback.message.answer(
        format_history(chunk, page=page),
        reply_markup=history_keyboard(page, has_more),
    )


@router.callback_query(F.data == "menu:settings")
async def menu_settings(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    if callback.from_user is None or not isinstance(callback.message, Message):
        return
    user = await get_or_create_user(session, callback.from_user.id, callback.from_user.username)
    await callback.message.answer(settings_text(user), reply_markup=settings_keyboard(user))


@router.callback_query(F.data.startswith("settings:toggle:"))
async def toggle_setting(callback: CallbackQuery, session: AsyncSession) -> None:
    if callback.from_user is None or callback.data is None:
        return
    field = callback.data.split(":")[-1]
    allowed = {"notify_signals", "notify_liq_longs", "notify_liq_shorts", "notify_funding"}
    if field not in allowed:
        await callback.answer("Неизвестная настройка.", show_alert=True)
        return

    user = await get_or_create_user(session, callback.from_user.id, callback.from_user.username)
    user = await toggle_user_flag(session, user, field)
    await callback.answer("Сохранено")
    if isinstance(callback.message, Message):
        await callback.message.edit_text(settings_text(user), reply_markup=settings_keyboard(user))


# backward compat
@router.callback_query(F.data == "menu:notify")
async def menu_notify_legacy(callback: CallbackQuery, session: AsyncSession) -> None:
    await menu_settings(callback, session)


@router.message(Command("stats"))
async def stats_cmd(message: Message, session: AsyncSession, settings: Settings) -> None:
    admin = await is_admin(message.from_user.id, settings.parsed_admin_ids) if message.from_user else False
    stats = await get_statistics(session)
    await message.answer(format_stats(stats), reply_markup=main_menu_keyboard(is_admin=admin))


@router.message(Command("signal"))
async def signal_cmd(message: Message, session: AsyncSession, settings: Settings) -> None:
    open_signals = await list_open_signals(session)
    cfg, candles, snap, _, _ = await _market_context(session, settings)
    if open_signals:
        await answer_with_chart(message, format_signal_message(open_signals[0]), candles, cfg, signal=open_signals[0])
    else:
        await answer_with_chart(message, format_no_signal(snap), candles, cfg)
