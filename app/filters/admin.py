from typing import Any

from aiogram.filters import Filter
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.config import Settings
from app.database.repositories import is_admin


class AdminFilter(Filter):
    async def __call__(self, event: TelegramObject, settings: Settings) -> bool:
        actor = None
        if isinstance(event, (Message, CallbackQuery)):
            actor = event.from_user
        if actor is None:
            return False
        return await is_admin(actor.id, settings.parsed_admin_ids)
