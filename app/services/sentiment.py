"""Market sentiment data — Fear & Greed Index."""

from __future__ import annotations

import logging

import aiohttp

logger = logging.getLogger(__name__)

FNG_URL = "https://api.alternative.me/fng/?limit=1"


def fear_greed_emoji(value: int) -> str:
    if value <= 24:
        return "😱"
    if value <= 49:
        return "😨"
    if value <= 74:
        return "😏"
    return "🤑"


def fear_greed_label(value: int) -> str:
    if value <= 24:
        return "Экстремальный страх"
    if value <= 49:
        return "Страх"
    if value <= 74:
        return "Жадность"
    return "Экстремальная жадность"


async def fetch_fear_greed() -> dict[str, str | int] | None:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(FNG_URL, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                resp.raise_for_status()
                data = await resp.json()
        entry = data.get("data", [{}])[0]
        value = int(entry.get("value", 0))
        return {
            "value": value,
            "classification": entry.get("value_classification", fear_greed_label(value)),
            "emoji": fear_greed_emoji(value),
            "label": fear_greed_label(value),
        }
    except Exception:
        logger.warning("Failed to fetch Fear & Greed index", exc_info=True)
        return None
