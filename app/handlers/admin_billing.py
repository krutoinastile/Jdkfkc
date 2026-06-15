"""Admin billing, Crypto Pay, and giveaway settings."""

from __future__ import annotations

import random

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.billing_repositories import (
    create_giveaway,
    finish_giveaway,
    get_active_giveaway,
    get_billing_settings,
    list_giveaway_entries,
    update_billing_settings,
)
from app.database.models import User
from app.database.repositories import get_or_create_user
from app.filters.admin import AdminFilter
from app.keyboards.admin import admin_home_keyboard
from app.keyboards.billing import billing_admin_keyboard
from app.states.admin import AdminStates
from app.utils.billing_messages import format_billing_admin

router = Router(name="admin_billing")
router.message.filter(AdminFilter())
router.callback_query.filter(AdminFilter())


@router.callback_query(F.data == "admin:billing")
async def admin_billing_home(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    if not isinstance(callback.message, Message):
        return
    billing = await get_billing_settings(session)
    giveaway = await get_active_giveaway(session)
    await callback.message.edit_text(
        format_billing_admin(billing, token_set=bool(billing.cryptopay_api_token), giveaway=giveaway),
        reply_markup=billing_admin_keyboard(billing),
    )


@router.callback_query(F.data == "admin:billing:token")
async def admin_billing_token_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(AdminStates.billing_token)
    if isinstance(callback.message, Message):
        await callback.message.answer(
            "🔑 Отправьте <b>Crypto Pay API token</b>\n"
            "(из @CryptoBot → Crypto Pay → My Apps).\n\n"
            "/cancel — отмена"
        )


@router.message(StateFilter(AdminStates.billing_token))
async def admin_billing_token_save(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if message.text is None:
        return
    token = message.text.strip()
    await update_billing_settings(session, cryptopay_api_token=token)
    await state.clear()
    billing = await get_billing_settings(session)
    await message.answer(
        "✅ Crypto Pay token сохранён.",
        reply_markup=billing_admin_keyboard(billing),
    )


@router.callback_query(F.data == "admin:billing:price:custom")
async def admin_billing_price_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(AdminStates.billing_price)
    if isinstance(callback.message, Message):
        await callback.message.answer("💵 Введите цену подписки (число, например 19.99):\n/cancel — отмена")


@router.message(StateFilter(AdminStates.billing_price))
async def admin_billing_price_save(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if message.text is None:
        return
    try:
        price = float(message.text.replace(",", ".").strip())
    except ValueError:
        await message.answer("Введите число.")
        return
    if price <= 0:
        await message.answer("Цена должна быть больше 0.")
        return
    billing = await update_billing_settings(session, subscription_price=price)
    await state.clear()
    await message.answer(f"✅ Цена: {price:g} {billing.subscription_asset}", reply_markup=billing_admin_keyboard(billing))


@router.callback_query(F.data.regexp(r"^admin:billing:price:\d+$"))
async def admin_billing_price_preset(callback: CallbackQuery, session: AsyncSession) -> None:
    if callback.data is None or not isinstance(callback.message, Message):
        return
    price = float(callback.data.rsplit(":", maxsplit=1)[-1])
    billing = await update_billing_settings(session, subscription_price=price)
    await callback.answer(f"${price:g}")
    await callback.message.edit_text(
        format_billing_admin(billing, token_set=bool(billing.cryptopay_api_token), giveaway=await get_active_giveaway(session)),
        reply_markup=billing_admin_keyboard(billing),
    )


@router.callback_query(F.data.regexp(r"^admin:billing:disc:\d+$"))
async def admin_billing_discount(callback: CallbackQuery, session: AsyncSession) -> None:
    if callback.data is None or not isinstance(callback.message, Message):
        return
    pct = float(callback.data.rsplit(":", maxsplit=1)[-1])
    billing = await update_billing_settings(session, discount_percent=pct, discount_enabled=True)
    await callback.answer(f"Скидка {pct:g}%")
    await callback.message.edit_text(
        format_billing_admin(billing, token_set=bool(billing.cryptopay_api_token), giveaway=await get_active_giveaway(session)),
        reply_markup=billing_admin_keyboard(billing),
    )


@router.callback_query(F.data.regexp(r"^admin:billing:ref:\d+$"))
async def admin_billing_referral(callback: CallbackQuery, session: AsyncSession) -> None:
    if callback.data is None or not isinstance(callback.message, Message):
        return
    days = int(callback.data.rsplit(":", maxsplit=1)[-1])
    billing = await update_billing_settings(session, referral_bonus_days=days)
    await callback.answer(f"+{days} дн.")
    await callback.message.edit_text(
        format_billing_admin(billing, token_set=bool(billing.cryptopay_api_token), giveaway=await get_active_giveaway(session)),
        reply_markup=billing_admin_keyboard(billing),
    )


@router.callback_query(F.data.startswith("admin:billing:toggle:"))
async def admin_billing_toggle(callback: CallbackQuery, session: AsyncSession) -> None:
    if callback.data is None or not isinstance(callback.message, Message):
        return
    key = callback.data.rsplit(":", maxsplit=1)[-1]
    billing = await get_billing_settings(session)
    mapping = {
        "testnet": ("cryptopay_testnet", not billing.cryptopay_testnet),
        "vip": ("require_subscription_for_signals", not billing.require_subscription_for_signals),
        "discount": ("discount_enabled", not billing.discount_enabled),
    }
    field, value = mapping[key]
    billing = await update_billing_settings(session, **{field: value})
    await callback.answer("Обновлено")
    await callback.message.edit_text(
        format_billing_admin(billing, token_set=bool(billing.cryptopay_api_token), giveaway=await get_active_giveaway(session)),
        reply_markup=billing_admin_keyboard(billing),
    )


@router.callback_query(F.data == "admin:billing:giveaway:new")
async def admin_giveaway_new(callback: CallbackQuery, session: AsyncSession) -> None:
    if not isinstance(callback.message, Message):
        return
    row = await create_giveaway(
        session,
        title="Подписка BTC Bot",
        prize_days=30,
        winners_count=3,
        extra_discount_percent=15.0,
        duration_days=7,
    )
    await callback.answer("Розыгрыш запущен")
    billing = await get_billing_settings(session)
    await callback.message.edit_text(
        format_billing_admin(billing, token_set=bool(billing.cryptopay_api_token), giveaway=row),
        reply_markup=billing_admin_keyboard(billing),
    )


@router.callback_query(F.data == "admin:billing:giveaway:draw")
async def admin_giveaway_draw(callback: CallbackQuery, session: AsyncSession) -> None:
    if callback.message is None or callback.message.bot is None:
        return
    giveaway = await get_active_giveaway(session)
    if giveaway is None:
        await callback.answer("Нет активного розыгрыша", show_alert=True)
        return
    entries = await list_giveaway_entries(session, giveaway.id)
    if not entries:
        await callback.answer("Нет участников", show_alert=True)
        return
    winners = random.sample(entries, k=min(giveaway.winners_count, len(entries)))
    billing = await get_billing_settings(session)
    from app.database.billing_repositories import extend_subscription

    for entry in winners:
        user = await session.get(User, entry.user_id)
        if user is None:
            continue
        await extend_subscription(session, user, giveaway.prize_days)
        try:
            await callback.message.bot.send_message(
                user.tg_id,
                f"🏆 <b>Вы выиграли розыгрыш!</b>\n\n"
                f"+{giveaway.prize_days} дн. подписки начислено автоматически.",
            )
        except Exception:
            pass
    await finish_giveaway(session, giveaway)
    await callback.answer(f"Победителей: {len(winners)}")
    billing = await get_billing_settings(session)
    await callback.message.answer(
        f"✅ Розыгрыш завершён. Победителей: <b>{len(winners)}</b>",
        reply_markup=admin_home_keyboard(),
    )
