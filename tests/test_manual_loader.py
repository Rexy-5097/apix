"""The manual-collection loader — the bridge from a person to the store.

Manual collection is the only permitted mode (the Checkpoint 2G automation gate
rates zero sources ``AUTOMATION_ALLOWED``), so this loader is the sole path by
which a real fare reaches APIx. Every defect it fails to catch becomes a number
in a published index.

The tests are therefore mostly about **refusals**. What the loader must never do
quietly matters more than what it does: a blank that becomes a zero, a sold-out
flight that acquires a price, an attempt whose claimed count drifts from what was
stored. Each of those is invisible downstream and none is recoverable.
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from apix.ingestion.store import UnpricedFlight, open_store
from apix.schemas.enums import Availability, CollectionOutcome

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "collection"))

from load_manual import LoadError, load_day

T = date(2026, 9, 12)
TRAVEL = "2026-09-19"  # exactly T+7 — spec A.3 assigns by EXACT lead time

ATTEMPT_HEADER = "travel_date,source_id,time_ist,origin,destination,outcome,source_group,notes"
FARE_HEADER = (
    "travel_date,source_id,time_ist,origin,destination,carrier,flight_number,"
    "departure_time,stops,duration_minutes,fare_family_raw,availability,"
    "payable_fare,base_fare,taxes,fees,user_development_fee,"
    "checked_baggage_kg,change_permitted,cancellation_permitted,source_group,notes"
)


def _csv_line(values: Iterable[str]) -> str:
    """Quote like a real CSV writer, so a value containing a comma survives."""
    buf = io.StringIO()
    csv.writer(buf, lineterminator="").writerow(list(values))
    return buf.getvalue()


def fare_row(**over: str) -> str:
    cells = {
        "travel_date": TRAVEL,
        "source_id": "indigo-direct",
        "time_ist": "21:15",
        "origin": "DEL",
        "destination": "BOM",
        "carrier": "6E",
        "flight_number": "2045",
        "departure_time": "06:20",
        "stops": "0",
        "duration_minutes": "135",
        "fare_family_raw": "SAVER",
        "availability": "AVAILABLE",
        "payable_fare": "5432.00",
        "base_fare": "4100.00",
        "taxes": "1002.00",
        "fees": "",
        "user_development_fee": "330.00",
        "checked_baggage_kg": "15",
        "change_permitted": "FEE",
        "cancellation_permitted": "FEE",
        "source_group": "",
        "notes": "",
    }
    cells.update(over)
    return _csv_line(cells[k] for k in FARE_HEADER.split(","))


def attempt_row(**over: str) -> str:
    cells = {
        "travel_date": TRAVEL,
        "source_id": "indigo-direct",
        "time_ist": "21:05",
        "origin": "DEL",
        "destination": "BOM",
        "outcome": "SUCCESS",
        "source_group": "",
        "notes": "",
    }
    cells.update(over)
    return _csv_line(cells[k] for k in ATTEMPT_HEADER.split(","))


def run_load(
    tmp_path: Path, attempts: list[str], fares: list[str], **kw: object
) -> dict[str, object]:
    (tmp_path / "a.csv").write_text("\n".join([ATTEMPT_HEADER, *attempts]), encoding="utf-8")
    (tmp_path / "f.csv").write_text("\n".join([FARE_HEADER, *fares]), encoding="utf-8")
    args = argparse.Namespace(
        store=tmp_path / "store",
        date=T,
        window="primary",
        collector="Test Collector",
        fares=tmp_path / "f.csv",
        attempts=tmp_path / "a.csv",
        artifacts=None,
        precedence="spike-single-source-v1",
        basket="2026-Q3",
        protocol="acquisition-protocol-2G",
        methodology="2.1",
        notes="",
        started=None,
    )
    for k, v in kw.items():
        setattr(args, k, v)
    return load_day(args)


# ─── The happy path ──────────────────────────────────────────────────────────


def test_loads_a_clean_day(tmp_path: Path) -> None:
    report = run_load(tmp_path, [attempt_row()], [fare_row()])

    assert report["attempts"] == 1
    assert report["observations"] == 1
    assert report["successes"] == 1
    assert report["routes"] == ["DEL-BOM"]
    assert report["integrity_problems"] == []


def test_attempt_count_is_reconciled_not_trusted(tmp_path: Path) -> None:
    """The attempt's claimed count comes from what was recorded, not the CSV.

    ``CollectionAttempt`` requires ``len(observation_ids) == quotes_parsed``, and
    ``verify()`` compares that claim against the observations actually stored. A
    loader that let the human type the count would be reconciling the store
    against a number the human also typed.
    """
    report = run_load(
        tmp_path,
        [attempt_row()],
        [fare_row(), fare_row(flight_number="5011", departure_time="09:45")],
    )
    assert report["observations"] == 2
    assert report["integrity_problems"] == []

    store = open_store(tmp_path / "store")
    try:
        attempt = store.attempts(T)[0]
        assert attempt.quotes_parsed == 2
        assert len(attempt.observation_ids) == 2
    finally:
        store.close()


def test_apw_bucket_is_derived_from_the_exact_lead_time(tmp_path: Path) -> None:
    report = run_load(tmp_path, [attempt_row()], [fare_row()])
    assert report["apw_buckets"] == [7]


def test_a_lead_time_matching_no_bucket_still_loads(tmp_path: Path) -> None:
    """Spec A.3 permits no rounding, so an off-bucket quote is stored, not lost.

    It is inadmissible and will not reach the index. Refusing to store it would
    destroy the evidence that the collection happened at all.
    """
    off = "2026-09-20"  # T+8 — matches no bucket
    report = run_load(tmp_path, [attempt_row(travel_date=off)], [fare_row(travel_date=off)])
    assert report["observations"] == 1
    assert report["apw_buckets"] == []


# ─── Blank is not zero ───────────────────────────────────────────────────────


def test_an_unrendered_component_stays_none(tmp_path: Path) -> None:
    """The single most damaging thing a loader could do quietly.

    A zero asserts the charge does not exist; ``None`` says the source did not
    render it. Spec A.4 is explicit that the index is never blocked on a
    breakdown the site does not show — so there is nothing to gain by inventing
    the parts, and a fabricated component is undetectable downstream.
    """
    run_load(tmp_path, [attempt_row()], [fare_row(fees="")])

    store = open_store(tmp_path / "store")
    try:
        breakdown = store.observations(T)[0].fare_breakdown
        assert breakdown.fees is None
        assert breakdown.fees != Decimal("0")
        assert breakdown.base_fare == Decimal("4100.00")
    finally:
        store.close()


def test_a_fully_blank_breakdown_is_reported_not_repaired(tmp_path: Path) -> None:
    report = run_load(
        tmp_path,
        [attempt_row()],
        [fare_row(base_fare="", taxes="", fees="", user_development_fee="")],
    )
    assert report["observations"] == 1
    assert report["incomplete_fare_breakdown"] == 1


def test_a_non_numeric_fare_is_refused(tmp_path: Path) -> None:
    with pytest.raises(LoadError, match="not a number"):
        run_load(tmp_path, [attempt_row()], [fare_row(payable_fare="n/a")])


def test_rupee_symbols_and_separators_are_tolerated(tmp_path: Path) -> None:
    """Typing what the page shows must not be a data-entry trap."""
    run_load(tmp_path, [attempt_row()], [fare_row(payable_fare="₹5,432.00")])
    store = open_store(tmp_path / "store")
    try:
        assert store.observations(T)[0].payable_fare == Decimal("5432.00")
    finally:
        store.close()


# ─── Sold out is a disappeared item, not a cheap fare ────────────────────────


def test_a_sold_out_flight_is_stored_without_a_price(tmp_path: Path) -> None:
    """Spec D.6. It cannot be a canonical observation, and must not be dropped.

    ``Observation.payable_fare`` is a non-optional positive Decimal, so the only
    ways to put a sold-out flight there are to invent a number or write a zero.
    Dropping it instead would make "sold out" indistinguishable from "flight not
    operating" — the distinction AMB-8's denominator turns on.
    """
    report = run_load(
        tmp_path,
        [attempt_row(outcome="TECHNICAL_FAILURE")],
        [fare_row(availability="SOLD_OUT", payable_fare="")],
    )
    assert report["observations"] == 0
    assert report["unpriced_flights"] == 1

    store = open_store(tmp_path / "store")
    try:
        flight = store.unpriced_flights(T)[0]
        assert flight.availability is Availability.SOLD_OUT
        assert flight.flight_number == "2045"
        assert flight.route == "DEL-BOM"
    finally:
        store.close()


def test_sold_out_with_a_price_is_refused(tmp_path: Path) -> None:
    with pytest.raises(LoadError, match="SOLD_OUT carries no payable_fare"):
        run_load(
            tmp_path,
            [attempt_row()],
            [fare_row(availability="SOLD_OUT", payable_fare="5432.00")],
        )


def test_available_without_a_price_is_refused(tmp_path: Path) -> None:
    """The mirror error, and the one that would otherwise become a zero."""
    with pytest.raises(LoadError, match="needs a payable_fare"):
        run_load(tmp_path, [attempt_row()], [fare_row(payable_fare="")])


def test_an_available_unpriced_flight_cannot_be_constructed() -> None:
    with pytest.raises(ValueError, match="belongs in canonical_observation"):
        UnpricedFlight(
            unpriced_id="u1",
            run_id="r1",
            attempt_id="a1",
            collection_date=T,
            origin="DEL",
            destination="BOM",
            travel_date=date(2026, 9, 19),
            carrier="6E",
            flight_number="2045",
            departure_time_local=__import__("datetime").time(6, 20),
            observation_ts=__import__("datetime").datetime(2026, 9, 12, 21, 15),
            source_id="indigo-direct",
            availability=Availability.AVAILABLE,
        )


# ─── Every fare belongs to a recorded attempt ────────────────────────────────


def test_a_fare_without_an_attempt_is_refused(tmp_path: Path) -> None:
    """The link is what makes coverage measurable at all."""
    with pytest.raises(LoadError, match="not in"):
        run_load(tmp_path, [attempt_row()], [fare_row(travel_date="2026-10-12")])


def test_success_with_no_fares_is_refused(tmp_path: Path) -> None:
    """An attempt that ran cleanly and found nothing is not SUCCESS — spec H.1."""
    with pytest.raises(LoadError, match="SUCCESS but no fares"):
        run_load(tmp_path, [attempt_row()], [])


def test_a_failed_attempt_claiming_fares_is_refused(tmp_path: Path) -> None:
    with pytest.raises(LoadError, match="NO_FLIGHT but 1 fares"):
        run_load(tmp_path, [attempt_row(outcome="NO_FLIGHT")], [fare_row()])


def test_an_unknown_outcome_is_refused_with_the_valid_set(tmp_path: Path) -> None:
    with pytest.raises(LoadError, match="is not one of"):
        run_load(tmp_path, [attempt_row(outcome="BLOCKED")], [fare_row()])


def test_a_stop_signal_round_trips(tmp_path: Path) -> None:
    """An access challenge is recorded as itself, never as a generic outage.

    It is a policy event with a compliance meaning: the run must not be repeated
    against that source until a human has reviewed it.
    """
    report = run_load(tmp_path, [attempt_row(outcome="CAPTCHA_OR_ANTIBOT_STOP")], [])
    assert report["collector_failures"] == 1
    assert report["observations"] == 0

    store = open_store(tmp_path / "store")
    try:
        attempt = store.attempts(T)[0]
        assert attempt.outcome is CollectionOutcome.CAPTCHA_OR_ANTIBOT_STOP
        assert attempt.outcome.is_stop_signal
    finally:
        store.close()


# ─── Identity hygiene ────────────────────────────────────────────────────────


def test_a_carrier_prefixed_flight_number_is_refused(tmp_path: Path) -> None:
    """Two spellings of one flight defeat the spec D.4 duplicate rule."""
    with pytest.raises(LoadError, match="digits only"):
        run_load(tmp_path, [attempt_row()], [fare_row(flight_number="6E2045")])


def test_a_duplicate_offer_fails_the_load(tmp_path: Path) -> None:
    """Spec D.4. Not silently replaced — both readings need a person to look."""
    with pytest.raises(Exception, match=r"constraint|duplicate|UNIQUE"):
        run_load(tmp_path, [attempt_row()], [fare_row(), fare_row()])


def test_two_fare_families_on_one_flight_both_load(tmp_path: Path) -> None:
    """They differ in the duplicate tuple, so they are two offers, not one."""
    report = run_load(
        tmp_path,
        [attempt_row()],
        [fare_row(), fare_row(fare_family_raw="FLEXI", payable_fare="7800.00")],
    )
    assert report["observations"] == 2


def test_a_missing_required_column_names_the_row(tmp_path: Path) -> None:
    with pytest.raises(LoadError, match="row 2: required column 'carrier'"):
        run_load(tmp_path, [attempt_row()], [fare_row(carrier="")])


# ─── Nothing is written on a validation failure ──────────────────────────────


def test_a_rejected_day_writes_nothing(tmp_path: Path) -> None:
    """A half-loaded day is worse than an unloaded one: it looks complete."""
    good = fare_row()
    bad = fare_row(flight_number="5011", departure_time="07:45", payable_fare="oops")
    with pytest.raises(LoadError):
        run_load(tmp_path, [attempt_row()], [good, bad])

    assert not (tmp_path / "store" / "collection.sqlite3").exists()


# ─── The window comes from the declared file, not from the caller ────────────


def test_the_window_is_read_from_the_declared_yaml(tmp_path: Path) -> None:
    run_load(tmp_path, [attempt_row()], [fare_row()])
    store = open_store(tmp_path / "store")
    try:
        run = store.runs()[0]
        assert run.collection_window_start.hour == 21
        assert run.collection_window_end.hour == 22
        assert run.frame_id.endswith("@primary")
        assert run.collector_identity == "Test Collector"
    finally:
        store.close()


def test_the_diagnostic_window_is_a_separate_frame(tmp_path: Path) -> None:
    """ADR-0064: only ``@primary`` runs are index input.

    Blending them would average 09:00 and 21:00 prices, which spec A.5 says are
    two different prices rather than two draws from one.
    """
    run_load(
        tmp_path,
        [attempt_row(time_ist="09:10")],
        [fare_row(time_ist="09:12")],
        window="diagnostic_oq1",
    )
    store = open_store(tmp_path / "store")
    try:
        run = store.runs()[0]
        assert run.frame_id.endswith("@diagnostic-oq1")
        assert run.collection_window_start.hour == 9
    finally:
        store.close()


def test_an_undeclared_window_is_refused(tmp_path: Path) -> None:
    with pytest.raises(LoadError, match="not declared"):
        run_load(tmp_path, [attempt_row()], [fare_row()], window="whenever")


def test_a_quote_outside_the_window_is_flagged_not_discarded(tmp_path: Path) -> None:
    """Spec A.5. Storing it and flagging it is the whole rule.

    Faking the timestamp to stay inside the window would corrupt the record
    permanently; recording it honestly costs one flagged row.
    """
    report = run_load(tmp_path, [attempt_row()], [fare_row(time_ist="23:40")])
    assert report["observations"] == 1
    problems = report["integrity_problems"]
    assert isinstance(problems, list)
    assert len(problems) == 1
    assert "outside its" in problems[0]


# ─── Screenshots are evidence, so they are never filed against a guess ───────


def test_a_screenshot_is_bound_to_its_attempt(tmp_path: Path) -> None:
    shots = tmp_path / "shots"
    shots.mkdir()
    (shots / "20260912-primary-20260919.png").write_bytes(b"\x89PNG fake results page")

    report = run_load(tmp_path, [attempt_row()], [fare_row()], artifacts=shots)
    assert report["artifacts"] == 1
    assert report["integrity_problems"] == []

    store = open_store(tmp_path / "store")
    try:
        ref = store.artifact_refs()[0]
        assert ref.attempt_id == store.attempts(T)[0].attempt_id
        assert store.observations(T)[0].observation_id
        assert store.artifacts.get(ref.sha256) == b"\x89PNG fake results page"
    finally:
        store.close()


def test_an_unmatched_screenshot_fails_the_load(tmp_path: Path) -> None:
    """Better to refuse than to attach evidence to the wrong search."""
    shots = tmp_path / "shots"
    shots.mkdir()
    (shots / "screenshot.png").write_bytes(b"\x89PNG no date in the name")

    with pytest.raises(LoadError, match="matches 0 attempts"):
        run_load(tmp_path, [attempt_row()], [fare_row()], artifacts=shots)


def test_an_unmatched_screenshot_leaves_no_partial_day(tmp_path: Path) -> None:
    """The artifact check runs before the first write, not after.

    Checking inside the store block would commit the run and its attempts and
    then abort — exactly the half-loaded day that looks complete.
    """
    shots = tmp_path / "shots"
    shots.mkdir()
    (shots / "screenshot.png").write_bytes(b"\x89PNG no date in the name")

    with pytest.raises(LoadError):
        run_load(tmp_path, [attempt_row()], [fare_row()], artifacts=shots)

    assert not (tmp_path / "store" / "collection.sqlite3").exists()


def test_an_edited_artifact_is_reported_by_verify(tmp_path: Path) -> None:
    """Spec P.3 reproducibility is a claim about bytes, and this is the check."""
    shots = tmp_path / "shots"
    shots.mkdir()
    (shots / "20260912-primary-20260919.png").write_bytes(b"\x89PNG original")
    run_load(tmp_path, [attempt_row()], [fare_row()], artifacts=shots)

    store = open_store(tmp_path / "store")
    try:
        stored = store.artifact_refs()[0]
        (store.artifacts.root / stored.relative_path).write_bytes(b"\x89PNG tampered")
        problems = store.verify(T)
        assert len(problems) == 1
        assert "modified on disk" in problems[0]
    finally:
        store.close()


# ─── The flight-selection rule is machine-checked, not trusted ───────────────
#
# ADR-0065 §4. One flight per departure band, bands 2-6. The selection happens
# in a person's browser, so the loader is the only point it passes through code
# — and a violation is undetectable downstream: "the earliest five" on a dense
# route is internally consistent, silently morning-biased, and leaves
# departure_hour_band degenerate for the whole study.


def banded_day() -> tuple[list[str], list[str]]:
    """One eligible flight in each contracted band — the compliant shape."""
    times = [
        ("2045", "06:20"),
        ("5011", "09:45"),
        ("6153", "13:10"),
        ("2177", "16:35"),
        ("6821", "19:50"),
    ]
    return (
        [attempt_row()],
        [fare_row(flight_number=fn, departure_time=dt) for fn, dt in times],
    )


def test_one_flight_per_band_loads(tmp_path: Path) -> None:
    attempts, fares = banded_day()
    report = run_load(tmp_path, attempts, fares)
    assert report["observations"] == 5


def test_two_flights_in_one_band_is_refused(tmp_path: Path) -> None:
    """'The earliest five' clusters in bands 2-3 and must not load."""
    earliest_five = [
        fare_row(flight_number=fn, departure_time=dt)
        for fn, dt in [
            ("2045", "06:20"),
            ("5011", "06:55"),
            ("6153", "07:30"),
            ("2177", "08:05"),
            ("6821", "08:40"),
        ]
    ]
    with pytest.raises(LoadError, match="different flights in departure band 2"):
        run_load(tmp_path, [attempt_row()], earliest_five)


def test_one_flight_at_two_fare_families_is_one_selection(tmp_path: Path) -> None:
    """Two fare families on the same flight is one selection, not two."""
    report = run_load(
        tmp_path,
        [attempt_row()],
        [fare_row(), fare_row(fare_family_raw="FLEXI", payable_fare="7800.00")],
    )
    assert report["observations"] == 2


def test_a_flight_outside_the_contracted_bands_is_refused(tmp_path: Path) -> None:
    """Band 7 (21:00-24:00) is intermittently served and not collected."""
    with pytest.raises(LoadError, match=r"outside the contracted bands"):
        run_load(tmp_path, [attempt_row()], [fare_row(departure_time="22:15")])


def test_a_missing_band_is_not_an_error(tmp_path: Path) -> None:
    """An empty band is a market fact. Never pad it from a neighbour."""
    report = run_load(
        tmp_path,
        [attempt_row()],
        [
            fare_row(flight_number="2045", departure_time="06:20"),
            fare_row(flight_number="6821", departure_time="19:50"),
        ],
    )
    assert report["observations"] == 2


def test_a_sold_out_flight_still_occupies_its_band(tmp_path: Path) -> None:
    """It was selected, so it counts against the one-per-band rule."""
    with pytest.raises(LoadError, match="different flights in departure band 2"):
        run_load(
            tmp_path,
            [attempt_row()],
            [
                fare_row(flight_number="2045", departure_time="06:20"),
                fare_row(
                    flight_number="5011",
                    departure_time="07:30",
                    availability="SOLD_OUT",
                    payable_fare="",
                ),
            ],
        )
