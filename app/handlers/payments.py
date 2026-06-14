import logging

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, Message, PreCheckoutQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories import (
    create_payment_record,
    extend_subscription,
    get_account_by_id,
    get_or_create_account,
    get_payment_by_charge_id,
    get_payment_settings,
)
from app.keyboards.payments import crypto_pay_keyboard
from app.services.crypto_payments import (
    check_crypto_invoice_by_id,
    create_crypto_subscription_invoice,
)
from app.services.payments import send_subscription_invoice
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

    if payment_settings.currency == "CRYPTO":
        try:
            invoice = await create_crypto_subscription_invoice(session, account, payment_settings)
        except ValueError as exc:
            if str(exc) == "crypto_token_required":
                await callback.answer("Crypto Pay API не настроен.", show_alert=True)
            else:
                await callback.answer("Не удалось создать счёт.", show_alert=True)
            return

        if not invoice.pay_url:
            await callback.answer("Не получена ссылка на оплату.", show_alert=True)
            return

        await callback.answer()
        if isinstance(callback.message, Message):
            await callback.message.answer(
                "🪙 <b>Оплата через Crypto Pay</b>\n\n"
                f"Сумма: <b>{invoice.amount} {invoice.asset}</b>\n"
                f"Срок подписки: <b>{payment_settings.subscription_days} дн.</b>\n\n"
                "Нажмите «Перейти к оплате», затем «Проверить оплату» после перевода.",
                reply_markup=crypto_pay_keyboard(invoice.pay_url, invoice.crypto_invoice_id),
            )
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


@router.callback_query(F.data.regexp(r"^pay:crypto:check:\d+$"))
async def check_crypto_payment(callback: CallbackQuery, session: AsyncSession, bot: Bot) -> None:
    if callback.from_user is None or callback.data is None:
        return

    crypto_invoice_id = int(callback.data.rsplit(":", maxsplit=1)[-1])
    result = await check_crypto_invoice_by_id(
        session,
        bot,
        crypto_invoice_id=crypto_invoice_id,
        user_tg_id=callback.from_user.id,
    )

    if result == "not_found":
        await callback.answer("Счёт не найден.", show_alert=True)
        return
    if result == "forbidden":
        await callback.answer("Этот счёт принадлежит другому пользователю.", show_alert=True)
        return
    if result == "already_paid":
        await callback.answer("Оплата уже была зачислена.", show_alert=True)
        return
    if result == "paid":
        payment_settings = await get_payment_settings(session)
        await callback.answer("Оплата подтверждена!", show_alert=True)
        if isinstance(callback.message, Message):
            account = await get_or_create_account(
                session,
                callback.from_user.id,
                callback.from_user.username,
                callback.from_user.first_name,
            )
            await callback.message.answer(
                "✅ <b>Крипто-оплата прошла успешно!</b>\n\n"
                f"Подписка продлена на {payment_settings.subscription_days} дн.\n"
                f"{subscription_status_text(account)}",
            )
        return

    await callback.answer("Оплата ещё не поступила. Попробуйте через минуту.", show_alert=True)


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
