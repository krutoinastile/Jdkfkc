import asyncio
from dataclasses import replace

from aiogram import F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.database.repositories import (
    count_closed_signals,
    get_or_create_user,
    get_signal_by_id,
    get_statistics,
    get_strategy_settings,
    is_admin,
    list_closed_signals,
    list_history_signals,
    list_open_signals,
    toggle_user_flag,
)
from app.keyboards.user import (
    back_keyboard,
    backtest_result_keyboard,
    backtest_trades_keyboard,
    calculator_amount_keyboard,
    calculator_period_keyboard,
    calculator_result_keyboard,
    history_detail_keyboard,
    history_keyboard,
    main_menu_keyboard,
    refresh_keyboard,
    settings_keyboard,
    settings_text,
    stats_keyboard,
)
from app.services.backtest import run_backtest
from app.services.derivatives import fetch_derivatives_stats
from app.services.funding import fetch_funding_rate
from app.services.market_data import fetch_candles
from app.services.profit_calc import PERIOD_OPTIONS, period_label as calc_period_label, simulate_profit
from app.services.sentiment import fetch_fear_greed
from app.services.strategy import market_snapshot
from app.services.strategy_config import StrategyConfig
from app.services.trade_tracker import format_signal_message
from app.states.user import CalculatorStates
from app.utils.messages import (
    format_backtest_intro,
    format_backtest_result,
    format_calculator_empty,
    format_calculator_intro,
    format_calculator_period_step,
    format_calculator_result,
    format_dashboard,
    format_history,
    format_history_detail,
    format_history_empty,
    format_market,
    format_no_signal,
    format_stats,
    help_text,
    welcome_text,
)
from app.utils.telegram import answer_with_chart

from app.utils.backtest_ui import (
    BACKTEST_DAYS,
    BACKTEST_MAX_TRADES,
    candles_for_period,
    htf_candles_for_period,
    min_hours_for_max_trades,
    period_label,
    trades_per_day_label,
)

router = Router(name="user")

PAGE_SIZE = 5


async def _cfg(session: AsyncSession) -> StrategyConfig:
    return StrategyConfig.from_db(await get_strategy_settings(session))


async def _market_context(session: AsyncSession, settings: Settings) -> tuple:
    cfg = await _cfg(session)
    candles, fear_greed, funding, derivatives = await asyncio.gather(
        fetch_candles(settings.symbol, cfg.timeframe),
        fetch_fear_greed(),
        fetch_funding_rate(settings.symbol),
        fetch_derivatives_stats(settings.symbol),
    )
    snap = market_snapshot(candles, cfg)
    return cfg, candles, snap, fear_greed, funding, derivatives


async def _period_counts(session: AsyncSession) -> dict[int, int]:
    counts: dict[int, int] = {}
    for days in PERIOD_OPTIONS:
        counts[days] = await count_closed_signals(session, days=None if days == 0 else days)
    return counts


async def _run_calculation(
    message: Message,
    session: AsyncSession,
    amount: float,
    *,
    days: int = 0,
) -> None:
    period_days = days if days > 0 else 0
    total_in_period = await count_closed_signals(session, days=None if period_days == 0 else period_days)
    signals = await list_closed_signals(session, days=None if period_days == 0 else period_days)

    if not signals:
        await message.answer(
            format_calculator_empty(days=period_days),
            reply_markup=calculator_period_keyboard(await _period_counts(session)),
        )
        return

    sim = simulate_profit(
        signals,
        amount,
        period_days=period_days,
        total_in_period=total_in_period,
    )
    if sim is None:
        await message.answer(
            format_calculator_empty(days=period_days),
            reply_markup=calculator_period_keyboard(await _period_counts(session)),
        )
        return

    await message.answer(
        format_calculator_result(sim),
        reply_markup=calculator_result_keyboard(period_days, int(amount)),
    )

async def _show_history(
    message: Message,
    session: AsyncSession,
    *,
    status_filter: str = "all",
    days: int = 0,
    page: int = 0,
) -> None:
    all_signals = await list_history_signals(
        session, status_filter=status_filter, days=days, limit=100,
    )
    if not all_signals and status_filter == "all" and days == 0:
        await message.answer(
            format_history_empty(),
            reply_markup=history_keyboard(
                page=0, has_more=False, status_filter="all", days=0,
            ),
        )
        return

    chunk = all_signals[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]
    has_more = len(all_signals) > (page + 1) * PAGE_SIZE
    wins = sum(1 for s in all_signals if s.status == "win")
    losses = sum(1 for s in all_signals if s.status == "loss")
    open_n = sum(1 for s in all_signals if s.status == "open")

    await message.answer(
        format_history(
            chunk,
            page=page,
            status_filter=status_filter,
            days=days,
            total_count=len(all_signals),
            wins=wins,
            losses=losses,
            open_n=open_n,
        ),
        reply_markup=history_keyboard(
            page=page,
            has_more=has_more,
            status_filter=status_filter,
            days=days,
            signals=chunk,
        ),
    )


