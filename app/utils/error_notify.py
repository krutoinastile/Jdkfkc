"""Notify Telegram users when handlers fail."""

from __future__ import annotations

import contextlib
import logging

from aiogram import Bot
from aiogram.types import Update

logger = logging.getLogger(__name__)

_USER_ERROR_TEXT = (
    "⚠️ <b>Временная ошибка</b>\n\n"
    "Бот не завис — попробуйте ещё раз через пару секунд.\n"
    "Если повторяется, отправьте /start."
)


async def notify_user_about_error(update: Update, bot: Bot) -> None:
    try:
        if update.callback_query is not None:
            cq = update.callback_query
            with contextlib.suppress(Exception):
                await cq.answer("Ошибка — попробуйте снова")
            if cq.message is not None:
                await bot.send_message(cq.message.chat.id, _USER_ERROR_TEXT)
            return
        if update.message is not None:
            await update.message.answer(_USER_ERROR_TEXT)
    except Exception:
        logger.exception("Failed to notify user about handler error")
