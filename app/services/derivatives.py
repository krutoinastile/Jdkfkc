"""Futures derivatives data — Open Interest and Long/Short ratio."""

from __future__ import annotations

import logging

import aiohttp

logger = logging.getLogger(__name__)


def _format_oi(value: float) -> str:
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2f}B"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    return f"${value:,.0f}"


def _ls_bias(long_pct: float) -> str:
    if long_pct >= 60:
        return "🟢 Перевес лонгов"
    if long_pct <= 40:
        return "🔴 Перевес шортов"
    return "⚖️ Баланс"


async def _fetch_okx(session: aiohttp.ClientSession, symbol: str) -> dict | None:
    inst = symbol.replace("USDT", "-USDT-SWAP")
    async with session.get(
        "https://www.okx.com/api/v5/public/open-interest",
        params={"instId": inst},
        timeout=aiohttp.ClientTimeout(total=10),
    ) as resp:
        resp.raise_for_status()
        oi_data = await resp.json()

    async with session.get(
        "https://www.okx.com/api/v5/rubik/stat/contracts/long-short-account-ratio",
        params={"ccy": symbol.replace("USDT", ""), "period": "1H"},
        timeout=aiohttp.ClientTimeout(total=10),
    ) as resp:
        resp.raise_for_status()
        ls_data = await resp.json()

    oi_row = oi_data.get("data", [{}])[0]
    ls_row = ls_data.get("data", [[None, None]])[-1]
    oi_usd = float(oi_row.get("oiUsd", 0) or 0)
    ratio = float(ls_row[1]) if len(ls_row) > 1 else 1.0
    long_pct = round(ratio / (1 + ratio) * 100, 1)
    short_pct = round(100 - long_pct, 1)

    return {
        "open_interest": oi_usd,
        "open_interest_fmt": _format_oi(oi_usd),
        "long_pct": long_pct,
        "short_pct": short_pct,
        "ls_bias": _ls_bias(long_pct),
        "source": "OKX",
    }


async def _fetch_binance(session: aiohttp.ClientSession, symbol: str) -> dict | None:
    async with session.get(
        "https://fapi.binance.com/fapi/v1/openInterest",
        params={"symbol": symbol},
        timeout=aiohttp.ClientTimeout(total=10),
    ) as resp:
        resp.raise_for_status()
        oi_data = await resp.json()

    async with session.get(
        "https://fapi.binance.com/futures/data/globalLongShortAccountRatio",
        params={"symbol": symbol, "period": "1h", "limit": 1},
        timeout=aiohttp.ClientTimeout(total=10),
    ) as resp:
        resp.raise_for_status()
        ls_data = await resp.json()

    oi_btc = float(oi_data.get("openInterest", 0))
    price = float(oi_data.get("sumOpenInterestValue", 0) or 0)
    if price <= 0:
        async with session.get(
            "https://fapi.binance.com/fapi/v1/ticker/price",
            params={"symbol": symbol},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            resp.raise_for_status()
            ticker = await resp.json()
        price = oi_btc * float(ticker.get("price", 0))

    ls_row = ls_data[0] if ls_data else {}
    long_pct = round(float(ls_row.get("longAccount", 0.5)) * 100, 1)
    short_pct = round(float(ls_row.get("shortAccount", 0.5)) * 100, 1)

    return {
        "open_interest": price,
        "open_interest_fmt": _format_oi(price),
        "long_pct": long_pct,
        "short_pct": short_pct,
        "ls_bias": _ls_bias(long_pct),
        "source": "Binance",
    }


async def fetch_derivatives_stats(symbol: str) -> dict | None:
    fetchers = (_fetch_okx, _fetch_binance)
    async with aiohttp.ClientSession() as session:
        for fetcher in fetchers:
            try:
                return await fetcher(session, symbol)
            except Exception:
                logger.warning("Derivatives fetch failed via %s", fetcher.__name__, exc_info=True)
    return None
