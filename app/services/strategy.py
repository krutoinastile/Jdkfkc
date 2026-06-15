"""
BTC trading strategy: Trend + EMA crossover + RSI filter.

Logic:
- Trend: EMA21 vs EMA55 defines direction
- Trigger: EMA9 crosses EMA21 in trend direction
- Filter: RSI confirms momentum (not overbought for longs, not oversold for shorts)
- Risk: ATR-based stop-loss (1.5x) and take-profit (2.5x ATR, ~1.67 R:R)
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.indicators import atr, ema, rsi
from app.services.market_data import Candle


@dataclass
class TradeSignal:
    direction: str  # long | short
    entry_price: float
    stop_loss: float
    take_profit: float
    rsi: float
    ema_fast: float
    ema_slow: float
    atr_value: float
    reason: str


EMA_FAST = 9
EMA_SLOW = 21
EMA_TREND = 55
RSI_PERIOD = 14
ATR_PERIOD = 14
ATR_SL_MULT = 1.5
ATR_TP_MULT = 2.5


def analyze_candles(candles: list[Candle]) -> TradeSignal | None:
    if len(candles) < 80:
        return None

    closes = [c.close for c in candles]
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]

    ema9 = ema(closes, EMA_FAST)
    ema21 = ema(closes, EMA_SLOW)
    ema55 = ema(closes, EMA_TREND)
    rsi_vals = rsi(closes, RSI_PERIOD)
    atr_vals = atr(highs, lows, closes, ATR_PERIOD)

    if not ema9 or not ema21 or not ema55 or not rsi_vals or not atr_vals:
        return None

    i = len(closes) - 1
    if i < 2:
        return None

    price = closes[i]
    prev_i = i - 1

    e9, e9p = ema9[i], ema9[prev_i]
    e21, e21p = ema21[i], ema21[prev_i]
    e55 = ema55[i]
    rsi_now = rsi_vals[i]
    rsi_prev = rsi_vals[prev_i]
    atr_now = atr_vals[-1]

    if atr_now <= 0 or e55 <= 0:
        return None

    bullish_cross = e9p <= e21p and e9 > e21
    bearish_cross = e9p >= e21p and e9 < e21

    # LONG: uptrend + bullish crossover + RSI not overbought
    if price > e55 and bullish_cross and 35 < rsi_now < 68:
        sl = price - ATR_SL_MULT * atr_now
        tp = price + ATR_TP_MULT * atr_now
        return TradeSignal(
            direction="long",
            entry_price=price,
            stop_loss=round(sl, 2),
            take_profit=round(tp, 2),
            rsi=round(rsi_now, 1),
            ema_fast=round(e9, 2),
            ema_slow=round(e21, 2),
            atr_value=round(atr_now, 2),
            reason=(
                f"Восходящий тренд (цена > EMA{EMA_TREND}). "
                f"EMA{EMA_FAST} пересекла EMA{EMA_SLOW} снизу вверх. RSI={rsi_now:.1f}."
            ),
        )

    # SHORT: downtrend + bearish crossover + RSI not oversold
    if price < e55 and bearish_cross and 32 < rsi_now < 65:
        sl = price + ATR_SL_MULT * atr_now
        tp = price - ATR_TP_MULT * atr_now
        return TradeSignal(
            direction="short",
            entry_price=price,
            stop_loss=round(sl, 2),
            take_profit=round(tp, 2),
            rsi=round(rsi_now, 1),
            ema_fast=round(e9, 2),
            ema_slow=round(e21, 2),
            atr_value=round(atr_now, 2),
            reason=(
                f"Нисходящий тренд (цена < EMA{EMA_TREND}). "
                f"EMA{EMA_FAST} пересекла EMA{EMA_SLOW} сверху вниз. RSI={rsi_now:.1f}."
            ),
        )

    return None


def market_snapshot(candles: list[Candle]) -> dict[str, float | str]:
    """Current market state for display when no signal."""
    closes = [c.close for c in candles]
    ema9 = ema(closes, EMA_FAST)
    ema21 = ema(closes, EMA_SLOW)
    ema55 = ema(closes, EMA_TREND)
    rsi_vals = rsi(closes, RSI_PERIOD)

    price = closes[-1]
    trend = "боковик"
    if ema55 and price > ema55[-1] * 1.002:
        trend = "бычий 📈"
    elif ema55 and price < ema55[-1] * 0.998:
        trend = "медвежий 📉"

    return {
        "price": round(price, 2),
        "rsi": round(rsi_vals[-1], 1) if rsi_vals else 0,
        "ema9": round(ema9[-1], 2) if ema9 else 0,
        "ema21": round(ema21[-1], 2) if ema21 else 0,
        "ema55": round(ema55[-1], 2) if ema55 else 0,
        "trend": trend,
    }
