"""Classic trading strategy variants for backtest comparison."""

from __future__ import annotations

from collections.abc import Callable

from app.services.indicators import (
    adx,
    atr,
    bb_width_percentile,
    bollinger_bands,
    donchian_channel,
    ema,
    macd,
    rsi,
    sma,
)
from app.services.market_data import Candle
from app.services.strategy import TradeSignal
from app.services.strategy_config import StrategyConfig

Analyzer = Callable[[list[Candle], StrategyConfig, list[Candle] | None], TradeSignal | None]


def _make_signal(
    *,
    direction: str,
    price: float,
    atr_now: float,
    cfg: StrategyConfig,
    reason: str,
    signal_type: str,
    strength: int,
    rsi_val: float,
    ema_fast: float,
    ema_slow: float,
    macd_hist: float = 0.0,
) -> TradeSignal:
    if direction == "long":
        sl = price - cfg.atr_sl_mult * atr_now
        tp = price + cfg.atr_tp_mult * atr_now
    else:
        sl = price + cfg.atr_sl_mult * atr_now
        tp = price - cfg.atr_tp_mult * atr_now
    return TradeSignal(
        direction=direction,
        entry_price=round(price, 2),
        stop_loss=round(sl, 2),
        take_profit=round(tp, 2),
        rsi=round(rsi_val, 1),
        ema_fast=round(ema_fast, 2),
        ema_slow=round(ema_slow, 2),
        atr_value=round(atr_now, 2),
        reason=reason,
        signal_type=signal_type,
        strength=strength,
        macd_hist=round(macd_hist, 2),
    )


def _base_series(candles: list[Candle], cfg: StrategyConfig):
    closes = [c.close for c in candles]
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    volumes = [c.volume for c in candles]
    ema_f = ema(closes, cfg.ema_fast)
    ema_s = ema(closes, cfg.ema_slow)
    ema_t = ema(closes, cfg.ema_trend)
    rsi_vals = rsi(closes, cfg.rsi_period)
    atr_vals = atr(highs, lows, closes, 14)
    adx_vals = adx(highs, lows, closes, 14)
    _, _, hist = macd(closes)
    vol_avg = sma(volumes, 20)
    if not all([ema_f, ema_s, ema_t, rsi_vals, atr_vals, adx_vals]):
        return None
    return closes, highs, lows, volumes, ema_f, ema_s, ema_t, rsi_vals, atr_vals, adx_vals, hist, vol_avg


def analyze_ema_cross(
    candles: list[Candle],
    cfg: StrategyConfig,
    *,
    htf_candles: list[Candle] | None = None,
) -> TradeSignal | None:
    """Classic EMA crossover (9/21) with EMA55 trend filter."""
    if len(candles) < cfg.ema_trend + 5:
        return None
    data = _base_series(candles, cfg)
    if not data:
        return None
    closes, _, _, _, ema_f, ema_s, ema_t, rsi_vals, atr_vals, adx_vals, hist, _ = data
    i, prev = len(closes) - 1, len(closes) - 2
    price = closes[i]
    atr_now = atr_vals[-1]
    if atr_now <= 0:
        return None

    bullish = ema_f[prev] <= ema_s[prev] and ema_f[i] > ema_s[i] and price > ema_t[i]
    bearish = ema_f[prev] >= ema_s[prev] and ema_f[i] < ema_s[i] and price < ema_t[i]
    adx_now = adx_vals[-1]
    rsi_now = rsi_vals[i]
    macd_h = hist[-1] if hist else 0.0

    if bullish and adx_now >= 15:
        return _make_signal(
            direction="long",
            price=price,
            atr_now=atr_now,
            cfg=cfg,
            reason=f"LONG: EMA crossover. ADX={adx_now:.0f}, RSI={rsi_now:.1f}.",
            signal_type="crossover",
            strength=min(60 + int(adx_now), 100),
            rsi_val=rsi_now,
            ema_fast=ema_f[i],
            ema_slow=ema_s[i],
            macd_hist=macd_h,
        )
    if bearish and adx_now >= 15:
        return _make_signal(
            direction="short",
            price=price,
            atr_now=atr_now,
            cfg=cfg,
            reason=f"SHORT: EMA crossover. ADX={adx_now:.0f}, RSI={rsi_now:.1f}.",
            signal_type="crossover",
            strength=min(60 + int(adx_now), 100),
            rsi_val=rsi_now,
            ema_fast=ema_f[i],
            ema_slow=ema_s[i],
            macd_hist=macd_h,
        )
    return None


