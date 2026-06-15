"""Technical indicators — pure Python, no numpy dependency."""

from __future__ import annotations


def ema(values: list[float], period: int) -> list[float]:
    if len(values) < period:
        return []
    k = 2 / (period + 1)
    result: list[float] = []
    sma = sum(values[:period]) / period
    result.extend([0.0] * (period - 1))
    result.append(sma)
    prev = sma
    for price in values[period:]:
        val = price * k + prev * (1 - k)
        result.append(val)
        prev = val
    return result


def rsi(values: list[float], period: int = 14) -> list[float]:
    if len(values) < period + 1:
        return []
    result: list[float] = [0.0] * period
    gains: list[float] = []
    losses: list[float] = []
    for i in range(1, len(values)):
        diff = values[i] - values[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period):
        if i == period - 1:
            rs = avg_gain / avg_loss if avg_loss > 0 else 100
            result.append(100 - 100 / (1 + rs))
        else:
            result.append(0.0)

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        rs = avg_gain / avg_loss if avg_loss > 0 else 100
        result.append(100 - 100 / (1 + rs))
    return result


def atr(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> list[float]:
    if len(closes) < period + 1:
        return []
    trs: list[float] = []
    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        trs.append(tr)

    result: list[float] = [0.0] * period
    val = sum(trs[:period]) / period
    result.append(val)
    for i in range(period, len(trs)):
        val = (val * (period - 1) + trs[i]) / period
        result.append(val)
    return result
