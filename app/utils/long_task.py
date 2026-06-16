"""User-visible progress for long-running bot handlers."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from aiogram.enums import ChatAction
from aiogram.types import Message


@asynccontextmanager
async def show_progress(message: Message, text: str = "⏳ Обрабатываю...") -> AsyncIterator[Message]:
    """Send status text + typing indicator while work runs."""
    bot = message.bot
    chat_id = message.chat.id
    status = await message.answer(text)

    async def _typing_loop() -> None:
        if bot is None:
            return
        try:
            while True:
                await bot.send_chat_action(chat_id, ChatAction.TYPING)
                await asyncio.sleep(4)
        except asyncio.CancelledError:
            return
        except Exception:
            return

    task = asyncio.create_task(_typing_loop())
    try:
        yield status
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task
        with contextlib.suppress(Exception):
            await status.delete()
