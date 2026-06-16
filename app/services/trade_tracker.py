"""Scan market, open signals, track outcomes."""

from __future__ import annotations

import logging

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.database.models import Signal, TradeStatus
from app.database.repositories import (
    can_open_new_signal,
    close_signal,
    create_signal,
    expire_old_signals,
    get_strategy_settings,
    has_open_signal,
    list_open_signals,
    mark_partial_take_profit,
)
from app.services.subscription import list_premium_notify_users, send_subscription_reminders
from app.services.market_data import Candle, fetch_candles, fetch_current_price
from app.services.trade_management import apply_trailing_stop
from app.utils.telegram import send_signal_chart
from app.services.strategy import analyze_candles
from app.services.strategy_config import StrategyConfig
from app.utils.leverage import get_leverage, spot_to_leveraged
from app.utils.trade_pnl import combined_close_pnl, partial_tp_hit, partial_tp_price, spot_pnl_pct
from app.utils.messages import format_signal_card, format_trade_closed

logger = logging.getLogger(__name__)

TRAIL_ALERTS = {
    "breakeven": "🛡 <b>SL в безубыток</b> — сделка #{id} ({dir} @ {entry})",
    "lock_half_r": "🔒 <b>+0.5R зафиксировано</b> — SL подтянут · #{id}",
    "trail": "📈 <b>Trailing SL</b> активен · сделка #{id}",
    "partial_tp": "🎯 <b>Частичный TP 50%</b> на +2R · сделка #{id} · +{pnl}%",
}


def format_signal_message(signal: Signal, *, is_new: bool = False, current_price: float | None = None) -> str:
    return format_signal_card(signal, is_new=is_new, current_price=current_price)


async def run_market_scan(
    session: AsyncSession,
    settings: Settings,
    bot: Bot,
    *,
    force: bool = False,
) -> Signal | None:
    db_cfg = await get_strategy_settings(session)
    if not db_cfg.scanning_enabled and not force:
        return None

    if not force:
        allowed, reason = await can_open_new_signal(
            session,
            settings.symbol,
            min_hours=db_cfg.min_hours_between_signals,
            max_per_day=db_cfg.max_signals_per_day,
        )
        if not allowed:
            logger.debug("Signal skipped: %s", reason)
            return None
    elif await has_open_signal(session, settings.symbol):
        return None

    cfg = StrategyConfig.from_db(db_cfg)
    candles = await fetch_candles(settings.symbol, cfg.timeframe)
    htf_candles = await fetch_candles(settings.symbol, cfg.higher_tf) if cfg.use_higher_tf else None
    trade_signal = analyze_candles(candles, cfg, htf_candles=htf_candles)
    if trade_signal is None:
        return None

    signal = await create_signal(
        session,
        symbol=settings.symbol,
        timeframe=cfg.timeframe,
        direction=trade_signal.direction,
        entry_price=trade_signal.entry_price,
        stop_loss=trade_signal.stop_loss,
        take_profit=trade_signal.take_profit,
        rsi=trade_signal.rsi,
        ema_fast=trade_signal.ema_fast,
        ema_slow=trade_signal.ema_slow,
        atr=trade_signal.atr_value,
        reason=trade_signal.reason,
        signal_type=trade_signal.signal_type,
        strength=trade_signal.strength,
        macd_hist=trade_signal.macd_hist,
        leverage=db_cfg.leverage,
    )
    await notify_signal(bot, session, signal, settings, candles=candles, cfg=cfg)
    return signal


