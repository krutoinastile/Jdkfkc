from collections.abc import Iterable

from sqlalchemy import func, select
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


async def list_pending_applications(session: AsyncSession, limit: int = 20) -> list[Application]:
    result = await session.execute(
        select(Application)
        .options(selectinload(Application.user))
        .where(Application.decision == ApplicationDecision.PENDING.value)
        .order_by(Application.created_at.asc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def count_pending_applications(session: AsyncSession) -> int:
    result = await session.execute(
        select(func.count(Application.id)).where(
            Application.decision == ApplicationDecision.PENDING.value,
        )
    )
    return int(result.scalar_one())


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
) -> Application:
    status_by_decision = {
        ApplicationDecision.APPROVED: UserStatus.APPROVED,
        ApplicationDecision.REJECTED: UserStatus.REJECTED,
        ApplicationDecision.RESUBMIT: UserStatus.RESUBMIT,
        ApplicationDecision.BLOCKED: UserStatus.BLOCKED,
    }
    application.decision = decision.value
    application.moderator = moderator_tg_id
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
