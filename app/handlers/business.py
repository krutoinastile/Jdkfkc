import logging

from aiogram import Bot, Router
from aiogram.types import BusinessConnection, BusinessMessagesDeleted, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.database.repositories import (
    activate_trial,
    get_connection_by_external_id,
    get_or_create_account,
    get_or_create_dialog,
    get_stored_message,
    is_subscription_active,
    mark_messages_deleted,
    record_message_edit,
    store_business_message,
    upsert_business_connection,
)
from app.services.notifications import (
    build_deleted_notification,
    build_edited_notification,
    build_new_message_notification,
    notify_owner,
)
from app.utils.message import extract_message_payload

logger = logging.getLogger(__name__)

router = Router(name="business")


@router.business_connection()
async def business_connection_handler(
    connection: BusinessConnection,
    session: AsyncSession,
    settings: Settings,
    bot: Bot,
) -> None:
    account = await get_or_create_account(
        session,
        connection.user.id,
        connection.user.username,
        connection.user.first_name,
    )
    if account.subscription_until is None and not account.trial_used:
        await activate_trial(session, account, settings.trial_days)

    rights_json = connection.rights.model_dump_json() if connection.rights else None
    stored_connection = await upsert_business_connection(
        session,
        account,
        connection.id,
        connection.user_chat_id,
        connection.is_enabled,
        connection.can_reply,
        rights_json,
    )

    if connection.is_enabled:
        text = (
            "✅ <b>Бизнес-подключение активно</b>\n\n"
            "Бот начнёт сохранять входящие сообщения, удаления и правки."
        )
    else:
        text = "⚠️ <b>Бизнес-подключение отключено</b>\n\nМониторинг приостановлен."

    await bot.send_message(chat_id=connection.user_chat_id, text=text)
    logger.info(
        "Business connection updated: account=%s enabled=%s connection=%s",
        account.tg_id,
        stored_connection.is_enabled,
        stored_connection.connection_id,
    )


async def _ensure_active_subscription(
    session: AsyncSession,
    connection_id: str,
    settings: Settings,
) -> tuple | None:
    connection = await get_connection_by_external_id(session, connection_id)
    if connection is None or not connection.is_enabled:
        return None
    account = connection.account
    if not is_subscription_active(account):
        return None
    return connection, account


@router.business_message()
async def business_message_handler(message: Message, session: AsyncSession, settings: Settings, bot: Bot) -> None:
    if message.business_connection_id is None:
        return

    ctx = await _ensure_active_subscription(session, message.business_connection_id, settings)
    if ctx is None:
        return
    connection, account = ctx

    payload = extract_message_payload(message)
    dialog = await get_or_create_dialog(
        session,
        connection,
        int(payload["chat_id"]),
        str(payload["chat_type"]),
        str(payload["chat_title"]) if payload["chat_title"] else None,
        str(payload["chat_username"]) if payload["chat_username"] else None,
    )
    stored = await store_business_message(
        session,
        connection,
        dialog,
        message_id=int(payload["message_id"]),
        chat_id=int(payload["chat_id"]),
        from_user_id=int(payload["from_user_id"]) if payload["from_user_id"] else None,
        from_username=str(payload["from_username"]) if payload["from_username"] else None,
        from_first_name=str(payload["from_first_name"]) if payload["from_first_name"] else None,
        text=str(payload["text"]) if payload["text"] else None,
        caption=str(payload["caption"]) if payload["caption"] else None,
        content_type=str(payload["content_type"]),
        media_file_id=str(payload["media_file_id"]) if payload["media_file_id"] else None,
        has_media_spoiler=bool(payload["has_media_spoiler"]),
        sent_at=message.date,
    )

    if account.notify_new:
        text = build_new_message_notification(stored, dialog.title, dialog.username)
        await notify_owner(bot, account, connection.user_chat_id, text, stored)


@router.edited_business_message()
async def edited_business_message_handler(
    message: Message,
    session: AsyncSession,
    settings: Settings,
    bot: Bot,
) -> None:
    if message.business_connection_id is None:
        return

    ctx = await _ensure_active_subscription(session, message.business_connection_id, settings)
    if ctx is None:
        return
    connection, account = ctx

    stored = await get_stored_message(session, connection.id, message.chat.id, message.message_id)
    payload = extract_message_payload(message)
    dialog = await get_or_create_dialog(
        session,
        connection,
        message.chat.id,
        message.chat.type,
        message.chat.title or message.chat.full_name,
        message.chat.username,
    )

    old_text = stored.text if stored else None
    old_caption = stored.caption if stored else None
    new_text = str(payload["text"]) if payload["text"] else None
    new_caption = str(payload["caption"]) if payload["caption"] else None

    if stored is None:
        stored = await store_business_message(
            session,
            connection,
            dialog,
            message_id=message.message_id,
            chat_id=message.chat.id,
            from_user_id=message.from_user.id if message.from_user else None,
            from_username=message.from_user.username if message.from_user else None,
            from_first_name=message.from_user.first_name if message.from_user else None,
            text=new_text,
            caption=new_caption,
            content_type=str(payload["content_type"]),
            media_file_id=str(payload["media_file_id"]) if payload["media_file_id"] else None,
            has_media_spoiler=bool(payload["has_media_spoiler"]),
            sent_at=message.date,
        )
    else:
        await record_message_edit(
            session,
            stored,
            old_text=old_text,
            old_caption=old_caption,
            new_text=new_text,
            new_caption=new_caption,
        )

    if account.notify_edit:
        text = build_edited_notification(
            stored,
            dialog.title,
            dialog.username,
            old_text,
            old_caption,
            new_text,
            new_caption,
        )
        await notify_owner(bot, account, connection.user_chat_id, text, stored)


@router.deleted_business_messages()
async def deleted_business_messages_handler(
    event: BusinessMessagesDeleted,
    session: AsyncSession,
    settings: Settings,
    bot: Bot,
) -> None:
    ctx = await _ensure_active_subscription(session, event.business_connection_id, settings)
    if ctx is None:
        return
    connection, account = ctx

    deleted_messages = await mark_messages_deleted(
        session,
        connection.id,
        event.chat.id,
        list(event.message_ids),
    )
    if not account.notify_delete:
        return

    for stored in deleted_messages:
        dialog_result = stored.dialog
        text = build_deleted_notification(stored, dialog_result.title, dialog_result.username)
        await notify_owner(bot, account, connection.user_chat_id, text, stored)

    if not deleted_messages and account.notify_delete:
        await notify_owner(
            bot,
            account,
            connection.user_chat_id,
            f"🗑 В диалоге {event.chat.id} удалены сообщения {event.message_ids}, "
            "но их копии не были сохранены ранее.",
        )
