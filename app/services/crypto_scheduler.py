"""Background polling for pending Crypto Pay invoices."""

from __future__ import annotations

import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.crypto_payments import process_paid_crypto_invoice

logger = logging.getLogger(__name__)


def setup_crypto_scheduler(
    session_pool: async_sessionmaker[AsyncSession],
    bot: Bot,
) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()

    async def check_pending_invoices() -> None:
        from app.database.repositories import list_pending_crypto_invoices

        async with session_pool() as session:
            pending = await list_pending_crypto_invoices(session, limit=50)
            for invoice in pending:
                try:
                    await process_paid_crypto_invoice(session, bot, invoice, notify_user=True)
                except Exception:
                    logger.exception("Failed to check crypto invoice %s", invoice.crypto_invoice_id)

    scheduler.add_job(check_pending_invoices, "interval", seconds=30, id="crypto_invoice_poll")
    return scheduler
