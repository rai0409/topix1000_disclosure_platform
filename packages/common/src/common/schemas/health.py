from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    service_name: str
    status: str


class ReadyResponse(BaseModel):
    service_name: str
    status: str
    database: str
