from __future__ import annotations

import json
import sys

import edinet_ingest.cli.backfill as backfill_cli
import edinet_ingest.cli.fetch_docs as fetch_docs_cli
import edinet_ingest.cli.fetch_list as fetch_list_cli
import edinet_ingest.cli.normalize_facts_from_csv as normalize_facts_from_csv_cli
from edinet_ingest.downloader.errors import EdinetApiKeyMissingError
from edinet_ingest.downloader.scheduler import BackfillSummary
from edinet_ingest.downloader.service import FetchDocsSummary, ListFetchSummary
from edinet_ingest.facts_csv.service import NormalizeFactsSummary


def test_fetch_list_cli_success(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        fetch_list_cli,
        "fetch_and_store_list_for_date",
        lambda _date: ListFetchSummary(
            target_date="2026-03-20",
            total_results=10,
            matched_results=3,
            stored_records=3,
        ),
    )
    monkeypatch.setattr(sys, "argv", ["fetch_list", "--date", "2026-03-20"])

    code = fetch_list_cli.main()

    assert code == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["stored_records"] == 3


def test_fetch_docs_cli_success(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        fetch_docs_cli,
        "fetch_documents_for_date",
        lambda _date, ensure_list=True: FetchDocsSummary(
            target_date="2026-03-20",
            total_candidates=3,
            fetched_count=3,
            skipped_count=0,
            failed_count=0,
        ),
    )
    monkeypatch.setattr(sys, "argv", ["fetch_docs", "--date", "2026-03-20"])

    code = fetch_docs_cli.main()

    assert code == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["fetched_count"] == 3


def test_backfill_cli_success(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        backfill_cli,
        "run_backfill",
        lambda **_kwargs: BackfillSummary(
            date_from="2026-03-20",
            date_to="2026-03-21",
            days=2,
            results=[{"target_date": "2026-03-20"}, {"target_date": "2026-03-21"}],
        ),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["backfill", "--from", "2026-03-20", "--to", "2026-03-21"],
    )

    code = backfill_cli.main()

    assert code == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["days"] == 2


def test_fetch_list_cli_missing_api_key_error(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        fetch_list_cli,
        "fetch_and_store_list_for_date",
        lambda _date: (_ for _ in ()).throw(EdinetApiKeyMissingError("EDINET_API_KEY is not set")),
    )
    monkeypatch.setattr(sys, "argv", ["fetch_list", "--date", "2026-03-20"])

    code = fetch_list_cli.main()

    assert code == 2
    err = capsys.readouterr().err
    assert "EDINET_API_KEY is not set" in err


def test_normalize_facts_from_csv_cli_success(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        normalize_facts_from_csv_cli,
        "normalize_facts_for_date",
        lambda _date: NormalizeFactsSummary(
            target_date="2026-03-27",
            total_candidates=10,
            normalized_count=8,
            skipped_count=1,
            failed_count=1,
        ),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["normalize_facts_from_csv", "--date", "2026-03-27"],
    )

    code = normalize_facts_from_csv_cli.main()

    assert code == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["normalized_count"] == 8
