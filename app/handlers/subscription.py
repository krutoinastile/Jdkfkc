"""User subscription and payment handlers."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.database.billing_repositories import (
    enter_giveaway,
    get_active_giveaway,
    get_billing_settings,
    is_subscription_active,
)
from app.database.repositories import get_or_create_user
from app.keyboards.billing import subscription_keyboard, subscription_pay_keyboard
from app.services.cryptopay import CryptoPayError
from app.services.subscription import (
    calculate_subscription_price,
    create_subscription_invoice,
    get_giveaway_stats,
    get_referral_stats,
    poll_pending_invoices,
)
from app.utils.billing_messages import format_subscription_page

logger = logging.getLogger(__name__)

router = Router(name="subscription")


async def _bot_username(message: Message) -> str:
    if message.bot is None:
        return "bot"
    me = await message.bot.get_me()
    return me.username or "bot"


async def _show_subscription(message: Message, session: AsyncSession, settings: Settings) -> None:
    if message.from_user is None:
        return
    user = await get_or_create_user(session, message.from_user.id, message.from_user.username)
    billing = await get_billing_settings(session)
    giveaway_info = await get_giveaway_stats(session)
    stats = await get_referral_stats(session, user)
    price = calculate_subscription_price(
        billing,
        has_referral=user.referrer_id is not None,
        giveaway=giveaway_info["giveaway"] if giveaway_info else None,
    )
    entered = False
    if giveaway_info:
        from sqlalchemy import select
        from app.database.models import GiveawayEntry

        result = await session.execute(
            select(GiveawayEntry)
            .where(GiveawayEntry.giveaway_id == giveaway_info["giveaway"].id)
            .where(GiveawayEntry.user_id == user.id)
        )
        entered = result.scalar_one_or_none() is not None

    text = format_subscription_page(
        user,
        billing,
        price=price,
        bot_username=await _bot_username(message),
        referral_stats=stats,
        giveaway_info=giveaway_info,
    )
    code = user.referral_code or ""
    referral_link = f"https://t.me/{await _bot_username(message)}?start=ref_{code}" if code else None
    await message.answer(
        text,
        reply_markup=subscription_keyboard(
            has_active=is_subscription_active(user),
            has_giveaway=giveaway_info is not None,
            entered_giveaway=entered,
            referral_link=referral_link,
        ),
    )


@router.callback_query(F.data == "menu:subscription")
async def menu_subscription(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await callback.answer()
    if not isinstance(callback.message, Message):
        return
    await _show_subscription(callback.message, session, settings)


@router.callback_query(F.data == "sub:pay")
async def subscription_pay(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    if callback.from_user is None or not isinstance(callback.message, Message):
        return
    user = await get_or_create_user(session, callback.from_user.id, callback.from_user.username)
    billing = await get_billing_settings(session)
    if not billing.cryptopay_api_token:
        await callback.message.answer(
            "⚠️ Оплата временно недоступна.\nАдминистратор ещё не настроил Crypto Pay.",
        )
        return
    try:
        pay_url, _ = await create_subscription_invoice(session, user)
    except CryptoPayError as exc:
        logger.exception("Failed to create subscription invoice")
        await callback.message.answer(f"❌ Не удалось создать счёт: {exc}")
        return
    except Exception:
        logger.exception("Unexpected error creating subscription invoice")
        await callback.message.answer("❌ Ошибка при создании счёта. Попробуйте позже.")
        return
    if not pay_url:
        await callback.message.answer("❌ Crypto Pay не вернул ссылку на оплату. Проверьте token в админке.")
        return
    await callback.message.answer(
        "💳 <b>Счёт создан</b>\n\nОплатите в Crypto Bot. После оплаты нажмите «Проверить оплату».",
        reply_markup=subscription_pay_keyboard(pay_url),
    )


@router.callback_query(F.data == "sub:check")
async def subscription_check(callback: CallbackQuery, session: AsyncSession) -> None:
    if callback.message is None or callback.message.bot is None:
        return
    await callback.answer("Проверяю...")
    await poll_pending_invoices(session, callback.message.bot)
    if callback.from_user is None:
        return
    user = await get_or_create_user(session, callback.from_user.id, callback.from_user.username)
    if is_subscription_active(user):
        await callback.message.answer("✅ Оплата подтверждена! Подписка активна.")
    else:
        await callback.message.answer("⏳ Оплата пока не найдена. Если уже оплатили — подождите минуту и проверьте снова.")


@router.callback_query(F.data == "sub:referral")
async def subscription_referral(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    if callback.from_user is None or not isinstance(callback.message, Message):
        return
    user = await get_or_create_user(session, callback.from_user.id, callback.from_user.username)
    if callback.message.bot is None:
        return
    me = await callback.message.bot.get_me()
    code = user.referral_code or "—"
    link = f"https://t.me/{me.username}?start=ref_{code}"
    await callback.message.answer(
        f"📋 <b>Ваша реферальная ссылка</b>\n\n<code>{link}</code>\n\n"
        f"<i>Друг получит скидку, вы — бонусные дни подписки.</i>"
    )


@router.callback_query(F.data == "sub:giveaway:enter")
async def subscription_giveaway_enter(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    if callback.from_user is None or not isinstance(callback.message, Message):
        return
    giveaway = await get_active_giveaway(session)
    if giveaway is None:
        await callback.message.answer("Розыгрыш уже завершён.")
        return
    user = await get_or_create_user(session, callback.from_user.id, callback.from_user.username)
    await enter_giveaway(session, giveaway, user)
    await callback.message.answer(
        f"🎁 Вы участвуете в розыгрыше «{giveaway.title}»!\n"
        f"Победители получат <b>{giveaway.prize_days}</b> дн. подписки.",
    )
