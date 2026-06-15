import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.config import get_settings
from app.handlers.admin import router as admin_router
from app.handlers.user import router as user_router
from app.logging_config import setup_logging
from app.middlewares.db import DbSessionMiddleware
from app.database.session import create_engine, create_session_pool, init_database
from app.services.trade_tracker import setup_scheduler

logger = logging.getLogger(__name__)


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)

    engine = create_engine(settings.database_url)
    session_pool = create_session_pool(engine)
    await init_database(engine)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher()
    dispatcher["settings"] = settings

    dispatcher.update.middleware(DbSessionMiddleware(session_pool))
    dispatcher.include_router(admin_router)
    dispatcher.include_router(user_router)

    scheduler = setup_scheduler(session_pool, bot, settings)
    scheduler.start()

    logger.info("Starting BTC trading bot (symbol=%s, tf=%s)", settings.symbol, settings.timeframe)
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dispatcher.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
