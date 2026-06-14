from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.database.repositories import (
    count_accounts,
    count_active_connections,
    count_stored_messages,
    extend_subscription,
    get_account_by_tg_id,
    get_payment_settings,
    list_accounts,
    set_account_blocked,
    update_payment_settings,
)
from app.filters.admin import AdminFilter
from app.keyboards.admin import admin_home_keyboard, admin_user_actions_keyboard, admin_users_keyboard
from app.keyboards.payments import admin_payment_keyboard
from app.services.payments import payment_settings_text
from app.states.admin import AdminPaymentSettings
from app.utils.text import subscription_status_text

router = Router(name="admin")
router.message.filter(AdminFilter())
router.callback_query.filter(AdminFilter())

PAGE_SIZE = 10


@router.message(Command("admin"))
async def admin_command(message: Message, session: AsyncSession) -> None:
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


@router.callback_query(F.data == "admin:payments")
async def admin_payments(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    if not isinstance(callback.message, Message):
        return
    payment_settings = await get_payment_settings(session)
    await callback.message.answer(
        payment_settings_text(payment_settings),
        reply_markup=admin_payment_keyboard(payment_settings),
    )


@router.callback_query(F.data == "admin:payments:toggle")
async def admin_payments_toggle(callback: CallbackQuery, session: AsyncSession) -> None:
    payment_settings = await get_payment_settings(session)
    payment_settings = await update_payment_settings(
        session,
        is_enabled=not payment_settings.is_enabled,
    )
    await callback.answer("Статус оплаты обновлён.")
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            payment_settings_text(payment_settings),
            reply_markup=admin_payment_keyboard(payment_settings),
        )


@router.callback_query(F.data == "admin:payments:currency:toggle")
async def admin_payments_currency_toggle(callback: CallbackQuery, session: AsyncSession) -> None:
    payment_settings = await get_payment_settings(session)
    new_currency = "RUB" if payment_settings.currency == "XTR" else "XTR"
    new_price = 29900 if new_currency == "RUB" else 100
    payment_settings = await update_payment_settings(
        session,
        currency=new_currency,
        price_amount=new_price,
        provider_token=None if new_currency == "XTR" else payment_settings.provider_token,
    )
    await callback.answer(f"Валюта: {new_currency}")
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            payment_settings_text(payment_settings),
            reply_markup=admin_payment_keyboard(payment_settings),
        )


@router.callback_query(F.data == "admin:payments:edit:token")
async def admin_payments_edit_token(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(AdminPaymentSettings.edit_provider_token)
    if isinstance(callback.message, Message):
        await callback.message.answer(
            "Отправьте <b>provider token</b> от платёжной системы.\n\n"
            "Для Telegram Stars отправьте <code>-</code> (token не нужен).\n"
            "Для отмены: /cancel"
        )


@router.callback_query(F.data == "admin:payments:edit:price")
async def admin_payments_edit_price(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    payment_settings = await get_payment_settings(session)
    await callback.answer()
    await state.set_state(AdminPaymentSettings.edit_price)
    if isinstance(callback.message, Message):
        hint = (
            "количество Stars (например: 100)"
            if payment_settings.currency == "XTR"
            else "сумму в рублях (например: 299 или 299.50)"
        )
        await callback.message.answer(
            f"Отправьте новую цену — {hint}.\n\nДля отмены: /cancel"
        )


@router.callback_query(F.data == "admin:payments:edit:days")
async def admin_payments_edit_days(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(AdminPaymentSettings.edit_days)
    if isinstance(callback.message, Message):
        await callback.message.answer(
            "Отправьте количество дней подписки за одну оплату (например: 30).\n\n"
            "Для отмены: /cancel"
        )


@router.message(Command("cancel"), StateFilter(AdminPaymentSettings))
async def admin_cancel_edit(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    payment_settings = await get_payment_settings(session)
    await message.answer(
        "Изменение отменено.",
        reply_markup=admin_payment_keyboard(payment_settings),
    )


@router.message(StateFilter(AdminPaymentSettings.edit_provider_token))
async def admin_save_provider_token(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if message.text is None:
        await message.answer("Отправьте текстовое сообщение.")
        return

    token = None if message.text.strip() == "-" else message.text.strip()
    payment_settings = await update_payment_settings(session, provider_token=token)
    await state.clear()
    await message.answer(
        "Provider token обновлён.\n\n" + payment_settings_text(payment_settings),
        reply_markup=admin_payment_keyboard(payment_settings),
    )


@router.message(StateFilter(AdminPaymentSettings.edit_price))
async def admin_save_price(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if message.text is None:
        await message.answer("Отправьте число.")
        return

    payment_settings = await get_payment_settings(session)
    raw = message.text.strip().replace(",", ".")

    try:
        if payment_settings.currency == "XTR":
            price = int(raw)
            if price <= 0:
                raise ValueError
        else:
            price = int(round(float(raw) * 100))
            if price <= 0:
                raise ValueError
    except ValueError:
        await message.answer("Некорректная цена. Попробуйте снова или /cancel")
        return

    payment_settings = await update_payment_settings(session, price_amount=price)
    await state.clear()
    await message.answer(
        "Цена обновлена.\n\n" + payment_settings_text(payment_settings),
        reply_markup=admin_payment_keyboard(payment_settings),
    )


@router.message(StateFilter(AdminPaymentSettings.edit_days))
async def admin_save_days(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if message.text is None:
        await message.answer("Отправьте число.")
        return

    try:
        days = int(message.text.strip())
        if days <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Некорректное число дней. Попробуйте снова или /cancel")
        return

    payment_settings = await update_payment_settings(session, subscription_days=days)
    await state.clear()
    await message.answer(
        "Срок подписки обновлён.\n\n" + payment_settings_text(payment_settings),
        reply_markup=admin_payment_keyboard(payment_settings),
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
