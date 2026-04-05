from __future__ import annotations

from common.db.session import check_connection
from common.schemas.health import HealthResponse, ReadyResponse
from fastapi import APIRouter, HTTPException, status


def build_health_router(service_name: str) -> APIRouter:
    router = APIRouter()

    @router.get("/healthz", response_model=HealthResponse, tags=["health"])
    def healthz() -> HealthResponse:
        return HealthResponse(service_name=service_name, status="ok")

    @router.get("/readyz", response_model=ReadyResponse, tags=["health"])
    def readyz() -> ReadyResponse:
        if not check_connection():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="database_unavailable",
            )
        return ReadyResponse(service_name=service_name, status="ok", database="ok")

    return router
