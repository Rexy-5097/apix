"""Automated collection: the contract, the navigation plan and the IndiGo parser.

The contract tests pin the automated collector to the frozen values it must not
drift from -- the APW vector (no T+21), bands 2-6, one adult, Economy, INR,
one-way, Saver -- by reading them from the same enums the statistics layer uses.

The parser tests use display strings in the format goindigo.in rendered in the
2026-09-12 manual screenshots. Every page payload is SYNTHETIC; see
``tests/fixtures/indigo_synthetic.py``.
"""

from __future__ import annotations

import copy
import json
import sys
from datetime import date, time, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from apix.ingestion.collectors.candidates import PageState
from apix.ingestion.collectors.contract import (
    CONTRACT_BANDS,
    FROZEN_APW,
    CollectionConfig,
    CollectionContract,
    ConfigError,
    SearchParams,
    band_of,
    band_window,
    parse_apw,
)
from apix.ingestion.collectors.indigo import parse as P
from apix.ingestion.collectors.indigo.navigation import (
    BASE_URL,
    SELECTOR_STATUS,
    build_navigation_plan,
)
from apix.schemas.enums import APWBucket, ChangePolicy
from tests.fixtures.indigo_synthetic import (
    COLLECTION_DATE,
    RUPEE,
    build_fixture,
    day_payload,
    non_results_page,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "indigo" / "extract_2026-09-15.json"
sys.path.insert(0, str(ROOT / "tools" / "collection"))


def params(lead_time: int = 7) -> SearchParams:
    return SearchParams(
        source_id="indigo-direct",
        contract=CollectionContract(),
        collection_date=COLLECTION_DATE,
        travel_date=COLLECTION_DATE + timedelta(days=lead_time),
    )


# ── the frozen values ────────────────────────────────────────────────────────


def test_the_apw_vector_is_the_frozen_production_vector_with_no_t21() -> None:
    assert FROZEN_APW == (1, 3, 7, 15, 30, 45, 60)
    assert tuple(b.value for b in APWBucket) == FROZEN_APW
    assert 21 not in FROZEN_APW


def test_t21_is_refused_rather_than_collected_into_a_production_run() -> None:
    with pytest.raises(ConfigError, match="T\\+21 is not a production bucket"):
        parse_apw("7,21,30")


def test_apw_list_is_sorted_and_duplicates_are_refused() -> None:
    assert parse_apw("60,1,7") == (1, 7, 60)
    with pytest.raises(ConfigError, match="repeats"):
        parse_apw("7,7")
    with pytest.raises(ConfigError, match="not comma-separated integers"):
        parse_apw("7,x")


def test_full_apw_config_builds_one_search_per_bucket_and_labels_itself() -> None:
    config = CollectionConfig.for_apw("indigo", COLLECTION_DATE, FROZEN_APW)
    assert config.lead_times == FROZEN_APW
    assert [p.apw_bucket for p in config.search_params("indigo-direct")] == list(APWBucket)
    assert (
        config.frame_id("@fixture") == "DEL-BOM/6E/AIRLINE_DIRECT/T1-T3-T7-T15-T30-T45-T60@fixture"
    )


def test_a_single_off_frame_travel_date_is_allowed_but_declared() -> None:
    config = CollectionConfig("indigo", COLLECTION_DATE, (date(2026, 9, 19),), CollectionContract())
    assert config.off_frame_lead_times == (4,)


def test_travel_dates_must_follow_the_collection_date() -> None:
    with pytest.raises(ConfigError, match="not after the collection date"):
        CollectionConfig("indigo", COLLECTION_DATE, (COLLECTION_DATE,), CollectionContract())


def test_pacing_cannot_be_set_below_the_protocol_floor() -> None:
    with pytest.raises(ConfigError, match="10 s floor"):
        CollectionConfig.for_apw("indigo", COLLECTION_DATE, [7], min_interval_seconds=2.0)


def test_contract_bands_are_06_00_to_20_59_and_agree_with_the_manual_loader() -> None:
    from load_manual import CONTRACT_BANDS as LOADER_BANDS

    assert frozenset(CONTRACT_BANDS) == LOADER_BANDS
    assert band_window(2) == "06:00-08:59"
    assert band_window(6) == "18:00-20:59"


@pytest.mark.parametrize(
    ("clock", "band"),
    [
        (time(5, 59), 1),
        (time(6, 0), 2),
        (time(8, 59), 2),
        (time(9, 0), 3),
        (time(11, 59), 3),
        (time(12, 0), 4),
        (time(15, 0), 5),
        (time(20, 59), 6),
        (time(21, 0), 7),
    ],
)
def test_band_edges(clock: time, band: int) -> None:
    assert band_of(clock) == band


@pytest.mark.parametrize(
    "override",
    [
        {"adults": 2},
        {"children": 1},
        {"cabin": "BUSINESS"},
        {"currency": "USD"},
        {"trip_type": "ROUND_TRIP"},
        {"fare_type": "STUDENT"},
        {"signed_in": True},
        {"nearby_airports": True},
        {"nonstop_only": False},
        {"carrier": "AI"},
        {"fare_family": "Lite"},
        {"origin": "BOM", "destination": "DEL"},
    ],
)
def test_any_deviation_from_the_frozen_contract_is_refused(override: dict[str, object]) -> None:
    with pytest.raises(ConfigError):
        CollectionContract(**override)  # type: ignore[arg-type]


def test_search_parameters_are_recorded_as_evidence() -> None:
    record = params(7).as_record()
    assert record["adults"] == 1
    assert record["cabin"] == "ECONOMY"
    assert record["currency"] == "INR"
    assert record["trip_type"] == "ONE_WAY"
    assert record["nearby_airports"] is False
    assert record["lead_time_days"] == 7
    assert record["apw_bucket"] == 7
    assert record["fare_family"] == "Saver"
    assert "never by price" in str(record["selection_rule"])


# ── navigation plan ──────────────────────────────────────────────────────────


def test_navigation_plan_is_the_contracted_search() -> None:
    p = params(7)
    plan = build_navigation_plan(p)
    assert plan[0].action == "goto"
    assert plan[0].value == BASE_URL == "https://www.goindigo.in/"
    steps = {(s.action, s.target): s.value for s in plan}
    assert steps[("fill_airport", "origin_input")] == "DEL"
    assert steps[("fill_airport", "destination_input")] == "BOM"
    assert steps[("pick_date", "calendar_day")] == "2026-09-22"
    assert steps[("set_count", "adults_count")] == "1"
    assert steps[("set_count", "children_count")] == "0"
    assert steps[("choose", "currency_select")] == "INR"
    assert steps[("choose", "fare_type_regular")] == "REGULAR"
    assert ("assert_off", "nearby_airports_toggle") in steps
    assert ("assert_signed_out", "sign_in_state") in steps
    assert ("click", "cookie_decline") in steps
    assert plan[-2].action == "wait"


def test_navigation_plan_never_sorts_by_price_or_signs_in() -> None:
    text = " ".join(
        f"{s.action} {s.target} {s.value}" for s in build_navigation_plan(params())
    ).lower()
    for forbidden in ("price", "cheap", "login", "sign_in_submit", "captcha", "password"):
        assert forbidden not in text


def test_selectors_are_declared_unverified() -> None:
    assert SELECTOR_STATUS == "UNVERIFIED"


# ── display-string parsers ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("06:05", time(6, 5)),
        ("6:05 PM", time(18, 5)),
        ("12:10 am", time(0, 10)),
        ("25:00", None),
        ("early", None),
        ("", None),
    ],
)
def test_parse_clock(text: str, expected: time | None) -> None:
    assert P.parse_clock(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [("02h 15m", 135), ("2h 25m", 145), ("2h", 120), ("45m", 45), ("", None), ("two hours", None)],
)
def test_parse_duration(text: str, expected: int | None) -> None:
    assert P.parse_duration(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("6E 6218", ("6E", "6218")),
        ("6E6218", ("6E", "6218")),
        ("AI 101", ("AI", "101")),
        ("6218", None),
        ("", None),
    ],
)
def test_parse_flight_label_yields_digits_only_numbers(
    text: str, expected: tuple[str, str] | None
) -> None:
    assert P.parse_flight_label(text) == expected


