"""Crypto Pay API client (https://help.crypt.bot/crypto-pay-api)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)

MAINNET_URL = "https://pay.crypt.bot/api/"
TESTNET_URL = "https://testnet-pay.crypt.bot/api/"


@dataclass
class CryptoInvoice:
    invoice_id: int
    pay_url: str
    status: str
    amount: str
    asset: str
    payload: str | None = None


class CryptoPayError(Exception):
    pass


class CryptoPayClient:
    def __init__(self, api_token: str, *, testnet: bool = False) -> None:
        if not api_token:
            raise CryptoPayError("Crypto Pay API token is not configured")
        self._token = api_token
        self._base = TESTNET_URL if testnet else MAINNET_URL

    async def _request(self, method: str, **params: Any) -> Any:
        url = f"{self._base}{method}"
        headers = {"Crypto-Pay-API-Token": self._token}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                data = await resp.json(content_type=None)
        if not data.get("ok"):
            raise CryptoPayError(data.get("error", "Crypto Pay API error"))
        return data.get("result")

    async def get_me(self) -> dict:
        return await self._request("getMe")

    async def create_invoice(
        self,
        *,
        asset: str,
        amount: str,
        description: str,
        payload: str,
        expires_in: int = 3600,
    ) -> CryptoInvoice:
        result = await self._request(
            "createInvoice",
            asset=asset,
            amount=amount,
            description=description,
            payload=payload,
            expires_in=expires_in,
            allow_comments=False,
            allow_anonymous=True,
        )
        item = result if isinstance(result, dict) else result[0]
        return CryptoInvoice(
            invoice_id=int(item["invoice_id"]),
            pay_url=str(item["pay_url"] or item.get("bot_invoice_url", "")),
            status=str(item.get("status", "active")),
            amount=str(item.get("amount", amount)),
            asset=str(item.get("asset", asset)),
            payload=item.get("payload"),
        )

    async def get_invoice(self, invoice_id: int) -> CryptoInvoice | None:
        result = await self._request("getInvoices", invoice_ids=str(invoice_id))
        items = result.get("items") if isinstance(result, dict) else result
        if not items:
            return None
        item = items[0]
        return CryptoInvoice(
            invoice_id=int(item["invoice_id"]),
            pay_url=str(item.get("pay_url") or item.get("bot_invoice_url") or ""),
            status=str(item.get("status", "")),
            amount=str(item.get("amount", "")),
            asset=str(item.get("asset", "")),
            payload=item.get("payload"),
        )
