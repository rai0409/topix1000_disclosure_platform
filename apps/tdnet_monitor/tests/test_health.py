from __future__ import annotations

from fastapi.routing import APIRoute
from tdnet_monitor.api import health as health_module
from tdnet_monitor.api.health import build_health_router


def test_healthz() -> None:
    router = build_health_router(service_name="tdnet-monitor")
    routes = {route.path for route in router.routes}
    assert "/healthz" in routes

    health_route = next(route for route in router.routes if isinstance(route, APIRoute) and route.path == "/healthz")
    payload = health_route.endpoint()
    assert payload.model_dump() == {"service_name": "tdnet-monitor", "status": "ok"}


def test_readyz(monkeypatch) -> None:
    monkeypatch.setattr(health_module, "check_connection", lambda: True)
    router = build_health_router(service_name="tdnet-monitor")
    routes = {route.path for route in router.routes}
    assert "/readyz" in routes

    ready_route = next(route for route in router.routes if isinstance(route, APIRoute) and route.path == "/readyz")
    payload = ready_route.endpoint()
    assert payload.model_dump() == {
        "service_name": "tdnet-monitor",
        "status": "ok",
        "database": "ok",
    }
