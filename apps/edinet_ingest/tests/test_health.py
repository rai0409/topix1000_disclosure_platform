from __future__ import annotations

from edinet_ingest.api import health as health_module
from edinet_ingest.api.health import build_health_router
from fastapi.routing import APIRoute


def test_healthz() -> None:
    router = build_health_router(service_name="edinet-ingest")
    routes = {route.path for route in router.routes}
    assert "/healthz" in routes

    health_route = next(route for route in router.routes if isinstance(route, APIRoute) and route.path == "/healthz")
    payload = health_route.endpoint()
    assert payload.model_dump() == {"service_name": "edinet-ingest", "status": "ok"}


def test_readyz(monkeypatch) -> None:
    monkeypatch.setattr(health_module, "check_connection", lambda: True)
    router = build_health_router(service_name="edinet-ingest")
    routes = {route.path for route in router.routes}
    assert "/readyz" in routes

    ready_route = next(route for route in router.routes if isinstance(route, APIRoute) and route.path == "/readyz")
    payload = ready_route.endpoint()
    assert payload.model_dump() == {
        "service_name": "edinet-ingest",
        "status": "ok",
        "database": "ok",
    }
