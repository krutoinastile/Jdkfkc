"""Entry filters shared by live strategy analyzers (MACD, volume, HTF)."""

from __future__ import annotations

from app.services.indicators import ema, macd, sma
from app.services.market_data import Candle
from app.services.strategy import TradeSignal
from app.services.strategy_config import StrategyConfig


def htf_trend(candles: list[Candle], cfg: StrategyConfig) -> str | None:
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


def volume_ok(candles: list[Candle], cfg: StrategyConfig) -> bool:
    if not cfg.use_volume_filter:
        return True
    volumes = [c.volume for c in candles]
    avg_vol = sma(volumes, 20)
    if not avg_vol:
        return True
    return volumes[-1] >= avg_vol[-1] * 0.85


def macd_ok(closes: list[float], direction: str, cfg: StrategyConfig) -> bool:
    if not cfg.use_macd_filter:
        return True
    _, _, hist = macd(closes)
    if not hist:
        return True
    h = hist[-1]
    return h > 0 if direction == "long" else h < 0


def htf_allows(direction: str, htf: str | None, cfg: StrategyConfig) -> bool:
    if not cfg.use_higher_tf or htf is None:
        return True
    if cfg.htf_strict:
        return htf == ("bull" if direction == "long" else "bear")
    if direction == "long" and htf == "bear":
        return False
    if direction == "short" and htf == "bull":
        return False
    return True


def passes_entry_filters(
    signal: TradeSignal,
    candles: list[Candle],
    cfg: StrategyConfig,
    htf_candles: list[Candle] | None,
) -> bool:
    closes = [c.close for c in candles]
    if not macd_ok(closes, signal.direction, cfg):
        return False
    if not volume_ok(candles, cfg):
        return False
    htf = htf_trend(htf_candles, cfg) if cfg.use_higher_tf and htf_candles else None
    return htf_allows(signal.direction, htf, cfg)
