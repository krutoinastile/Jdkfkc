"""Telegram send helpers."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from aiogram import Bot
from aiogram.enums import ChatAction
from aiogram.types import BufferedInputFile, InlineKeyboardMarkup, Message

from app.services.chart import render_chart
from app.services.market_data import Candle

if TYPE_CHECKING:
    from app.database.models import Signal
    from app.services.strategy_config import StrategyConfig

logger = logging.getLogger(__name__)


async def send_signal_chart(
    bot: Bot,
    chat_id: int,
    caption: str,
    candles: list[Candle],
    cfg: StrategyConfig,
    signal: Signal,
) -> None:
    try:
        await bot.send_chat_action(chat_id, ChatAction.UPLOAD_PHOTO)
        chart_bytes = await asyncio.to_thread(render_chart, candles, cfg, signal)
        photo = BufferedInputFile(chart_bytes, filename="btc_chart.png")
        await bot.send_photo(chat_id=chat_id, photo=photo, caption=caption)
    except Exception:
        logger.exception("Chart render failed for chat %s, sending text only", chat_id)
        await bot.send_message(chat_id=chat_id, text=caption)


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
        await message.bot.send_chat_action(message.chat.id, ChatAction.UPLOAD_PHOTO)
        chart_bytes = await asyncio.to_thread(render_chart, candles, cfg, signal)
        photo = BufferedInputFile(chart_bytes, filename="btc_chart.png")
        await message.answer_photo(photo=photo, caption=caption, reply_markup=reply_markup)
    except Exception:
        logger.exception("Chart render failed, sending text only")
        await message.answer(caption, reply_markup=reply_markup)
