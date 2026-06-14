from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.config import Settings
from app.database.base import Base
from app.database.repositories import upsert_admins


async def init_database(
    engine: AsyncEngine,
    session_pool: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_ensure_application_columns)

    async with session_pool() as session:
        await upsert_admins(session, settings.parsed_admin_ids)


def _ensure_application_columns(connection: Connection) -> None:
    columns = {column["name"] for column in inspect(connection).get_columns("applications")}
    if "decision_reason" not in columns:
        connection.execute(text("ALTER TABLE applications ADD COLUMN decision_reason VARCHAR(512)"))
    if "decided_at" not in columns:
        if connection.dialect.name == "sqlite":
            connection.execute(text("ALTER TABLE applications ADD COLUMN decided_at DATETIME"))
        else:
            connection.execute(text("ALTER TABLE applications ADD COLUMN decided_at TIMESTAMP WITH TIME ZONE"))
