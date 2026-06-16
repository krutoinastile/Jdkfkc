"""Admin Telegram alerts — loss streaks, drawdown, health failures."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.database.models import Signal, TradeStatus
from app.database.repositories import get_statistics, list_closed_signals
from app.utils.leverage import DEFAULT_BANK_ALLOCATION_PCT, pnl_on_bank

logger = logging.getLogger(__name__)

LOSS_STREAK_THRESHOLD = 3
WEEKLY_DRAWDOWN_THRESHOLD = 12.0
_streak_notified_at: datetime | None = None
_drawdown_notified_at: datetime | None = None
_health_fail_count = 0


async def _recent_closed(session: AsyncSession, *, limit: int = 10) -> list[Signal]:
    result = await session.execute(
        select(Signal)
        .where(Signal.status.in_((TradeStatus.WIN.value, TradeStatus.LOSS.value)))
        .where(Signal.pnl_percent.is_not(None))
        .order_by(Signal.closed_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def _notify_admins(bot: Bot, settings: Settings, text: str) -> None:
    for admin_id in settings.parsed_admin_ids:
        try:
            await bot.send_message(chat_id=admin_id, text=text)
        except Exception:
            logger.exception("Admin alert failed for %s", admin_id)


async def on_trade_closed(
    session: AsyncSession,
    bot: Bot,
    settings: Settings,
    signal: Signal,
) -> None:
    global _streak_notified_at

    if signal.status != TradeStatus.LOSS.value:
        return

    recent = await _recent_closed(session, limit=LOSS_STREAK_THRESHOLD)
    if len(recent) < LOSS_STREAK_THRESHOLD:
        return
    if not all(s.status == TradeStatus.LOSS.value for s in recent):
        return

    now = datetime.now(tz=UTC)
    if _streak_notified_at and (now - _streak_notified_at) < timedelta(hours=6):
        return
    _streak_notified_at = now

    ids = ", ".join(f"#{s.id}" for s in reversed(recent))
    total_pnl = sum(s.pnl_percent or 0 for s in recent)
    await _notify_admins(
        bot,
        settings,
        (
            f"⚠️ <b>Серия убытков</b>\n\n"
            f"Подряд <b>{LOSS_STREAK_THRESHOLD}</b> LOSS: {ids}\n"
            f"Суммарный P&L: <b>{total_pnl:+.1f}%</b> (маржа)\n\n"
            f"<i>Проверьте рынок и настройки стратегии.</i>"
        ),
    )


async def check_weekly_drawdown(
    session: AsyncSession,
    bot: Bot,
    settings: Settings,
) -> None:
    global _drawdown_notified_at

    closed = await list_closed_signals(session, days=7, limit=200)
    if len(closed) < 3:
        return

    capital = 1000.0
    peak = capital
    max_dd = 0.0
    for s in closed:
        if s.pnl_percent is None:
            continue
        bank_pnl = pnl_on_bank(s.pnl_percent, DEFAULT_BANK_ALLOCATION_PCT)
        capital *= 1 + bank_pnl / 100
        peak = max(peak, capital)
        if peak > 0:
            max_dd = max(max_dd, (peak - capital) / peak * 100)

    if max_dd < WEEKLY_DRAWDOWN_THRESHOLD:
        return

    now = datetime.now(tz=UTC)
    if _drawdown_notified_at and (now - _drawdown_notified_at) < timedelta(days=3):
        return
    _drawdown_notified_at = now

    await _notify_admins(
        bot,
        settings,
        (
            f"📉 <b>Просадка за 7 дней</b>\n\n"
            f"Max drawdown: <b>{max_dd:.1f}%</b> (банк 10%)\n"
            f"Сделок: <b>{len(closed)}</b>\n\n"
            f"<i>Порог алерта: {WEEKLY_DRAWDOWN_THRESHOLD:g}%</i>"
        ),
    )


async def on_health_check_failed(
    bot: Bot,
    settings: Settings,
    *,
    error: str,
) -> None:
    global _health_fail_count

    _health_fail_count += 1
    if _health_fail_count < 2:
        return

    await _notify_admins(
        bot,
        settings,
        (
            f"🚨 <b>Бот не отвечает</b>\n\n"
            f"Health check провалился {_health_fail_count}× подряд.\n"
            f"<code>{error[:200]}</code>\n\n"
            f"<i>Проверьте supervisor и логи.</i>"
        ),
    )


def on_health_check_ok() -> None:
    global _health_fail_count
    _health_fail_count = 0
