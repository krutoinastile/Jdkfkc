from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class PaymentStatus(StrEnum):
    PENDING = "pending"
    PAID = "paid"
    EXPIRED = "expired"


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
    subscription_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    referrer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    referral_code: Mapped[str | None] = mapped_column(String(16), unique=True, index=True)
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
    leverage: Mapped[int] = mapped_column(default=20, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default=TradeStatus.OPEN.value, index=True)
    exit_price: Mapped[float | None] = mapped_column(Float)
    pnl_percent: Mapped[float | None] = mapped_column(Float)
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BillingSettings(Base):
    """Singleton billing configuration (row id=1)."""

    __tablename__ = "billing_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    cryptopay_api_token: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    cryptopay_testnet: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    subscription_price: Mapped[float] = mapped_column(Float, default=15.0, nullable=False)
    subscription_asset: Mapped[str] = mapped_column(String(16), default="USDT", nullable=False)
    subscription_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    discount_percent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    discount_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    referral_bonus_days: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    referral_discount_percent: Mapped[float] = mapped_column(Float, default=10.0, nullable=False)
    require_subscription_for_signals: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class PaymentInvoice(Base):
    __tablename__ = "payment_invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    cryptopay_invoice_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    amount: Mapped[str] = mapped_column(String(32), nullable=False)
    asset: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default=PaymentStatus.PENDING.value, index=True)
    pay_url: Mapped[str] = mapped_column(String(512), nullable=False)
    payload: Mapped[str] = mapped_column(String(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Giveaway(Base):
    __tablename__ = "giveaways"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    prize_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    winners_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    extra_discount_percent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    drawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class GiveawayEntry(Base):
    __tablename__ = "giveaway_entries"
    __table_args__ = (UniqueConstraint("giveaway_id", "user_id", name="uq_giveaway_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    giveaway_id: Mapped[int] = mapped_column(ForeignKey("giveaways.id"), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


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
    atr_tp_mult: Mapped[float] = mapped_column(Float, default=4.0, nullable=False)
    use_macd_filter: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    use_volume_filter: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    use_higher_tf: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    htf_strict: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    min_adx: Mapped[float] = mapped_column(Float, default=16.0, nullable=False)
    trend_separation_pct: Mapped[float] = mapped_column(Float, default=0.002, nullable=False)
    pullback_atr_mult: Mapped[float] = mapped_column(Float, default=0.55, nullable=False)
    scanning_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    min_signal_strength: Mapped[int] = mapped_column(default=55, nullable=False)
    min_hours_between_signals: Mapped[float] = mapped_column(Float, default=12.0, nullable=False)
    max_signals_per_day: Mapped[int] = mapped_column(default=2, nullable=False)
    leverage: Mapped[int] = mapped_column(default=20, nullable=False)
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
