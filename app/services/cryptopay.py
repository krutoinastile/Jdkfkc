"""Crypto Pay API client (https://help.crypt.bot/crypto-pay-api)."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)

MAINNET_URL = "https://pay.crypt.bot/api"
TESTNET_URL = "https://testnet-pay.crypt.bot/api"


class CryptoPayError(Exception):
    def __init__(self, message: str, *, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code


class CryptoPayClient:
    def __init__(self, api_token: str, *, testnet: bool = False) -> None:
        self.api_token = api_token
        self.base_url = TESTNET_URL if testnet else MAINNET_URL

    async def _request(self, method: str, **params: Any) -> dict[str, Any]:
        url = f"{self.base_url}/{method}"
        headers = {"Crypto-Pay-API-Token": self.api_token}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                data = await response.json(content_type=None)

        if not data.get("ok"):
            error = data.get("error", {})
            raise CryptoPayError(
                str(error.get("name", "CryptoPay API error")),
                code=error.get("code"),
            )
        return data["result"]

    async def create_invoice(
        self,
        *,
        asset: str,
        amount: str,
        description: str,
        payload: str,
        expires_in: int = 3600,
    ) -> dict[str, Any]:
        params = {
            "asset": asset,
            "amount": amount,
            "description": description[:1024],
            "payload": payload[:4096],
            "expires_in": expires_in,
        }
        return await self._request("createInvoice", **params)

    async def get_invoice(self, invoice_id: int) -> dict[str, Any] | None:
        result = await self._request("getInvoices", invoice_ids=str(invoice_id))
        if isinstance(result, dict):
            items = result.get("items", [])
        elif isinstance(result, list):
            items = result
        else:
            items = []
        return items[0] if items else None

    async def get_me(self) -> dict[str, Any]:
        return await self._request("getMe")
