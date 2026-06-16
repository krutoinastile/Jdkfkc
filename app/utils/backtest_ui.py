"""Backtest helpers."""

from __future__ import annotations

BACKTEST_PERIODS: dict[int, str] = {
    30: "30 дней",
    90: "90 дней",
}

BACKTEST_DAYS = 30

BACKTEST_MAX_TRADES: dict[int, str] = {
    1: "1 в день",
    2: "2 в день",
    3: "3 в день",
    5: "5 в день",
    10: "10 в день",
}

BARS_PER_DAY = {"15m": 96, "1h": 24, "4h": 6, "1d": 1}
WARMUP_BARS = 90
MAX_CANDLES = 9000


def period_label(days: int = BACKTEST_DAYS) -> str:
    return BACKTEST_PERIODS.get(days, f"{days} дн.")


def trades_per_day_label(max_per_day: int) -> str:
    return BACKTEST_MAX_TRADES.get(max_per_day, f"{max_per_day} в день")


def min_hours_for_max_trades(max_per_day: int) -> float:
    if max_per_day <= 0:
        return 0.0
    return 24.0 / max_per_day


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
