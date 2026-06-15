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
    list_subscribed_users,
)
from app.services.market_data import fetch_candles, fetch_current_price
from app.services.strategy import analyze_candles
from app.services.strategy_config import StrategyConfig
from app.utils.leverage import get_leverage, spot_to_leveraged
from app.utils.messages import format_signal_card, format_trade_closed

logger = logging.getLogger(__name__)


def format_signal_message(signal: Signal, *, is_new: bool = False) -> str:
    return format_signal_card(signal, is_new=is_new)


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
    if settings.notify_on_signal:
        await notify_signal(bot, session, signal)
    return signal


async def check_open_trades(session: AsyncSession, settings: Settings) -> list[Signal]:
    price = await fetch_current_price(settings.symbol)
    closed: list[Signal] = []

    for signal in await list_open_signals(session):
        lev = get_leverage(signal)
        if signal.direction == "long":
            if price >= signal.take_profit:
                spot = (signal.take_profit - signal.entry_price) / signal.entry_price * 100
                await close_signal(session, signal, status=TradeStatus.WIN.value, exit_price=price, pnl_percent=spot_to_leveraged(spot, lev))
                closed.append(signal)
            elif price <= signal.stop_loss:
                spot = (signal.stop_loss - signal.entry_price) / signal.entry_price * 100
                await close_signal(session, signal, status=TradeStatus.LOSS.value, exit_price=price, pnl_percent=spot_to_leveraged(spot, lev))
                closed.append(signal)
        else:
            if price <= signal.take_profit:
                spot = (signal.entry_price - signal.take_profit) / signal.entry_price * 100
                await close_signal(session, signal, status=TradeStatus.WIN.value, exit_price=price, pnl_percent=spot_to_leveraged(spot, lev))
                closed.append(signal)
            elif price >= signal.stop_loss:
                spot = (signal.entry_price - signal.stop_loss) / signal.entry_price * 100
                await close_signal(session, signal, status=TradeStatus.LOSS.value, exit_price=price, pnl_percent=spot_to_leveraged(spot, lev))
                closed.append(signal)

    await expire_old_signals(session)
    return closed


async def notify_signal(bot: Bot, session: AsyncSession, signal: Signal) -> None:
    text = format_signal_message(signal, is_new=True)
    for user in await list_subscribed_users(session):
        try:
            await bot.send_message(chat_id=user.tg_id, text=text)
        except Exception:
            logger.exception("Failed to notify user %s", user.tg_id)


async def notify_trade_closed(bot: Bot, session: AsyncSession, signal: Signal) -> None:
    text = format_trade_closed(signal)
    for user in await list_subscribed_users(session):
        try:
            await bot.send_message(chat_id=user.tg_id, text=text)
        except Exception:
            logger.exception("Failed to notify user %s about closed trade", user.tg_id)


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
                closed = await check_open_trades(session, settings)
                for signal in closed:
                    await notify_trade_closed(bot, session, signal)
            except Exception:
                logger.exception("Check trades job failed")

    scheduler.add_job(scan_job, "interval", minutes=settings.scan_interval_minutes, id="market_scan")
    scheduler.add_job(check_job, "interval", minutes=settings.trade_check_interval_minutes, id="trade_check")
    return scheduler
