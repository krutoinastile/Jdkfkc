"""Trailing stop and breakeven management."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Signal
from app.database.repositories import update_signal_stop_loss
from app.utils.trade_pnl import initial_risk

logger = logging.getLogger(__name__)


def _better_sl(signal: Signal, candidate: float) -> bool:
    if signal.direction == "long":
        return candidate > signal.stop_loss
    return candidate < signal.stop_loss


async def apply_trailing_stop(session: AsyncSession, signal: Signal, price: float) -> str | None:
    """Move SL to breakeven at +1R, lock +0.5R at +2R, trail by 1 ATR at +3R."""
    risk = initial_risk(signal)
    if risk <= 0:
        return None

    entry = signal.entry_price
    atr = signal.atr or risk
    new_sl: float | None = None
    event: str | None = None

    if signal.direction == "long":
        profit = price - entry
        if profit >= risk:
            new_sl = entry
            event = "breakeven"
        if profit >= 2 * risk:
            new_sl = max(new_sl or entry, entry + 0.5 * risk)
            event = "lock_half_r"
        if profit >= 3 * risk:
            trail = price - atr
            new_sl = max(new_sl or trail, trail)
            event = "trail"
    else:
        profit = entry - price
        if profit >= risk:
            new_sl = entry
            event = "breakeven"
        if profit >= 2 * risk:
            new_sl = min(new_sl or entry, entry - 0.5 * risk)
            event = "lock_half_r"
        if profit >= 3 * risk:
            trail = price + atr
            new_sl = min(new_sl or trail, trail)
            event = "trail"

    if new_sl is None or not _better_sl(signal, new_sl):
        return None

    old_sl = signal.stop_loss
    await update_signal_stop_loss(session, signal, new_sl)
    logger.info(
        "Trailing SL signal #%s %s: %.2f → %.2f (price %.2f, %s)",
        signal.id,
        signal.direction,
        old_sl,
        new_sl,
        price,
        event,
    )
    return event
