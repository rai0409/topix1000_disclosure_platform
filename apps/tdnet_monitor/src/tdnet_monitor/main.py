from __future__ import annotations

from common.logging import configure_logging
from common.settings import get_settings
from fastapi import FastAPI

from tdnet_monitor.api.health import build_health_router

SERVICE_NAME = "tdnet-monitor"


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="TOPIX1000 TDnet Monitor Skeleton",
        debug=settings.app_debug,
    )
    app.include_router(build_health_router(service_name=SERVICE_NAME))
    return app


app = create_app()
