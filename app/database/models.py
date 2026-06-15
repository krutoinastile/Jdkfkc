from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, Boolean, DateTime, Float, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class TradeDirection(StrEnum):
    LONG = "long"
    SHORT = "short"


class TradeStatus(StrEnum):
    OPEN = "open"
    WIN = "win"
    LOSS = "loss"
    EXPIRED = "expired"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(255))
    notify_signals: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_liq_longs: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notify_liq_shorts: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notify_funding: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    stop_loss: Mapped[float] = mapped_column(Float, nullable=False)
    take_profit: Mapped[float] = mapped_column(Float, nullable=False)
    rsi: Mapped[float] = mapped_column(Float, nullable=False)
    ema_fast: Mapped[float] = mapped_column(Float, nullable=False)
    ema_slow: Mapped[float] = mapped_column(Float, nullable=False)
    atr: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    signal_type: Mapped[str] = mapped_column(String(32), default="crossover", nullable=False)
    strength: Mapped[int] = mapped_column(default=0, nullable=False)
    macd_hist: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(16), default=TradeStatus.OPEN.value, index=True)
    exit_price: Mapped[float | None] = mapped_column(Float)
    pnl_percent: Mapped[float | None] = mapped_column(Float)
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class StrategySettings(Base):
    """Singleton strategy configuration (row id=1), editable from admin panel."""

    __tablename__ = "strategy_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    timeframe: Mapped[str] = mapped_column(String(8), default="1h", nullable=False)
    higher_tf: Mapped[str] = mapped_column(String(8), default="4h", nullable=False)
    ema_fast: Mapped[int] = mapped_column(default=9, nullable=False)
    ema_slow: Mapped[int] = mapped_column(default=21, nullable=False)
    ema_trend: Mapped[int] = mapped_column(default=55, nullable=False)
    rsi_period: Mapped[int] = mapped_column(default=14, nullable=False)
    rsi_long_min: Mapped[float] = mapped_column(Float, default=40.0, nullable=False)
    rsi_long_max: Mapped[float] = mapped_column(Float, default=65.0, nullable=False)
    rsi_short_min: Mapped[float] = mapped_column(Float, default=35.0, nullable=False)
    rsi_short_max: Mapped[float] = mapped_column(Float, default=60.0, nullable=False)
    atr_sl_mult: Mapped[float] = mapped_column(Float, default=1.5, nullable=False)
    atr_tp_mult: Mapped[float] = mapped_column(Float, default=3.0, nullable=False)
    use_macd_filter: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    use_volume_filter: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    use_higher_tf: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    scanning_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    min_signal_strength: Mapped[int] = mapped_column(default=60, nullable=False)
    min_liquidation_usd: Mapped[float] = mapped_column(Float, default=50_000.0, nullable=False)
    liquidations_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    funding_alerts_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    min_funding_rate_pct: Mapped[float] = mapped_column(Float, default=0.05, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
