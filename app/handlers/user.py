import re

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.database.models import UserStatus
from app.database.repositories import (
    create_application,
    get_or_create_user,
    is_admin as is_user_admin,
    mark_user_registered,
)
from app.keyboards.user import cancel_keyboard, main_menu_keyboard, registered_keyboard
from app.services.notifications import notify_admins_new_application
from app.states.application import ApplicationForm
from app.utils.text import STATUS_LABELS, welcome_text

router = Router(name="user")

BINGX_UID_PATTERN = re.compile(r"^\d{4,32}$")


@router.message(CommandStart())
async def start_command(message: Message, session: AsyncSession, settings: Settings) -> None:
    if message.from_user is None:
        return

    await get_or_create_user(session, message.from_user.id, message.from_user.username)
    admin = await is_user_admin(session, message.from_user.id, settings.parsed_admin_ids)
    await message.answer(welcome_text(), reply_markup=main_menu_keyboard(settings, is_admin=admin))


@router.message(Command("cancel"))
async def cancel_command(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Действие отменено.")


@router.callback_query(F.data == "user:menu")
async def show_menu(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await callback.answer()
    if isinstance(callback.message, Message):
        admin = await is_user_admin(session, callback.from_user.id, settings.parsed_admin_ids)
        await callback.message.answer(welcome_text(), reply_markup=main_menu_keyboard(settings, is_admin=admin))


@router.callback_query(F.data == "user:registered")
async def confirm_registered(callback: CallbackQuery, session: AsyncSession) -> None:
    if callback.from_user is None:
        return

    user = await get_or_create_user(session, callback.from_user.id, callback.from_user.username)
    if user.status == UserStatus.BLOCKED.value:
        await callback.answer("Ваш доступ заблокирован.", show_alert=True)
        return

    await mark_user_registered(session, user)
    await callback.answer("Регистрация отмечена.")
    if isinstance(callback.message, Message):
        await callback.message.answer(
            "Отлично. Теперь подайте заявку и приложите данные для проверки.",
            reply_markup=registered_keyboard(),
        )


@router.callback_query(F.data == "user:status")
async def status_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    if callback.from_user is None:
        return

    user = await get_or_create_user(session, callback.from_user.id, callback.from_user.username)
    status = STATUS_LABELS.get(user.status, user.status)
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.answer(f"🔎 Ваш статус: <b>{status}</b>.")


@router.callback_query(F.data == "user:support")
async def support_callback(callback: CallbackQuery) -> None:
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.answer("Напишите администратору проекта для получения поддержки.")


@router.callback_query(F.data == "application:start")
async def start_application(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    if callback.from_user is None:
        return

    user = await get_or_create_user(session, callback.from_user.id, callback.from_user.username)
    if user.status == UserStatus.NEW.value:
        await callback.answer("Сначала зарегистрируйтесь по реферальной ссылке.", show_alert=True)
        return
    if user.status == UserStatus.PENDING.value:
        await callback.answer("Ваша заявка уже находится на проверке.", show_alert=True)
        return
    if user.status == UserStatus.APPROVED.value:
        await callback.answer("Доступ уже одобрен.", show_alert=True)
        return
    if user.status == UserStatus.BLOCKED.value:
        await callback.answer("Ваш доступ заблокирован.", show_alert=True)
        return

    await state.clear()
    await state.set_state(ApplicationForm.waiting_uid)
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.answer(
            "Введите ваш <b>BingX UID</b>. UID должен содержать только цифры.",
            reply_markup=cancel_keyboard(),
        )


@router.callback_query(F.data == "application:cancel")
async def cancel_application(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer("Заявка отменена.")
    if isinstance(callback.message, Message):
        await callback.message.answer("Подача заявки отменена.")


@router.message(ApplicationForm.waiting_uid)
async def receive_uid(message: Message, state: FSMContext) -> None:
    uid = (message.text or "").strip()
    if not BINGX_UID_PATTERN.fullmatch(uid):
        await message.answer("UID обязателен и должен содержать 4-32 цифры. Введите UID еще раз.")
        return

    await state.update_data(bingx_uid=uid)
    await state.set_state(ApplicationForm.waiting_register_photo)
    await message.answer(
        "Пришлите <b>скрин регистрации BingX</b> одним изображением.",
        reply_markup=cancel_keyboard(),
    )


@router.message(ApplicationForm.waiting_register_photo, F.photo)
async def receive_register_photo(message: Message, state: FSMContext) -> None:
    if not message.photo:
        await message.answer("Нужно отправить изображение.")
        return

    await state.update_data(register_photo=message.photo[-1].file_id)
    await state.set_state(ApplicationForm.waiting_deposit_photo)
    await message.answer(
        "Теперь пришлите <b>скрин пополнения баланса BingX</b> одним изображением.",
        reply_markup=cancel_keyboard(),
    )


@router.message(ApplicationForm.waiting_register_photo)
async def reject_non_photo_registration(message: Message) -> None:
    await message.answer("Скрин регистрации обязателен. Отправьте именно изображение.")


@router.message(ApplicationForm.waiting_deposit_photo, F.photo)
async def receive_deposit_photo(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
    bot: Bot,
) -> None:
    if message.from_user is None or not message.photo:
        return

    data = await state.get_data()
    user = await get_or_create_user(session, message.from_user.id, message.from_user.username)
    try:
        application = await create_application(
            session=session,
            user=user,
            bingx_uid=str(data["bingx_uid"]),
            register_photo=str(data["register_photo"]),
            deposit_photo=message.photo[-1].file_id,
        )
    except ValueError:
        await state.clear()
        await message.answer("У вас уже есть активная заявка или доступ заблокирован.")
        return

    await state.clear()
    await message.answer("📩 Заявка принята и передана администратору на проверку.")
    await notify_admins_new_application(bot, session, settings, application)


@router.message(ApplicationForm.waiting_deposit_photo)
async def reject_non_photo_deposit(message: Message) -> None:
    await message.answer("Скрин пополнения обязателен. Отправьте именно изображение.")
