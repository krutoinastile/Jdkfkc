"""Periodic funding rate monitor with user alerts."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.database.repositories import get_strategy_settings, list_users_notify_funding
from app.services.funding import fetch_funding_rate, is_extreme_funding
from app.utils.messages import format_funding_alert

logger = logging.getLogger(__name__)

_last_alert_at: datetime | None = None
_last_alert_rate: float | None = None
COOLDOWN = timedelta(hours=4)


async def check_funding_rate(
    session: AsyncSession,
    settings: Settings,
    bot: Bot,
) -> None:
    global _last_alert_at, _last_alert_rate

    cfg = await get_strategy_settings(session)
    if not cfg.funding_alerts_enabled:
        return

    funding = await fetch_funding_rate(settings.symbol)
    if funding is None:
        return

    rate_pct = funding["rate_pct"]
    if not is_extreme_funding(rate_pct, cfg.min_funding_rate_pct):
        return

    now = datetime.now(tz=UTC)
    if _last_alert_at and now - _last_alert_at < COOLDOWN:
        if _last_alert_rate is not None and abs(rate_pct - _last_alert_rate) < cfg.min_funding_rate_pct * 0.5:
            return

    text = format_funding_alert(funding)
    users = await list_users_notify_funding(session)
    if not users:
        return

    for user in users:
        try:
            await bot.send_message(chat_id=user.tg_id, text=text)
        except Exception:
            logger.exception("Failed to send funding alert to %s", user.tg_id)

    _last_alert_at = now
    _last_alert_rate = rate_pct
    logger.info("Funding alert sent: %.4f%% to %d users", rate_pct, len(users))


def setup_funding_scheduler(session_pool: async_sessionmaker[AsyncSession], bot: Bot, settings: Settings):
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    scheduler = AsyncIOScheduler()

    async def funding_job() -> None:
        async with session_pool() as session:
            try:
                await check_funding_rate(session, settings, bot)
            except Exception:
                logger.exception("Funding check job failed")

    scheduler.add_job(funding_job, "interval", minutes=30, id="funding_check")
    return scheduler
