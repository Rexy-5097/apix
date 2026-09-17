"""Exports — PS 26056 requirement 8 (a de-duplicated database, exposed).

Column orders are the contract. A consumer parsing by position breaks silently
when a column moves, so the tuples are asserted verbatim. Absent values are
empty, never ``0``.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from apix.export import EXPORTS, write_all
from apix.export.exports import (
    OBSERVATION_COLUMNS,
    PROVENANCE_COLUMNS,
    ROUTE_COLUMNS,
    SERIES_COLUMNS,
    SOURCE_COLUMNS,
    observations_csv,
    route_weights_csv,
    series_csv,
)
from apix.series import Frequency


def _rows(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text)))


def test_observation_columns_are_the_contract() -> None:
    assert OBSERVATION_COLUMNS[:5] == (
        "observation_id",
        "collection_date",
        "travel_date",
        "apw",
        "band",
    )
    assert {"base_fare", "taxes", "user_development_fee", "fees", "total"} <= set(
        OBSERVATION_COLUMNS
    )
    header = observations_csv().splitlines()[0]
    assert header == ",".join(OBSERVATION_COLUMNS)


def test_observations_export_has_35_rows_and_never_zero_for_absent_components() -> None:
    rows = _rows(observations_csv())
    assert len(rows) == 35
    for r in rows:
        assert r["total"] != ""
        assert r["currency"] == "INR"
        for comp in ("base_fare", "taxes", "user_development_fee", "fees"):
            assert r[comp] != "0", f"{r['observation_id']} has {comp}=0; absent must be empty"


def test_demo_series_export_is_labelled_demo_on_every_row() -> None:
    for freq in Frequency:
        rows = _rows(series_csv(freq, demo=True))
        assert rows, f"{freq.value} demo series is empty"
        assert {r["output_class"] for r in rows} == {"DEMO"}
        assert list(rows[0]) == list(SERIES_COLUMNS)


def test_real_series_export_is_empty_because_no_index_exists() -> None:
    for freq in Frequency:
        assert _rows(series_csv(freq, demo=False)) == []


def test_route_weights_export_has_no_publication_grade_row() -> None:
    rows = _rows(route_weights_csv())
    assert rows
    assert {r["is_publication_grade"] for r in rows} == {"False"}
    assert list(rows[0]) == list(ROUTE_COLUMNS)
    pilot = [r for r in rows if r["basket_version"] == "pilot-2026Q3"]
    assert len(pilot) == 1 and pilot[0]["observations_held"] == "35"


def test_write_all_produces_every_declared_file(tmp_path: Path) -> None:
    written = write_all(tmp_path)
    assert [p.name for p in written] == list(EXPORTS)
    assert len(EXPORTS) == 17
    for p in written:
        assert p.exists() and p.stat().st_size > 0


def test_json_exports_are_the_api_envelope(tmp_path: Path) -> None:
    write_all(tmp_path)
    for name in ("observations.json", "index_daily.json", "sources.json", "backtest.json"):
        body = json.loads((tmp_path / name).read_text(encoding="utf-8"))
        assert {"output_class", "publication_status", "methodology_version", "data"} <= set(body)
        assert body["output_class"] != "PRODUCTION"


def test_export_readme_states_no_production_value_exists(tmp_path: Path) -> None:
    write_all(tmp_path)
    readme = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "No file here contains a production index value" in readme
    assert "DEMO" in readme


def test_source_and_provenance_columns_are_declared() -> None:
    assert "operational_status" in SOURCE_COLUMNS
    assert "data_rights" in SOURCE_COLUMNS
    assert PROVENANCE_COLUMNS[0] == "observation_id"
    assert "parser_version" in PROVENANCE_COLUMNS
