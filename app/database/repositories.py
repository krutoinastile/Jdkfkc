from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Signal, TradeStatus, User


async def get_or_create_user(session: AsyncSession, tg_id: int, username: str | None) -> User:
    result = await session.execute(select(User).where(User.tg_id == tg_id))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(tg_id=tg_id, username=username)
        session.add(user)
        await session.commit()
        await session.refresh(user)
    elif user.username != username:
        user.username = username
        await session.commit()
    return user


async def list_subscribed_users(session: AsyncSession) -> list[User]:
    result = await session.execute(select(User).where(User.notify_signals.is_(True)))
    return list(result.scalars().all())


async def toggle_notifications(session: AsyncSession, user: User) -> User:
    user.notify_signals = not user.notify_signals
    await session.commit()
    await session.refresh(user)
    return user


async def has_open_signal(session: AsyncSession, symbol: str) -> bool:
    result = await session.execute(
        select(Signal.id)
        .where(Signal.symbol == symbol)
        .where(Signal.status == TradeStatus.OPEN.value)
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def create_signal(session: AsyncSession, **fields: object) -> Signal:
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
    }


async def expire_old_signals(session: AsyncSession, max_age_hours: int = 72) -> int:
    cutoff = datetime.now(tz=UTC) - timedelta(hours=max_age_hours)
    result = await session.execute(
        select(Signal)
        .where(Signal.status == TradeStatus.OPEN.value)
        .where(Signal.opened_at < cutoff)
    )
    signals = list(result.scalars().all())
    for signal in signals:
        await close_signal(session, signal, status=TradeStatus.EXPIRED.value, exit_price=signal.entry_price, pnl_percent=0.0)
    return len(signals)
