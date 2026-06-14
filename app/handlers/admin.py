import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InputMediaPhoto, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.database.models import ApplicationDecision
from app.database.repositories import (
    get_application,
    list_pending_applications,
    set_application_decision,
)
from app.filters.admin import AdminFilter
from app.keyboards.admin import applications_keyboard, decision_keyboard
from app.services.access import create_one_time_invite_link
from app.services.notifications import notify_user_decision
from app.utils.text import application_text

logger = logging.getLogger(__name__)

router = Router(name="admin")
router.message.filter(AdminFilter())
router.callback_query.filter(AdminFilter())

ACTION_TO_DECISION = {
    "approve": ApplicationDecision.APPROVED,
    "reject": ApplicationDecision.REJECTED,
    "resubmit": ApplicationDecision.RESUBMIT,
    "block": ApplicationDecision.BLOCKED,
}


@router.message(Command("admin"))
async def admin_command(message: Message, session: AsyncSession) -> None:
    await send_applications_list(message, session)


@router.callback_query(F.data == "admin:applications:refresh")
async def refresh_applications(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    if isinstance(callback.message, Message):
        await send_applications_list(callback.message, session)


@router.callback_query(F.data.regexp(r"^admin:application:\d+:open$"))
async def open_application(callback: CallbackQuery, session: AsyncSession) -> None:
    application_id = _extract_application_id(callback.data)
    application = await get_application(session, application_id)
    if application is None:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return

    await callback.answer()
    if not isinstance(callback.message, Message):
        return

    media = [
        InputMediaPhoto(media=application.register_photo, caption="Скрин регистрации BingX"),
        InputMediaPhoto(media=application.deposit_photo, caption="Скрин пополнения BingX"),
    ]
    await callback.message.answer_media_group(media)
    await callback.message.answer(
        application_text(application),
        reply_markup=decision_keyboard(application.id),
    )


@router.callback_query(F.data.regexp(r"^admin:application:\d+:(approve|reject|resubmit|block)$"))
async def decide_application(
    callback: CallbackQuery,
    session: AsyncSession,
    settings: Settings,
    bot: Bot,
) -> None:
    application_id = _extract_application_id(callback.data)
    action = str(callback.data).rsplit(":", maxsplit=1)[-1]
    decision = ACTION_TO_DECISION[action]

    application = await get_application(session, application_id)
    if application is None:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return
    if application.decision != ApplicationDecision.PENDING.value:
        await callback.answer("По этой заявке уже принято решение.", show_alert=True)
        return

    invite_link: str | None = None
    if decision == ApplicationDecision.APPROVED:
        try:
            invite_link = await create_one_time_invite_link(bot, settings.channel_id, application.id)
        except Exception:
            logger.exception("Failed to create invite link for application #%s", application.id)
            await callback.answer(
                "Не удалось создать ссылку. Проверьте, что бот админ канала.",
                show_alert=True,
            )
            return

    application = await set_application_decision(
        session=session,
        application=application,
        decision=decision,
        moderator_tg_id=callback.from_user.id,
    )
    await notify_user_decision(bot, application.user, decision, invite_link)

    await callback.answer("Решение сохранено.")
    if isinstance(callback.message, Message):
        await callback.message.answer(
            f"Решение по заявке #{application.id}: <b>{decision.value}</b>",
        )


async def send_applications_list(message: Message, session: AsyncSession) -> None:
    applications = await list_pending_applications(session)
    if not applications:
        await message.answer("Очередь заявок пуста.", reply_markup=applications_keyboard([]))
        return

    await message.answer(
        "📋 <b>Заявки на проверку</b>\n\nВыберите заявку, чтобы открыть UID и скриншоты.",
        reply_markup=applications_keyboard(applications),
    )


def _extract_application_id(callback_data: str | None) -> int:
    if callback_data is None:
        raise ValueError("callback_data is empty")
    return int(callback_data.split(":")[2])
