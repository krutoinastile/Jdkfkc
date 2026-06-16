"""Trailing stop management."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Signal
from app.database.repositories import update_signal_stop_loss
from app.services.trailing_sl import compute_trailing_stop
from app.utils.trade_pnl import initial_risk

logger = logging.getLogger(__name__)


def _better_sl(signal: Signal, candidate: float) -> bool:
    if signal.direction == "long":
        return candidate > signal.stop_loss
    return candidate < signal.stop_loss


async def apply_trailing_stop(session: AsyncSession, signal: Signal, price: float) -> str | None:
    """Move SL: lock +0.5R at +2R, ATR trail at +3R (no early breakeven at +1R)."""
    risk = initial_risk(signal)
    if risk <= 0:
        return None

    atr = signal.atr or risk
    new_sl, event = compute_trailing_stop(
        direction=signal.direction,
        entry=signal.entry_price,
        current_sl=signal.stop_loss,
        initial_sl=signal.initial_stop_loss or signal.stop_loss,
        atr=atr,
        price=price,
    )
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
