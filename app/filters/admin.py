from typing import Any

from aiogram.filters import Filter
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.database.repositories import is_admin


class AdminFilter(Filter):
    async def __call__(
        self,
        event: TelegramObject,
        session: AsyncSession,
        settings: Settings,
    ) -> bool:
        actor: Any
        if isinstance(event, Message):
            actor = event.from_user
        elif isinstance(event, CallbackQuery):
            actor = event.from_user
        else:
            actor = getattr(event, "from_user", None)

        if actor is None:
            return False
        return await is_admin(session, actor.id, settings.parsed_admin_ids)
