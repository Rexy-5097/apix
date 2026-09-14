"""Automated collection: eligibility, earliest-per-band selection, fare choice.

The load-bearing invariant of this file:

    Selection is the EARLIEST ELIGIBLE flight in each band -- never the cheapest.

It is tested four ways: the worked example from the collection brief, a
property test over random prices and page orders, a structural test proving the
selection code never touches a fare, and (in ``test_collector_runner.py``) an
end-to-end regression on a page listed cheapest-first.
"""

from __future__ import annotations

from datetime import date, time, timedelta
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from apix.ingestion.collectors.candidates import FareOption, FlightCandidate
from apix.ingestion.collectors.contract import CollectionContract, SearchParams
from apix.ingestion.collectors.eligibility import Ineligibility, assess, assess_all
from apix.ingestion.collectors.fares import (
    FareExclusion,
    FareStatus,
    choose_contract_fare,
    normalise_family_label,
)
from apix.ingestion.collectors.normalize import to_observation, to_unpriced
from apix.ingestion.collectors.selection import SelectionResult, select_earliest_per_band
from apix.schemas.enums import APWBucket, ChangePolicy, FareClass, SourceType
from apix.schemas.observation import FareBreakdown

COLLECTION = date(2026, 9, 15)
TRAVEL = COLLECTION + timedelta(days=7)
PARAMS = SearchParams("indigo-direct", CollectionContract(), COLLECTION, TRAVEL)
CONTRACT = CollectionContract()


def fare(
    family: str,
    price: int | None,
    *,
    bag: int | None = 15,
    available: bool = True,
    currency: str | None = "INR",
    concession: bool = False,
    change: ChangePolicy | None = ChangePolicy.FEE,
    cancel: ChangePolicy | None = ChangePolicy.FEE,
) -> FareOption:
    return FareOption(
        family_label=family,
        payable_fare=None if price is None else Decimal(price),
        currency=currency,
        available=available,
        checked_baggage_kg=bag,
        change_policy=change,
        cancellation_policy=cancel,
        breakdown=FareBreakdown(base_fare=Decimal("5065"), taxes=Decimal("1465")),
        concession=concession,
    )


def standard(saver_price: int) -> tuple[FareOption, ...]:
    return (
        fare("Lite fare", saver_price - 225, bag=0),
        fare("Saver fare", saver_price),
        fare("Flexi fare", saver_price + 1500, change=ChangePolicy.FREE),
    )


def flight(
    number: str | None,
    dep: time | None,
    *,
    position: int = 0,
    price: int = 6000,
    origin: str | None = "DEL",
    destination: str | None = "BOM",
    stops: int | None = 0,
    carrier: str | None = "6E",
    operator: str | None = "6E",
    departure_date: date | None = TRAVEL,
    duration: int | None = 135,
    fares: tuple[FareOption, ...] | None = None,
    sold_out: bool = False,
) -> FlightCandidate:
    return FlightCandidate(
        position=position,
        raw_label=f"6E {number}",
        marketing_carrier=carrier,
        operating_carrier=operator,
        flight_number=number,
        origin=origin,
        destination=destination,
        departure_date=departure_date,
        departure_time=dep,
        arrival_time=None,
        duration_minutes=duration,
        stops=stops,
        sold_out=sold_out,
        fares=standard(price) if fares is None else fares,
    )


def select(flights: list[FlightCandidate]) -> SelectionResult:
    return select_earliest_per_band(assess_all(flights, PARAMS))


def selected_numbers(result: SelectionResult) -> dict[int, str | None]:
    return {b.band: (b.selected.flight_number if b.selected else None) for b in result.bands}


# ── the invariant ────────────────────────────────────────────────────────────


def test_earliest_flight_is_selected_even_when_later_flights_are_cheaper() -> None:
    """The worked example: 06:05 at 6530, 07:20 at 6100, 08:40 at 5900 -> 06:05."""
    result = select(
        [
            flight("9103", time(8, 40), position=0, price=5900),
            flight("9102", time(7, 20), position=1, price=6100),
            flight("9101", time(6, 5), position=2, price=6530),
        ]
    )
    chosen = result.band(2).selected
    assert chosen is not None
    assert (chosen.flight_number, chosen.departure_time) == ("9101", time(6, 5))
    assert result.band(2).eligible_count == 3


