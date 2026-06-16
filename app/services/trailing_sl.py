"""Shared trailing stop logic for live trading and backtest."""

from __future__ import annotations


def _better_sl(direction: str, candidate: float, current_sl: float) -> bool:
    if direction == "long":
        return candidate > current_sl
    return candidate < current_sl


def compute_trailing_stop(
    *,
    direction: str,
    entry: float,
    current_sl: float,
    initial_sl: float,
    atr: float,
    price: float,
) -> tuple[float | None, str | None]:
    """
    Late trailing: no +1R breakeven (cuts win rate on 1h).
    Lock +0.5R at +2R, ATR trail at +3R.
    """
    risk = abs(entry - initial_sl)
    if risk <= 0:
        return None, None

    new_sl: float | None = None
    event: str | None = None

    if direction == "long":
        profit = price - entry
        if profit >= 2 * risk:
            new_sl = max(entry + 0.5 * risk, entry)
            event = "lock_half_r"
        if profit >= 3 * risk:
            trail = price - atr
            new_sl = max(new_sl or trail, trail)
            event = "trail"
    else:
        profit = entry - price
        if profit >= 2 * risk:
            new_sl = min(entry - 0.5 * risk, entry)
            event = "lock_half_r"
        if profit >= 3 * risk:
            trail = price + atr
            new_sl = min(new_sl or trail, trail)
            event = "trail"

    if new_sl is None or not _better_sl(direction, new_sl, current_sl):
        return None, None
    return new_sl, event
