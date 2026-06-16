from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.billing_repositories import generate_referral_code, get_user_by_referral_code
from app.database.models import Signal, StrategySettings, TradeStatus, User


async def get_or_create_user(
    session: AsyncSession,
    tg_id: int,
    username: str | None,
    *,
    referrer_code: str | None = None,
) -> User:
    result = await session.execute(select(User).where(User.tg_id == tg_id))
    user = result.scalar_one_or_none()
    if user is None:
        referrer_id = None
        if referrer_code:
            referrer = await get_user_by_referral_code(session, referrer_code)
            if referrer and referrer.tg_id != tg_id:
                referrer_id = referrer.id
        user = User(
            tg_id=tg_id,
            username=username,
            referrer_id=referrer_id,
            referral_code=generate_referral_code(),
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    else:
        updated = False
        if user.username != username:
            user.username = username
            updated = True
        if not user.referral_code:
            user.referral_code = generate_referral_code()
            updated = True
        if updated:
            await session.commit()
            await session.refresh(user)
    return user


async def list_subscribed_users(session: AsyncSession) -> list[User]:
    result = await session.execute(select(User).where(User.notify_signals.is_(True)))
    return list(result.scalars().all())


async def ensure_admin_users(session: AsyncSession, admin_ids: tuple[int, ...]) -> None:
    for tg_id in admin_ids:
        user = await get_or_create_user(session, tg_id, None)
        if not user.notify_signals:
            user.notify_signals = True
            await session.commit()
            await session.refresh(user)


async def toggle_notifications(session: AsyncSession, user: User) -> User:
    user.notify_signals = not user.notify_signals
    await session.commit()
    await session.refresh(user)
    return user


async def toggle_user_flag(session: AsyncSession, user: User, field: str) -> User:
    if not hasattr(user, field):
        raise ValueError(f"Unknown field: {field}")
    setattr(user, field, not getattr(user, field))
    await session.commit()
    await session.refresh(user)
    return user


async def list_users_notify_liq_longs(session: AsyncSession) -> list[User]:
    result = await session.execute(select(User).where(User.notify_liq_longs.is_(True)))
    return list(result.scalars().all())


async def list_users_notify_liq_shorts(session: AsyncSession) -> list[User]:
    result = await session.execute(select(User).where(User.notify_liq_shorts.is_(True)))
    return list(result.scalars().all())


async def list_users_notify_funding(session: AsyncSession) -> list[User]:
    result = await session.execute(select(User).where(User.notify_funding.is_(True)))
    return list(result.scalars().all())


async def has_open_signal(session: AsyncSession, symbol: str) -> bool:
    result = await session.execute(
        select(Signal.id)
        .where(Signal.symbol == symbol)
        .where(Signal.status == TradeStatus.OPEN.value)
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def count_signals_today(session: AsyncSession, symbol: str) -> int:
    today_start = datetime.now(tz=UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    result = await session.execute(
        select(func.count(Signal.id))
        .where(Signal.symbol == symbol)
        .where(Signal.opened_at >= today_start)
    )
    return int(result.scalar_one())


async def hours_since_last_signal(session: AsyncSession, symbol: str) -> float | None:
    result = await session.execute(
        select(Signal.opened_at)
        .where(Signal.symbol == symbol)
        .order_by(Signal.opened_at.desc())
        .limit(1)
    )
    last = result.scalar_one_or_none()
    if last is None:
        return None
    delta = datetime.now(tz=UTC) - last
    return delta.total_seconds() / 3600


async def can_open_new_signal(
    session: AsyncSession,
    symbol: str,
    *,
    min_hours: float,
    max_per_day: int,
) -> tuple[bool, str]:
    if await has_open_signal(session, symbol):
        return False, "open_trade"

    if max_per_day > 0:
        today_count = await count_signals_today(session, symbol)
        if today_count >= max_per_day:
            return False, "daily_limit"

    if min_hours > 0:
        since = await hours_since_last_signal(session, symbol)
        if since is not None and since < min_hours:
            return False, "cooldown"

    return True, "ok"


async def mark_partial_take_profit(
    session: AsyncSession,
    signal: Signal,
    partial_pnl: float,
) -> Signal:
    signal.partial_tp_hit = True
    signal.partial_pnl_percent = round(partial_pnl, 2)
    await session.commit()
    await session.refresh(signal)
    return signal


async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    return await session.get(User, user_id)


async def get_user_by_tg_id(session: AsyncSession, tg_id: int) -> User | None:
    result = await session.execute(select(User).where(User.tg_id == tg_id))
    return result.scalar_one_or_none()


async def update_signal_stop_loss(session: AsyncSession, signal: Signal, stop_loss: float) -> Signal:
    signal.stop_loss = round(stop_loss, 2)
    await session.commit()
    await session.refresh(signal)
    return signal


async def create_signal(session: AsyncSession, **fields: object) -> Signal:
    if "initial_stop_loss" not in fields and "stop_loss" in fields:
        fields["initial_stop_loss"] = fields["stop_loss"]
    signal = Signal(**fields)
    session.add(signal)
    await session.commit()
    await session.refresh(signal)
    return signal


async def list_open_signals(session: AsyncSession) -> list[Signal]:
    result = await session.execute(
        select(Signal).where(Signal.status == TradeStatus.OPEN.value).order_by(Signal.opened_at.desc())
    )
    return list(result.scalars().all())


async def list_recent_signals(session: AsyncSession, limit: int = 10) -> list[Signal]:
    result = await session.execute(
        select(Signal).order_by(Signal.opened_at.desc()).limit(limit)
    )
    return list(result.scalars().all())


async def list_history_signals(
    session: AsyncSession,
    *,
    status_filter: str = "all",
    days: int = 0,
    limit: int = 100,
) -> list[Signal]:
    query = select(Signal)
    if status_filter == "win":
        query = query.where(Signal.status == TradeStatus.WIN.value)
    elif status_filter == "loss":
        query = query.where(Signal.status == TradeStatus.LOSS.value)
    elif status_filter == "open":
        query = query.where(Signal.status == TradeStatus.OPEN.value)
    if days > 0:
        cutoff = datetime.now(tz=UTC) - timedelta(days=days)
        query = query.where(Signal.opened_at >= cutoff)
    query = query.order_by(Signal.opened_at.desc()).limit(limit)
    result = await session.execute(query)
    return list(result.scalars().all())


async def count_history_signals(
    session: AsyncSession,
    *,
    status_filter: str = "all",
    days: int = 0,
) -> int:
    query = select(func.count(Signal.id))
    if status_filter == "win":
        query = query.where(Signal.status == TradeStatus.WIN.value)
    elif status_filter == "loss":
        query = query.where(Signal.status == TradeStatus.LOSS.value)
    elif status_filter == "open":
        query = query.where(Signal.status == TradeStatus.OPEN.value)
    if days > 0:
        cutoff = datetime.now(tz=UTC) - timedelta(days=days)
        query = query.where(Signal.opened_at >= cutoff)
    result = await session.execute(query)
    return int(result.scalar_one())


async def list_closed_signals(
    session: AsyncSession,
    *,
    days: int | None = None,
    limit: int = 500,
) -> list[Signal]:
    query = (
        select(Signal)
        .where(Signal.status.in_((TradeStatus.WIN.value, TradeStatus.LOSS.value)))
        .where(Signal.pnl_percent.is_not(None))
    )
    if days and days > 0:
        cutoff = datetime.now(tz=UTC) - timedelta(days=days)
        query = query.where(func.coalesce(Signal.closed_at, Signal.opened_at) >= cutoff)
    query = query.order_by(Signal.opened_at.asc()).limit(limit)
    result = await session.execute(query)
    return list(result.scalars().all())


async def count_closed_signals(session: AsyncSession, *, days: int | None = None) -> int:
    query = (
        select(func.count(Signal.id))
        .where(Signal.status.in_((TradeStatus.WIN.value, TradeStatus.LOSS.value)))
        .where(Signal.pnl_percent.is_not(None))
    )
    if days and days > 0:
        cutoff = datetime.now(tz=UTC) - timedelta(days=days)
        query = query.where(func.coalesce(Signal.closed_at, Signal.opened_at) >= cutoff)
    result = await session.execute(query)
    return int(result.scalar_one())


async def close_signal(
    session: AsyncSession,
    signal: Signal,
    *,
    status: str,
    exit_price: float,
    pnl_percent: float,
) -> Signal:
    signal.status = status
    signal.exit_price = exit_price
    signal.pnl_percent = pnl_percent
    signal.closed_at = datetime.now(tz=UTC)
    await session.commit()
    await session.refresh(signal)
    return signal


async def get_statistics(session: AsyncSession) -> dict[str, float | int]:
    from app.utils.leverage import pnl_on_bank, DEFAULT_BANK_ALLOCATION_PCT

    total = await session.execute(select(func.count(Signal.id)))
    wins = await session.execute(
        select(func.count(Signal.id)).where(Signal.status == TradeStatus.WIN.value)
    )
    losses = await session.execute(
        select(func.count(Signal.id)).where(Signal.status == TradeStatus.LOSS.value)
    )
    expired = await session.execute(
        select(func.count(Signal.id)).where(Signal.status == TradeStatus.EXPIRED.value)
    )
    open_count = await session.execute(
        select(func.count(Signal.id)).where(Signal.status == TradeStatus.OPEN.value)
    )
    avg_pnl = await session.execute(
        select(func.avg(Signal.pnl_percent)).where(Signal.pnl_percent.is_not(None))
    )

    closed_signals = await list_closed_signals(session, limit=500)
    best_pnl = 0.0
    worst_pnl = 0.0
    total_bank_pnl = 0.0
    max_drawdown = 0.0
    equity_curve: list[float] = [1000.0]
    if closed_signals:
        bank_pnls = [pnl_on_bank(p, DEFAULT_BANK_ALLOCATION_PCT) for p in (s.pnl_percent for s in closed_signals) if p is not None]
        if bank_pnls:
            best_pnl = max(bank_pnls)
            worst_pnl = min(bank_pnls)
            total_bank_pnl = sum(bank_pnls)
            capital = 1000.0
            peak = capital
            for bp in bank_pnls:
                capital *= 1 + bp / 100
                equity_curve.append(round(capital, 2))
                peak = max(peak, capital)
                if peak > 0:
                    max_drawdown = max(max_drawdown, (peak - capital) / peak * 100)

    total_n = int(total.scalar_one())
    wins_n = int(wins.scalar_one())
    losses_n = int(losses.scalar_one())
    closed = wins_n + losses_n
    win_rate = (wins_n / closed * 100) if closed > 0 else 0.0

    return {
        "total": total_n,
        "wins": wins_n,
        "losses": losses_n,
        "expired": int(expired.scalar_one()),
        "open": int(open_count.scalar_one()),
        "win_rate": round(win_rate, 1),
        "avg_pnl": round(float(avg_pnl.scalar_one() or 0), 2),
        "best_pnl": round(best_pnl, 2),
        "worst_pnl": round(worst_pnl, 2),
        "total_bank_pnl": round(total_bank_pnl, 2),
        "max_drawdown": round(max_drawdown, 2),
        "equity_curve": equity_curve if len(equity_curve) > 1 else [],
    }


async def expire_old_signals(
    session: AsyncSession,
    max_age_hours: int = 72,
    *,
    current_price: float | None = None,
) -> int:
    cutoff = datetime.now(tz=UTC) - timedelta(hours=max_age_hours)
    result = await session.execute(
        select(Signal)
        .where(Signal.status == TradeStatus.OPEN.value)
        .where(Signal.opened_at < cutoff)
    )
    signals = list(result.scalars().all())
    for signal in signals:
        if current_price is not None:
            await force_close_signal(session, signal, current_price)
        else:
            await close_signal(
                session,
                signal,
                status=TradeStatus.EXPIRED.value,
                exit_price=signal.entry_price,
                pnl_percent=0.0,
            )
    return len(signals)


async def is_admin(tg_id: int, env_admin_ids: tuple[int, ...]) -> bool:
    return tg_id in env_admin_ids


async def count_users(session: AsyncSession) -> int:
    result = await session.execute(select(func.count(User.id)))
    return int(result.scalar_one())


async def list_users(session: AsyncSession, limit: int = 20, offset: int = 0) -> list[User]:
    result = await session.execute(
        select(User).order_by(User.created_at.desc()).offset(offset).limit(limit)
    )
    return list(result.scalars().all())


async def get_strategy_settings(session: AsyncSession) -> StrategySettings:
    result = await session.execute(select(StrategySettings).where(StrategySettings.id == 1))
    row = result.scalar_one_or_none()
    if row is None:
        row = StrategySettings(id=1)
        session.add(row)
        await session.commit()
        await session.refresh(row)
    return row


async def update_strategy_settings(session: AsyncSession, **fields: object) -> StrategySettings:
    settings = await get_strategy_settings(session)
    for key, value in fields.items():
        if hasattr(settings, key):
            setattr(settings, key, value)
    await session.commit()
    await session.refresh(settings)
    return settings


async def get_signal_by_id(session: AsyncSession, signal_id: int) -> Signal | None:
    result = await session.execute(select(Signal).where(Signal.id == signal_id))
    return result.scalar_one_or_none()


async def force_close_signal(session: AsyncSession, signal: Signal, exit_price: float) -> Signal:
    from app.utils.leverage import get_leverage, spot_to_leveraged
    from app.utils.trade_pnl import combined_close_pnl

    lev = get_leverage(signal)
    if signal.direction == "long":
        spot = (exit_price - signal.entry_price) / signal.entry_price * 100
    else:
        spot = (signal.entry_price - exit_price) / signal.entry_price * 100
    remaining = 0.5 if signal.partial_tp_hit else 1.0
    margin = spot_to_leveraged(spot, lev) * remaining
    pnl = combined_close_pnl(signal, margin)
    status = TradeStatus.WIN.value if spot > 0 else TradeStatus.LOSS.value
    return await close_signal(
        session, signal, status=status, exit_price=exit_price,
        pnl_percent=pnl,
    )