@router.message(CommandStart())
async def start(message: Message, session: AsyncSession, settings: Settings) -> None:
    if message.from_user is None:
        return
    await get_or_create_user(session, message.from_user.id, message.from_user.username)
    admin = await is_admin(message.from_user.id, settings.parsed_admin_ids)
    await message.answer(welcome_text(), reply_markup=main_menu_keyboard(is_admin=admin))


@router.callback_query(F.data == "menu:home")
async def menu_home(callback: CallbackQuery, session: AsyncSession, settings: Settings, state: FSMContext) -> None:
    await state.clear()
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

    cfg, candles, snap, fear_greed, funding, derivatives = await _market_context(session, settings)
    stats = await get_statistics(session)
    open_signals = await list_open_signals(session)
    caption = format_dashboard(
        snap,
        stats,
        has_open=bool(open_signals),
        fear_greed=fear_greed,
        funding=funding,
        derivatives=derivatives,
    )
    await answer_with_chart(
        callback.message,
        caption,
        candles,
        cfg,
        reply_markup=refresh_keyboard("menu:dashboard"),
    )


@router.callback_query(F.data == "menu:help")
async def menu_help(callback: CallbackQuery) -> None:
    await callback.answer()
    if not isinstance(callback.message, Message):
        return
    await callback.message.answer(help_text(), reply_markup=back_keyboard())


