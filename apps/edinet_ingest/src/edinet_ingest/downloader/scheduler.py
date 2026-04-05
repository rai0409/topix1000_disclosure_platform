from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from edinet_ingest.downloader.client import EdinetApiClient
from edinet_ingest.downloader.service import FetchDocsSummary, fetch_documents_for_date
from edinet_ingest.downloader.storage import RawStorageService


@dataclass(frozen=True, slots=True)
class BackfillSummary:
    date_from: str
    date_to: str
    days: int
    results: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_backfill(
    *,
    date_from: date,
    date_to: date,
    session_factory: sessionmaker[Session] | None = None,
    client: EdinetApiClient | None = None,
    storage: RawStorageService | None = None,
) -> BackfillSummary:
    if date_to < date_from:
        raise ValueError("--to must be greater than or equal to --from")

    results: list[dict[str, Any]] = []
    current = date_from
    days = 0
    while current <= date_to:
        summary: FetchDocsSummary = fetch_documents_for_date(
            current,
            session_factory=session_factory,
            client=client,
            storage=storage,
            ensure_list=True,
        )
        results.append(summary.to_dict())
        days += 1
        current += timedelta(days=1)

    return BackfillSummary(
        date_from=date_from.isoformat(),
        date_to=date_to.isoformat(),
        days=days,
        results=results,
    )