@pytest.mark.parametrize(
    ("text", "amount", "currency"),
    [
        (f"{RUPEE}6,530", Decimal("6530"), "INR"),
        ("INR 6,530", Decimal("6530"), "INR"),
        ("Rs. 6530", Decimal("6530"), "INR"),
        ("$120", Decimal("120"), "USD"),
        (f"{RUPEE}", None, "INR"),
        ("", None, None),
    ],
)
def test_parse_money(text: str, amount: Decimal | None, currency: str | None) -> None:
    assert P.parse_money(text) == (amount, currency)


@pytest.mark.parametrize(
    ("text", "expected"),
    [("DEL, T1", "DEL"), ("HDO, T1", "HDO"), ("BOM, T2", "BOM"), ("Delhi", None)],
)
def test_parse_airport_code(text: str, expected: str | None) -> None:
    assert P.parse_airport_code(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [("Non-stop", 0), ("Nonstop", 0), ("1 Stop", 1), ("2 stops", 2), ("via BLR", None)],
)
def test_parse_stops(text: str, expected: int | None) -> None:
    assert P.parse_stops(text) == expected


@pytest.mark.parametrize(
    ("lines", "expected"),
    [
        (["7 kg Cabin bag allowance", "15 kg Check-in bag allowance"], 15),
        (["7 kg Cabin bag only", "No check-in bag included"], 0),
        (["7 kg Cabin bag allowance"], None),
        (["15 kg Check-in bag allowance", "20 kg Check-in bag allowance"], None),
        ([], None),
    ],
)
def test_checked_baggage_reads_the_checked_allowance_only(
    lines: list[str], expected: int | None
) -> None:
    assert P.parse_checked_baggage(lines) == expected


