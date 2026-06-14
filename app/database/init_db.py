from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.config import Settings
from app.database.base import Base
from app.database.repositories import get_payment_settings, upsert_admins

PAYMENT_SETTINGS_MIGRATIONS = (
    ("crypto_pay_api_token", "TEXT"),
    ("crypto_asset", "VARCHAR(16) DEFAULT 'USDT'"),
    ("crypto_amount", "VARCHAR(32) DEFAULT '5.00'"),
    ("crypto_testnet", "BOOLEAN DEFAULT 0"),
)


async def _migrate_schema(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        def migrate(sync_conn) -> None:
            rows = sync_conn.execute(text("PRAGMA table_info(payment_settings)")).fetchall()
            existing = {row[1] for row in rows}
            for column, ddl in PAYMENT_SETTINGS_MIGRATIONS:
                if column not in existing:
                    sync_conn.execute(text(f"ALTER TABLE payment_settings ADD COLUMN {column} {ddl}"))

        await conn.run_sync(migrate)


async def init_database(
    engine: AsyncEngine,
    session_pool: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await _migrate_schema(engine)

    async with session_pool() as session:
        await upsert_admins(session, settings.parsed_admin_ids)
        await get_payment_settings(session)