def analyze_mean_reversion(
    candles: list[Candle],
    cfg: StrategyConfig,
    *,
    htf_candles: list[Candle] | None = None,
) -> TradeSignal | None:
    """Bollinger + RSI mean reversion in ranging markets (low ADX)."""
    if len(candles) < 55:
        return None
    data = _base_series(candles, cfg)
    if not data:
        return None
    closes, _, _, _, ema_f, ema_s, ema_t, rsi_vals, atr_vals, adx_vals, hist, _ = data
    upper, middle, lower = bollinger_bands(closes, 20, 2.0)
    if not upper:
        return None

    i = len(closes) - 1
    price = closes[i]
    atr_now = atr_vals[-1]
    adx_now = adx_vals[-1]
    rsi_now = rsi_vals[i]
    if atr_now <= 0 or adx_now > 28:
        return None

    macd_h = hist[-1] if hist else 0.0
    at_lower = price <= lower[i] * 1.002 and rsi_now < 32
    at_upper = price >= upper[i] * 0.998 and rsi_now > 68

    if at_lower and closes[i] > closes[i - 1]:
        return _make_signal(
            direction="long",
            price=price,
            atr_now=atr_now,
            cfg=cfg,
            reason=f"LONG: Mean reversion от BB. RSI={rsi_now:.1f}, ADX={adx_now:.0f}.",
            signal_type="mean_reversion",
            strength=min(55 + int(28 - adx_now), 90),
            rsi_val=rsi_now,
            ema_fast=ema_f[i],
            ema_slow=ema_s[i],
            macd_hist=macd_h,
        )
    if at_upper and closes[i] < closes[i - 1]:
        return _make_signal(
            direction="short",
            price=price,
            atr_now=atr_now,
            cfg=cfg,
            reason=f"SHORT: Mean reversion от BB. RSI={rsi_now:.1f}, ADX={adx_now:.0f}.",
            signal_type="mean_reversion",
            strength=min(55 + int(28 - adx_now), 90),
            rsi_val=rsi_now,
            ema_fast=ema_f[i],
            ema_slow=ema_s[i],
            macd_hist=macd_h,
        )
    return None


def analyze_donchian_breakout(
    candles: list[Candle],
    cfg: StrategyConfig,
    *,
    htf_candles: list[Candle] | None = None,
) -> TradeSignal | None:
    """Turtle-style Donchian channel breakout."""
    if len(candles) < 55:
        return None
    data = _base_series(candles, cfg)
    if not data:
        return None
    closes, highs, lows, volumes, ema_f, ema_s, ema_t, rsi_vals, atr_vals, adx_vals, hist, vol_avg = data
    upper, lower, _ = donchian_channel(highs, lows, 20)
    if not upper:
        return None

    i, prev = len(closes) - 1, len(closes) - 2
    price = closes[i]
    atr_now = atr_vals[-1]
    adx_now = adx_vals[-1]
    rsi_now = rsi_vals[i]
    if atr_now <= 0:
        return None

    vol_ok = not vol_avg or volumes[i] >= vol_avg[-1] * 0.9
    macd_h = hist[-1] if hist else 0.0
    prev_upper = upper[prev]
    prev_lower = lower[prev]

    if price > prev_upper and price > ema_t[i] and adx_now >= 18 and vol_ok:
        return _make_signal(
            direction="long",
            price=price,
            atr_now=atr_now,
            cfg=cfg,
            reason=f"LONG: Donchian breakout. ADX={adx_now:.0f}.",
            signal_type="breakout",
            strength=min(58 + int(adx_now / 2), 100),
            rsi_val=rsi_now,
            ema_fast=ema_f[i],
            ema_slow=ema_s[i],
            macd_hist=macd_h,
        )
    if price < prev_lower and price < ema_t[i] and adx_now >= 18 and vol_ok:
        return _make_signal(
            direction="short",
            price=price,
            atr_now=atr_now,
            cfg=cfg,
            reason=f"SHORT: Donchian breakout. ADX={adx_now:.0f}.",
            signal_type="breakout",
            strength=min(58 + int(adx_now / 2), 100),
            rsi_val=rsi_now,
            ema_fast=ema_f[i],
            ema_slow=ema_s[i],
            macd_hist=macd_h,
        )
    return None