@pytest.mark.parametrize(
    ("lines", "expected"),
    [
        (["Change and cancellation charges: Standard"], (ChangePolicy.FEE, ChangePolicy.FEE)),
        (["Free date change", "Cancellation fee applies"], (ChangePolicy.FREE, ChangePolicy.FEE)),
        (["Non-refundable"], (None, ChangePolicy.NONE)),
        (["Partial"], (None, None)),
        (["Free cancellation", "Non-refundable"], (None, None)),
    ],
)
def test_policy_is_read_from_displayed_text_and_never_guessed(
    lines: list[str], expected: tuple[ChangePolicy | None, ChangePolicy | None]
) -> None:
    assert P.parse_change_cancellation(lines) == expected


def test_breakdown_records_only_displayed_components_never_zero() -> None:
    fb = P.parse_breakdown(
        {
            "Base Airfare": f"{RUPEE}5,065",
            "Total Tax": f"{RUPEE}1,465",
            "TOTAL FARE": f"{RUPEE}6,530",
        }
    )
    assert fb.base_fare == Decimal("5065")
    assert fb.taxes == Decimal("1465")
    assert fb.fees is None
    assert fb.user_development_fee is None
    assert P.parse_breakdown({}).declared_total is None


@pytest.mark.parametrize(
    ("label", "reference", "expected"),
    [
        ("22nd Sep", date(2026, 9, 22), date(2026, 9, 22)),
        ("2nd Jan", date(2026, 12, 30), date(2027, 1, 2)),
        ("2026-10-15", date(2026, 10, 15), date(2026, 10, 15)),
        ("someday", date(2026, 9, 22), None),
    ],
)
def test_parse_day_month(label: str, reference: date, expected: date | None) -> None:
    assert P.parse_day_month(label, reference) == expected


