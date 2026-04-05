from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx
from common.settings import get_settings

from edinet_ingest.downloader.errors import EdinetApiKeyMissingError, EdinetApiResponseError

LIST_DOCUMENTS_TYPE = "2"
FETCH_TYPE_ORIGINAL_ZIP = "1"
FETCH_TYPE_PDF = "2"
FETCH_TYPE_CSV_ZIP = "5"


@dataclass(frozen=True, slots=True)
class EdinetDocumentListResponse:
    payload: dict[str, Any]

    @property
    def results(self) -> list[dict[str, Any]]:
        raw = self.payload.get("results")
        if isinstance(raw, list):
            return [entry for entry in raw if isinstance(entry, dict)]
        return []


class EdinetApiClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = "https://disclosure.edinet-fsa.go.jp/api/v2",
        timeout_sec: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout_sec = timeout_sec
        self._transport = transport

    def list_documents(self, target_date: date) -> EdinetDocumentListResponse:
        payload = self._request_json(
            path="/documents.json",
            params={
                "date": target_date.isoformat(),
                "type": LIST_DOCUMENTS_TYPE,
            },
        )
        return EdinetDocumentListResponse(payload=payload)

    def fetch_document_bytes(self, *, doc_id: str, response_type: str) -> bytes:
        return self._request_bytes(
            path=f"/documents/{doc_id}",
            params={"type": response_type},
        )

    def fetch_document_response(self, *, doc_id: str, response_type: str) -> httpx.Response:
        return self._request(
            path=f"/documents/{doc_id}",
            params={"type": response_type},
            raise_for_status=False,
        )

    def _request_json(self, *, path: str, params: dict[str, str]) -> dict[str, Any]:
        response = self._request(path=path, params=params)
        try:
            payload = response.json()
        except ValueError as exc:
            raise EdinetApiResponseError(f"invalid JSON response: {response.text[:256]}") from exc
        if not isinstance(payload, dict):
            raise EdinetApiResponseError("unexpected JSON payload type")
        return payload

    def _request_bytes(self, *, path: str, params: dict[str, str]) -> bytes:
        response = self._request(path=path, params=params)
        return response.content

    def _request(
        self,
        *,
        path: str,
        params: dict[str, str],
        raise_for_status: bool = True,
    ) -> httpx.Response:
        api_key = self._resolve_api_key()
        merged_params = {**params, "Subscription-Key": api_key}
        headers = {
            "Accept": "application/json, application/zip, application/pdf, application/octet-stream",
            "User-Agent": "topix1000-disclosure-platform/phase2",
            "Ocp-Apim-Subscription-Key": api_key,
        }

        try:
            with httpx.Client(
                base_url=self._base_url,
                timeout=self._timeout_sec,
                transport=self._transport,
                follow_redirects=True,
            ) as client:
                response = client.get(path, params=merged_params, headers=headers)
        except httpx.HTTPError as exc:
            raise EdinetApiResponseError(f"request failed: {exc}") from exc

        if raise_for_status and response.status_code >= 400:
            raise EdinetApiResponseError(
                f"EDINET API error status={response.status_code} path={path} body={response.text[:256]}"
            )
        return response

    def _resolve_api_key(self) -> str:
        if self._api_key:
            return self._api_key
        key = get_settings().edinet_api_key
        if key:
            return key
        raise EdinetApiKeyMissingError(
            "EDINET_API_KEY is not set. Set EDINET_API_KEY to call EDINET API endpoints."
        )