@router.callback_query(F.data == "menu:calculator")
async def menu_calculator(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    if not isinstance(callback.message, Message):
        return

    counts = await _period_counts(session)
    total = counts.get(0, 0)
    await callback.message.answer(
        format_calculator_intro(total),
        reply_markup=calculator_period_keyboard(counts),
    )


@router.callback_query(F.data.regexp(r"^calc:period:\d+$"))
async def calc_select_period(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    if callback.data is None or not isinstance(callback.message, Message):
        return

    days = int(callback.data.rsplit(":", maxsplit=1)[-1])
    trade_count = await count_closed_signals(session, days=None if days == 0 else days)
    await callback.message.answer(
        format_calculator_period_step(days, trade_count),
        reply_markup=calculator_amount_keyboard(days),
    )


@router.callback_query(F.data.regexp(r"^calc:run:\d+:\d+$"))
async def calc_run(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    await callback.answer("Считаю...")
    if callback.data is None or not isinstance(callback.message, Message):
        return

    _, _, days_str, amount_str = callback.data.split(":", maxsplit=3)
    await _run_calculation(callback.message, session, float(amount_str), days=int(days_str))


@router.callback_query(F.data.regexp(r"^calc:custom:\d+$"))
async def calc_custom_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    if callback.data is None:
        return
    days = int(callback.data.rsplit(":", maxsplit=1)[-1])
    await state.set_state(CalculatorStates.waiting_amount)
    await state.update_data(period_days=days)
    if isinstance(callback.message, Message):
        label = calc_period_label(days)
        await callback.message.answer(
            f"📅 Период: <b>{label}</b>\n\n"
            f"Введите стартовый капитал в USD (например: <b>2500</b>)\n\n"
            f"/cancel — отмена",
        )


@router.message(StateFilter(CalculatorStates.waiting_amount))
async def calc_custom_amount(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if message.text is None:
        return
    if message.text.strip().lower() == "/cancel":
        await state.clear()
        await message.answer("Отменено.", reply_markup=back_keyboard())
        return

    try:
        amount = float(message.text.replace(",", "").replace("$", "").strip())
    except ValueError:
        await message.answer("Введите число, например: 1000")
        return

    if amount < 10 or amount > 10_000_000:
        await message.answer("Сумма должна быть от $10 до $10,000,000")
        return

    data = await state.get_data()
    days = int(data.get("period_days", 0))
    await state.clear()
    await _run_calculation(message, session, amount, days=days)


@router.callback_query(F.data == "menu:backtest")
async def menu_backtest(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await callback.answer()
    if not isinstance(callback.message, Message):
        return
    cfg = await _cfg(session)
    await callback.message.answer(
        format_backtest_intro(cfg.timeframe),
        reply_markup=backtest_trades_keyboard(),
    )


async def _run_backtest(
    message: Message,
    session: AsyncSession,
    settings: Settings,
    *,
    max_trades_per_day: int,
) -> None:
    if max_trades_per_day not in BACKTEST_MAX_TRADES:
        await message.answer("Неизвестный лимит.", reply_markup=back_keyboard())
        return

    cfg = await _cfg(session)
    cfg = replace(
        cfg,
        max_signals_per_day=max_trades_per_day,
        min_hours_between_signals=min_hours_for_max_trades(max_trades_per_day),
    )
    days = BACKTEST_DAYS
    limit = candles_for_period(days, cfg.timeframe)
    htf_limit = htf_candles_for_period(days, cfg.higher_tf) if cfg.use_higher_tf else 0

    if cfg.use_higher_tf:
        candles, htf_candles = await asyncio.gather(
            fetch_candles(settings.symbol, cfg.timeframe, limit=limit),
            fetch_candles(settings.symbol, cfg.higher_tf, limit=htf_limit),
        )
    else:
        candles = await fetch_candles(settings.symbol, cfg.timeframe, limit=limit)
        htf_candles = None

    result = await asyncio.to_thread(
        run_backtest,
        candles,
        cfg,
        htf_candles=htf_candles,
        initial_capital=1000.0,
    )
    text = format_backtest_result(
        result,
        timeframe=cfg.timeframe,
        days=days,
        bars=len(candles),
        max_trades_per_day=max_trades_per_day,
    )
    await message.answer(text, reply_markup=backtest_result_keyboard())


@router.callback_query(F.data.regexp(r"^backtest:max:\d+$"))
async def backtest_run(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    if callback.data is None or not isinstance(callback.message, Message):
        return
    max_trades = int(callback.data.rsplit(":", maxsplit=1)[-1])
    await callback.answer(f"Считаю 30 дней · {trades_per_day_label(max_trades)}...")
    await _run_backtest(callback.message, session, settings, max_trades_per_day=max_trades)


@router.callback_query(F.data == "menu:signal")
async def menu_signal(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await callback.answer("Загружаю...")
    if not isinstance(callback.message, Message):
        return

    open_signals = await list_open_signals(session)
    cfg, candles, snap, _, _, _ = await _market_context(session, settings)

    if open_signals:
        signal = open_signals[0]
        await answer_with_chart(
            callback.message,
            format_signal_message(signal),
            candles,
            cfg,
            signal=signal,
            reply_markup=refresh_keyboard("menu:signal"),
        )
        return

    await answer_with_chart(
        callback.message,
        format_no_signal(snap),
        candles,
        cfg,
        reply_markup=refresh_keyboard("menu:signal"),
    )


@router.callback_query(F.data == "menu:market")
async def menu_market(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await callback.answer("Загружаю...")
    if not isinstance(callback.message, Message):
        return

    cfg, candles, snap, fear_greed, funding, derivatives = await _market_context(session, settings)
    caption = format_market(
        snap, cfg.timeframe, fear_greed=fear_greed, funding=funding, derivatives=derivatives,
    )
    await answer_with_chart(
        callback.message,
        caption,
        candles,
        cfg,
        reply_markup=refresh_keyboard("menu:market"),
    )


@router.callback_query(F.data == "menu:stats")
async def menu_stats(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    if not isinstance(callback.message, Message):
        return
    stats = await get_statistics(session)
    await callback.message.answer(format_stats(stats), reply_markup=stats_keyboard())


@router.callback_query(F.data.regexp(r"^hist:(all|win|loss|open):\d+:\d+$"))
async def menu_history(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    if callback.data is None or not isinstance(callback.message, Message):
        return
    status_filter, days, page = parse_history_callback(callback.data)
    await _show_history(
        callback.message, session,
        status_filter=status_filter, days=days, page=page,
    )


@router.callback_query(F.data.regexp(r"^hist:detail:\d+$"))
async def history_detail(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    if callback.data is None or not isinstance(callback.message, Message):
        return
    signal_id = int(callback.data.rsplit(":", maxsplit=1)[-1])
    signal = await get_signal_by_id(session, signal_id)
    if signal is None:
        await callback.message.answer("Сделка не найдена.", reply_markup=back_keyboard())
        return
    await callback.message.answer(
        format_history_detail(signal),
        reply_markup=history_detail_keyboard(signal_id),
    )


@router.callback_query(F.data.regexp(r"^menu:history:\d+$"))
async def menu_history_legacy(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    if not isinstance(callback.message, Message):
        return
    await _show_history(callback.message, session, status_filter="all", days=0, page=0)


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
    cfg, candles, snap, _, _, _ = await _market_context(session, settings)
    if open_signals:
        await answer_with_chart(message, format_signal_message(open_signals[0]), candles, cfg, signal=open_signals[0])
    else:
        await answer_with_chart(message, format_no_signal(snap), candles, cfg)


@router.message(Command("calc"))
async def calc_cmd(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    counts = await _period_counts(session)
    await message.answer(
        format_calculator_intro(counts.get(0, 0)),
        reply_markup=calculator_period_keyboard(counts),
    )
