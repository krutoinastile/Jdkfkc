from aiogram.types import Message


def extract_message_payload(message: Message) -> dict[str, object]:
    text = message.text
    caption = message.caption
    content_type = message.content_type
    media_file_id: str | None = None

    if message.photo:
        media_file_id = message.photo[-1].file_id
    elif message.video:
        media_file_id = message.video.file_id
    elif message.document:
        media_file_id = message.document.file_id
    elif message.voice:
        media_file_id = message.voice.file_id
    elif message.video_note:
        media_file_id = message.video_note.file_id
    elif message.audio:
        media_file_id = message.audio.file_id
    elif message.sticker:
        media_file_id = message.sticker.file_id
    elif message.animation:
        media_file_id = message.animation.file_id

    from_user = message.from_user
    chat = message.chat

    return {
        "message_id": message.message_id,
        "chat_id": chat.id,
        "chat_type": chat.type,
        "chat_title": chat.title or chat.full_name,
        "chat_username": chat.username,
        "from_user_id": from_user.id if from_user else None,
        "from_username": from_user.username if from_user else None,
        "from_first_name": from_user.first_name if from_user else None,
        "text": text,
        "caption": caption,
        "content_type": content_type,
        "media_file_id": media_file_id,
        "has_media_spoiler": bool(message.has_media_spoiler),
        "sent_at": message.date,
    }


def format_user_label(username: str | None, first_name: str | None, user_id: int | None) -> str:
    if username:
        return f"@{username}"
    if first_name:
        return first_name
    if user_id:
        return f"ID {user_id}"
    return "Неизвестный отправитель"


def format_dialog_label(title: str | None, username: str | None, chat_id: int) -> str:
    if title:
        return title
    if username:
        return f"@{username}"
    return f"Чат {chat_id}"


def format_message_preview(stored_text: str | None, stored_caption: str | None, content_type: str) -> str:
    body = stored_text or stored_caption
    if body:
        preview = body.replace("\n", " ")
        if len(preview) > 120:
            return preview[:117] + "..."
        return preview
    return f"[{content_type}]"
