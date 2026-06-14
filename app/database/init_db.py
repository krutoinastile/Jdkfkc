from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.config import Settings
from app.database.base import Base
from app.database.repositories import get_payment_settings, upsert_admins


async def init_database(
    engine: AsyncEngine,
    session_pool: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_pool() as session:
        await upsert_admins(session, settings.parsed_admin_ids)
        await get_payment_settings(session)
