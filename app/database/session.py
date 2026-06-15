from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.database.base import Base

SIGNAL_MIGRATIONS = (
    ("signal_type", "VARCHAR(32) DEFAULT 'crossover'"),
    ("strength", "INTEGER DEFAULT 0"),
    ("macd_hist", "FLOAT"),
)

USER_MIGRATIONS = (
    ("notify_liq_longs", "BOOLEAN DEFAULT 0"),
    ("notify_liq_shorts", "BOOLEAN DEFAULT 0"),
    ("notify_funding", "BOOLEAN DEFAULT 0"),
)

STRATEGY_MIGRATIONS = (
    ("min_liquidation_usd", "FLOAT DEFAULT 50000"),
    ("liquidations_enabled", "BOOLEAN DEFAULT 1"),
    ("funding_alerts_enabled", "BOOLEAN DEFAULT 1"),
    ("min_funding_rate_pct", "FLOAT DEFAULT 0.05"),
)


def create_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(database_url, echo=False)


def create_session_pool(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


def _migrate_table(sync_conn, table: str, migrations: tuple[tuple[str, str], ...]) -> None:
    rows = sync_conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    existing = {row[1] for row in rows}
    for column, ddl in migrations:
        if column not in existing:
            sync_conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))


async def init_database(engine: AsyncEngine) -> None:
    from app.database.repositories import get_strategy_settings

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with engine.begin() as conn:
        def migrate(sync_conn) -> None:
            _migrate_table(sync_conn, "signals", SIGNAL_MIGRATIONS)
            _migrate_table(sync_conn, "users", USER_MIGRATIONS)
            _migrate_table(sync_conn, "strategy_settings", STRATEGY_MIGRATIONS)

        await conn.run_sync(migrate)

    pool = create_session_pool(engine)
    async with pool() as session:
        await get_strategy_settings(session)
