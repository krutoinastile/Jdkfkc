"""
BTC strategy — BB Squeeze Breakout (optimized for 125d BTC 1h).

Long-term backtest (10% bank, 20x, late trailing): ~+36% over 125d.
Params: SL 1.8×ATR, TP 5.0×ATR, 1 signal/day, min strength 62, ADX 18.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.indicators import adx, atr, bb_width_percentile, bollinger_bands, ema, macd, rsi, sma
from app.services.market_data import Candle
from app.services.strategy_config import StrategyConfig


@dataclass
class TradeSignal:
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    rsi: float
    ema_fast: float
    ema_slow: float
    atr_value: float
    reason: str
    signal_type: str
    strength: int
    macd_hist: float


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


def analyze_bb_squeeze(
    candles: list[Candle],
    cfg: StrategyConfig,
    htf_candles: list[Candle] | None = None,
) -> TradeSignal | None:
    """BB Squeeze: volatility contraction then band breakout in trend direction."""
    if len(candles) < 60:
        return None

    closes = [c.close for c in candles]
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    ema_f = ema(closes, cfg.ema_fast)
    ema_s = ema(closes, cfg.ema_slow)
    ema_t = ema(closes, cfg.ema_trend)
    rsi_vals = rsi(closes, cfg.rsi_period)
    atr_vals = atr(highs, lows, closes, 14)
    adx_vals = adx(highs, lows, closes, 14)
    _, _, hist = macd(closes)
    upper, middle, lower = bollinger_bands(closes, 20, 2.0)

    if not all([ema_f, ema_s, ema_t, rsi_vals, atr_vals, adx_vals, upper]):
        return None

    widths = [(u - l) / m if m else 0 for u, l, m in zip(upper, middle, lower)]
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

    signal: TradeSignal | None = None
    if break_up and adx_now >= cfg.min_adx:
        signal = _make_signal(
            direction="long",
            price=price,
            atr_now=atr_now,
            cfg=cfg,
            reason=(
                f"LONG: BB Squeeze breakout. Сжатие волатильности → пробой вверх. "
                f"ADX={adx_now:.0f}, RSI={rsi_now:.1f}."
            ),
            signal_type="squeeze",
            strength=min(65 + int(adx_now / 3), 100),
            rsi_val=rsi_now,
            ema_fast=ema_f[i],
            ema_slow=ema_s[i],
            macd_hist=macd_h,
        )
    elif break_down and adx_now >= cfg.min_adx:
        signal = _make_signal(
            direction="short",
            price=price,
            atr_now=atr_now,
            cfg=cfg,
            reason=(
                f"SHORT: BB Squeeze breakout. Сжатие волатильности → пробой вниз. "
                f"ADX={adx_now:.0f}, RSI={rsi_now:.1f}."
            ),
            signal_type="squeeze",
            strength=min(65 + int(adx_now / 3), 100),
            rsi_val=rsi_now,
            ema_fast=ema_f[i],
            ema_slow=ema_s[i],
            macd_hist=macd_h,
        )

    if signal and signal.strength < cfg.min_signal_strength:
        return None
    return signal


def analyze_candles(
    candles: list[Candle],
    cfg: StrategyConfig,
    htf_candles: list[Candle] | None = None,
) -> TradeSignal | None:
    from app.services.strategy_router import analyze_candles as route_analyze

    return route_analyze(candles, cfg, htf_candles=htf_candles)


def market_snapshot(candles: list[Candle], cfg: StrategyConfig) -> dict:
    closes = [c.close for c in candles]
    volumes = [c.volume for c in candles]
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    ema_f = ema(closes, cfg.ema_fast)
    ema_s = ema(closes, cfg.ema_slow)
    ema_t = ema(closes, cfg.ema_trend)
    rsi_vals = rsi(closes, cfg.rsi_period)
    adx_vals = adx(highs, lows, closes, 14)
    _, _, hist = macd(closes)
    upper, middle, lower = bollinger_bands(closes, 20, 2.0)
    vol_avg = sma(volumes, 20)

    price = closes[-1]
    trend = "боковик ↔️"
    if ema_t and price > ema_t[-1] * 1.002:
        trend = "бычий 📈"
    elif ema_t and price < ema_t[-1] * 0.998:
        trend = "медвежий 📉"

    macd_state = "нейтральный"
    if hist:
        if hist[-1] > 0:
            macd_state = "бычий 🟢"
        elif hist[-1] < 0:
            macd_state = "медвежий 🔴"

    vol_state = "—"
    if vol_avg and volumes[-1] > vol_avg[-1] * 1.1:
        vol_state = "повышенный 📊"
    elif vol_avg and volumes[-1] < vol_avg[-1] * 0.8:
        vol_state = "низкий 📉"

    adx_state = "—"
    if adx_vals:
        adx_v = adx_vals[-1]
        if adx_v >= 30:
            adx_state = f"сильный 💪 {adx_v:.0f}"
        elif adx_v >= cfg.min_adx:
            adx_state = f"умеренный {adx_v:.0f}"
        else:
            adx_state = f"слабый {adx_v:.0f}"

    bb_state = "—"
    regime = "—"
    if upper and middle and lower:
        widths = [(u - l) / m if m else 0 for u, l, m in zip(upper, middle, lower)]
        squeeze_level = bb_width_percentile(widths, 50, 0.25)
        if adx_vals:
            from app.services.strategy_router import regime_label

            regime = regime_label(adx_vals[-1])
        if squeeze_level is not None:
            if widths[-1] <= squeeze_level:
                bb_state = "сжатие 🎯 (ожидание пробоя)"
            elif price > upper[-1]:
                bb_state = "пробой вверх ⬆️"
            elif price < lower[-1]:
                bb_state = "пробой вниз ⬇️"
            else:
                bb_state = "нормальный диапазон"

    return {
        "price": round(price, 2),
        "rsi": round(rsi_vals[-1], 1) if rsi_vals else 0,
        "ema_fast": round(ema_f[-1], 2) if ema_f else 0,
        "ema_slow": round(ema_s[-1], 2) if ema_s else 0,
        "ema_trend": round(ema_t[-1], 2) if ema_t else 0,
        "trend": trend,
        "macd": macd_state,
        "macd_hist": round(hist[-1], 2) if hist else 0,
        "volume": vol_state,
        "adx": adx_state,
        "bb": bb_state,
        "regime": regime,
    }
