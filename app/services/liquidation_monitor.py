"""Binance Futures liquidation monitor via WebSocket."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime

import aiohttp
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.repositories import (
    get_strategy_settings,
    list_users_notify_liq_longs,
    list_users_notify_liq_shorts,
)
from app.utils.messages import format_liquidation

logger = logging.getLogger(__name__)

BINANCE_FORCE_ORDER_WS = "wss://fstream.binance.com/ws/btcusdt@forceOrder"


def _parse_liquidation(data: dict) -> tuple[str, str, float, float, float] | None:
    if data.get("e") != "forceOrder":
        return None
    order = data.get("o", {})
    if order.get("X") != "FILLED":
        return None

    symbol = order.get("s", "BTCUSDT")
    side_raw = order.get("S", "")
    price = float(order.get("ap") or order.get("p") or 0)
    qty = float(order.get("q") or order.get("l") or 0)
    if price <= 0 or qty <= 0:
        return None

    # SELL liquidation order = long position liquidated
    # BUY liquidation order = short position liquidated
    liq_side = "long" if side_raw == "SELL" else "short"
    usd_value = price * qty
    return liq_side, symbol, price, qty, usd_value


async def _notify_users(
    bot: Bot,
    session: AsyncSession,
    *,
    liq_side: str,
    text: str,
) -> None:
    if liq_side == "long":
        users = await list_users_notify_liq_longs(session)
    else:
        users = await list_users_notify_liq_shorts(session)

    for user in users:
        try:
            await bot.send_message(chat_id=user.tg_id, text=text)
        except Exception:
            logger.exception("Failed to send liquidation alert to %s", user.tg_id)


async def _handle_message(
    bot: Bot,
    session_pool: async_sessionmaker[AsyncSession],
    raw: str,
) -> None:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return

    parsed = _parse_liquidation(data)
    if parsed is None:
        return

    liq_side, symbol, price, qty, usd_value = parsed

    async with session_pool() as session:
        cfg = await get_strategy_settings(session)
        if not cfg.liquidations_enabled:
            return
        if usd_value < cfg.min_liquidation_usd:
            return

        text = format_liquidation(
            side=liq_side,
            symbol=symbol,
            price=price,
            quantity=qty,
            usd_value=usd_value,
        )
        await _notify_users(bot, session, liq_side=liq_side, text=text)
        logger.info(
            "Liquidation %s %s $%.0f at %s",
            liq_side,
            symbol,
            usd_value,
            datetime.now(tz=UTC).isoformat(),
        )


async def run_liquidation_monitor(
    bot: Bot,
    session_pool: async_sessionmaker[AsyncSession],
) -> None:
    """Listen to Binance forceOrder stream with auto-reconnect."""
    while True:
        try:
            async with aiohttp.ClientSession() as http_session:
                async with http_session.ws_connect(BINANCE_FORCE_ORDER_WS, heartbeat=30) as ws:
                    logger.info("Liquidation monitor connected: %s", BINANCE_FORCE_ORDER_WS)
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            await _handle_message(bot, session_pool, msg.data)
                        elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                            break
        except Exception:
            logger.exception("Liquidation monitor disconnected, reconnecting in 10s")
        await asyncio.sleep(10)
