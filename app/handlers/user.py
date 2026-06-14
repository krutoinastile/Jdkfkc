from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.database.repositories import (
    count_account_dialogs,
    count_dialog_messages,
    get_account_by_tg_id,
    get_or_create_account,
    get_payment_settings,
    is_admin,
    list_account_dialogs,
    list_dialog_messages,
    toggle_notification,
)
from app.services.payments import format_price
from app.keyboards.payments import subscription_keyboard
from app.keyboards.user import (
    dialogs_keyboard,
    history_keyboard,
    main_menu_keyboard,
    settings_keyboard,
)
from app.utils.message import format_dialog_label, format_message_preview, format_user_label
from app.utils.text import (
    connection_help_text,
    settings_text,
    subscription_status_text,
    welcome_text,
)

router = Router(name="user")

PAGE_SIZE = 10


@router.message(CommandStart())
async def start_command(message: Message, session: AsyncSession, settings: Settings) -> None:
    if message.from_user is None:
        return

    account = await get_or_create_account(
        session,
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
    )
    admin = await is_admin(session, message.from_user.id, settings.parsed_admin_ids)
    await message.answer(
        welcome_text(),
        reply_markup=main_menu_keyboard(settings, is_admin=admin),
    )
    if account.subscription_until is None and not account.trial_used:
        await message.answer(
            "После подключения бизнес-аккаунта вам будет доступен "
            f"пробный период на {settings.trial_days} дн."
        )


@router.callback_query(F.data == "menu:home")
async def menu_home(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await callback.answer()
    if callback.from_user is None or not isinstance(callback.message, Message):
        return
    admin = await is_admin(session, callback.from_user.id, settings.parsed_admin_ids)
    await callback.message.answer(
        welcome_text(),
        reply_markup=main_menu_keyboard(settings, is_admin=admin),
    )


@router.callback_query(F.data == "menu:connect")
async def menu_connect(callback: CallbackQuery) -> None:
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.answer(connection_help_text())


@router.callback_query(F.data == "menu:subscription")
async def menu_subscription(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await callback.answer()
    if callback.from_user is None or not isinstance(callback.message, Message):
        return
    account = await get_or_create_account(
        session,
        callback.from_user.id,
        callback.from_user.username,
        callback.from_user.first_name,
    )
    payment_settings = await get_payment_settings(session)
    price_line = ""
    if payment_settings.is_enabled:
        price_line = f"\nСтоимость: <b>{format_price(payment_settings)}</b> / {payment_settings.subscription_days} дн."
    text = (
        "<b>Подписка</b>\n\n"
        f"{subscription_status_text(account)}"
        f"{price_line}\n\n"
        f"{settings.subscription_price_text}"
    )
    await callback.message.answer(text, reply_markup=subscription_keyboard(payment_settings))


@router.callback_query(F.data == "menu:settings")
async def menu_settings(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    if callback.from_user is None or not isinstance(callback.message, Message):
        return
    account = await get_or_create_account(
        session,
        callback.from_user.id,
        callback.from_user.username,
        callback.from_user.first_name,
    )
    await callback.message.answer(settings_text(account), reply_markup=settings_keyboard(account))


@router.callback_query(F.data.startswith("settings:toggle:"))
async def toggle_settings(callback: CallbackQuery, session: AsyncSession) -> None:
    if callback.from_user is None or callback.data is None:
        return
    field = callback.data.split(":")[-1]
    if field not in {"notify_new", "notify_edit", "notify_delete"}:
        await callback.answer("Неизвестная настройка.", show_alert=True)
        return

    account = await get_or_create_account(
        session,
        callback.from_user.id,
        callback.from_user.username,
        callback.from_user.first_name,
    )
    account = await toggle_notification(session, account, field)
    await callback.answer("Настройка обновлена.")
    if isinstance(callback.message, Message):
        await callback.message.edit_text(settings_text(account), reply_markup=settings_keyboard(account))


@router.callback_query(F.data.regexp(r"^menu:dialogs:\d+$"))
async def menu_dialogs(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await callback.answer()
    if callback.from_user is None or callback.data is None or not isinstance(callback.message, Message):
        return

    page = int(callback.data.rsplit(":", maxsplit=1)[-1])
    account = await get_or_create_account(
        session,
        callback.from_user.id,
        callback.from_user.username,
        callback.from_user.first_name,
    )
    total = await count_account_dialogs(session, account.id)
    dialogs = await list_account_dialogs(session, account.id, limit=PAGE_SIZE, offset=page * PAGE_SIZE)
    if not dialogs:
        await callback.message.answer(
            "Диалогов пока нет. Подключите бота к Telegram Business и дождитесь входящих сообщений.",
            reply_markup=main_menu_keyboard(settings),
        )
        return

    await callback.message.answer(
        f"📂 <b>Диалоги</b> ({total})",
        reply_markup=dialogs_keyboard(dialogs, page, total, PAGE_SIZE),
    )


@router.callback_query(F.data.regexp(r"^history:dialog:\d+:\d+$"))
async def dialog_history(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    if callback.data is None or not isinstance(callback.message, Message):
        return

    _, _, dialog_id_raw, page_raw = callback.data.split(":")
    dialog_id = int(dialog_id_raw)
    page = int(page_raw)

    total = await count_dialog_messages(session, dialog_id)
    messages = await list_dialog_messages(session, dialog_id, limit=PAGE_SIZE, offset=page * PAGE_SIZE)
    if not messages:
        await callback.message.answer("В этом диалоге пока нет сохранённых сообщений.")
        return

    lines: list[str] = ["📜 <b>История сообщений</b>\n"]
    for stored in reversed(messages):
        sender = format_user_label(stored.from_username, stored.from_first_name, stored.from_user_id)
        preview = format_message_preview(stored.text, stored.caption, stored.content_type)
        status = " 🗑" if stored.is_deleted else ""
        lines.append(f"• {sender}{status}: {preview}")

    await callback.message.answer(
        "\n".join(lines),
        reply_markup=history_keyboard(dialog_id, page, total, PAGE_SIZE),
    )


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(connection_help_text())
