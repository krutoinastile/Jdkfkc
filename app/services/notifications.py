import logging

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.database.models import Application, ApplicationDecision, User
from app.database.repositories import list_admin_ids
from app.keyboards.admin import decision_keyboard
from app.utils.text import application_text

logger = logging.getLogger(__name__)


async def notify_admins_new_application(
    bot: Bot,
    session: AsyncSession,
    settings: Settings,
    application: Application,
) -> None:
    admin_ids = await list_admin_ids(session, settings.parsed_admin_ids)
    if not admin_ids:
        logger.warning("New application #%s received, but no admins are configured", application.id)
        return

    text = "🆕 <b>Новая заявка на доступ</b>\n\n" + application_text(application)
    for admin_id in admin_ids:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=text,
                reply_markup=decision_keyboard(application.id),
            )
        except Exception:
            logger.exception("Failed to notify admin %s about application #%s", admin_id, application.id)


async def notify_user_decision(
    bot: Bot,
    user: User,
    decision: ApplicationDecision,
    invite_link: str | None = None,
    reason: str | None = None,
) -> None:
    reason_text = f"\n\nПричина: <b>{reason}</b>" if reason else ""
    if decision == ApplicationDecision.APPROVED:
        text = (
            "✅ <b>Заявка одобрена!</b>\n\n"
            "Ваша одноразовая ссылка в закрытый канал действует 24 часа и рассчитана на 1 вход:\n"
            f"{invite_link}"
        )
    elif decision == ApplicationDecision.REJECTED:
        text = (
            "❌ <b>Заявка отклонена.</b>\n\n"
            "Проверьте корректность UID, регистрацию по реферальной ссылке и скриншот пополнения."
            f"{reason_text}"
        )
    elif decision == ApplicationDecision.RESUBMIT:
        text = (
            "📝 <b>Администратор запросил повторную отправку.</b>\n\n"
            "Пожалуйста, подайте заявку заново и приложите корректные скриншоты."
            f"{reason_text}"
        )
    elif decision == ApplicationDecision.BLOCKED:
        text = f"🚫 <b>Доступ заблокирован.</b>{reason_text}"
    else:
        text = "Статус вашей заявки изменился."

    try:
        await bot.send_message(chat_id=user.tg_id, text=text)
    except Exception:
        logger.exception("Failed to notify user %s about decision %s", user.tg_id, decision.value)
