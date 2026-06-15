"""
Improved BTC strategy v2:
- Higher timeframe (4H) trend confirmation
- EMA crossover + pullback entries
- MACD momentum filter
- Volume above average filter
- Signal strength score (0-100)
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.indicators import atr, ema, macd, rsi, sma
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


def _htf_trend(candles: list[Candle], cfg: StrategyConfig) -> str | None:
    if len(candles) < cfg.ema_trend + 10:
        return None
    closes = [c.close for c in candles]
    ema_trend = ema(closes, cfg.ema_trend)
    _, _, hist = macd(closes)
    if not ema_trend or not hist:
        return None
    price = closes[-1]
    if price > ema_trend[-1] and hist[-1] > 0:
        return "bull"
    if price < ema_trend[-1] and hist[-1] < 0:
        return "bear"
    return "neutral"


def _volume_ok(candles: list[Candle], cfg: StrategyConfig) -> bool:
    if not cfg.use_volume_filter:
        return True
    volumes = [c.volume for c in candles]
    avg_vol = sma(volumes, 20)
    if not avg_vol:
        return True
    return volumes[-1] >= avg_vol[-1] * 0.85


def _macd_ok(closes: list[float], direction: str, cfg: StrategyConfig) -> bool:
    if not cfg.use_macd_filter:
        return True
    _, _, hist = macd(closes)
    if not hist:
        return True
    h = hist[-1]
    return h > 0 if direction == "long" else h < 0


def _score(
    *,
    direction: str,
    rsi_val: float,
    cfg: StrategyConfig,
    htf: str | None,
    vol_ok: bool,
    macd_ok: bool,
    signal_type: str,
) -> int:
    score = 50
    if signal_type == "crossover":
        score += 15
    else:
        score += 10
    if htf == ("bull" if direction == "long" else "bear"):
        score += 20
    elif htf == "neutral":
        score += 5
    if vol_ok:
        score += 10
    if macd_ok:
        score += 10
    if direction == "long":
        if cfg.rsi_long_min < rsi_val < cfg.rsi_long_max:
            score += 5
    elif cfg.rsi_short_min < rsi_val < cfg.rsi_short_max:
        score += 5
    return min(score, 100)


def analyze_candles(
    candles: list[Candle],
    cfg: StrategyConfig,
    *,
    htf_candles: list[Candle] | None = None,
) -> TradeSignal | None:
    if len(candles) < cfg.ema_trend + 30:
        return None

    closes = [c.close for c in candles]
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]

    ema_f = ema(closes, cfg.ema_fast)
    ema_s = ema(closes, cfg.ema_slow)
    ema_t = ema(closes, cfg.ema_trend)
    rsi_vals = rsi(closes, cfg.rsi_period)
    atr_vals = atr(highs, lows, closes, 14)
    _, _, hist = macd(closes)

    if not all([ema_f, ema_s, ema_t, rsi_vals, atr_vals]):
        return None

    i = len(closes) - 1
    prev = i - 1
    price = closes[i]
    atr_now = atr_vals[-1]
    if atr_now <= 0:
        return None

    htf = _htf_trend(htf_candles, cfg) if cfg.use_higher_tf and htf_candles else None
    vol_ok = _volume_ok(candles, cfg)

    e_f, e_fp = ema_f[i], ema_f[prev]
    e_s, e_sp = ema_s[i], ema_s[prev]
    e_t = ema_t[i]
    rsi_now = rsi_vals[i]
    macd_h = hist[-1] if hist else 0.0

    bullish_cross = e_fp <= e_sp and e_f > e_s
    bearish_cross = e_fp >= e_sp and e_f < e_s

    # Pullback: price near EMA slow in trend, bouncing
    near_ema = abs(price - e_s) <= atr_now * 0.5
    bullish_pullback = price > e_t and near_ema and closes[prev] < closes[i] and rsi_now > rsi_vals[prev]
    bearish_pullback = price < e_t and near_ema and closes[prev] > closes[i] and rsi_now < rsi_vals[prev]

    candidates: list[tuple[str, str]] = []
    if price > e_t and bullish_cross and cfg.rsi_long_min < rsi_now < cfg.rsi_long_max:
        candidates.append(("long", "crossover"))
    if price < e_t and bearish_cross and cfg.rsi_short_min < rsi_now < cfg.rsi_short_max:
        candidates.append(("short", "crossover"))
    if price > e_t and bullish_pullback and cfg.rsi_long_min < rsi_now < cfg.rsi_long_max:
        candidates.append(("long", "pullback"))
    if price < e_t and bearish_pullback and cfg.rsi_short_min < rsi_now < cfg.rsi_short_max:
        candidates.append(("short", "pullback"))

    best: TradeSignal | None = None
    for direction, sig_type in candidates:
        if cfg.use_higher_tf and htf:
            if direction == "long" and htf == "bear":
                continue
            if direction == "short" and htf == "bull":
                continue
        if not _macd_ok(closes, direction, cfg):
            continue
        if not vol_ok:
            continue

        strength = _score(
            direction=direction,
            rsi_val=rsi_now,
            cfg=cfg,
            htf=htf,
            vol_ok=vol_ok,
            macd_ok=True,
            signal_type=sig_type,
        )
        if strength < cfg.min_signal_strength:
            continue

        if direction == "long":
            sl = price - cfg.atr_sl_mult * atr_now
            tp = price + cfg.atr_tp_mult * atr_now
            type_label = "пересечение EMA" if sig_type == "crossover" else "откат к EMA"
            reason = (
                f"LONG: {type_label}. Тренд вверх (EMA{cfg.ema_trend}). "
                f"RSI={rsi_now:.1f}, MACD hist={macd_h:.1f}. "
                f"Сила сигнала: {strength}/100."
            )
        else:
            sl = price + cfg.atr_sl_mult * atr_now
            tp = price - cfg.atr_tp_mult * atr_now
            type_label = "пересечение EMA" if sig_type == "crossover" else "откат к EMA"
            reason = (
                f"SHORT: {type_label}. Тренд вниз (EMA{cfg.ema_trend}). "
                f"RSI={rsi_now:.1f}, MACD hist={macd_h:.1f}. "
                f"Сила сигнала: {strength}/100."
            )

        signal = TradeSignal(
            direction=direction,
            entry_price=round(price, 2),
            stop_loss=round(sl, 2),
            take_profit=round(tp, 2),
            rsi=round(rsi_now, 1),
            ema_fast=round(e_f, 2),
            ema_slow=round(e_s, 2),
            atr_value=round(atr_now, 2),
            reason=reason,
            signal_type=sig_type,
            strength=strength,
            macd_hist=round(macd_h, 2),
        )
        if best is None or signal.strength > best.strength:
            best = signal

    return best


def market_snapshot(candles: list[Candle], cfg: StrategyConfig) -> dict:
    closes = [c.close for c in candles]
    volumes = [c.volume for c in candles]
    ema_f = ema(closes, cfg.ema_fast)
    ema_s = ema(closes, cfg.ema_slow)
    ema_t = ema(closes, cfg.ema_trend)
    rsi_vals = rsi(closes, cfg.rsi_period)
    _, _, hist = macd(closes)
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
    }