BAND_FLIGHTS = [
    ("9101", time(6, 5)),
    ("9102", time(7, 20)),
    ("9201", time(9, 30)),
    ("9202", time(11, 0)),
    ("9301", time(12, 45)),
    ("9401", time(15, 5)),
    ("9501", time(18, 30)),
    ("9502", time(20, 10)),
]
EXPECTED = {2: "9101", 3: "9201", 4: "9301", 5: "9401", 6: "9501"}


@settings(max_examples=200, deadline=None)
@given(
    prices=st.lists(st.integers(min_value=1500, max_value=30000), min_size=8, max_size=8),
    order=st.permutations(list(range(8))),
)
def test_selection_is_invariant_to_prices_and_page_order(
    prices: list[int], order: list[int]
) -> None:
    flights = [
        flight(num, dep, position=order[i], price=prices[i])
        for i, (num, dep) in enumerate(BAND_FLIGHTS)
    ]
    shuffled = [flights[i] for i in order]
    assert selected_numbers(select(shuffled)) == EXPECTED


class _Untouchable(tuple):  # type: ignore[type-arg]
    """A fares tuple that fails the test the moment anything reads it."""

    def __iter__(self):  # type: ignore[no-untyped-def]
        raise AssertionError("selection read a fare")

    def __len__(self) -> int:
        raise AssertionError("selection read a fare")

    def __getitem__(self, item):  # type: ignore[no-untyped-def]
        raise AssertionError("selection read a fare")


def test_eligibility_and_selection_never_read_a_fare() -> None:
    flights = [flight(num, dep, fares=_Untouchable()) for num, dep in BAND_FLIGHTS]
    assert selected_numbers(select(flights)) == EXPECTED


def test_same_minute_departures_break_ties_by_flight_number_not_page_order() -> None:
    a = flight("9105", time(6, 5), position=0, price=5000)
    b = flight("9102", time(6, 5), position=1, price=9000)
    assert selected_numbers(select([a, b]))[2] == "9102"
    assert selected_numbers(select([b, a]))[2] == "9102"


def test_a_repeated_card_for_the_same_flight_is_not_selected_twice() -> None:
    result = select(
        [flight("9101", time(6, 5), position=0), flight("9101", time(6, 5), position=4)]
    )
    assert result.band(2).eligible_count == 1
    assert len(result.repeated_cards) == 1


def test_an_empty_band_is_never_filled_from_a_neighbouring_band() -> None:
    result = select(
        [
            flight("9101", time(6, 5)),
            flight("9102", time(7, 5)),
            flight("9103", time(8, 5)),
            flight("9201", time(9, 5)),
        ]
    )
    assert selected_numbers(result) == {2: "9101", 3: "9201", 4: None, 5: None, 6: None}
    assert result.empty_bands == (4, 5, 6)


# ── eligibility ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"origin": "HDO"}, Ineligibility.ALTERNATE_ORIGIN),
        ({"destination": "NMI"}, Ineligibility.ALTERNATE_DESTINATION),
        ({"origin": None}, Ineligibility.MISSING_ROUTE),
        ({"stops": 1}, Ineligibility.NOT_NONSTOP),
        ({"stops": None}, Ineligibility.STOPS_UNKNOWN),
        ({"carrier": "AI"}, Ineligibility.NOT_MARKETED_BY_CARRIER),
        ({"operator": "Operated by Partner Air"}, Ineligibility.NOT_OPERATED_BY_CARRIER),
        ({"operator": None}, Ineligibility.OPERATOR_UNKNOWN),
        ({"departure_date": TRAVEL + timedelta(days=1)}, Ineligibility.WRONG_DEPARTURE_DATE),
        ({"departure_date": None}, Ineligibility.MISSING_DEPARTURE_DATE),
    ],
)
def test_ineligible_flights_carry_their_reason(
    kwargs: dict[str, object], reason: Ineligibility
) -> None:
    verdict = assess(flight("9101", time(6, 5), **kwargs), PARAMS)  # type: ignore[arg-type]
    assert not verdict.eligible
    assert reason in verdict.reasons


