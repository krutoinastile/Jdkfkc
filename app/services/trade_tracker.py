"""Scan market, open signals, track outcomes."""

from __future__ import annotations

import logging

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.database.models import Signal, TradeStatus
from app.database.repositories import (
    close_signal,
    create_signal,
    expire_old_signals,
    has_open_signal,
    list_open_signals,
    list_subscribed_users,
)
from app.services.market_data import fetch_candles, fetch_current_price
from app.services.strategy import analyze_candles

logger = logging.getLogger(__name__)


def format_signal_message(signal: Signal, *, is_new: bool = False) -> str:
    emoji = "🟢" if signal.direction == "long" else "🔴"
    action = "LONG (покупка)" if signal.direction == "long" else "SHORT (продажа)"
    header = "🚨 <b>Новый сигнал!</b>" if is_new else "📊 <b>Текущий сигнал</b>"
    risk = abs(signal.entry_price - signal.stop_loss)
    reward = abs(signal.take_profit - signal.entry_price)
    rr = round(reward / risk, 2) if risk > 0 else 0

    return (
        f"{header}\n\n"
        f"{emoji} <b>{action}</b> | BTC/USDT\n"
        f"Таймфрейм: {signal.timeframe}\n\n"
        f"💰 Вход: <b>${signal.entry_price:,.2f}</b>\n"
        f"🛑 Stop-Loss: <b>${signal.stop_loss:,.2f}</b>\n"
        f"🎯 Take-Profit: <b>${signal.take_profit:,.2f}</b>\n"
        f"📐 R:R = 1:{rr}\n\n"
        f"RSI: {signal.rsi} | EMA9: ${signal.ema_fast:,.0f} | EMA21: ${signal.ema_slow:,.0f}\n"
        f"ATR: ${signal.atr:,.2f}\n\n"
        f"<i>{signal.reason}</i>"
    )


async def scan_for_signal(session: AsyncSession, settings: Settings) -> Signal | None:
    if await has_open_signal(session, settings.symbol):
        return None

    candles = await fetch_candles(settings.symbol, settings.timeframe)
    trade_signal = analyze_candles(candles)
    if trade_signal is None:
        return None

    return await create_signal(
        session,
        symbol=settings.symbol,
        timeframe=settings.timeframe,
        direction=trade_signal.direction,
        entry_price=trade_signal.entry_price,
        stop_loss=trade_signal.stop_loss,
        take_profit=trade_signal.take_profit,
        rsi=trade_signal.rsi,
        ema_fast=trade_signal.ema_fast,
        ema_slow=trade_signal.ema_slow,
        atr=trade_signal.atr_value,
        reason=trade_signal.reason,
    )


async def check_open_trades(session: AsyncSession, settings: Settings) -> list[Signal]:
    price = await fetch_current_price(settings.symbol)
    closed: list[Signal] = []

    for signal in await list_open_signals(session):
        if signal.direction == "long":
            if price >= signal.take_profit:
                pnl = (signal.take_profit - signal.entry_price) / signal.entry_price * 100
                await close_signal(session, signal, status=TradeStatus.WIN.value, exit_price=price, pnl_percent=pnl)
                closed.append(signal)
            elif price <= signal.stop_loss:
                pnl = (signal.stop_loss - signal.entry_price) / signal.entry_price * 100
                await close_signal(session, signal, status=TradeStatus.LOSS.value, exit_price=price, pnl_percent=pnl)
                closed.append(signal)
        else:
            if price <= signal.take_profit:
                pnl = (signal.entry_price - signal.take_profit) / signal.entry_price * 100
                await close_signal(session, signal, status=TradeStatus.WIN.value, exit_price=price, pnl_percent=pnl)
                closed.append(signal)
            elif price >= signal.stop_loss:
                pnl = (signal.entry_price - signal.stop_loss) / signal.entry_price * 100
                await close_signal(session, signal, status=TradeStatus.LOSS.value, exit_price=price, pnl_percent=pnl)
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
    if signal.status == TradeStatus.WIN.value:
        emoji, label = "✅", "УСПЕХ"
    elif signal.status == TradeStatus.LOSS.value:
        emoji, label = "❌", "УБЫТОК"
    else:
        emoji, label = "⏱", "ИСТЁК"

    text = (
        f"{emoji} <b>Сделка закрыта: {label}</b>\n\n"
        f"Направление: {signal.direction.upper()}\n"
        f"Вход: ${signal.entry_price:,.2f}\n"
        f"Выход: ${signal.exit_price:,.2f}\n"
        f"P&L: <b>{signal.pnl_percent:+.2f}%</b>"
    )
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
                signal = await scan_for_signal(session, settings)
                if signal and settings.notify_on_signal:
                    await notify_signal(bot, session, signal)
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
