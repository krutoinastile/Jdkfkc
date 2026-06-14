import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import get_settings
from app.database.init_db import init_database
from app.database.session import create_engine, create_session_pool
from app.handlers.admin import router as admin_router
from app.handlers.business import router as business_router
from app.handlers.payments import router as payments_router
from app.handlers.user import router as user_router
from app.logging_config import setup_logging
from app.middlewares.db import DbSessionMiddleware
from app.middlewares.throttling import ThrottlingMiddleware

logger = logging.getLogger(__name__)

BUSINESS_UPDATE_TYPES = [
    "message",
    "callback_query",
    "pre_checkout_query",
    "business_connection",
    "business_message",
    "edited_business_message",
    "deleted_business_messages",
]


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)

    engine = create_engine(settings.database_url)
    session_pool = create_session_pool(engine)
    await init_database(engine, session_pool, settings)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher["settings"] = settings

    dispatcher.update.middleware(ThrottlingMiddleware(settings.rate_limit_seconds))
    dispatcher.update.middleware(DbSessionMiddleware(session_pool))
    dispatcher.include_router(business_router)
    dispatcher.include_router(payments_router)
    dispatcher.include_router(admin_router)
    dispatcher.include_router(user_router)

    logger.info("Starting business chat monitor bot")
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dispatcher.start_polling(
            bot,
            allowed_updates=BUSINESS_UPDATE_TYPES,
        )
    finally:
        await bot.session.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
