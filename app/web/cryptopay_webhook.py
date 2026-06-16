"""Crypto Pay webhook server for instant payment activation."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import UTC, datetime

from aiohttp import web
from aiogram import Bot
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.config import Settings
from app.database.billing_repositories import get_billing_settings
from app.services.subscription import process_paid_invoice

logger = logging.getLogger(__name__)


def _verify_signature(body: bytes, signature: str | None, api_token: str) -> bool:
    if not signature or not api_token:
        return False
    secret = hashlib.sha256(api_token.encode()).digest()
    expected = hmac.new(secret, body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


async def cryptopay_webhook_handler(request: web.Request) -> web.Response:
    session_pool: async_sessionmaker[AsyncSession] = request.app["session_pool"]
    bot: Bot = request.app["bot"]
    settings: Settings = request.app["settings"]

    body = await request.read()
    signature = request.headers.get("crypto-pay-api-signature")

    async with session_pool() as session:
        billing = await get_billing_settings(session)
        if not billing.cryptopay_api_token:
            return web.Response(status=503, text="billing not configured")
        if not _verify_signature(body, signature, billing.cryptopay_api_token):
            logger.warning("Crypto Pay webhook: invalid signature")
            return web.Response(status=403, text="forbidden")

    try:
        payload = json.loads(body.decode())
    except json.JSONDecodeError:
        return web.Response(status=400, text="bad json")

    update_type = payload.get("update_type")
    if update_type != "invoice_paid":
        return web.Response(text="ok")

    request_data = payload.get("payload") or {}
    invoice_id = request_data.get("invoice_id")
    if not invoice_id:
        return web.Response(text="ok")

    async with session_pool() as session:
        paid = await process_paid_invoice(session, bot, int(invoice_id))
        if paid:
            logger.info("Crypto Pay webhook: invoice %s activated", invoice_id)

    return web.Response(text="ok")


async def health_handler(request: web.Request) -> web.Response:
    settings: Settings = request.app["settings"]
    payload = {
        "status": "ok",
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "symbol": settings.symbol,
        "timeframe": settings.timeframe,
    }
    return web.json_response(payload)


async def start_webhook_server(
    *,
    settings: Settings,
    session_pool: async_sessionmaker[AsyncSession],
    bot: Bot,
) -> web.AppRunner:
    app = web.Application()
    app["session_pool"] = session_pool
    app["bot"] = bot
    app["settings"] = settings
    app.router.add_post(settings.cryptopay_webhook_path, cryptopay_webhook_handler)
    app.router.add_get("/health", health_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, settings.webhook_host, settings.webhook_port)
    await site.start()
    logger.info(
        "Crypto Pay webhook listening on %s:%s%s",
        settings.webhook_host,
        settings.webhook_port,
        settings.cryptopay_webhook_path,
    )
    return runner
