"""Technical indicators — pure Python, no numpy dependency."""

from __future__ import annotations


def sma(values: list[float], period: int) -> list[float]:
    if len(values) < period:
        return []
    result: list[float] = [0.0] * (period - 1)
    for i in range(period - 1, len(values)):
        result.append(sum(values[i - period + 1 : i + 1]) / period)
    return result


def macd(
    values: list[float],
    fast: int = 12,
    slow: int = 26,
    signal_period: int = 9,
) -> tuple[list[float], list[float], list[float]]:
    ema_fast = ema(values, fast)
    ema_slow = ema(values, slow)
    if not ema_fast or not ema_slow:
        return [], [], []

    macd_line: list[float] = []
    for i in range(len(values)):
        if ema_fast[i] == 0 or ema_slow[i] == 0:
            macd_line.append(0.0)
        else:
            macd_line.append(ema_fast[i] - ema_slow[i])

    signal_line = ema([v for v in macd_line if v != 0], signal_period)
    if not signal_line:
        return macd_line, [], []

    padded_signal = [0.0] * (len(macd_line) - len(signal_line)) + signal_line
    histogram = [m - s for m, s in zip(macd_line, padded_signal)]
    return macd_line, padded_signal, histogram


def ema(values: list[float], period: int) -> list[float]:
    if len(values) < period:
        return []
    k = 2 / (period + 1)
    result: list[float] = []
    seed = sum(values[:period]) / period
    result.extend([0.0] * (period - 1))
    result.append(seed)
    prev = seed
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
