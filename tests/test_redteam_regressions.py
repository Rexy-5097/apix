"""Regressions for the Checkpoint 2C red-team findings.

Each test here exists because an adversarial probe reproduced a defect that the
197-test suite passed over. They are kept in one file so the provenance of each
is unambiguous: **this is what green CI failed to catch.**

    D-1  parent_level silently converted a missing weight into zero
    D-2  Tier-1 provenance named observations that did not contribute
    D-3  build_matched_set accepted mixed collection dates
    T-1  the telescoping identity — the sole justification for the geometric
         mean — had no numeric test

None of these changes a v2.1 rule. They make the implementation do what the
methodology already said.
"""

from __future__ import annotations

import dataclasses
import math
from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest

from apix.schemas.enums import (
    CellStatus,
    ChangePolicy,
    Channel,
    SourceType,
    Tier,
)
from apix.schemas.keys import CellKey
from apix.schemas.observation import Entitlements, Observation
from apix.schemas.results import CellState
from apix.statistics.aggregation.weights import WeightError, renormalise_over_live_set
from apix.statistics.elementary.bands import band_price
from apix.statistics.elementary.matching import build_matched_set, cell_key_for
from apix.statistics.elementary.sources import SourcePrecedence
from apix.statistics.index.parent import parent_level

MONDAY = date(2026, 10, 5) - timedelta(days=date(2026, 10, 5).isoweekday() - 1)
APW = 7
STANDARD = Entitlements(15, ChangePolicy.FEE, ChangePolicy.FEE)
PRECEDENCE = SourcePrecedence(version="rt-v1", order={Channel.AIRLINE_DIRECT: ("a", "b")})


def ob(
    travel: date,
    flight: str,
    fare: str,
    *,
    dep: time = time(6, 0),
    source: str = "a",
    carrier: str = "6E",
    oid: str | None = None,
    collection: date | None = None,
) -> Observation:
    coll = collection if collection is not None else travel - timedelta(days=APW)
    return Observation(
        observation_id=oid or f"{coll}-{carrier}{flight}-{dep}-{source}",
        origin="DEL",
        destination="BOM",
        travel_date=travel,
        departure_time_local=dep,
        observation_ts=datetime.combine(coll, time(6, 0)),
        collection_date=coll,
        carrier=carrier,
        flight_number=flight,
        stops=0,
        duration_minutes=120,
        fare_family_raw="SAVER",
        channel=Channel.AIRLINE_DIRECT,
        source_id=source,
        entitlements=STANDARD,
        payable_fare=Decimal(fare),
        source_type=SourceType.SYNTHETIC,
    )


def state(cell: CellKey, level: float) -> CellState:
    return CellState(
        cell=cell,
        collection_date=MONDAY,
        level=level,
        status=CellStatus.PUBLISHED,
        parent=cell.parent(),
    )


# ---------------------------------------------------------------------------
# D-1 — a live child with no weight entry must raise, never default to zero
# ---------------------------------------------------------------------------


def test_d1_parent_level_rejects_a_live_child_with_no_weight() -> None:
    """Spec E.7.2, F.4, G.5. A missing weight is a defect, not a value of zero.

    **What the defect did.** ``parent_level`` called
    ``cell_weights.get(state.cell, 0.0)``, so a child absent from the weight map
    was silently given zero weight and dropped out of the mean. On the fixture
    below that turned the correct **200.0** into **150.0** — a 25% error on the
    level a new cell would enter at, with nothing logged.

    **Why the existing guard did not fire.** ``renormalise_over_live_set`` is
    documented to raise ``WeightError`` when *"live members have no weight
    assigned"*, and it does — see the companion test below. The ``.get`` default
    substituted a value before that check could ever see a missing key.
    """
    base = cell_key_for(ob(MONDAY, "101", "5000"))
    a = dataclasses.replace(base, carrier="6E")
    b = dataclasses.replace(base, carrier="AI")
    c = dataclasses.replace(base, carrier="SG")

    states = [state(a, 100.0), state(b, 200.0), state(c, 300.0)]

    # Sanity: with every weight present the answer is the equal-weighted mean.
    assert parent_level(states, {a: 1.0, b: 1.0, c: 1.0}) == pytest.approx(200.0)

    # 'c' is live and independently determined, but carries no weight entry.
    with pytest.raises(WeightError, match="no weight"):
        parent_level(states, {a: 1.0, b: 1.0})


def test_d1_the_underlying_renormalisation_guard_is_still_intact() -> None:
    """The guard the defect bypassed must remain, and must remain reachable."""
    with pytest.raises(WeightError, match="no weight assigned"):
        renormalise_over_live_set({"a": 1.0}, ["a", "missing"])

    # And the other two weight invariants it enforces are untouched.
    with pytest.raises(WeightError):
        renormalise_over_live_set({"a": 1.0, "b": -0.5}, ["a", "b"])
    assert renormalise_over_live_set({"a": 1.0}, []) == {}


def test_d1_a_weight_of_exactly_zero_is_still_a_legitimate_value() -> None:
    """Rejecting *missing* must not reject *present and zero*.

    A cell may legitimately carry zero weight. The fix distinguishes "absent from
    the map" from "present with value 0.0"; conflating them would trade one
    silent error for another.
    """
    base = cell_key_for(ob(MONDAY, "101", "5000"))
    a = dataclasses.replace(base, carrier="6E")
    b = dataclasses.replace(base, carrier="AI")

    level = parent_level([state(a, 100.0), state(b, 300.0)], {a: 0.0, b: 1.0})
    assert level == pytest.approx(300.0), (
        "a zero-weight child contributes nothing, but is not an error"
    )


