from __future__ import annotations

import csv
import json
import sys

import edinet_ingest.cli.build_prices_dataset as build_prices_dataset_cli


def test_build_prices_dataset_cli_success_normalizes_deterministically(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    input_path = tmp_path / "source_prices.csv"
    output_path = tmp_path / "prices.csv"

    with input_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["adj_close", "extra_col", "date", "security_code", "close"])
        writer.writerow([" 101 ", "ok", " 2026-02-03 ", " 0010 ", " 100 "])
        writer.writerow(["101", "duplicate_row", "2026-02-03", "0010", "100"])
        writer.writerow(["101", "conflict_row", "2026-02-03", "0010", "099"])
        writer.writerow(["200", "missing_security_code", "2026-02-04", "", "200"])
        writer.writerow(["200", "missing_date", "", "0020", "200"])
        writer.writerow(["", "missing_price", "2026-02-04", "0030", ""])
        writer.writerow([" 300 ", "ok", "2026-02-01", " 0002 ", ""])
        writer.writerow(["", "", "", "", ""])
        writer.writerow(["", "ok", "2026-02-01", "0003", "400"])

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_prices_dataset",
            "--input",
            str(input_path),
            "--out",
            str(output_path),
        ],
    )

    code = build_prices_dataset_cli.main()

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert set(payload.keys()) == {
        "input_path",
        "output_path",
        "input_row_count",
        "valid_row_count",
        "dropped_missing_security_code_count",
        "dropped_missing_date_count",
        "dropped_missing_price_count",
        "duplicate_row_count",
        "conflicting_security_date_count",
        "output_row_count",
    }
    assert payload["input_path"] == str(input_path.resolve())
    assert payload["output_path"] == str(output_path.resolve())
    assert payload["input_row_count"] == 9
    assert payload["valid_row_count"] == 5
    assert payload["dropped_missing_security_code_count"] == 1
    assert payload["dropped_missing_date_count"] == 1
    assert payload["dropped_missing_price_count"] == 1
    assert payload["duplicate_row_count"] == 1
    assert payload["conflicting_security_date_count"] == 1
    assert payload["output_row_count"] == 3
    # One completely blank row is included in input_row_count only.
    assert payload["input_row_count"] == payload["valid_row_count"] + payload[
        "dropped_missing_security_code_count"
    ] + payload["dropped_missing_date_count"] + payload["dropped_missing_price_count"] + 1

    with output_path.open("r", encoding="utf-8", newline="") as csv_file:
        rows = list(csv.reader(csv_file))
    assert rows[0] == ["security_code", "date", "close", "adj_close"]
    assert rows[1:] == [
        ["0002", "2026-02-01", "", "300"],
        ["0003", "2026-02-01", "400", ""],
        ["0010", "2026-02-03", "099", "101"],
    ]


def test_build_prices_dataset_cli_missing_input_file_returns_1(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    input_path = tmp_path / "missing_source_prices.csv"
    output_path = tmp_path / "prices.csv"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_prices_dataset",
            "--input",
            str(input_path),
            "--out",
            str(output_path),
        ],
    )

    code = build_prices_dataset_cli.main()

    assert code == 1
    assert "build_prices_dataset failed:" in capsys.readouterr().err


def test_build_prices_dataset_cli_missing_required_columns_returns_1(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    input_path = tmp_path / "source_prices.csv"
    output_path = tmp_path / "prices.csv"
    with input_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["security_code", "close"])
        writer.writerow(["1301", "100"])

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_prices_dataset",
            "--input",
            str(input_path),
            "--out",
            str(output_path),
        ],
    )

    code = build_prices_dataset_cli.main()

    assert code == 1
    err = capsys.readouterr().err
    assert "build_prices_dataset failed:" in err
    assert "missing required headers: security_code,date" in err


def test_build_prices_dataset_cli_invalid_date_returns_1(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    input_path = tmp_path / "source_prices.csv"
    output_path = tmp_path / "prices.csv"
    with input_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["security_code", "date", "close"])
        writer.writerow(["1301", "2026-2-3", "100"])

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_prices_dataset",
            "--input",
            str(input_path),
            "--out",
            str(output_path),
        ],
    )

    code = build_prices_dataset_cli.main()

    assert code == 1
    err = capsys.readouterr().err
    assert "build_prices_dataset failed:" in err
    assert "invalid date '2026-2-3'" in err


def test_build_prices_dataset_cli_empty_file_returns_1(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    input_path = tmp_path / "source_prices.csv"
    output_path = tmp_path / "prices.csv"
    input_path.write_text("", encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_prices_dataset",
            "--input",
            str(input_path),
            "--out",
            str(output_path),
        ],
    )

    code = build_prices_dataset_cli.main()

    assert code == 1
    err = capsys.readouterr().err
    assert "build_prices_dataset failed:" in err
    assert "missing required headers: security_code,date" in err


def test_build_prices_dataset_cli_header_only_file_is_valid_with_zero_counts(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    input_path = tmp_path / "source_prices.csv"
    output_path = tmp_path / "prices.csv"
    with input_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["security_code", "date", "adj_close"])

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_prices_dataset",
            "--input",
            str(input_path),
            "--out",
            str(output_path),
        ],
    )

    code = build_prices_dataset_cli.main()

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["input_row_count"] == 0
    assert payload["valid_row_count"] == 0
    assert payload["dropped_missing_security_code_count"] == 0
    assert payload["dropped_missing_date_count"] == 0
    assert payload["dropped_missing_price_count"] == 0
    assert payload["duplicate_row_count"] == 0
    assert payload["conflicting_security_date_count"] == 0
    assert payload["output_row_count"] == 0

    with output_path.open("r", encoding="utf-8", newline="") as csv_file:
        rows = list(csv.reader(csv_file))
    assert rows == [["security_code", "date", "close", "adj_close"]]
