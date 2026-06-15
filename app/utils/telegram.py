"""Telegram send helpers."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from aiogram.types import BufferedInputFile, InlineKeyboardMarkup, Message

from app.services.chart import render_chart
from app.services.market_data import Candle

if TYPE_CHECKING:
    from app.database.models import Signal
    from app.services.strategy_config import StrategyConfig

logger = logging.getLogger(__name__)


async def answer_with_chart(
    message: Message,
    caption: str,
    candles: list[Candle],
    cfg: StrategyConfig,
    *,
    signal: Signal | None = None,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    try:
        chart_bytes = await asyncio.to_thread(render_chart, candles, cfg, signal)
        photo = BufferedInputFile(chart_bytes, filename="btc_chart.png")
        await message.answer_photo(photo=photo, caption=caption, reply_markup=reply_markup)
    except Exception:
        logger.exception("Chart render failed, sending text only")
        await message.answer(caption, reply_markup=reply_markup)
