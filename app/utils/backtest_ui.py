"""Backtest period helpers."""

from __future__ import annotations

BACKTEST_PERIODS: dict[int, str] = {
    30: "30 дней",
    90: "90 дней",
    180: "6 месяцев",
    365: "1 год",
}

BARS_PER_DAY = {"1h": 24, "4h": 6, "1d": 1}
WARMUP_BARS = 90
MAX_CANDLES = 9000


def period_label(days: int) -> str:
    return BACKTEST_PERIODS.get(days, f"{days} дн.")


def candles_for_period(days: int, timeframe: str) -> int:
    bars_day = BARS_PER_DAY.get(timeframe, 24)
    needed = days * bars_day + WARMUP_BARS
    return min(needed, MAX_CANDLES)


def htf_candles_for_period(days: int, higher_tf: str) -> int:
    return min(candles_for_period(days, higher_tf), MAX_CANDLES)


def period_days_from_candles(candle_count: int, timeframe: str) -> float:
    bars_day = BARS_PER_DAY.get(timeframe, 24)
    effective = max(candle_count - WARMUP_BARS, 0)
    return round(effective / bars_day, 1)
