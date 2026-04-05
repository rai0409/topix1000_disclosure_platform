from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = Field(default="local", alias="APP_ENV")
    tz: str = Field(default="Asia/Tokyo", alias="TZ")
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/topix1000_disclosure",
        alias="DATABASE_URL",
    )
    raw_storage_root: Path = Field(
        default=Path("/home/rai/data/topix1000_disclosure/raw"),
        alias="RAW_STORAGE_ROOT",
    )
    edinet_api_key: str | None = Field(default=None, alias="EDINET_API_KEY")
    smtp_host: str | None = Field(default=None, alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_username: str | None = Field(default=None, alias="SMTP_USERNAME")
    smtp_password: str | None = Field(default=None, alias="SMTP_PASSWORD")
    smtp_from: str | None = Field(default=None, alias="SMTP_FROM")
    generic_webhook_url: str | None = Field(default=None, alias="GENERIC_WEBHOOK_URL")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    app_debug: bool = Field(default=False, alias="APP_DEBUG")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