def analyze_macd_momentum(
    candles: list[Candle],
    cfg: StrategyConfig,
    *,
    htf_candles: list[Candle] | None = None,
) -> TradeSignal | None:
    """MACD line crosses signal with ADX trend confirmation."""
    if len(candles) < cfg.ema_trend + 5:
        return None
    data = _base_series(candles, cfg)
    if not data:
        return None
    closes, _, _, _, ema_f, ema_s, ema_t, rsi_vals, atr_vals, adx_vals, hist, _ = data
    macd_line, signal_line, _ = macd(closes)
    if not macd_line or not signal_line:
        return None

    i, prev = len(closes) - 1, len(closes) - 2
    price = closes[i]
    atr_now = atr_vals[-1]
    adx_now = adx_vals[-1]
    rsi_now = rsi_vals[i]
    if atr_now <= 0 or adx_now < 20:
        return None

    macd_h = hist[-1] if hist else 0.0
    bull_cross = macd_line[prev] <= signal_line[prev] and macd_line[i] > signal_line[i]
    bear_cross = macd_line[prev] >= signal_line[prev] and macd_line[i] < signal_line[i]

    if bull_cross and price > ema_t[i] and cfg.rsi_long_min < rsi_now < 72:
        return _make_signal(
            direction="long",
            price=price,
            atr_now=atr_now,
            cfg=cfg,
            reason=f"LONG: MACD momentum. ADX={adx_now:.0f}, hist={macd_h:.1f}.",
            signal_type="momentum",
            strength=min(62 + int(adx_now / 2), 100),
            rsi_val=rsi_now,
            ema_fast=ema_f[i],
            ema_slow=ema_s[i],
            macd_hist=macd_h,
        )
    if bear_cross and price < ema_t[i] and 28 < rsi_now < cfg.rsi_short_max + 10:
        return _make_signal(
            direction="short",
            price=price,
            atr_now=atr_now,
            cfg=cfg,
            reason=f"SHORT: MACD momentum. ADX={adx_now:.0f}, hist={macd_h:.1f}.",
            signal_type="momentum",
            strength=min(62 + int(adx_now / 2), 100),
            rsi_val=rsi_now,
            ema_fast=ema_f[i],
            ema_slow=ema_s[i],
            macd_hist=macd_h,
        )
    return None


def analyze_bb_squeeze(
    candles: list[Candle],
    cfg: StrategyConfig,
    *,
    htf_candles: list[Candle] | None = None,
) -> TradeSignal | None:
    """Bollinger squeeze breakout after volatility contraction."""
    if len(candles) < 60:
        return None
    data = _base_series(candles, cfg)
    if not data:
        return None
    closes, _, _, _, ema_f, ema_s, ema_t, rsi_vals, atr_vals, adx_vals, hist, _ = data
    upper, middle, lower = bollinger_bands(closes, 20, 2.0)
    if not upper:
        return None

    widths = [(u - l) / m if m else 0 for u, l, m in zip(upper, lower, middle)]
    squeeze_level = bb_width_percentile(widths, 50, 0.25)
    if squeeze_level is None:
        return None

    i, prev = len(closes) - 1, len(closes) - 2
    price = closes[i]
    atr_now = atr_vals[-1]
    adx_now = adx_vals[-1]
    rsi_now = rsi_vals[i]
    if atr_now <= 0:
        return None

    was_squeeze = widths[prev] <= squeeze_level
    macd_h = hist[-1] if hist else 0.0
    break_up = was_squeeze and price > upper[i] and price > ema_t[i]
    break_down = was_squeeze and price < lower[i] and price < ema_t[i]

    if break_up and adx_now >= 16:
        return _make_signal(
            direction="long",
            price=price,
            atr_now=atr_now,
            cfg=cfg,
            reason=f"LONG: BB squeeze breakout. ADX={adx_now:.0f}.",
            signal_type="squeeze",
            strength=min(65 + int(adx_now / 3), 100),
            rsi_val=rsi_now,
            ema_fast=ema_f[i],
            ema_slow=ema_s[i],
            macd_hist=macd_h,
        )
    if break_down and adx_now >= 16:
        return _make_signal(
            direction="short",
            price=price,
            atr_now=atr_now,
            cfg=cfg,
            reason=f"SHORT: BB squeeze breakout. ADX={adx_now:.0f}.",
            signal_type="squeeze",
            strength=min(65 + int(adx_now / 3), 100),
            rsi_val=rsi_now,
            ema_fast=ema_f[i],
            ema_slow=ema_s[i],
            macd_hist=macd_h,
        )
    return None


