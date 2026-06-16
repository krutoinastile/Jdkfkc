"""Adaptive strategy router — picks best signal by market regime (ADX)."""

from __future__ import annotations

from app.services.indicators import adx
from app.services.market_data import Candle
from app.services.signal_filters import passes_entry_filters
from app.services.strategy import TradeSignal, analyze_bb_squeeze
from app.services.strategy_config import StrategyConfig
from app.services.strategy_variants import analyze_mean_reversion, analyze_swing_breakout


def _adx_now(candles: list[Candle]) -> float | None:
    if len(candles) < 40:
        return None
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    closes = [c.close for c in candles]
    vals = adx(highs, lows, closes, 14)
    if not vals:
        return None
    return vals[-1]


def regime_label(adx_val: float) -> str:
    if adx_val < 20:
        return "боковик → Mean Reversion"
    if adx_val >= 30:
        return "тренд → Swing Breakout"
    return "умеренный → BB Squeeze"


def analyze_candles(
    candles: list[Candle],
    cfg: StrategyConfig,
    htf_candles: list[Candle] | None = None,
) -> TradeSignal | None:
    adx_val = _adx_now(candles)
    if adx_val is None:
        return analyze_bb_squeeze(candles, cfg, htf_candles=htf_candles)

    candidates: list[TradeSignal] = []

    squeeze = analyze_bb_squeeze(candles, cfg, htf_candles=htf_candles)
    if squeeze and passes_entry_filters(squeeze, candles, cfg, htf_candles):
        candidates.append(squeeze)

    if adx_val < 22:
        mr = analyze_mean_reversion(candles, cfg, htf_candles=htf_candles)
        if mr and passes_entry_filters(mr, candles, cfg, htf_candles):
            candidates.append(mr)
    elif adx_val >= 28:
        swing = analyze_swing_breakout(candles, cfg, htf_candles=htf_candles)
        if swing and passes_entry_filters(swing, candles, cfg, htf_candles):
            candidates.append(swing)

    if not candidates:
        return None

    best = max(candidates, key=lambda s: s.strength)
    mode = regime_label(adx_val)
    best.reason = f"[{mode}] {best.reason}"
    return best
