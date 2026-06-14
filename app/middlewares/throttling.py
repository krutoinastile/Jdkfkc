import time
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject


class ThrottlingMiddleware(BaseMiddleware):
    """Simple in-memory rate limit per Telegram user."""

    def __init__(self, rate_limit_seconds: float) -> None:
        self.rate_limit_seconds = rate_limit_seconds
        self._last_seen: dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        actor = getattr(event, "from_user", None)
        if actor is None:
            return await handler(event, data)

        now = time.monotonic()
        last_seen = self._last_seen.get(actor.id, 0.0)
        if now - last_seen < self.rate_limit_seconds:
            await self._notify_rate_limited(event)
            return None

        self._last_seen[actor.id] = now
        self._cleanup(now)
        return await handler(event, data)

    async def _notify_rate_limited(self, event: TelegramObject) -> None:
        text = "Слишком много действий подряд. Попробуйте через пару секунд."
        if isinstance(event, CallbackQuery):
            await event.answer(text, show_alert=False)
        elif isinstance(event, Message):
            await event.answer(text)

    def _cleanup(self, now: float) -> None:
        stale_after = max(self.rate_limit_seconds * 10, 30.0)
        stale_users = [user_id for user_id, seen_at in self._last_seen.items() if now - seen_at > stale_after]
        for user_id in stale_users:
            self._last_seen.pop(user_id, None)