async def check_open_trades(
    session: AsyncSession,
    settings: Settings,
    bot: Bot,
) -> list[Signal]:
    price = await fetch_current_price(settings.symbol)
    closed: list[Signal] = []

    for signal in await list_open_signals(session):
        trail_event = await apply_trailing_stop(session, signal, price)
        if trail_event:
            await _notify_trailing(bot, session, signal, settings, trail_event)

        if partial_tp_hit(signal, price):
            pt = partial_tp_price(signal)
            lev = get_leverage(signal)
            spot = spot_pnl_pct(signal, pt)
            half_margin = spot_to_leveraged(spot, lev) * 0.5
            await mark_partial_take_profit(session, signal, half_margin)
            await _notify_trailing(
                bot, session, signal, settings, "partial_tp", extra={"pnl": f"{half_margin:+.1f}"}
            )

        lev = get_leverage(signal)
        remaining = 0.5 if signal.partial_tp_hit else 1.0

        if signal.direction == "long":
            if price >= signal.take_profit:
                spot = (signal.take_profit - signal.entry_price) / signal.entry_price * 100
                margin = spot_to_leveraged(spot, lev) * remaining
                pnl = combined_close_pnl(signal, margin)
                await close_signal(session, signal, status=TradeStatus.WIN.value, exit_price=price, pnl_percent=pnl)
                closed.append(signal)
            elif price <= signal.stop_loss:
                spot = (signal.stop_loss - signal.entry_price) / signal.entry_price * 100
                margin = spot_to_leveraged(spot, lev) * remaining
                pnl = combined_close_pnl(signal, margin)
                await close_signal(session, signal, status=TradeStatus.LOSS.value, exit_price=price, pnl_percent=pnl)
                closed.append(signal)
        else:
            if price <= signal.take_profit:
                spot = (signal.entry_price - signal.take_profit) / signal.entry_price * 100
                margin = spot_to_leveraged(spot, lev) * remaining
                pnl = combined_close_pnl(signal, margin)
                await close_signal(session, signal, status=TradeStatus.WIN.value, exit_price=price, pnl_percent=pnl)
                closed.append(signal)
            elif price >= signal.stop_loss:
                spot = (signal.entry_price - signal.stop_loss) / signal.entry_price * 100
                margin = spot_to_leveraged(spot, lev) * remaining
                pnl = combined_close_pnl(signal, margin)
                await close_signal(session, signal, status=TradeStatus.LOSS.value, exit_price=price, pnl_percent=pnl)
                closed.append(signal)

    await expire_old_signals(session, current_price=price)
    return closed


async def _notify_trailing(
    bot: Bot,
    session: AsyncSession,
    signal: Signal,
    settings: Settings,
    event: str,
    *,
    extra: dict | None = None,
) -> None:
    template = TRAIL_ALERTS.get(event)
    if not template:
        return
    fmt = {
        "id": signal.id,
        "dir": signal.direction.upper(),
        "entry": signal.entry_price,
        **(extra or {}),
    }
    text = template.format(**fmt)
    recipient_ids = set(settings.parsed_admin_ids)
    if settings.notify_on_signal:
        recipient_ids.update(user.tg_id for user in await list_premium_notify_users(session, settings))
    for tg_id in recipient_ids:
        try:
            await bot.send_message(chat_id=tg_id, text=text)
        except Exception:
            logger.exception("Trailing alert failed for %s", tg_id)


async def notify_signal(
    bot: Bot,
    session: AsyncSession,
    signal: Signal,
    settings: Settings,
    *,
    candles: list[Candle] | None = None,
    cfg: StrategyConfig | None = None,
) -> None:
    text = format_signal_message(signal, is_new=True)
    recipient_ids = set(settings.parsed_admin_ids)
    if settings.notify_on_signal:
        recipient_ids.update(user.tg_id for user in await list_premium_notify_users(session, settings))

    for tg_id in recipient_ids:
        try:
            await bot.send_message(chat_id=tg_id, text=text)
            if candles and cfg:
                await send_signal_chart(bot, tg_id, candles, cfg, signal)
        except Exception:
            logger.exception("Failed to notify user %s", tg_id)


async def notify_trade_closed(
    bot: Bot,
    session: AsyncSession,
    signal: Signal,
    settings: Settings,
) -> None:
    text = format_trade_closed(signal)
    recipient_ids = set(settings.parsed_admin_ids)
    if settings.notify_on_signal:
        recipient_ids.update(user.tg_id for user in await list_premium_notify_users(session, settings))

    for tg_id in recipient_ids:
        try:
            await bot.send_message(chat_id=tg_id, text=text)
        except Exception:
            logger.exception("Failed to notify user %s about closed trade", tg_id)


def setup_scheduler(session_pool: async_sessionmaker[AsyncSession], bot: Bot, settings: Settings):
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    scheduler = AsyncIOScheduler()

    async def scan_job() -> None:
        async with session_pool() as session:
            try:
                await run_market_scan(session, settings, bot)
            except Exception:
                logger.exception("Scan job failed")

    async def check_job() -> None:
        async with session_pool() as session:
            try:
                closed = await check_open_trades(session, settings, bot)
                for signal in closed:
                    await notify_trade_closed(bot, session, signal, settings)
            except Exception:
                logger.exception("Check trades job failed")

    async def subscription_reminder_job() -> None:
        async with session_pool() as session:
            try:
                await send_subscription_reminders(session, bot)
            except Exception:
                logger.exception("Subscription reminder job failed")

    scheduler.add_job(scan_job, "interval", minutes=settings.scan_interval_minutes, id="market_scan")
    scheduler.add_job(check_job, "interval", minutes=settings.trade_check_interval_minutes, id="trade_check")
    scheduler.add_job(subscription_reminder_job, "interval", hours=12, id="sub_reminders")
    return scheduler
