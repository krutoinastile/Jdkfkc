"""Adaptive strategy router — BB Squeeze with HTF/MACD/volume filters."""

from __future__ import annotations

from app.services.indicators import adx
from app.services.market_data import Candle
from app.services.signal_filters import passes_entry_filters
from app.services.strategy import TradeSignal, analyze_bb_squeeze
from app.services.strategy_config import StrategyConfig


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
        return "боковик"
    if adx_val >= 30:
        return "тренд"
    return "умеренный"


def analyze_candles(
    candles: list[Candle],
    cfg: StrategyConfig,
    htf_candles: list[Candle] | None = None,
) -> TradeSignal | None:
    """BB Squeeze only — best long-term edge vs multi-strategy router."""
    signal = analyze_bb_squeeze(candles, cfg, htf_candles=htf_candles)
    if signal is None or not passes_entry_filters(signal, candles, cfg, htf_candles):
        return None

    adx_val = _adx_now(candles)
    if adx_val is not None:
        mode = regime_label(adx_val)
        signal.reason = f"[{mode} · BB Squeeze] {signal.reason}"
    return signal
