"""Earliest eligible flight per departure band -- ADR-0065 s4. Never by price.

    Sort by DEPARTURE TIME. Take the earliest eligible flight in each
    departure-hour band 2-6. Never select by price.

This module is where that sentence is enforced for automated collection, and it
is deliberately incapable of violating it: the only ordering it uses is
:func:`departure_order`, which reads departure time and flight number and
nothing else. It never reads a fare, and it never reads the order the page
rendered the cards in -- IndiGo defaults to cheapest-first, so page order *is*
price order.

A band with no eligible flight yields no selection. Nothing is borrowed from a
neighbouring band to make up the count; an empty band is a market fact.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import time

from apix.ingestion.collectors.candidates import FlightCandidate
from apix.ingestion.collectors.contract import CONTRACT_BANDS, band_window
from apix.ingestion.collectors.eligibility import CandidateVerdict


def departure_order(candidate: FlightCandidate) -> tuple[time, int]:
    """The only sort key selection uses: departure time, then flight number.

    The flight-number tie-break makes two flights departing in the same minute
    select identically on every run, whatever order the page listed them in.
    Callers must pass eligible candidates, which guarantees both fields exist.
    """
    assert candidate.departure_time is not None
    assert candidate.flight_number is not None
    return candidate.departure_time, int(candidate.flight_number)


@dataclass(frozen=True, slots=True)
class BandSelection:
    """One contracted band: its eligible flights in departure order, and the pick."""

    band: int
    eligible: tuple[FlightCandidate, ...]

    @property
    def window(self) -> str:
        return band_window(self.band)

    @property
    def eligible_count(self) -> int:
        return len(self.eligible)

    @property
    def selected(self) -> FlightCandidate | None:
        return self.eligible[0] if self.eligible else None


@dataclass(frozen=True, slots=True)
class SelectionResult:
    """The band selections plus the flights that could not be selected, and why."""

    bands: tuple[BandSelection, ...]
    ineligible: tuple[CandidateVerdict, ...]
    #: Cards repeating a flight identity already seen. Kept for audit, not selected twice.
    repeated_cards: tuple[FlightCandidate, ...] = ()

    def band(self, number: int) -> BandSelection:
        for b in self.bands:
            if b.band == number:
                return b
        raise KeyError(f"band {number} is not a contracted band {CONTRACT_BANDS}")

    @property
    def selected(self) -> tuple[FlightCandidate, ...]:
        return tuple(b.selected for b in self.bands if b.selected is not None)

    @property
    def empty_bands(self) -> tuple[int, ...]:
        return tuple(b.band for b in self.bands if b.selected is None)

    def ineligible_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for verdict in self.ineligible:
            for reason in verdict.reasons:
                counts[reason.value] = counts.get(reason.value, 0) + 1
        return dict(sorted(counts.items()))


def select_earliest_per_band(verdicts: Iterable[CandidateVerdict]) -> SelectionResult:
    """Apply the selection rule to assessed flights.

    Deterministic and order-independent: the same set of flights produces the
    same selection however it is ordered, and however its fares are set.
    """
    ineligible: list[CandidateVerdict] = []
    by_band: dict[int, list[FlightCandidate]] = {b: [] for b in CONTRACT_BANDS}
    for verdict in verdicts:
        if not verdict.eligible:
            ineligible.append(verdict)
            continue
        band = verdict.band
        assert band is not None and band in by_band  # eligibility guarantees both
        by_band[band].append(verdict.candidate)

    bands: list[BandSelection] = []
    repeated: list[FlightCandidate] = []
    for band in CONTRACT_BANDS:
        unique: list[FlightCandidate] = []
        seen: set[tuple[time, int]] = set()
        # Sorting by (departure_order, position) only decides which of two cards
        # for the SAME flight is kept; it never chooses between flights.
        for cand in sorted(by_band[band], key=lambda c: (departure_order(c), c.position)):
            key = departure_order(cand)
            if key in seen:
                repeated.append(cand)
                continue
            seen.add(key)
            unique.append(cand)
        bands.append(BandSelection(band=band, eligible=tuple(unique)))

    return SelectionResult(
        bands=tuple(bands),
        ineligible=tuple(sorted(ineligible, key=lambda v: v.candidate.position)),
        repeated_cards=tuple(repeated),
    )


__all__ = ["BandSelection", "SelectionResult", "departure_order", "select_earliest_per_band"]
