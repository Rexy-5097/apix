"""Which returned flights may be selected at all -- procedure s4, ADR-0065 s4.

A flight is eligible only if **every** condition holds. Each failure is recorded
with a reason rather than silently dropped, so the returned universe stays
auditable: a reviewer can see that the 05:40 departure, the one-stop and the
codeshare were on the page and why none of them was taken.

Price is not an input to anything in this module.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

from apix.ingestion.collectors.candidates import FlightCandidate
from apix.ingestion.collectors.contract import CONTRACT_BANDS, SearchParams, band_of


class Ineligibility(Enum):
    """Why a returned flight cannot be selected. Checked in declaration order."""

    MISSING_FLIGHT_IDENTITY = "MISSING_FLIGHT_IDENTITY"
    MISSING_DEPARTURE_TIME = "MISSING_DEPARTURE_TIME"
    MISSING_DEPARTURE_DATE = "MISSING_DEPARTURE_DATE"
    MISSING_ROUTE = "MISSING_ROUTE"
    #: A nearby or alternate airport, e.g. Hindon for Delhi. Not DEL.
    ALTERNATE_ORIGIN = "ALTERNATE_ORIGIN"
    ALTERNATE_DESTINATION = "ALTERNATE_DESTINATION"
    #: Departs on a date other than the one searched.
    WRONG_DEPARTURE_DATE = "WRONG_DEPARTURE_DATE"
    STOPS_UNKNOWN = "STOPS_UNKNOWN"
    NOT_NONSTOP = "NOT_NONSTOP"
    NOT_MARKETED_BY_CARRIER = "NOT_MARKETED_BY_CARRIER"
    OPERATOR_UNKNOWN = "OPERATOR_UNKNOWN"
    #: A codeshare on another carrier's metal.
    NOT_OPERATED_BY_CARRIER = "NOT_OPERATED_BY_CARRIER"
    #: Departs before 06:00 -- bands 0 and 1 are not collected.
    BEFORE_CONTRACT_BANDS = "BEFORE_CONTRACT_BANDS"
    #: Departs 21:00 or later -- band 7 is not collected.
    AFTER_CONTRACT_BANDS = "AFTER_CONTRACT_BANDS"


@dataclass(frozen=True, slots=True)
class CandidateVerdict:
    """A returned flight and every reason it cannot be selected (empty if eligible)."""

    candidate: FlightCandidate
    reasons: tuple[Ineligibility, ...]

    @property
    def eligible(self) -> bool:
        return not self.reasons

    @property
    def band(self) -> int | None:
        dep = self.candidate.departure_time
        return None if dep is None else band_of(dep)


def assess(candidate: FlightCandidate, params: SearchParams) -> CandidateVerdict:
    """Apply the eligibility rules to one flight. Collects every failing rule."""
    c = params.contract
    reasons: list[Ineligibility] = []

    if not candidate.flight_number or not candidate.flight_number.isdigit():
        reasons.append(Ineligibility.MISSING_FLIGHT_IDENTITY)
    if candidate.departure_time is None:
        reasons.append(Ineligibility.MISSING_DEPARTURE_TIME)
    if candidate.departure_date is None:
        reasons.append(Ineligibility.MISSING_DEPARTURE_DATE)
    if candidate.origin is None or candidate.destination is None:
        reasons.append(Ineligibility.MISSING_ROUTE)
    if candidate.origin is not None and candidate.origin != c.origin:
        reasons.append(Ineligibility.ALTERNATE_ORIGIN)
    if candidate.destination is not None and candidate.destination != c.destination:
        reasons.append(Ineligibility.ALTERNATE_DESTINATION)
    if candidate.departure_date is not None and candidate.departure_date != params.travel_date:
        reasons.append(Ineligibility.WRONG_DEPARTURE_DATE)
    if candidate.stops is None:
        reasons.append(Ineligibility.STOPS_UNKNOWN)
    elif c.nonstop_only and candidate.stops != 0:
        reasons.append(Ineligibility.NOT_NONSTOP)
    if candidate.marketing_carrier != c.carrier:
        reasons.append(Ineligibility.NOT_MARKETED_BY_CARRIER)
    if candidate.operating_carrier is None:
        reasons.append(Ineligibility.OPERATOR_UNKNOWN)
    elif candidate.operating_carrier != c.carrier:
        reasons.append(Ineligibility.NOT_OPERATED_BY_CARRIER)
    if candidate.departure_time is not None:
        band = band_of(candidate.departure_time)
        if band < min(CONTRACT_BANDS):
            reasons.append(Ineligibility.BEFORE_CONTRACT_BANDS)
        elif band > max(CONTRACT_BANDS):
            reasons.append(Ineligibility.AFTER_CONTRACT_BANDS)

    return CandidateVerdict(candidate=candidate, reasons=tuple(reasons))


def assess_all(
    candidates: Iterable[FlightCandidate], params: SearchParams
) -> tuple[CandidateVerdict, ...]:
    return tuple(assess(c, params) for c in candidates)


__all__ = ["CandidateVerdict", "Ineligibility", "assess", "assess_all"]
