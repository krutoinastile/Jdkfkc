from collections.abc import Iterable
from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import Admin, Application, ApplicationDecision, User, UserStatus


async def get_user_by_tg_id(session: AsyncSession, tg_id: int) -> User | None:
    result = await session.execute(select(User).where(User.tg_id == tg_id))
    return result.scalar_one_or_none()


async def get_or_create_user(session: AsyncSession, tg_id: int, username: str | None) -> User:
    user = await get_user_by_tg_id(session, tg_id)
    if user is None:
        user = User(tg_id=tg_id, username=username)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user

    if user.username != username:
        user.username = username
        await session.commit()
    return user


async def mark_user_registered(session: AsyncSession, user: User) -> User:
    if user.status == UserStatus.NEW.value:
        user.status = UserStatus.REGISTERED.value
        await session.commit()
        await session.refresh(user)
    return user


async def create_application(
    session: AsyncSession,
    user: User,
    bingx_uid: str,
    register_photo: str,
    deposit_photo: str,
) -> Application:
    active_decisions = {ApplicationDecision.PENDING.value, ApplicationDecision.APPROVED.value}
    if user.status in {UserStatus.PENDING.value, UserStatus.APPROVED.value, UserStatus.BLOCKED.value}:
        raise ValueError("active_application_exists")

    result = await session.execute(
        select(Application)
        .where(Application.user_id == user.id)
        .where(Application.decision.in_(active_decisions))
        .limit(1)
    )
    if result.scalar_one_or_none() is not None:
        raise ValueError("active_application_exists")

    user.bingx_uid = bingx_uid
    user.status = UserStatus.PENDING.value
    application = Application(
        user_id=user.id,
        register_photo=register_photo,
        deposit_photo=deposit_photo,
    )
    session.add(application)
    await session.commit()
    await session.refresh(application, attribute_names=["user"])
    return application


async def list_applications(
    session: AsyncSession,
    decision: ApplicationDecision | None = None,
    page: int = 0,
    page_size: int = 5,
) -> list[Application]:
    statement = select(Application).options(selectinload(Application.user))
    if decision is not None:
        statement = statement.where(Application.decision == decision.value)

    order_by = Application.created_at.asc() if decision == ApplicationDecision.PENDING else Application.created_at.desc()
    result = await session.execute(
        statement.order_by(order_by).offset(page * page_size).limit(page_size),
    )
    return list(result.scalars().all())


async def list_pending_applications(session: AsyncSession, limit: int = 20) -> list[Application]:
    return await list_applications(session, ApplicationDecision.PENDING, page=0, page_size=limit)


async def count_applications(
    session: AsyncSession,
    decision: ApplicationDecision | None = None,
) -> int:
    statement = select(func.count(Application.id))
    if decision is not None:
        statement = statement.where(Application.decision == decision.value)
    result = await session.execute(statement)
    return int(result.scalar_one())


async def count_pending_applications(session: AsyncSession) -> int:
    return await count_applications(session, ApplicationDecision.PENDING)


async def get_application_counts(session: AsyncSession) -> dict[str, int]:
    result = await session.execute(
        select(Application.decision, func.count(Application.id)).group_by(Application.decision),
    )
    counts = {decision.value: 0 for decision in ApplicationDecision}
    for decision, count in result.all():
        counts[str(decision)] = int(count)
    counts["all"] = sum(counts.values())
    return counts


async def count_users(session: AsyncSession) -> int:
    result = await session.execute(select(func.count(User.id)))
    return int(result.scalar_one())


async def search_applications(session: AsyncSession, query: str, limit: int = 10) -> list[Application]:
    normalized_query = query.strip().lower().lstrip("@")
    if not normalized_query:
        return []

    conditions = [
        func.lower(User.username).like(f"%{normalized_query}%"),
        func.lower(User.bingx_uid).like(f"%{normalized_query}%"),
    ]
    if normalized_query.isdigit():
        conditions.append(User.tg_id == int(normalized_query))
        conditions.append(Application.id == int(normalized_query))

    result = await session.execute(
        select(Application)
        .join(Application.user)
        .options(selectinload(Application.user))
        .where(or_(*conditions))
        .order_by(Application.created_at.desc())
        .limit(limit),
    )
    return list(result.scalars().all())


async def get_application(session: AsyncSession, application_id: int) -> Application | None:
    result = await session.execute(
        select(Application)
        .options(selectinload(Application.user))
        .where(Application.id == application_id)
    )
    return result.scalar_one_or_none()


async def set_application_decision(
    session: AsyncSession,
    application: Application,
    decision: ApplicationDecision,
    moderator_tg_id: int,
    reason: str | None = None,
) -> Application:
    status_by_decision = {
        ApplicationDecision.APPROVED: UserStatus.APPROVED,
        ApplicationDecision.REJECTED: UserStatus.REJECTED,
        ApplicationDecision.RESUBMIT: UserStatus.RESUBMIT,
        ApplicationDecision.BLOCKED: UserStatus.BLOCKED,
    }
    application.decision = decision.value
    application.moderator = moderator_tg_id
    application.decision_reason = reason
    application.decided_at = datetime.now(timezone.utc)
    application.user.status = status_by_decision[decision].value
    await session.commit()
    await session.refresh(application, attribute_names=["user"])
    return application


async def upsert_admins(session: AsyncSession, admin_ids: Iterable[int]) -> None:
    for tg_id in admin_ids:
        result = await session.execute(select(Admin).where(Admin.tg_id == tg_id))
        if result.scalar_one_or_none() is None:
            session.add(Admin(tg_id=tg_id))
    await session.commit()


async def is_admin(session: AsyncSession, tg_id: int, env_admin_ids: Iterable[int]) -> bool:
    if tg_id in set(env_admin_ids):
        return True
    result = await session.execute(select(Admin).where(Admin.tg_id == tg_id))
    return result.scalar_one_or_none() is not None


async def list_admin_ids(session: AsyncSession, env_admin_ids: Iterable[int]) -> list[int]:
    result = await session.execute(select(Admin.tg_id))
    admin_ids = set(result.scalars().all())
    admin_ids.update(env_admin_ids)
    return sorted(admin_ids)
