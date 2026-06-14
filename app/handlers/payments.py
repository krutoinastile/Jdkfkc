import logging

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, Message, PreCheckoutQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories import (
    create_payment_record,
    extend_subscription,
    get_account_by_id,
    get_account_by_tg_id,
    get_or_create_account,
    get_payment_by_charge_id,
    get_payment_settings,
)
from app.services.payments import format_price, send_subscription_invoice
from app.utils.text import subscription_status_text

logger = logging.getLogger(__name__)

router = Router(name="payments")


@router.callback_query(F.data == "pay:subscription")
async def pay_subscription(callback: CallbackQuery, session: AsyncSession, bot: Bot) -> None:
    if callback.from_user is None:
        return

    account = await get_or_create_account(
        session,
        callback.from_user.id,
        callback.from_user.username,
        callback.from_user.first_name,
    )
    payment_settings = await get_payment_settings(session)

    if not payment_settings.is_enabled:
        await callback.answer("Оплата временно недоступна.", show_alert=True)
        return

    try:
        await send_subscription_invoice(bot, callback.from_user.id, account, payment_settings)
        await callback.answer()
    except ValueError as exc:
        if str(exc) == "provider_token_required":
            await callback.answer(
                "Платёжный token не настроен. Обратитесь к администратору.",
                show_alert=True,
            )
        else:
            await callback.answer("Не удалось создать счёт.", show_alert=True)
        logger.exception("Failed to send invoice")


@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout: PreCheckoutQuery, session: AsyncSession) -> None:
    payment_settings = await get_payment_settings(session)
    payload = pre_checkout.invoice_payload

    if not payload.startswith("subscription:"):
        await pre_checkout.answer(ok=False, error_message="Некорректный платёж.")
        return

    try:
        account_id = int(payload.split(":")[1])
    except (IndexError, ValueError):
        await pre_checkout.answer(ok=False, error_message="Некорректный платёж.")
        return

    account = await get_account_by_id(session, account_id)
    if account is None or account.tg_id != pre_checkout.from_user.id:
        await pre_checkout.answer(ok=False, error_message="Платёж не привязан к вашему аккаунту.")
        return

    if not payment_settings.is_enabled:
        await pre_checkout.answer(ok=False, error_message="Оплата временно недоступна.")
        return

    if (
        pre_checkout.currency != payment_settings.currency
        or pre_checkout.total_amount != payment_settings.price_amount
    ):
        await pre_checkout.answer(
            ok=False,
            error_message="Сумма изменилась. Откройте раздел «Подписка» заново.",
        )
        return

    await pre_checkout.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment_handler(message: Message, session: AsyncSession) -> None:
    if message.from_user is None or message.successful_payment is None:
        return

    payment = message.successful_payment
    if await get_payment_by_charge_id(session, payment.telegram_payment_charge_id):
        await message.answer("Этот платёж уже был обработан ранее.")
        return

    payload = payment.invoice_payload
    try:
        account_id = int(payload.split(":")[1])
    except (IndexError, ValueError):
        await message.answer("Ошибка обработки платежа. Обратитесь в поддержку.")
        return

    account = await get_account_by_id(session, account_id)
    if account is None or account.tg_id != message.from_user.id:
        await message.answer("Ошибка обработки платежа. Обратитесь в поддержку.")
        return

    payment_settings = await get_payment_settings(session)
    await create_payment_record(
        session,
        account_id=account.id,
        telegram_payment_charge_id=payment.telegram_payment_charge_id,
        payload=payload,
        currency=payment.currency,
        total_amount=payment.total_amount,
        subscription_days=payment_settings.subscription_days,
    )
    account = await extend_subscription(session, account, payment_settings.subscription_days)

    await message.answer(
        "✅ <b>Оплата прошла успешно!</b>\n\n"
        f"Подписка продлена на {payment_settings.subscription_days} дн.\n"
        f"{subscription_status_text(account)}"
    )
