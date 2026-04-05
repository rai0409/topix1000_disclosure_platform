from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import httpx
from edinet_ingest.downloader.client import EdinetApiClient
from edinet_ingest.downloader.errors import EdinetApiKeyMissingError


def test_client_raises_clear_error_when_api_key_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        "edinet_ingest.downloader.client.get_settings",
        lambda: SimpleNamespace(edinet_api_key=None),
    )

    called = {"value": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        called["value"] += 1
        return httpx.Response(200, json={"results": []})

    client = EdinetApiClient(api_key=None, transport=httpx.MockTransport(handler))

    try:
        client.list_documents(date(2026, 3, 20))
        raise AssertionError("expected EdinetApiKeyMissingError")
    except EdinetApiKeyMissingError as exc:
        assert "EDINET_API_KEY is not set" in str(exc)

    assert called["value"] == 0
