"""BingX exchange API scaffold (optional auto-trading)."""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from typing import Any
from urllib.parse import urlencode

import aiohttp

from app.config import Settings

logger = logging.getLogger(__name__)

MAINNET = "https://open-api.bingx.com"
TESTNET = "https://open-api-vst.bingx.com"


class BingXError(Exception):
    pass


class BingXClient:
    """Minimal BingX REST client for future order execution."""

    def __init__(self, settings: Settings) -> None:
        if not settings.bingx_api_key or not settings.bingx_api_secret:
            raise BingXError("BingX API keys not configured")
        self._key = settings.bingx_api_key
        self._secret = settings.bingx_api_secret
        self._base = TESTNET if settings.bingx_testnet else MAINNET

    def _sign(self, params: dict[str, Any]) -> str:
        query = urlencode(sorted(params.items()))
        return hmac.new(self._secret.encode(), query.encode(), hashlib.sha256).hexdigest()

    async def _request(self, method: str, path: str, params: dict[str, Any] | None = None) -> Any:
        params = dict(params or {})
        params["timestamp"] = int(time.time() * 1000)
        params["signature"] = self._sign(params)
        headers = {"X-BX-APIKEY": self._key}
        url = f"{self._base}{path}"
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method, url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=20)
            ) as resp:
                data = await resp.json(content_type=None)
        if data.get("code") not in (0, "0", None):
            raise BingXError(str(data.get("msg", data)))
        return data.get("data", data)

    async def get_balance(self) -> Any:
        return await self._request("GET", "/openApi/swap/v2/user/balance")

    async def place_market_order(
        self,
        *,
        symbol: str,
        side: str,
        quantity: float,
        position_side: str = "LONG",
    ) -> Any:
        """Place market order (scaffold — enable after testing on testnet)."""
        return await self._request(
            "POST",
            "/openApi/swap/v2/trade/order",
            {
                "symbol": symbol,
                "side": side,
                "positionSide": position_side,
                "type": "MARKET",
                "quantity": quantity,
            },
        )


def bingx_configured(settings: Settings) -> bool:
    return bool(settings.bingx_api_key and settings.bingx_api_secret)
