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


def adx(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> list[float]:
    """Average Directional Index — trend strength (0-100)."""
    if len(closes) < period * 2:
        return []
    plus_dm: list[float] = []
    minus_dm: list[float] = []
    trs: list[float] = []
    for i in range(1, len(closes)):
        up = highs[i] - highs[i - 1]
        down = lows[i - 1] - lows[i]
        plus_dm.append(up if up > down and up > 0 else 0.0)
        minus_dm.append(down if down > up and down > 0 else 0.0)
        trs.append(
            max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
        )

    def _smooth(values: list[float]) -> list[float]:
        if len(values) < period:
            return []
        smoothed = [sum(values[:period]) / period]
        for val in values[period:]:
            smoothed.append((smoothed[-1] * (period - 1) + val) / period)
        return smoothed

    tr_s = _smooth(trs)
    pdm_s = _smooth(plus_dm)
    mdm_s = _smooth(minus_dm)
    if not tr_s or not pdm_s or not mdm_s:
        return []

    dx_vals: list[float] = []
    for tr_v, p_v, m_v in zip(tr_s, pdm_s, mdm_s):
        if tr_v <= 0:
            dx_vals.append(0.0)
            continue
        pdi = 100 * p_v / tr_v
        mdi = 100 * m_v / tr_v
        denom = pdi + mdi
        dx_vals.append(abs(pdi - mdi) / denom * 100 if denom else 0.0)

    if len(dx_vals) < period:
        return []
    adx_vals = [sum(dx_vals[:period]) / period]
    for dx in dx_vals[period:]:
        adx_vals.append((adx_vals[-1] * (period - 1) + dx) / period)

    pad = len(closes) - len(adx_vals)
    return [0.0] * pad + adx_vals
