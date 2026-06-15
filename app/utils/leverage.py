"""Futures leverage helpers."""

from __future__ import annotations

DEFAULT_LEVERAGE = 20
DEFAULT_BANK_ALLOCATION_PCT = 10.0


def get_leverage(signal_or_settings) -> int:  # noqa: ANN001
    lev = getattr(signal_or_settings, "leverage", None)
    if lev is None or lev <= 0:
        return DEFAULT_LEVERAGE
    return int(lev)


def spot_to_leveraged(spot_pnl_pct: float, leverage: int) -> float:
    return round(spot_pnl_pct * leverage, 2)


def leveraged_move(spot_move_pct: float, leverage: int) -> float:
    return round(abs(spot_move_pct) * leverage, 2)


def pnl_on_bank(
    margin_pnl_pct: float,
    bank_allocation_pct: float = DEFAULT_BANK_ALLOCATION_PCT,
) -> float:
    """Convert leveraged margin P&L % to change on total bank."""
    return round(margin_pnl_pct * bank_allocation_pct / 100, 2)
