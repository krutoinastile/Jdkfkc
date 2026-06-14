import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.repositories import count_pending_applications

logger = logging.getLogger(__name__)


async def log_pending_applications_count(
    session_pool: async_sessionmaker[AsyncSession],
) -> None:
    async with session_pool() as session:
        pending_count = await count_pending_applications(session)
    logger.info("Pending applications: %s", pending_count)


def setup_scheduler(session_pool: async_sessionmaker[AsyncSession]) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        log_pending_applications_count,
        trigger="interval",
        minutes=30,
        args=[session_pool],
        id="pending_applications_count",
        replace_existing=True,
        max_instances=1,
    )
    return scheduler
