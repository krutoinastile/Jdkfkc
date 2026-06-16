"""BingX exchange API — market orders with SL/TP."""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from typing import Any
from urllib.parse import urlencode

import aiohttp

from app.config import Settings
from app.database.models import Signal

logger = logging.getLogger(__name__)

MAINNET = "https://open-api.bingx.com"
TESTNET = "https://open-api-vst.bingx.com"
MAINNET_TRADE_URL = "https://bingx.com/en/perpetual"
TESTNET_TRADE_URL = "https://bingx.com/en-us/futures/forward"


class BingXError(Exception):
    pass


def bingx_symbol(symbol: str) -> str:
    """BTCUSDT → BTC-USDT."""
    if "-" in symbol:
        return symbol
    if symbol.endswith("USDT"):
        return f"{symbol[:-4]}-USDT"
    return symbol


def bingx_trade_url(symbol: str, *, testnet: bool = False) -> str:
    pair = bingx_symbol(symbol)
    base = TESTNET_TRADE_URL if testnet else MAINNET_TRADE_URL
    return f"{base}/{pair}"


def bingx_configured(settings: Settings) -> bool:
    return bool(settings.bingx_api_key and settings.bingx_api_secret)


def _round_qty(quantity: float) -> float:
    return round(quantity, 5)


class BingXClient:
    """BingX REST client for swap market orders + conditional SL/TP."""

    def __init__(self, settings: Settings) -> None:
        if not settings.bingx_api_key or not settings.bingx_api_secret:
            raise BingXError("BingX API keys not configured")
        self._key = settings.bingx_api_key
        self._secret = settings.bingx_api_secret
        self._base = TESTNET if settings.bingx_testnet else MAINNET
        self._order_usdt = settings.bingx_order_usdt

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
        position_side: str,
    ) -> Any:
        return await self._request(
            "POST",
            "/openApi/swap/v2/trade/order",
            {
                "symbol": bingx_symbol(symbol),
                "side": side,
                "positionSide": position_side,
                "type": "MARKET",
                "quantity": _round_qty(quantity),
            },
        )

    async def place_stop_loss(
        self,
        *,
        symbol: str,
        side: str,
        quantity: float,
        position_side: str,
        stop_price: float,
    ) -> Any:
        return await self._request(
            "POST",
            "/openApi/swap/v2/trade/order",
            {
                "symbol": bingx_symbol(symbol),
                "side": side,
                "positionSide": position_side,
                "type": "STOP_MARKET",
                "stopPrice": stop_price,
                "quantity": _round_qty(quantity),
            },
        )

    async def place_take_profit(
        self,
        *,
        symbol: str,
        side: str,
        quantity: float,
        position_side: str,
        stop_price: float,
    ) -> Any:
        return await self._request(
            "POST",
            "/openApi/swap/v2/trade/order",
            {
                "symbol": bingx_symbol(symbol),
                "side": side,
                "positionSide": position_side,
                "type": "TAKE_PROFIT_MARKET",
                "stopPrice": stop_price,
                "quantity": _round_qty(quantity),
            },
        )

    async def execute_signal(self, signal: Signal) -> dict[str, Any]:
        """Market entry + separate SL/TP orders for an open signal."""
        is_long = signal.direction == "long"
        position_side = "LONG" if is_long else "SHORT"
        entry_side = "BUY" if is_long else "SELL"
        exit_side = "SELL" if is_long else "BUY"
        qty = _round_qty(self._order_usdt / signal.entry_price)
        if qty <= 0:
            raise BingXError("Quantity too small for order size")

        entry = await self.place_market_order(
            symbol=signal.symbol,
            side=entry_side,
            quantity=qty,
            position_side=position_side,
        )
        sl = await self.place_stop_loss(
            symbol=signal.symbol,
            side=exit_side,
            quantity=qty,
            position_side=position_side,
            stop_price=signal.stop_loss,
        )
        tp = await self.place_take_profit(
            symbol=signal.symbol,
            side=exit_side,
            quantity=qty,
            position_side=position_side,
            stop_price=signal.take_profit,
        )
        return {"entry": entry, "sl": sl, "tp": tp, "quantity": qty}
