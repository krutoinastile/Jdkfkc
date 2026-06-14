from datetime import UTC, datetime

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.database.repositories import (
    count_accounts,
    count_active_connections,
    count_stored_messages,
    extend_subscription,
    get_account_by_tg_id,
    list_accounts,
    set_account_blocked,
)
from app.filters.admin import AdminFilter
from app.keyboards.admin import admin_home_keyboard, admin_user_actions_keyboard, admin_users_keyboard
from app.utils.text import subscription_status_text

router = Router(name="admin")
router.message.filter(AdminFilter())
router.callback_query.filter(AdminFilter())

PAGE_SIZE = 10


@router.message(Command("admin"))
async def admin_command(message: Message) -> None:
    await message.answer("🛠 <b>Админ-панель</b>", reply_markup=admin_home_keyboard())


@router.callback_query(F.data == "admin:home")
async def admin_home(callback: CallbackQuery) -> None:
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.answer("🛠 <b>Админ-панель</b>", reply_markup=admin_home_keyboard())


@router.callback_query(F.data == "admin:stats")
async def admin_stats(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    if not isinstance(callback.message, Message):
        return

    users = await count_accounts(session)
    connections = await count_active_connections(session)
    messages = await count_stored_messages(session)
    await callback.message.answer(
        "<b>Статистика</b>\n\n"
        f"Пользователей: {users}\n"
        f"Активных подключений: {connections}\n"
        f"Сохранённых сообщений: {messages}"
    )


@router.callback_query(F.data.regexp(r"^admin:users:\d+$"))
async def admin_users(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    if callback.data is None or not isinstance(callback.message, Message):
        return

    page = int(callback.data.rsplit(":", maxsplit=1)[-1])
    total = await count_accounts(session)
    accounts = await list_accounts(session, limit=PAGE_SIZE, offset=page * PAGE_SIZE)
    await callback.message.answer(
        f"👥 <b>Пользователи</b> ({total})",
        reply_markup=admin_users_keyboard(accounts, page, total, PAGE_SIZE),
    )


@router.callback_query(F.data.regexp(r"^admin:user:\d+$"))
async def admin_user_card(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    if callback.data is None or not isinstance(callback.message, Message):
        return

    tg_id = int(callback.data.rsplit(":", maxsplit=1)[-1])
    account = await get_account_by_tg_id(session, tg_id)
    if account is None:
        await callback.message.answer("Пользователь не найден.")
        return

    label = account.username or account.first_name or str(account.tg_id)
    await callback.message.answer(
        f"<b>{label}</b>\n"
        f"Telegram ID: <code>{account.tg_id}</code>\n"
        f"{subscription_status_text(account)}",
        reply_markup=admin_user_actions_keyboard(account.tg_id),
    )


@router.callback_query(F.data.regexp(r"^admin:extend:\d+:\d+$"))
async def admin_extend(callback: CallbackQuery, session: AsyncSession) -> None:
    if callback.data is None:
        return
    _, _, tg_id_raw, days_raw = callback.data.split(":")
    account = await get_account_by_tg_id(session, int(tg_id_raw))
    if account is None:
        await callback.answer("Пользователь не найден.", show_alert=True)
        return

    account = await extend_subscription(session, account, int(days_raw))
    await callback.answer("Подписка продлена.")
    if isinstance(callback.message, Message):
        await callback.message.answer(
            f"Подписка пользователя {account.tg_id} продлена.\n{subscription_status_text(account)}",
            reply_markup=admin_user_actions_keyboard(account.tg_id),
        )


@router.callback_query(F.data.regexp(r"^admin:block:\d+:[01]$"))
async def admin_block(callback: CallbackQuery, session: AsyncSession) -> None:
    if callback.data is None:
        return
    _, _, tg_id_raw, blocked_raw = callback.data.split(":")
    account = await get_account_by_tg_id(session, int(tg_id_raw))
    if account is None:
        await callback.answer("Пользователь не найден.", show_alert=True)
        return

    account = await set_account_blocked(session, account, blocked_raw == "1")
    await callback.answer("Статус обновлён.")
    if isinstance(callback.message, Message):
        await callback.message.answer(
            f"Статус пользователя {account.tg_id} обновлён.\n{subscription_status_text(account)}",
            reply_markup=admin_user_actions_keyboard(account.tg_id),
        )