def test_passengers_and_trip_labels() -> None:
    assert P.parse_passengers("1 Passenger") == 1
    assert P.parse_passengers("2 Adults") == 2
    assert P.parse_trip("One Way") == "ONE_WAY"
    assert P.parse_trip("Round Trip") == "ROUND_TRIP"
    assert P.parse_currency("INR") == "INR"


# ── payload parsing ──────────────────────────────────────────────────────────


def test_results_page_keeps_the_whole_returned_universe() -> None:
    parsed = P.parse_extracted(day_payload(7), params(7))
    assert parsed.page_state is PageState.RESULTS
    assert parsed.structural_issues == ()
    assert len(parsed.candidates) == 13
    shown = parsed.displayed
    assert shown is not None
    assert (shown.origin, shown.destination, shown.travel_date) == ("DEL", "BOM", date(2026, 9, 22))
    assert (shown.adults, shown.currency, shown.trip_type) == (1, "INR", "ONE_WAY")

    by_number = {c.flight_number: c for c in parsed.candidates}
    assert by_number["9202"].operating_carrier == "Operated by Partner Air"
    assert by_number["9301"].origin == "HDO"
    assert by_number["9201"].stops == 1
    assert by_number["9101"].departure_date == date(2026, 9, 22)
    saver = next(f for f in by_number["9101"].fares if f.family_label == "Saver fare")
    assert (saver.checked_baggage_kg, saver.change_policy, saver.cancellation_policy) == (
        15,
        ChangePolicy.FEE,
        ChangePolicy.FEE,
    )


def test_page_order_is_cheapest_first_so_it_must_never_drive_selection() -> None:
    """Guards the fixture's purpose: if page order were departure order, the
    earliest-not-cheapest tests would pass for the wrong reason."""
    parsed = P.parse_extracted(day_payload(7), params(7))
    band2 = [
        c.flight_number for c in parsed.candidates if c.flight_number in ("9101", "9102", "9103")
    ]
    assert band2 == ["9103", "9102", "9101"]


def test_a_missing_payload_key_is_reported_as_a_dom_change() -> None:
    payload = copy.deepcopy(day_payload(7))
    del payload["flights"][0]["duration"]  # type: ignore[index]
    parsed = P.parse_extracted(payload, params(7))
    assert any(
        "MISSING_KEYS" in issue and "duration" in issue for issue in parsed.structural_issues
    )

    payload = copy.deepcopy(day_payload(7))
    del payload["flights"][2]["fares"][1]["policy"]  # type: ignore[index]
    assert any("FARE_TILE" in i for i in P.parse_extracted(payload, params(7)).structural_issues)


def test_an_unreadable_value_is_none_with_an_issue_not_a_guess() -> None:
    payload = copy.deepcopy(day_payload(7))
    payload["flights"][0]["departure"] = "early morning"  # type: ignore[index]
    first = P.parse_extracted(payload, params(7)).candidates[0]
    assert first.departure_time is None
    assert any("departure unreadable" in i for i in first.parse_issues)


def test_unknown_schema_is_unrecognised() -> None:
    payload = {**day_payload(7), "schema": "indigo-extract/2"}
    assert P.parse_extracted(payload, params()).page_state is PageState.UNRECOGNISED


@pytest.mark.parametrize(
    ("kind", "state"),
    [
        ("challenge", PageState.ACCESS_CHALLENGE),
        ("error", PageState.SITE_ERROR),
        ("no_flights", PageState.NO_FLIGHTS_MESSAGE),
        ("maintenance", PageState.UNRECOGNISED),
    ],
)
def test_non_results_pages_are_classified(kind: str, state: PageState) -> None:
    assert P.parse_extracted(non_results_page(kind, "x"), params()).page_state is state


def test_the_committed_fixture_is_generated_by_the_documented_builder() -> None:
    committed = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert committed == json.loads(json.dumps(build_fixture()))
    assert committed["data_class"] == "SYNTHETIC_FIXTURE"
    numbers = {f["flight_label"] for page in committed["pages"].values() for f in page["flights"]}
    assert numbers and all(n.startswith("6E 9") for n in numbers), (
        "fixture flight numbers must be invented"
    )