def analyze_swing_breakout(
    candles: list[Candle],
    cfg: StrategyConfig,
    *,
    htf_candles: list[Candle] | None = None,
) -> TradeSignal | None:
    """Price breaks recent swing high/low with trend alignment."""
    if len(candles) < cfg.ema_trend + 10:
        return None
    data = _base_series(candles, cfg)
    if not data:
        return None
    closes, highs, lows, volumes, ema_f, ema_s, ema_t, rsi_vals, atr_vals, adx_vals, hist, vol_avg = data

    lookback = 12
    i = len(closes) - 1
    if i < lookback + 1:
        return None

    swing_high = max(highs[i - lookback : i])
    swing_low = min(lows[i - lookback : i])
    price = closes[i]
    atr_now = atr_vals[-1]
    adx_now = adx_vals[-1]
    rsi_now = rsi_vals[i]
    if atr_now <= 0 or adx_now < 18:
        return None

    vol_ok = not vol_avg or volumes[i] >= vol_avg[-1] * 0.85
    macd_h = hist[-1] if hist else 0.0

    if price > swing_high and price > ema_t[i] and ema_f[i] > ema_s[i] and vol_ok:
        return _make_signal(
            direction="long",
            price=price,
            atr_now=atr_now,
            cfg=cfg,
            reason=f"LONG: Swing breakout. ADX={adx_now:.0f}.",
            signal_type="breakout",
            strength=min(60 + int(adx_now / 2), 100),
            rsi_val=rsi_now,
            ema_fast=ema_f[i],
            ema_slow=ema_s[i],
            macd_hist=macd_h,
        )
    if price < swing_low and price < ema_t[i] and ema_f[i] < ema_s[i] and vol_ok:
        return _make_signal(
            direction="short",
            price=price,
            atr_now=atr_now,
            cfg=cfg,
            reason=f"SHORT: Swing breakout. ADX={adx_now:.0f}.",
            signal_type="breakout",
            strength=min(60 + int(adx_now / 2), 100),
            rsi_val=rsi_now,
            ema_fast=ema_f[i],
            ema_slow=ema_s[i],
            macd_hist=macd_h,
        )
    return None


STRATEGY_LABELS: dict[str, str] = {
    "bb_squeeze": "BB Squeeze Breakout ⭐",
    "trend_v3": "Тренд v3 (EMA+ADX+HTF)",
    "ema_cross": "EMA Crossover",
    "mean_reversion": "Mean Reversion (BB+RSI)",
    "donchian": "Donchian Breakout",
    "macd_momentum": "MACD Momentum",
    "bb_squeeze": "BB Squeeze Breakout",
    "swing_breakout": "Swing Breakout",
}


def get_all_analyzers() -> dict[str, Analyzer]:
    from app.services.strategy import analyze_candles as bb_squeeze_main
    from app.services.strategy_trend_v3 import analyze_candles as trend_v3

    def _wrap(fn: Analyzer) -> Analyzer:
        def wrapped(candles, cfg, htf_candles=None):
            return fn(candles, cfg, htf_candles=htf_candles)

        return wrapped

    return {
        "bb_squeeze": _wrap(bb_squeeze_main),
        "trend_v3": _wrap(trend_v3),
        "ema_cross": _wrap(analyze_ema_cross),
        "mean_reversion": _wrap(analyze_mean_reversion),
        "donchian": _wrap(analyze_donchian_breakout),
        "macd_momentum": _wrap(analyze_macd_momentum),
        "swing_breakout": _wrap(analyze_swing_breakout),
    }
