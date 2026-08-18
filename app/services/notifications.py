import logging

from aiogram import Bot
from aiogram.types import FSInputFile, InputMediaPhoto, InputMediaVideo
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Account, StoredMessage
from app.utils.message import format_dialog_label, format_message_preview, format_user_label

logger = logging.getLogger(__name__)


async def notify_owner(
    bot: Bot,
    account: Account,
    connection_user_chat_id: int,
    text: str,
    stored: StoredMessage | None = None,
) -> None:
    try:
        if stored and stored.media_file_id:
            if stored.content_type == "photo":
                await bot.send_photo(
                    chat_id=connection_user_chat_id,
                    photo=stored.media_file_id,
                    caption=text,
                )
                return
            if stored.content_type == "video":
                await bot.send_video(
                    chat_id=connection_user_chat_id,
                    video=stored.media_file_id,
                    caption=text,
                )
                return
            if stored.content_type == "document":
                await bot.send_document(
                    chat_id=connection_user_chat_id,
                    document=stored.media_file_id,
                    caption=text,
                )
                return
            if stored.content_type == "voice":
                await bot.send_voice(
                    chat_id=connection_user_chat_id,
                    voice=stored.media_file_id,
                    caption=text,
                )
                return
            if stored.content_type == "video_note":
                await bot.send_video_note(
                    chat_id=connection_user_chat_id,
                    video_note=stored.media_file_id,
                )
                await bot.send_message(chat_id=connection_user_chat_id, text=text)
                return

        await bot.send_message(chat_id=connection_user_chat_id, text=text)
    except Exception:
        logger.exception("Failed to notify owner %s", account.tg_id)


def build_new_message_notification(stored: StoredMessage, dialog_title: str | None, dialog_username: str | None) -> str:
    dialog = format_dialog_label(dialog_title, dialog_username, stored.chat_id)
    sender = format_user_label(stored.from_username, stored.from_first_name, stored.from_user_id)
    preview = format_message_preview(stored.text, stored.caption, stored.content_type)
    spoiler = " (скрытое медиа)" if stored.has_media_spoiler else ""
    return (
        f"📩 <b>Новое сообщение</b>{spoiler}\n"
        f"Диалог: {dialog}\n"
        f"От: {sender}\n\n"
        f"{preview}"
    )


def build_deleted_notification(stored: StoredMessage, dialog_title: str | None, dialog_username: str | None) -> str:
    dialog = format_dialog_label(dialog_title, dialog_username, stored.chat_id)
    sender = format_user_label(stored.from_username, stored.from_first_name, stored.from_user_id)
    preview = format_message_preview(stored.text, stored.caption, stored.content_type)
    return (
        f"🗑 <b>Удалено сообщение</b>\n"
        f"Диалог: {dialog}\n"
        f"От: {sender}\n\n"
        f"Сохранённый текст:\n{preview}"
    )


def build_edited_notification(
    stored: StoredMessage,
    dialog_title: str | None,
    dialog_username: str | None,
    old_text: str | None,
    old_caption: str | None,
    new_text: str | None,
    new_caption: str | None,
) -> str:
    dialog = format_dialog_label(dialog_title, dialog_username, stored.chat_id)
    sender = format_user_label(stored.from_username, stored.from_first_name, stored.from_user_id)
    old_body = old_text or old_caption or "—"
    new_body = new_text or new_caption or "—"
    return (
        f"✏️ <b>Изменено сообщение</b>\n"
        f"Диалог: {dialog}\n"
        f"От: {sender}\n\n"
        f"<b>Было:</b>\n{old_body}\n\n"
        f"<b>Стало:</b>\n{new_body}"
    )


async def notify_admins_text(bot: Bot, admin_ids: list[int], text: str) -> None:
    for admin_id in admin_ids:
        try:
            await bot.send_message(chat_id=admin_id, text=text)
        except Exception:
            logger.exception("Failed to notify admin %s", admin_id)
