from __future__ import annotations

import csv
import json
import sys

import edinet_ingest.cli.build_code_map as build_code_map_cli


def test_build_code_map_cli_success_normalizes_deterministically(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    input_path = tmp_path / "source_mapping.csv"
    output_path = tmp_path / "code_map.csv"

    with input_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["security_code", "extra_col", "edinet_code"])
        writer.writerow([" 0100 ", "ok", " E00002 "])
        writer.writerow(["0100", "duplicate_pair", "E00002"])
        writer.writerow(["0099", "conflict_candidate", "E00002"])
        writer.writerow(["2000", "ok", "E00001"])
        writer.writerow(["", "missing_security_code", "E00003"])
        writer.writerow(["3000", "missing_edinet_code", ""])
        writer.writerow(["", "", ""])
        writer.writerow([" 0400 ", "ok", " E00004 "])

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_code_map",
            "--input",
            str(input_path),
            "--out",
            str(output_path),
        ],
    )

    code = build_code_map_cli.main()

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert set(payload.keys()) == {
        "input_path",
        "output_path",
        "input_row_count",
        "valid_row_count",
        "dropped_missing_code_count",
        "duplicate_pair_count",
        "conflicting_edinet_code_count",
        "output_row_count",
    }
    assert payload["input_path"] == str(input_path.resolve())
    assert payload["output_path"] == str(output_path.resolve())
    assert payload["input_row_count"] == 8
    assert payload["valid_row_count"] == 5
    assert payload["dropped_missing_code_count"] == 2
    assert payload["duplicate_pair_count"] == 1
    assert payload["conflicting_edinet_code_count"] == 1
    assert payload["output_row_count"] == 3
    # blank row is counted in input rows, but excluded from valid/dropped counts.
    assert payload["input_row_count"] == payload["valid_row_count"] + payload[
        "dropped_missing_code_count"
    ] + 1

    with output_path.open("r", encoding="utf-8", newline="") as csv_file:
        rows = list(csv.reader(csv_file))
    assert rows[0] == ["edinet_code", "security_code"]
    assert rows[1:] == [
        ["E00001", "2000"],
        ["E00002", "0099"],
        ["E00004", "0400"],
    ]


def test_build_code_map_cli_missing_input_file_returns_1(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    input_path = tmp_path / "missing_source.csv"
    output_path = tmp_path / "code_map.csv"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_code_map",
            "--input",
            str(input_path),
            "--out",
            str(output_path),
        ],
    )

    code = build_code_map_cli.main()

    assert code == 1
    assert "build_code_map failed:" in capsys.readouterr().err


def test_build_code_map_cli_missing_required_columns_returns_1(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    input_path = tmp_path / "source_mapping.csv"
    output_path = tmp_path / "code_map.csv"
    with input_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["edinet_code", "ticker"])
        writer.writerow(["E00001", "1301"])

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_code_map",
            "--input",
            str(input_path),
            "--out",
            str(output_path),
        ],
    )

    code = build_code_map_cli.main()

    assert code == 1
    err = capsys.readouterr().err
    assert "build_code_map failed:" in err
    assert "missing required headers: edinet_code,security_code" in err


def test_build_code_map_cli_empty_file_returns_1(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    input_path = tmp_path / "source_mapping.csv"
    output_path = tmp_path / "code_map.csv"
    input_path.write_text("", encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_code_map",
            "--input",
            str(input_path),
            "--out",
            str(output_path),
        ],
    )

    code = build_code_map_cli.main()

    assert code == 1
    err = capsys.readouterr().err
    assert "build_code_map failed:" in err
    assert "missing required headers: edinet_code,security_code" in err


def test_build_code_map_cli_header_only_file_is_valid_with_zero_counts(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    input_path = tmp_path / "source_mapping.csv"
    output_path = tmp_path / "code_map.csv"
    with input_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["edinet_code", "security_code"])

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_code_map",
            "--input",
            str(input_path),
            "--out",
            str(output_path),
        ],
    )

    code = build_code_map_cli.main()

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["input_row_count"] == 0
    assert payload["valid_row_count"] == 0
    assert payload["dropped_missing_code_count"] == 0
    assert payload["duplicate_pair_count"] == 0
    assert payload["conflicting_edinet_code_count"] == 0
    assert payload["output_row_count"] == 0

    with output_path.open("r", encoding="utf-8", newline="") as csv_file:
        rows = list(csv.reader(csv_file))
    assert rows == [["edinet_code", "security_code"]]
