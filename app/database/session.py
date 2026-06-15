from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.database.base import Base

SIGNAL_MIGRATIONS = (
    ("signal_type", "VARCHAR(32) DEFAULT 'crossover'"),
    ("strength", "INTEGER DEFAULT 0"),
    ("macd_hist", "FLOAT"),
)


def create_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(database_url, echo=False)


def create_session_pool(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def init_database(engine: AsyncEngine) -> None:
    from app.database.repositories import get_strategy_settings

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with engine.begin() as conn:
        def migrate(sync_conn) -> None:
            rows = sync_conn.execute(text("PRAGMA table_info(signals)")).fetchall()
            existing = {row[1] for row in rows}
            for column, ddl in SIGNAL_MIGRATIONS:
                if column not in existing:
                    sync_conn.execute(text(f"ALTER TABLE signals ADD COLUMN {column} {ddl}"))

        await conn.run_sync(migrate)

    pool = create_session_pool(engine)
    async with pool() as session:
        await get_strategy_settings(session)
