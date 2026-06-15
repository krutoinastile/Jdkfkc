"""Fetch OHLCV candles from public exchange APIs with fallbacks."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class Candle:
    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float


INTERVAL_MAP = {
    "1h": {"binance": "1h", "bybit": "60", "okx": "1H"},
    "4h": {"binance": "4h", "bybit": "240", "okx": "4H"},
    "1d": {"binance": "1d", "bybit": "D", "okx": "1D"},
}


async def _get_json(session: aiohttp.ClientSession, url: str, params: dict) -> object:
    async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
        resp.raise_for_status()
        return await resp.json(content_type=None)


async def _fetch_binance(session: aiohttp.ClientSession, symbol: str, interval: str, limit: int) -> list[Candle]:
    iv = INTERVAL_MAP.get(interval, INTERVAL_MAP["1h"])["binance"]
    raw = await _get_json(
        session,
        "https://api.binance.com/api/v3/klines",
        {"symbol": symbol, "interval": iv, "limit": limit},
    )
    return [
        Candle(int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5]))
        for r in raw
    ]


async def _fetch_bybit(session: aiohttp.ClientSession, symbol: str, interval: str, limit: int) -> list[Candle]:
    iv = INTERVAL_MAP.get(interval, INTERVAL_MAP["1h"])["bybit"]
    data = await _get_json(
        session,
        "https://api.bybit.com/v5/market/kline",
        {"category": "spot", "symbol": symbol, "interval": iv, "limit": limit},
    )
    rows = data.get("result", {}).get("list", [])
    rows.reverse()
    return [
        Candle(int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5]))
        for r in rows
    ]


async def _fetch_okx(session: aiohttp.ClientSession, symbol: str, interval: str, limit: int) -> list[Candle]:
    iv = INTERVAL_MAP.get(interval, INTERVAL_MAP["1h"])["okx"]
    inst = symbol.replace("USDT", "-USDT")
    raw = await _get_json(
        session,
        "https://www.okx.com/api/v5/market/candles",
        {"instId": inst, "bar": iv, "limit": str(limit)},
    )
    rows = raw.get("data", [])
    rows.reverse()
    return [
        Candle(int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5]))
        for r in rows
    ]


async def fetch_candles(symbol: str, interval: str, limit: int = 200) -> list[Candle]:
    if limit <= 300:
        return await _fetch_candles_single(symbol, interval, limit)
    return await fetch_candles_history(symbol, interval, limit)


async def _fetch_candles_single(symbol: str, interval: str, limit: int) -> list[Candle]:
    fetchers = (_fetch_bybit, _fetch_okx, _fetch_binance)
    cap = min(limit, 1000)
    async with aiohttp.ClientSession() as session:
        for fetcher in fetchers:
            try:
                candles = await fetcher(session, symbol, interval, cap)
                if len(candles) >= min(60, limit):
                    logger.debug("Candles from %s: %d rows", fetcher.__name__, len(candles))
                    return candles
            except Exception:
                logger.warning("Failed to fetch candles via %s", fetcher.__name__, exc_info=True)
    raise RuntimeError("All market data sources failed")


async def fetch_candles_history(symbol: str, interval: str, limit: int) -> list[Candle]:
    """Fetch extended history via OKX pagination (fallback to single batch)."""
    iv = INTERVAL_MAP.get(interval, INTERVAL_MAP["1h"])["okx"]
    inst = symbol.replace("USDT", "-USDT")
    batch_size = 300
    all_candles: list[Candle] = []
    after: str | None = None

    try:
        async with aiohttp.ClientSession() as session:
            while len(all_candles) < limit:
                params: dict[str, str] = {"instId": inst, "bar": iv, "limit": str(batch_size)}
                if after:
                    params["after"] = after
                async with session.get(
                    "https://www.okx.com/api/v5/market/candles",
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=20),
                ) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
                rows = data.get("data", [])
                if not rows:
                    break
                rows.reverse()
                batch = [
                    Candle(int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5]))
                    for r in rows
                ]
                all_candles = batch + all_candles
                after = str(batch[0].open_time)
                if len(rows) < batch_size:
                    break
        if len(all_candles) >= 60:
            logger.debug("Extended candles from OKX: %d rows", len(all_candles))
            return all_candles[-limit:]
    except Exception:
        logger.warning("Extended candle fetch failed, falling back to single batch", exc_info=True)

    return await _fetch_candles_single(symbol, interval, min(limit, 1000))


async def fetch_current_price(symbol: str) -> float:
    async with aiohttp.ClientSession() as session:
        for url, params in (
            ("https://api.bybit.com/v5/market/tickers", {"category": "spot", "symbol": symbol}),
            ("https://www.okx.com/api/v5/market/ticker", {"instId": symbol.replace("USDT", "-USDT")}),
            ("https://api.binance.com/api/v3/ticker/price", {"symbol": symbol}),
        ):
            try:
                data = await _get_json(session, url, params)
                if "result" in data:
                    return float(data["result"]["list"][0]["lastPrice"])
                if "data" in data:
                    return float(data["data"][0]["last"])
                return float(data["price"])
            except Exception:
                logger.warning("Price fetch failed for %s", url, exc_info=True)
    raise RuntimeError("All price sources failed")
