from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.database.base import Base

SIGNAL_MIGRATIONS = (
    ("signal_type", "VARCHAR(32) DEFAULT 'crossover'"),
    ("strength", "INTEGER DEFAULT 0"),
    ("macd_hist", "FLOAT"),
    ("leverage", "INTEGER DEFAULT 20"),
    ("initial_stop_loss", "FLOAT"),
    ("partial_tp_hit", "BOOLEAN DEFAULT 0"),
    ("partial_pnl_percent", "FLOAT"),
)

USER_MIGRATIONS = (
    ("notify_liq_longs", "BOOLEAN DEFAULT 0"),
    ("notify_liq_shorts", "BOOLEAN DEFAULT 0"),
    ("notify_funding", "BOOLEAN DEFAULT 0"),
    ("subscription_until", "DATETIME"),
    ("referrer_id", "INTEGER"),
    ("referral_code", "VARCHAR(16)"),
)

STRATEGY_MIGRATIONS = (
    ("min_liquidation_usd", "FLOAT DEFAULT 50000"),
    ("liquidations_enabled", "BOOLEAN DEFAULT 1"),
    ("funding_alerts_enabled", "BOOLEAN DEFAULT 1"),
    ("min_funding_rate_pct", "FLOAT DEFAULT 0.05"),
    ("min_hours_between_signals", "FLOAT DEFAULT 12"),
    ("max_signals_per_day", "INTEGER DEFAULT 2"),
    ("leverage", "INTEGER DEFAULT 20"),
    ("htf_strict", "BOOLEAN DEFAULT 1"),
    ("min_adx", "FLOAT DEFAULT 18"),
    ("trend_separation_pct", "FLOAT DEFAULT 0.002"),
    ("pullback_atr_mult", "FLOAT DEFAULT 0.55"),
    ("partial_tp_enabled", "BOOLEAN DEFAULT 0"),
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
    from app.database.billing_repositories import get_billing_settings
    from app.database.repositories import get_strategy_settings

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with engine.begin() as conn:
        def migrate(sync_conn) -> None:
            strategy_before = {row[1] for row in sync_conn.execute(text("PRAGMA table_info(strategy_settings)")).fetchall()}
            signals_before = {row[1] for row in sync_conn.execute(text("PRAGMA table_info(signals)")).fetchall()}
            _migrate_table(sync_conn, "signals", SIGNAL_MIGRATIONS)
            _migrate_table(sync_conn, "users", USER_MIGRATIONS)
            _migrate_table(sync_conn, "strategy_settings", STRATEGY_MIGRATIONS)
            if "leverage" not in strategy_before:
                sync_conn.execute(text(
                    "UPDATE strategy_settings SET "
                    "leverage = 20, "
                    "min_hours_between_signals = 12, "
                    "max_signals_per_day = 2 "
                    "WHERE id = 1"
                ))
            sync_conn.execute(text(
                "UPDATE strategy_settings SET "
                "max_signals_per_day = 2, "
                "min_hours_between_signals = 12 "
                "WHERE id = 1 "
                "AND max_signals_per_day = 1 "
                "AND min_hours_between_signals = 24"
            ))
            sync_conn.execute(text(
                "UPDATE strategy_settings SET "
                "timeframe = '1h', "
                "higher_tf = '4h', "
                "atr_sl_mult = 1.8, "
                "atr_tp_mult = 5.0, "
                "use_volume_filter = 1, "
                "htf_strict = 1, "
                "min_adx = 18, "
                "trend_separation_pct = 0.002, "
                "pullback_atr_mult = 0.55, "
                "min_signal_strength = 62, "
                "max_signals_per_day = 1, "
                "min_hours_between_signals = 24, "
                "partial_tp_enabled = 0, "
                "rsi_long_max = 68, "
                "rsi_short_min = 32 "
                "WHERE id = 1"
            ))
            signals_before = {row[1] for row in sync_conn.execute(text("PRAGMA table_info(signals)")).fetchall()}
            if "leverage" not in signals_before:
                sync_conn.execute(text(
                    "UPDATE signals SET leverage = 20 WHERE leverage IS NULL OR leverage = 0"
                ))
                sync_conn.execute(text(
                    "UPDATE signals SET pnl_percent = pnl_percent * 20 "
                    "WHERE pnl_percent IS NOT NULL AND ABS(pnl_percent) < 15"
                ))
            sync_conn.execute(text(
                "UPDATE signals SET initial_stop_loss = stop_loss "
                "WHERE initial_stop_loss IS NULL"
            ))
            sync_conn.execute(text(
                "UPDATE users SET referral_code = lower(hex(randomblob(4))) "
                "WHERE referral_code IS NULL OR referral_code = ''"
            ))

        await conn.run_sync(migrate)

    pool = create_session_pool(engine)
    async with pool() as session:
        await get_strategy_settings(session)
        await get_billing_settings(session)