def test_missing_identity_and_time_are_ineligible() -> None:
    assert Ineligibility.MISSING_FLIGHT_IDENTITY in assess(flight(None, time(6, 5)), PARAMS).reasons
    assert (
        Ineligibility.MISSING_FLIGHT_IDENTITY in assess(flight("6E91", time(6, 5)), PARAMS).reasons
    )
    assert Ineligibility.MISSING_DEPARTURE_TIME in assess(flight("9101", None), PARAMS).reasons


@pytest.mark.parametrize(
    ("dep", "reason"),
    [
        (time(5, 40), Ineligibility.BEFORE_CONTRACT_BANDS),
        (time(5, 59), Ineligibility.BEFORE_CONTRACT_BANDS),
        (time(21, 0), Ineligibility.AFTER_CONTRACT_BANDS),
        (time(23, 30), Ineligibility.AFTER_CONTRACT_BANDS),
    ],
)
def test_flights_outside_06_00_to_20_59_are_never_collected(
    dep: time, reason: Ineligibility
) -> None:
    assert assess(flight("9001", dep), PARAMS).reasons == (reason,)


@pytest.mark.parametrize("dep", [time(6, 0), time(8, 59), time(20, 59)])
def test_band_boundaries_inside_the_contract_are_eligible(dep: time) -> None:
    assert assess(flight("9101", dep), PARAMS).eligible


def test_an_early_cheap_flight_cannot_displace_band_2() -> None:
    result = select(
        [flight("9001", time(5, 40), price=3000), flight("9101", time(6, 5), price=9000)]
    )
    assert selected_numbers(result)[2] == "9101"
    assert result.ineligible_counts() == {"BEFORE_CONTRACT_BANDS": 1}


def test_an_ineligible_earlier_flight_in_band_does_not_block_the_next_eligible_one() -> None:
    result = select(
        [
            flight("9201", time(9, 10), stops=1, price=4000),
            flight("9202", time(9, 45), operator="Operated by Partner Air"),
            flight("9203", time(10, 30), price=8000),
        ]
    )
    assert selected_numbers(result)[3] == "9203"
    assert result.band(3).eligible_count == 1


# ── fare choice ──────────────────────────────────────────────────────────────


def test_saver_is_recorded_not_the_cheaper_lite() -> None:
    decision = choose_contract_fare(flight("9101", time(6, 5), price=6530), CONTRACT)
    assert decision.status is FareStatus.PRICED
    assert decision.option is not None
    assert decision.option.family_label == "Saver fare"
    assert decision.option.payable_fare == Decimal("6530")


def test_lite_is_never_substituted_when_saver_is_missing() -> None:
    fares = (fare("Lite fare", 5000, bag=0), fare("Flexi fare", 8000))
    decision = choose_contract_fare(flight("9101", time(6, 5), fares=fares), CONTRACT)
    assert decision.status is FareStatus.EXCLUDED
    assert decision.exclusion is FareExclusion.FARE_FAMILY_NOT_OFFERED
    assert decision.option is None


def test_a_sold_out_saver_is_unpriced_and_not_replaced_by_another_family() -> None:
    fares = (
        fare("Lite fare", 5000, bag=0),
        fare("Saver fare", 6000, available=False),
        fare("Flexi fare", 8000),
    )
    decision = choose_contract_fare(flight("9501", time(18, 30), fares=fares), CONTRACT)
    assert decision.status is FareStatus.SOLD_OUT
    assert "Flexi fare" in decision.detail


def test_a_sold_out_flight_is_unpriced() -> None:
    decision = choose_contract_fare(flight("9501", time(18, 30), sold_out=True, fares=()), CONTRACT)
    assert decision.status is FareStatus.SOLD_OUT


@pytest.mark.parametrize(
    ("saver", "exclusion"),
    [
        (fare("Saver fare", 6000, currency="USD"), FareExclusion.CURRENCY_MISMATCH),
        (fare("Saver fare", 6000, concession=True), FareExclusion.CONCESSION_FARE),
        (fare("Saver fare", None), FareExclusion.FARE_UNREADABLE),
        (fare("Saver fare", 6000, bag=None), FareExclusion.ENTITLEMENTS_UNDETERMINABLE),
        (fare("Saver fare", 6000, change=None), FareExclusion.ENTITLEMENTS_UNDETERMINABLE),
        (fare("Saver fare", 6000, bag=0), FareExclusion.NO_CHECKED_BAGGAGE),
    ],
)
def test_unusable_saver_fares_are_excluded_with_a_reason(
    saver: FareOption, exclusion: FareExclusion
) -> None:
    decision = choose_contract_fare(flight("9101", time(6, 5), fares=(saver,)), CONTRACT)
    assert decision.status is FareStatus.EXCLUDED
    assert decision.exclusion is exclusion


