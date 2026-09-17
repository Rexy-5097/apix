"""The reference/observation boundary, and the tariff parser.

Two jobs, and the first matters more.

**The boundary.** A declared tariff is not an airfare observation. It has no
flight, no departure time, no travel date and no advance-purchase window, so it
cannot be assigned an APW bucket (spec A.3), banded (spec B.2.2), or keyed to a
cell. If it ever reached the statistical layer it would contaminate the index
with numbers that are not prices anyone was quoted. These tests assert the
boundary structurally rather than trusting a docstring: the adapter lives outside
``src/apix/``, and nothing inside ``src/apix/`` imports it.

**The parser.** Exercised on literal lines from the real 01SEP26 document, with
no PDF dependency, so the suite still runs on the ``dev`` extra alone. The
retrieval and text-extraction paths need the ``reference`` extra and are
deliberately not called here.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "analysis"))

from pull_alliance_tariff import (
    MAX_FARE_LEVELS,
    OBSERVATION_FIELDS_ABSENT,
    amb11_evidence,
    find_effective_date,
    parse_basic_fares,
    parse_fare_cell,
    parse_remarks,
    split_sector,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
APIX_ROOT = REPO_ROOT / "src" / "apix"
ADAPTER = REPO_ROOT / "tools" / "analysis" / "pull_alliance_tariff.py"
RECORD = REPO_ROOT / "data" / "reference" / "alliance_air_tariff.json"

# Four verbatim Table 1 lines from the 01SEP26 document: a plain row, a row with
# a paired cell, a short row, and a row with trailing absences.
REAL_LINES = [
    "1 Ahmedabad Jalgaon Direct 1100 1800 2200 2600 3005/3061 3500 4000 4600 5200 6000 "
    "6800 7700 10500 14500 20000 - - -",
    "17 Delhi Daman Direct 2500 4000 4500 5000 5500 6000 6500 7400 8800 10600 12800 "
    "15400 19200 24000 29000",
    "21 Delhi Hisar Direct - 1000 1300 1600 2000 2500 3000 3600 4200 5000 6000 7500 "
    "10000 12500 15000 - - -",
    "13 Delhi Ambikapur Direct / Via - 5254 / 5357 6207 / 6310 6683 / 6786 7159 / 7262 "
    "7880 8670 9530 10480 11530 12690 - - - - - - -",
]

ARRIVAL_UDF_REMARK = (
    "** Arrival UDF will be charged from all stations to Delhi (DEL), Mumbai (BOM), "
    "Jaipur (JAI) and Guwahati (GAU)"
)
FEE_HEADER_REMARK = (
    "Development Fee CUTE Fee User Development Fee Passenger Service Fee (PSF) "
    "Aviation Security Fee"
)


@pytest.fixture(scope="module")
def record() -> dict:
    """The committed reference record."""
    return json.loads(RECORD.read_text(encoding="utf-8"))


# ─────────────────────────── the boundary ───────────────────────────


def test_adapter_lives_outside_the_apix_package() -> None:
    """The structural guarantee the whole boundary rests on.

    The statistics layer imports from ``apix.*``. Code that is not in ``apix.*``
    cannot be imported by it, whatever anyone later writes. Moving this adapter
    under ``src/apix/`` would silently remove that guarantee, so it is asserted.
    """
    assert ADAPTER.is_file(), f"adapter missing at {ADAPTER}"
    assert APIX_ROOT not in ADAPTER.parents, (
        "the tariff adapter must NOT live under src/apix/ -- being outside the "
        "package is what makes it unimportable by the statistics layer"
    )


def test_no_module_in_the_apix_package_imports_the_tariff_adapter() -> None:
    """Parsed statically, so an import guarded behind ``if`` is still caught."""
    offenders: list[str] = []
    for path in sorted(APIX_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            if any("pull_alliance_tariff" in n or "alliance" in n.lower() for n in names):
                offenders.append(f"{path.name}: {names}")
    assert not offenders, f"src/apix must not import reference-source code: {offenders}"


def test_record_declares_itself_inadmissible(record: dict) -> None:
    """The record carries its own refusal, so a reader cannot miss it."""
    assert record["role"] == "REFERENCE_ONLY"
    assert record["is_apix_input"] is False
    assert record["data_class"] == "DECLARED_TARIFF"
    assert record["admissibility"] == "INADMISSIBLE"
    assert record["admissibility_basis"]
    assert len(record["must_never"]) >= 5


def test_record_carries_no_observation_field(record: dict) -> None:
    """A tariff row must not look like an Observation anywhere in the document.

    Checked against the serialised JSON as whole-word keys, so a field cannot be
    introduced at any nesting depth without failing here.
    """
    blob = json.dumps(record)
    for field in OBSERVATION_FIELDS_ABSENT:
        assert not re.search(rf'"{re.escape(field)}"\s*:', blob), (
            f"{field!r} appears as a key in the reference record. A declared tariff "
            "has no such field, and inventing one is how reference data becomes a "
            "fake observation"
        )


def test_record_cannot_satisfy_the_observation_contract(record: dict) -> None:
    """Every Observation-required field is missing, so construction is impossible."""
    required = {
        "observation_id",
        "travel_date",
        "departure_time_local",
        "flight_number",
        "payable_fare",
        "fare_family_raw",
    }
    for row in record["basic_fares"]["rows"][:10]:
        assert not (required & set(row)), f"tariff row exposes observation fields: {row}"


def test_record_is_not_written_into_the_collection_store(record: dict) -> None:
    """Reference output stays out of the store, and claims no frame label.

    The record *mentions* ``@primary`` in ``must_never`` -- that is a prohibition,
    not a claim -- so the check is on structure: no frame field exists, and no
    string VALUE is a frame label.
    """
    written_to = str(RECORD.relative_to(REPO_ROOT)).replace("\\", "/")
    assert written_to.startswith("data/reference/")
    assert "data/collection" not in written_to

    assert "frame_id" not in record, "a reference record must not carry a collection frame"

    def string_values(node: object) -> list[str]:
        if isinstance(node, str):
            return [node]
        if isinstance(node, dict):
            return [s for v in node.values() for s in string_values(v)]
        if isinstance(node, list):
            return [s for v in node for s in string_values(v)]
        return []

    labels = [s for s in string_values(record) if s.strip().endswith("@primary")]
    assert not labels, f"a reference record must never be labelled as a frame: {labels}"


# ─────────────────────────── provenance ───────────────────────────


def test_provenance_fields_are_present(record: dict) -> None:
    p = record["provenance"]
    for field in ("url", "landing_page", "sha256"):
        assert p.get(field), f"provenance is missing {field}"
    assert p["url"].startswith("https://")
    assert re.fullmatch(r"[0-9a-f]{64}", p["sha256"]), "sha256 must be 64 hex characters"


def test_retrieval_metadata_is_recorded_for_a_fetched_document(record: dict) -> None:
    """A fetched record carries HTTP metadata; a re-parsed one says so instead."""
    p = record["provenance"]
    if p.get("retrieved_at_utc"):
        assert p["http_status"] == 200
        assert p["content_type"] == "application/pdf"
        assert p["content_length"] and p["content_length"] > 0
        assert p["user_agent"].startswith("APIx-")
    else:
        assert p.get("note"), "a record without retrieval metadata must say why"


def test_document_version_is_recorded(record: dict) -> None:
    """Without an effective date the record is undatable and cannot be compared."""
    assert re.fullmatch(r"\d{2}[A-Z]{3}\d{2}", record["effective_date_declared"])
    assert record["page_count"] >= 1
    assert record["publisher"] == "Alliance Air Aviation Limited"


# ─────────────────────────── parsed content ───────────────────────────


def test_committed_record_parsed_the_document(record: dict) -> None:
    fares = record["basic_fares"]
    assert fares["row_count"] >= 90, "the 01SEP26 sheet carries ~92 sectors"
    assert fares["unparsed_numbered_lines"] == [], "every numbered line must parse or be reported"
    assert fares["declared_fare_levels"] == MAX_FARE_LEVELS


def test_suspect_rows_are_flagged_with_a_reason_not_dropped(record: dict) -> None:
    """A row that fails a structural check is kept, flagged and explained."""
    for row in record["basic_fares"]["rows"]:
        if row["suspect"]:
            assert row["suspect_reasons"], f"row {row['serial']} is suspect with no reason"
        else:
            assert row["suspect_reasons"] == []


def test_fare_levels_are_never_zero_and_never_strings(record: dict) -> None:
    """An absent fare level is None. Zero would be a free flight."""
    for row in record["basic_fares"]["rows"]:
        for level in row["fare_levels"]:
            if level is None:
                continue
            values = level if isinstance(level, list) else [level]
            for value in values:
                assert isinstance(value, int) and not isinstance(value, bool)
                assert value > 0, f"row {row['serial']} has a non-positive fare {value}"


def test_non_suspect_rows_have_non_decreasing_fare_levels(record: dict) -> None:
    """The structural check that the columns were read in the right order."""
    for row in record["basic_fares"]["rows"]:
        if row["suspect"]:
            continue
        present = [v[0] if isinstance(v, list) else v for v in row["fare_levels"] if v is not None]
        assert present == sorted(present), f"row {row['serial']} fare levels out of order"


def test_station_fee_grid_is_declared_unextractable_with_its_reason(record: dict) -> None:
    """The honest gap. Three strategies failed, so nothing is emitted."""
    fees = record["station_fees"]
    assert fees["status"] == "NOT_MACHINE_EXTRACTABLE"
    assert len(fees["methods_tried"]) >= 3
    assert fees["reason"]
    assert fees["how_to_close"]
    # Nothing that looks like extracted rows may appear under it.
    assert "rows" not in fees and "stations" not in fees


# ─────────────────────────── AMB-11 ───────────────────────────


def test_amb11_names_the_pilot_route_endpoints(record: dict) -> None:
    """DEL and BOM are both named, which is why this bears on the pilot."""
    evidence = record["amb11_evidence"]
    assert evidence["ambiguity"] == "AMB-11"
    assert {"DEL", "BOM"} <= set(evidence["arrival_udf_stations_named"])
    assert evidence["quotes"], "evidence with no quoted text is an assertion"


def test_amb11_does_not_claim_to_resolve_the_ambiguity(record: dict) -> None:
    """An adapter cannot close an owner ruling, and must not imply it did."""
    evidence = record["amb11_evidence"]
    assert evidence["resolves_amb11"] is False
    assert evidence["why_not"]


def test_amb11_station_list_excludes_fee_abbreviations() -> None:
    """Regression: the fee column header contains "(PSF)", which is not an airport.

    Station codes are read only from a remark stating the arrival-UDF rule. A
    naive sweep of every three-letter parenthetical reported PSF as a station.
    """
    evidence = amb11_evidence([ARRIVAL_UDF_REMARK, FEE_HEADER_REMARK])
    assert evidence["arrival_udf_stations_named"] == ["BOM", "DEL", "GAU", "JAI"]
    assert "PSF" not in evidence["arrival_udf_stations_named"]
    assert FEE_HEADER_REMARK in evidence["quotes"], "the header is kept as context"
    assert FEE_HEADER_REMARK not in evidence["arrival_rule_quotes"]


def test_amb11_yields_no_stations_without_the_arrival_rule() -> None:
    """No arrival-UDF remark, no station list. Silence is not evidence."""
    assert amb11_evidence([FEE_HEADER_REMARK])["arrival_udf_stations_named"] == []


# ─────────────────────────── parser units ───────────────────────────


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("2500", 2500),
        ("-", None),
        ("NA", None),
        ("3005/3061", [3005, 3061]),
        ("2200 / 1600", [2200, 1600]),
        ("  4000  ", 4000),
    ],
)
def test_parse_fare_cell(token: str, expected: int | list[int] | None) -> None:
    assert parse_fare_cell(token) == expected


def test_paired_cell_keeps_both_published_values() -> None:
    """Choosing one of two published figures would be a silent editorial decision."""
    assert parse_fare_cell("2200 / 1600") == [2200, 1600]


@pytest.mark.parametrize(
    ("sector", "expected"),
    [
        ("Delhi Daman", ("Delhi", "Daman")),
        ("Chandigarh (Upto 306kms) Delhi", (None, None)),
        ("Delhi", (None, None)),
    ],
)
def test_split_sector_refuses_to_guess(sector: str, expected: tuple) -> None:
    assert split_sector(sector) == expected


def test_parse_basic_fares_on_real_document_lines() -> None:
    parsed = parse_basic_fares(REAL_LINES)
    assert parsed["row_count"] == 4
    assert parsed["unparsed_numbered_lines"] == []
    assert parsed["suspect_row_count"] == 0

    first = parsed["rows"][0]
    assert first["serial"] == 1
    assert first["sector_raw"] == "Ahmedabad Jalgaon"
    assert (first["origin"], first["destination"]) == ("Ahmedabad", "Jalgaon")
    assert first["routing"] == "Direct"
    assert first["level_count"] == MAX_FARE_LEVELS
    assert first["fare_levels"][4] == [3005, 3061]
    assert first["fare_levels"][-3:] == [None, None, None]

    via = parsed["rows"][3]
    assert via["routing"] == "Direct / Via"
    assert via["fare_levels"][0] is None
    assert via["fare_levels"][1] == [5254, 5357]


def test_parse_basic_fares_reports_a_numbered_line_it_cannot_read() -> None:
    """Unreadable rows are surfaced, never dropped."""
    parsed = parse_basic_fares(["7 Something Odd Nonstop 100 200"])
    assert parsed["row_count"] == 0
    assert parsed["unparsed_numbered_lines"] == ["7 Something Odd Nonstop 100 200"]


def test_row_exceeding_the_declared_level_count_is_suspect() -> None:
    cells = " ".join(str(1000 + 10 * i) for i in range(MAX_FARE_LEVELS + 1))
    parsed = parse_basic_fares([f"45 Hyderabad Bengaluru Direct {cells}"])
    row = parsed["rows"][0]
    assert row["suspect"] is True
    assert any("exceeds" in r for r in row["suspect_reasons"])


def test_row_with_decreasing_fare_levels_is_suspect() -> None:
    parsed = parse_basic_fares(["9 Alpha Beta Direct 5000 4000 3000"])
    row = parsed["rows"][0]
    assert row["suspect"] is True
    assert any("non-decreasing" in r for r in row["suspect_reasons"])


def test_find_effective_date() -> None:
    assert find_effective_date(["noise", "*Updated as on 01SEP26"]) == "01SEP26"
    assert find_effective_date(["no date anywhere"]) is None


def test_parse_remarks_keeps_prose_and_drops_numeric_debris() -> None:
    """The fee grid's stray numeric lines must not be mistaken for remarks."""
    pages = ["page one ignored", "\n".join(["- 105 378 - 236", "236", ARRIVAL_UDF_REMARK])]
    remarks = parse_remarks(pages)
    assert remarks == [ARRIVAL_UDF_REMARK]


def test_parse_remarks_skips_the_first_page() -> None:
    """Page 1 is the fare table; its notes are parsed as rows, not remarks."""
    assert parse_remarks([ARRIVAL_UDF_REMARK]) == []
