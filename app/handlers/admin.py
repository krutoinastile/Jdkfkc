import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InputMediaPhoto, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.database.models import Application, ApplicationDecision
from app.database.repositories import (
    count_applications,
    count_users,
    get_application,
    get_application_counts,
    list_applications,
    search_applications,
    set_application_decision,
)
from app.filters.admin import AdminFilter
from app.keyboards.admin import (
    DECISION_LABELS,
    PAGE_SIZE,
    REASON_LABELS,
    applications_keyboard,
    dashboard_keyboard,
    decision_keyboard,
    reason_keyboard,
    search_keyboard,
    search_results_keyboard,
)
from app.services.access import create_one_time_invite_link
from app.services.notifications import notify_user_decision
from app.states.admin import AdminSearchForm
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

STATUS_TO_DECISION = {decision.value: decision for decision in ApplicationDecision}


@router.message(Command("admin"))
async def admin_command(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    await send_dashboard(message, session)


@router.callback_query(F.data.in_({"admin:menu", "admin:applications:refresh"}))
async def admin_menu(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    if isinstance(callback.message, Message):
        await send_dashboard(callback.message, session)


@router.callback_query(F.data.regexp(r"^admin:list:(pending|approved|rejected|resubmit|blocked):\d+$"))
async def list_applications_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    status, page = _extract_status_page(callback.data)
    await callback.answer()
    if isinstance(callback.message, Message):
        await send_applications_list(callback.message, session, status, page)


@router.callback_query(F.data == "admin:search")
async def start_search(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(AdminSearchForm.waiting_query)
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.answer(
            "🔎 Введите BingX UID, Telegram ID, username или номер заявки.",
            reply_markup=search_keyboard(),
        )


@router.message(AdminSearchForm.waiting_query)
async def process_search(message: Message, session: AsyncSession, state: FSMContext) -> None:
    query = (message.text or "").strip()
    await state.clear()
    if len(query) < 2:
        await message.answer("Введите минимум 2 символа для поиска.", reply_markup=search_keyboard())
        return

    applications = await search_applications(session, query)
    if not applications:
        await message.answer("Ничего не найдено.", reply_markup=search_keyboard())
        return

    await message.answer(
        f"🔎 <b>Результаты поиска</b>\n\nЗапрос: <code>{query}</code>\nНайдено: {len(applications)}",
        reply_markup=search_results_keyboard(applications),
    )


@router.callback_query(F.data.regexp(r"^admin:app:\d+:open$"))
async def open_application(callback: CallbackQuery, session: AsyncSession) -> None:
    application_id = _extract_application_id(callback.data)
    application = await get_application(session, application_id)
    if application is None:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return

    await callback.answer()
    if isinstance(callback.message, Message):
        await send_application_card(callback.message, application)


@router.callback_query(F.data.regexp(r"^admin:app:\d+:approve$"))
async def approve_application(
    callback: CallbackQuery,
    session: AsyncSession,
    settings: Settings,
    bot: Bot,
) -> None:
    await process_decision(callback, session, settings, bot, ApplicationDecision.APPROVED)


@router.callback_query(F.data.regexp(r"^admin:reason:\d+:(reject|resubmit|block)$"))
async def choose_reason(callback: CallbackQuery, session: AsyncSession) -> None:
    application_id = _extract_application_id(callback.data)
    action = str(callback.data).split(":")[3]
    application = await get_application(session, application_id)
    if application is None:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return
    if application.decision != ApplicationDecision.PENDING.value:
        await callback.answer("По этой заявке уже принято решение.", show_alert=True)
        return

    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.answer(
            "Выберите причину решения. Она будет сохранена и отправлена пользователю.",
            reply_markup=reason_keyboard(application_id, action),
        )


@router.callback_query(F.data.regexp(r"^admin:setreason:\d+:(reject|resubmit|block):[a-z_]+$"))
async def decide_with_reason(
    callback: CallbackQuery,
    session: AsyncSession,
    settings: Settings,
    bot: Bot,
) -> None:
    parts = str(callback.data).split(":")
    application_id = int(parts[2])
    action = parts[3]
    reason_code = parts[4]
    decision = ACTION_TO_DECISION[action]
    reason = REASON_LABELS.get(reason_code, reason_code)

    await process_decision(callback, session, settings, bot, decision, application_id, reason)


async def process_decision(
    callback: CallbackQuery,
    session: AsyncSession,
    settings: Settings,
    bot: Bot,
    decision: ApplicationDecision,
    application_id: int | None = None,
    reason: str | None = None,
) -> None:
    application_id = application_id or _extract_application_id(callback.data)
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
        reason=reason,
    )
    await notify_user_decision(bot, application.user, decision, invite_link, reason)

    await callback.answer("Решение сохранено.")
    if isinstance(callback.message, Message):
        label = DECISION_LABELS.get(decision.value, decision.value)
        reason_line = f"\nПричина: <b>{reason}</b>" if reason else ""
        await callback.message.answer(
            f"Решение по заявке #{application.id}: <b>{label}</b>{reason_line}",
            reply_markup=dashboard_keyboard(),
        )


async def send_dashboard(message: Message, session: AsyncSession) -> None:
    counts = await get_application_counts(session)
    users_count = await count_users(session)
    text = (
        "🛠 <b>Админ-панель</b>\n\n"
        f"👤 Пользователей: <b>{users_count}</b>\n"
        f"📄 Всего заявок: <b>{counts['all']}</b>\n\n"
        f"📥 Новые: <b>{counts[ApplicationDecision.PENDING.value]}</b>\n"
        f"✅ Одобрено: <b>{counts[ApplicationDecision.APPROVED.value]}</b>\n"
        f"❌ Отклонено: <b>{counts[ApplicationDecision.REJECTED.value]}</b>\n"
        f"📝 Повторно: <b>{counts[ApplicationDecision.RESUBMIT.value]}</b>\n"
        f"🚫 Заблокировано: <b>{counts[ApplicationDecision.BLOCKED.value]}</b>"
    )
    await message.answer(text, reply_markup=dashboard_keyboard())


async def send_applications_list(
    message: Message,
    session: AsyncSession,
    status: str,
    page: int,
) -> None:
    decision = STATUS_TO_DECISION[status]
    total = await count_applications(session, decision)
    applications = await list_applications(session, decision, page=page, page_size=PAGE_SIZE)
    last_page = max((total - 1) // PAGE_SIZE, 0)
    label = DECISION_LABELS.get(status, status)

    if not applications:
        await message.answer(
            f"{label}\n\nЗаявок в этом разделе нет.",
            reply_markup=applications_keyboard([], status, 0, total),
        )
        return

    await message.answer(
        (
            f"📋 <b>{label}</b>\n\n"
            f"Страница: <b>{page + 1}/{last_page + 1}</b>\n"
            f"Всего: <b>{total}</b>\n\n"
            "Выберите заявку, чтобы открыть UID, данные пользователя и скриншоты."
        ),
        reply_markup=applications_keyboard(applications, status, page, total),
    )


async def send_application_card(message: Message, application: Application) -> None:
    media = [
        InputMediaPhoto(media=application.register_photo, caption="Скрин регистрации BingX"),
        InputMediaPhoto(media=application.deposit_photo, caption="Скрин пополнения BingX"),
    ]
    await message.answer_media_group(media)
    await message.answer(
        application_text(application),
        reply_markup=decision_keyboard(
            application.id,
            can_decide=application.decision == ApplicationDecision.PENDING.value,
        ),
    )


def _extract_application_id(callback_data: str | None) -> int:
    if callback_data is None:
        raise ValueError("callback_data is empty")
    return int(callback_data.split(":")[2])


def _extract_status_page(callback_data: str | None) -> tuple[str, int]:
    if callback_data is None:
        raise ValueError("callback_data is empty")
    _, _, status, page = callback_data.split(":")
    return status, int(page)
