from functools import lru_cache
from typing import Final

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_DATABASE_URL: Final[str] = "sqlite+aiosqlite:///./data/biztrace.db"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    bot_token: str = Field(validation_alias="BOT_TOKEN")
    admin_ids: str = Field(default="", validation_alias="ADMIN_IDS")
    database_url: str = Field(default=DEFAULT_DATABASE_URL, validation_alias="DATABASE_URL")
    support_url: str | None = Field(default=None, validation_alias="SUPPORT_URL")
    rate_limit_seconds: float = Field(default=0.5, validation_alias="RATE_LIMIT_SECONDS")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    trial_days: int = Field(default=3, validation_alias="TRIAL_DAYS")
    subscription_price_text: str = Field(
        default="Свяжитесь с поддержкой для продления подписки.",
        validation_alias="SUBSCRIPTION_PRICE_TEXT",
    )

    @property
    def parsed_admin_ids(self) -> tuple[int, ...]:
        ids: list[int] = []
        for raw_id in self.admin_ids.split(","):
            raw_id = raw_id.strip()
            if not raw_id:
                continue
            ids.append(int(raw_id))
        return tuple(ids)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
