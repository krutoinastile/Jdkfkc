from datetime import datetime, timedelta, timezone

from aiogram import Bot


async def create_one_time_invite_link(bot: Bot, channel_id: str, application_id: int) -> str:
    expire_date = datetime.now(timezone.utc) + timedelta(hours=24)
    invite_link = await bot.create_chat_invite_link(
        chat_id=channel_id,
        name=f"BingX application #{application_id}",
        expire_date=expire_date,
        member_limit=1,
    )
    return invite_link.invite_link
