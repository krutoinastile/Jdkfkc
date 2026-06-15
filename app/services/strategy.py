"""
BTC strategy v3 — trend-following with strict filters:
- Higher timeframe trend required (no neutral entries when htf_strict)
- ADX trend strength filter (skip sideways)
- EMA pullback + trend continuation entries
- Crossover only on strong ADX
- MACD + volume confirmation
- Signal strength score (0-100)
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.indicators import adx, atr, ema, macd, rsi, sma
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
    if price > ema_trend[-1] * 1.001 and hist[-1] > 0:
        return "bull"
    if price < ema_trend[-1] * 0.999 and hist[-1] < 0:
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


def _trend_separation_ok(price: float, ema_trend: float, direction: str, cfg: StrategyConfig) -> bool:
    sep = cfg.trend_separation_pct
    if direction == "long":
        return price > ema_trend * (1 + sep)
    return price < ema_trend * (1 - sep)


def _htf_allows(direction: str, htf: str | None, cfg: StrategyConfig) -> bool:
    if not cfg.use_higher_tf or htf is None:
        return True
    if cfg.htf_strict:
        return htf == ("bull" if direction == "long" else "bear")
    if direction == "long" and htf == "bear":
        return False
    if direction == "short" and htf == "bull":
        return False
    return True


def _near_slow_ema(price: float, ema_slow: float, atr_now: float, cfg: StrategyConfig) -> bool:
    return abs(price - ema_slow) <= atr_now * cfg.pullback_atr_mult


def _touched_slow_ema_recently(
    closes: list[float],
    ema_slow: list[float],
    atr_vals: list[float],
    cfg: StrategyConfig,
    *,
    lookback: int = 3,
) -> bool:
    for offset in range(1, lookback + 1):
        idx = len(closes) - 1 - offset
        if idx < 0:
            break
        atr_v = atr_vals[idx] if idx < len(atr_vals) else atr_vals[-1]
        if abs(closes[idx] - ema_slow[idx]) <= atr_v * cfg.pullback_atr_mult:
            return True
    return False


def _score(
    *,
    direction: str,
    rsi_val: float,
    cfg: StrategyConfig,
    htf: str | None,
    vol_ok: bool,
    adx_val: float,
    signal_type: str,
) -> int:
    score = 42
    if signal_type == "pullback":
        score += 22
    elif signal_type == "continuation":
        score += 16
    else:
        score += 8
    if htf == ("bull" if direction == "long" else "bear"):
        score += 22
    if adx_val >= 30:
        score += 14
    elif adx_val >= cfg.min_adx + 5:
        score += 10
    elif adx_val >= cfg.min_adx:
        score += 5
    if vol_ok:
        score += 8
    if direction == "long":
        if cfg.rsi_long_min < rsi_val < cfg.rsi_long_max:
            score += 6
    elif cfg.rsi_short_min < rsi_val < cfg.rsi_short_max:
        score += 6
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
    adx_vals = adx(highs, lows, closes, 14)
    _, _, hist = macd(closes)

    if not all([ema_f, ema_s, ema_t, rsi_vals, atr_vals, adx_vals]):
        return None

    i = len(closes) - 1
    prev = i - 1
    price = closes[i]
    atr_now = atr_vals[-1]
    adx_now = adx_vals[-1]
    if atr_now <= 0 or adx_now < cfg.min_adx:
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

    near_ema = _near_slow_ema(price, e_s, atr_now, cfg)
    touched_recent = _touched_slow_ema_recently(closes, ema_s, atr_vals, cfg)

    bullish_pullback = (
        price > e_t
        and near_ema
        and closes[prev] < closes[i]
        and rsi_now > rsi_vals[prev]
        and e_f > e_s
    )
    bearish_pullback = (
        price < e_t
        and near_ema
        and closes[prev] > closes[i]
        and rsi_now < rsi_vals[prev]
        and e_f < e_s
    )

    bullish_continuation = (
        price > e_t
        and e_f > e_s > e_t
        and touched_recent
        and closes[i] > closes[prev]
        and rsi_now >= cfg.rsi_long_min
    )
    bearish_continuation = (
        price < e_t
        and e_f < e_s < e_t
        and touched_recent
        and closes[i] < closes[prev]
        and rsi_now <= cfg.rsi_short_max
    )

    cross_min_adx = max(cfg.min_adx + 6, 26)
    candidates: list[tuple[str, str]] = []

    if (
        bullish_pullback
        and cfg.rsi_long_min < rsi_now < cfg.rsi_long_max
        and _trend_separation_ok(price, e_t, "long", cfg)
    ):
        candidates.append(("long", "pullback"))
    if (
        bearish_pullback
        and cfg.rsi_short_min < rsi_now < cfg.rsi_short_max
        and _trend_separation_ok(price, e_t, "short", cfg)
    ):
        candidates.append(("short", "pullback"))
    if (
        bullish_continuation
        and cfg.rsi_long_min < rsi_now < cfg.rsi_long_max + 5
        and _trend_separation_ok(price, e_t, "long", cfg)
    ):
        candidates.append(("long", "continuation"))
    if (
        bearish_continuation
        and cfg.rsi_short_min - 5 < rsi_now < cfg.rsi_short_max
        and _trend_separation_ok(price, e_t, "short", cfg)
    ):
        candidates.append(("short", "continuation"))

    if adx_now >= cross_min_adx:
        if price > e_t and bullish_cross and cfg.rsi_long_min < rsi_now < cfg.rsi_long_max:
            if _trend_separation_ok(price, e_t, "long", cfg):
                candidates.append(("long", "crossover"))
        if price < e_t and bearish_cross and cfg.rsi_short_min < rsi_now < cfg.rsi_short_max:
            if _trend_separation_ok(price, e_t, "short", cfg):
                candidates.append(("short", "crossover"))

    min_strength = cfg.min_signal_strength
    best: TradeSignal | None = None
    for direction, sig_type in candidates:
        if not _htf_allows(direction, htf, cfg):
            continue
        if not _macd_ok(closes, direction, cfg):
            continue
        if not vol_ok and sig_type != "pullback":
            continue

        required_strength = min_strength + (6 if sig_type == "crossover" else 0)
        strength = _score(
            direction=direction,
            rsi_val=rsi_now,
            cfg=cfg,
            htf=htf,
            vol_ok=vol_ok,
            adx_val=adx_now,
            signal_type=sig_type,
        )
        if strength < required_strength:
            continue

        type_labels = {
            "crossover": "пересечение EMA",
            "pullback": "откат к EMA",
            "continuation": "продолжение тренда",
        }
        type_label = type_labels.get(sig_type, sig_type)

        if direction == "long":
            sl = price - cfg.atr_sl_mult * atr_now
            tp = price + cfg.atr_tp_mult * atr_now
            reason = (
                f"LONG: {type_label}. Тренд ADX={adx_now:.0f}. "
                f"RSI={rsi_now:.1f}, MACD={macd_h:.1f}. Сила {strength}/100."
            )
        else:
            sl = price + cfg.atr_sl_mult * atr_now
            tp = price - cfg.atr_tp_mult * atr_now
            reason = (
                f"SHORT: {type_label}. Тренд ADX={adx_now:.0f}. "
                f"RSI={rsi_now:.1f}, MACD={macd_h:.1f}. Сила {strength}/100."
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
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    ema_f = ema(closes, cfg.ema_fast)
    ema_s = ema(closes, cfg.ema_slow)
    ema_t = ema(closes, cfg.ema_trend)
    rsi_vals = rsi(closes, cfg.rsi_period)
    adx_vals = adx(highs, lows, closes, 14)
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

    adx_state = "—"
    if adx_vals:
        adx_v = adx_vals[-1]
        if adx_v >= 30:
            adx_state = f"сильный 💪 {adx_v:.0f}"
        elif adx_v >= cfg.min_adx:
            adx_state = f"умеренный {adx_v:.0f}"
        else:
            adx_state = f"слабый {adx_v:.0f}"

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
    }
