"""Perpetual futures funding rate data."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import aiohttp

logger = logging.getLogger(__name__)


async def _fetch_binance(session: aiohttp.ClientSession, symbol: str) -> dict | None:
    async with session.get(
        "https://fapi.binance.com/fapi/v1/premiumIndex",
        params={"symbol": symbol},
        timeout=aiohttp.ClientTimeout(total=10),
    ) as resp:
        resp.raise_for_status()
        data = await resp.json()
    rate = float(data["lastFundingRate"])
    next_ms = int(data.get("nextFundingTime", 0))
    return {
        "rate": rate,
        "rate_pct": rate * 100,
        "next_funding": datetime.fromtimestamp(next_ms / 1000, tz=UTC) if next_ms else None,
        "source": "Binance",
    }


async def _fetch_bybit(session: aiohttp.ClientSession, symbol: str) -> dict | None:
    async with session.get(
        "https://api.bybit.com/v5/market/tickers",
        params={"category": "linear", "symbol": symbol},
        timeout=aiohttp.ClientTimeout(total=10),
    ) as resp:
        resp.raise_for_status()
        data = await resp.json()
    row = data.get("result", {}).get("list", [{}])[0]
    rate = float(row.get("fundingRate", 0))
    return {
        "rate": rate,
        "rate_pct": rate * 100,
        "next_funding": None,
        "source": "Bybit",
    }


async def _fetch_okx(session: aiohttp.ClientSession, symbol: str) -> dict | None:
    inst = symbol.replace("USDT", "-USDT-SWAP")
    async with session.get(
        "https://www.okx.com/api/v5/public/funding-rate",
        params={"instId": inst},
        timeout=aiohttp.ClientTimeout(total=10),
    ) as resp:
        resp.raise_for_status()
        data = await resp.json()
    row = data.get("data", [{}])[0]
    rate = float(row.get("fundingRate", 0))
    next_ms = int(row.get("nextFundingTime", 0) or 0)
    return {
        "rate": rate,
        "rate_pct": rate * 100,
        "next_funding": datetime.fromtimestamp(next_ms / 1000, tz=UTC) if next_ms else None,
        "source": "OKX",
    }


async def fetch_funding_rate(symbol: str) -> dict | None:
    fetchers = (_fetch_bybit, _fetch_okx, _fetch_binance)
    async with aiohttp.ClientSession() as session:
        for fetcher in fetchers:
            try:
                result = await fetcher(session, symbol)
                if result is not None:
                    result["bias"] = _funding_bias(result["rate_pct"])
                    return result
            except Exception:
                logger.warning("Funding fetch failed via %s", fetcher.__name__, exc_info=True)
    return None


def _funding_bias(rate_pct: float) -> str:
    if rate_pct >= 0.05:
        return "🔥 Перегрев лонгов"
    if rate_pct >= 0.01:
        return "📈 Лонги платят шортам"
    if rate_pct <= -0.05:
        return "🔥 Перегрев шортов"
    if rate_pct <= -0.01:
        return "📉 Шорты платят лонгам"
    return "⚖️ Нейтрально"


def is_extreme_funding(rate_pct: float, threshold_pct: float) -> bool:
    return abs(rate_pct) >= threshold_pct
