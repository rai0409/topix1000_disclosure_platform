from __future__ import annotations

from common.settings import get_settings


def test_settings_load_from_env(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("TZ", "Asia/Tokyo")
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("RAW_STORAGE_ROOT", "/tmp/topix1000/raw")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("APP_DEBUG", "true")

    get_settings.cache_clear()
    settings = get_settings()

    assert settings.app_env == "test"
    assert settings.database_url == "sqlite+pysqlite:///:memory:"
    assert str(settings.raw_storage_root) == "/tmp/topix1000/raw"
    assert settings.log_level == "DEBUG"
    assert settings.app_debug is True
