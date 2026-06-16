from functools import lru_cache
from typing import Final

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DATABASE_URL: Final[str] = "sqlite+aiosqlite:///./data/tradingbot.db"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    bot_token: str = Field(validation_alias="BOT_TOKEN")
    admin_ids: str = Field(default="", validation_alias="ADMIN_IDS")
    database_url: str = Field(default=DEFAULT_DATABASE_URL, validation_alias="DATABASE_URL")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    symbol: str = Field(default="BTCUSDT", validation_alias="SYMBOL")
    timeframe: str = Field(default="1h", validation_alias="TIMEFRAME")
    scan_interval_minutes: int = Field(default=15, validation_alias="SCAN_INTERVAL_MINUTES")
    trade_check_interval_minutes: int = Field(default=5, validation_alias="TRADE_CHECK_INTERVAL_MINUTES")
    notify_on_signal: bool = Field(default=True, validation_alias="NOTIFY_ON_SIGNAL")
    webhook_host: str = Field(default="0.0.0.0", validation_alias="WEBHOOK_HOST")
    webhook_port: int = Field(default=0, validation_alias="WEBHOOK_PORT")
    cryptopay_webhook_path: str = Field(default="/cryptopay/webhook", validation_alias="CRYPTOPAY_WEBHOOK_PATH")
    invoice_poll_seconds: int = Field(default=15, validation_alias="INVOICE_POLL_SECONDS")
    bingx_api_key: str = Field(default="", validation_alias="BINGX_API_KEY")
    bingx_api_secret: str = Field(default="", validation_alias="BINGX_API_SECRET")
    bingx_testnet: bool = Field(default=False, validation_alias="BINGX_TESTNET")
    bingx_order_usdt: float = Field(default=50.0, validation_alias="BINGX_ORDER_USDT")

    @property
    def parsed_admin_ids(self) -> tuple[int, ...]:
        ids: list[int] = []
        for raw in self.admin_ids.split(","):
            raw = raw.strip()
            if raw:
                ids.append(int(raw))
        return tuple(ids)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
