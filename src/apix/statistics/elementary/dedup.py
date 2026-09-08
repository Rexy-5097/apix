"""Deduplication — spec D.4.

Two observations in the same cell at the same *t* with identical
``(carrier, flight_number, travel_date, departure_time_local, fare_class,
channel, source_id)`` are duplicates. The one with the **latest
observation_ts within the collection window** is kept; the others are stored
with a duplicate reason code.

**Deduplication happens before M(c,t) is formed** (spec D.4, and the §L.1
pipeline places it immediately after admissibility). Deduplicating after
matching would let a duplicated item contribute twice to a geometric mean and
silently overweight it.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from apix.schemas.enums import ExclusionReason
from apix.schemas.observation import Observation
from apix.schemas.results import ExcludedObservation


def duplicate_key(obs: Observation) -> tuple[str, str, str, str, str, str, str, str]:
    """The identity spec D.4 defines a duplicate by.

    Spec D.4 qualifies duplicates as *"two observations **in the same cell** at
    the same t with identical (carrier, flight_number, travel_date,
    departure_time_local, fare_class, channel, source_id)"*.

    ``route`` is included even though it is absent from that parenthesised
    tuple, because **the "same cell" qualifier requires it**: a cell key
    (spec B.2) begins with the route, so observations on different routes are by
    definition in different cells and cannot be duplicates of each other. The
    literal tuple is under-specified relative to its own scoping clause — see
    the AMB-3 note in the Checkpoint 2 PR.

    This is not academic. Without ``route``, a carrier's flight number, date and
    departure time collide across every route it is generated for, and the
    deduplicator silently destroys observations that are not duplicates. Measured
    on a full-frame synthetic day: 2,800 admissible quotes collapsed to 140.

    ``source_id`` is part of the key for the opposite reason: the same fare seen
    on two different sources is **not** a duplicate. Collapsing across sources
    would erase the channel spread that spec B.5 exists to publish.
    """
    return (
        obs.route,
        obs.carrier,
        obs.flight_number,
        obs.travel_date.isoformat(),
        obs.departure_time_local.isoformat(),
        obs.fare_class.value,
        obs.channel.value,
        obs.source_id,
    )


@dataclass(frozen=True, slots=True)
class DedupResult:
    """Retained observations, plus the duplicates that lost with their reason."""

    retained: tuple[Observation, ...]
    duplicates: tuple[ExcludedObservation, ...]

    @property
    def duplicate_rate(self) -> float:
        total = len(self.retained) + len(self.duplicates)
        return len(self.duplicates) / total if total else 0.0


def deduplicate(observations: Iterable[Observation]) -> DedupResult:
    """Keep the latest observation per duplicate key — spec D.4.

    Args:
        observations: Admissible observations for a single collection date.

    Returns:
        A :class:`DedupResult`. Losers are retained with
        :attr:`ExclusionReason.DUPLICATE`, never dropped.

    Tie-breaking: when two duplicates share the same ``observation_ts`` to the
    microsecond, the one with the lexicographically **larger** ``observation_id``
    wins — the comparison below is ``>`` on the ``(ts, id)`` tuple.
    An arbitrary-but-fixed rule is required: leaving the tie to dictionary or
    input order would make the output depend on collection order and break
    spec P.2.
    """
    best: dict[tuple[str, ...], Observation] = {}
    losers: list[ExcludedObservation] = []

    for obs in sorted(observations, key=lambda o: o.observation_id):
        key = duplicate_key(obs)
        incumbent = best.get(key)
        if incumbent is None:
            best[key] = obs
            continue

        challenger_wins = (obs.observation_ts, obs.observation_id) > (
            incumbent.observation_ts,
            incumbent.observation_id,
        )
        winner, loser = (obs, incumbent) if challenger_wins else (incumbent, obs)
        best[key] = winner
        losers.append(
            ExcludedObservation(
                observation_id=loser.observation_id,
                reason=ExclusionReason.DUPLICATE,
                detail=f"superseded by {winner.observation_id}",
            )
        )

    retained = sorted(best.values(), key=lambda o: o.observation_id)
    return DedupResult(
        retained=tuple(retained),
        duplicates=tuple(sorted(losers, key=lambda e: e.observation_id)),
    )
