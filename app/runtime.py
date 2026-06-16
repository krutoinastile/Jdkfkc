"""Bot runtime — resilient polling with health checks and clean shutdown."""

from __future__ import annotations

import asyncio
import contextlib
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import ErrorEvent

from app.config import Settings
from app.database.repositories import ensure_admin_users
from app.database.session import create_engine, create_session_pool, init_database
from app.handlers.admin import router as admin_router
from app.handlers.subscription import router as subscription_router
from app.handlers.user import router as user_router
from app.middlewares.db import DbSessionMiddleware
from app.services.funding_monitor import setup_funding_scheduler
from app.services.liquidation_monitor import run_liquidation_monitor
from app.services.subscription import poll_pending_invoices
from app.services.trade_tracker import setup_scheduler

logger = logging.getLogger(__name__)


async def run_bot(settings: Settings) -> None:
    engine = create_engine(settings.database_url)
    session_pool = create_session_pool(engine)

    try:
        await init_database(engine)

        async with session_pool() as session:
            await ensure_admin_users(session, settings.parsed_admin_ids)

        bot = Bot(
            token=settings.bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        dispatcher = Dispatcher()
        dispatcher["settings"] = settings

        @dispatcher.errors()
        async def on_error(event: ErrorEvent) -> bool:
            logger.exception("Handler error: %s", event.exception)
            return True

        dispatcher.update.middleware(DbSessionMiddleware(session_pool))
        dispatcher.include_router(admin_router)
        admin_router.include_router(admin_billing_router)
        dispatcher.include_router(subscription_router)
        dispatcher.include_router(user_router)

        scheduler = setup_scheduler(session_pool, bot, settings)
        scheduler.start()

        async def invoice_poll_job() -> None:
            async with session_pool() as session:
                try:
                    await poll_pending_invoices(session, bot)
                except Exception:
                    logger.exception("Invoice poll failed")

        scheduler.add_job(invoice_poll_job, "interval", seconds=settings.invoice_poll_seconds, id="invoice_poll")

        async def health_check_job() -> None:
            try:
                me = await bot.get_me()
                logger.debug("Health OK: @%s", me.username)
            except Exception:
                logger.exception("Health check failed")

        scheduler.add_job(health_check_job, "interval", minutes=10, id="health_check")

        async def startup_scan() -> None:
            async with session_pool() as session:
                try:
                    from app.services.trade_tracker import run_market_scan

                    await run_market_scan(session, settings, bot)
                except Exception:
                    logger.exception("Startup market scan failed")

        asyncio.create_task(startup_scan())

        funding_scheduler = setup_funding_scheduler(session_pool, bot, settings)
        funding_scheduler.start()

        liq_task = asyncio.create_task(run_liquidation_monitor(bot, session_pool))

        webhook_runner = None
        if settings.webhook_port > 0:
            try:
                from app.web.cryptopay_webhook import start_webhook_server

                webhook_runner = await start_webhook_server(
                    settings=settings,
                    session_pool=session_pool,
                    bot=bot,
                )
            except Exception:
                logger.exception("Crypto Pay webhook server failed to start")

        logger.info("Bot online: symbol=%s", settings.symbol)
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            await dispatcher.start_polling(bot)
        finally:
            if webhook_runner is not None:
                await webhook_runner.cleanup()
            liq_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await liq_task
            funding_scheduler.shutdown(wait=False)
            scheduler.shutdown(wait=False)
            await bot.session.close()
    finally:
        await engine.dispose()