def test_a_cheaper_checked_baggage_family_means_saver_fails_the_procedure_rule() -> None:
    fares = (fare("Value fare", 5800, bag=15), fare("Saver fare", 6000))
    decision = choose_contract_fare(flight("9101", time(6, 5), fares=fares), CONTRACT)
    assert decision.exclusion is FareExclusion.CHEAPER_CHECKED_BAGGAGE_FARE


def test_two_saver_tiles_are_ambiguous() -> None:
    fares = (fare("Saver fare", 6000), fare("SAVER", 6100))
    decision = choose_contract_fare(flight("9101", time(6, 5), fares=fares), CONTRACT)
    assert decision.exclusion is FareExclusion.FARE_FAMILY_AMBIGUOUS


def test_an_unreadable_duration_excludes_rather_than_invents() -> None:
    decision = choose_contract_fare(flight("9101", time(6, 5), duration=None), CONTRACT)
    assert decision.exclusion is FareExclusion.REQUIRED_FIELD_UNREADABLE


@pytest.mark.parametrize(
    ("label", "normalised"),
    [
        ("Saver fare", "saver"),
        ("SAVER", "saver"),
        ("  Saver  Fare ", "saver"),
        ("Lite fare", "lite"),
        ("Flexi Plus", "flexi plus"),
    ],
)
def test_family_label_normalisation(label: str, normalised: str) -> None:
    assert normalise_family_label(label) == normalised


# ── canonical conversion ─────────────────────────────────────────────────────


def test_a_priced_decision_becomes_the_existing_canonical_observation() -> None:
    chosen = flight("9101", time(6, 5), price=6530)
    decision = choose_contract_fare(chosen, CONTRACT)
    obs = to_observation(
        decision,
        PARAMS,
        frame_tag="fixture",
        source_type=SourceType.SYNTHETIC,
        observed_at=COLLECTION_AT,
    )
    assert obs.observation_id == "20260915-fixture-indigo-direct-6E9101-20260922-Saver fare"
    assert (obs.origin, obs.destination, obs.carrier, obs.flight_number) == (
        "DEL",
        "BOM",
        "6E",
        "9101",
    )
    assert obs.payable_fare == Decimal("6530")
    assert obs.apw_bucket is APWBucket.T_PLUS_7
    assert obs.departure_hour_band == 2
    assert obs.fare_class is FareClass.STANDARD
    assert obs.source_type is SourceType.SYNTHETIC
    assert obs.source_group is None
    assert obs.fare_breakdown.fees is None
    assert obs.fare_breakdown.base_fare == Decimal("5065")


COLLECTION_AT = __import__("datetime").datetime(2026, 9, 15, 21, 10)


def test_conversions_refuse_the_wrong_decision_status() -> None:
    sold = choose_contract_fare(flight("9501", time(18, 30), sold_out=True, fares=()), CONTRACT)
    priced = choose_contract_fare(flight("9101", time(6, 5)), CONTRACT)
    with pytest.raises(ValueError, match="PRICED"):
        to_observation(
            sold,
            PARAMS,
            frame_tag="fixture",
            source_type=SourceType.SYNTHETIC,
            observed_at=COLLECTION_AT,
        )
    with pytest.raises(ValueError, match="SOLD_OUT"):
        to_unpriced(
            priced,
            PARAMS,
            frame_tag="fixture",
            run_id="r",
            attempt_id="a",
            observed_at=COLLECTION_AT,
        )
    unpriced = to_unpriced(
        sold, PARAMS, frame_tag="fixture", run_id="r", attempt_id="a", observed_at=COLLECTION_AT
    )
    assert unpriced.unpriced_id == "20260915-fixture-indigo-direct-6E9501-20260922-Saver"
