"""The collection-attempt record — spec H.1, and the missing half of AMB-8.

``Observation`` records what we **got**. This module records what we **tried**.

The gap between the two is the whole point. Spec H.1 names five distinct ways a
quote can be absent and treats them differently — one leaves the coverage
denominator, two are suppressed or carried, and two are *our* failure rather
than the market's. In a table of successful quotes all five are the same thing:
an empty result.

    You cannot measure missingness from a table of successes.

Without an attempt record, "no service was scheduled on that weekday" and "the
site presented an access challenge" are indistinguishable, and spec I's
``min_route_coverage`` denominator stays undefined no matter how long collection
runs. That is **AMB-8**, and this is the input it needs.

Nothing here is a price. Nothing here enters the index. These records feed the
coverage denominator, the exclusion-rate alarm (spec H.1) and the source-health
diagnostics — and they are what makes a published coverage figure *measured*
rather than optimistic.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime

from apix.schemas.enums import APWBucket, Channel, CollectionOutcome, SourceType


@dataclass(frozen=True, slots=True)
class CollectionRun:
    """One execution of the collection schedule — the reproducibility anchor.

    Spec P.1 guarantees a published value can be recomputed from its version
    vector. That guarantee starts here: every observation and every attempt
    carries a ``run_id``, so the set of inputs behind a published number is a
    query rather than a reconstruction.

    ``collection_window_start``/``end`` record the spec A.5 window **actually
    used**, not the one intended. The window's value is still **OQ-1, open** —
    spec A.5 is *"LOCKED as a rule, EMPIRICAL as a value"* — so recording what
    was used is the only way the spike can inform it.
    """

    run_id: str
    collection_date: date
    started_ts: datetime
    collection_window_start: datetime
    collection_window_end: datetime
    #: Identifier of the ordered source list in force — spec D.8, O.
    source_precedence_version: str
    #: Route/cell universe in force — spec O.1.
    basket_version: str
    #: Extraction logic that produced the observations — spec O.1.
    parser_version: str
    #: Git commit of the collector.
    collector_version: str
    finished_ts: datetime | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        if self.collection_window_end <= self.collection_window_start:
            raise ValueError(
                "collection_window_end must be after collection_window_start; got "
                f"{self.collection_window_start} -> {self.collection_window_end}"
            )
        missing = sorted(
            name
            for name, value in (
                ("run_id", self.run_id),
                ("source_precedence_version", self.source_precedence_version),
                ("basket_version", self.basket_version),
                ("parser_version", self.parser_version),
                ("collector_version", self.collector_version),
            )
            if not value
        )
        if missing:
            raise ValueError(f"collection run is missing required identifiers: {missing}")

    def contains(self, moment: datetime) -> bool:
        """Whether a timestamp falls inside the declared collection window.

        Spec A.5: quotes outside the window are *"flagged and excluded from the
        index while remaining in the observation store"*. This is the test that
        decides, and it is inclusive of both ends so a quote captured exactly on
        the boundary is kept rather than silently dropped.
        """
        return self.collection_window_start <= moment <= self.collection_window_end


@dataclass(frozen=True, slots=True)
class CollectionAttempt:
    """One attempt to retrieve quotes for one (source, route, travel date).

    Written **whether or not** it produced a fare. An attempt with
    ``outcome=SUCCESS`` and ``quotes_parsed=0`` is a contradiction and raises;
    so does a failure that claims to have parsed quotes.
    """

    attempt_id: str
    run_id: str
    collection_date: date
    attempt_ts: datetime
    source_id: str
    channel: Channel
    source_type: SourceType
    origin: str
    destination: str
    travel_date: date
    outcome: CollectionOutcome
    #: Independent source group — spec B.6. ``None`` means ungrouped, never
    #: independent. See :attr:`~apix.schemas.observation.Observation.source_group`.
    source_group: str | None = None
    quotes_parsed: int = 0
    #: Transport status where one applies. ``None`` for outcomes that never made
    #: a request (e.g. a basket entry known not to be served).
    http_status: int | None = None
    #: Wall-clock duration of the attempt, for source-health diagnostics.
    latency_ms: int | None = None
    #: Free text for the operator. Never parsed; diagnostics only.
    detail: str = ""
    #: Observation ids produced by this attempt, for provenance.
    observation_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.quotes_parsed < 0:
            raise ValueError(f"quotes_parsed must be >= 0, got {self.quotes_parsed}")
        if self.outcome is CollectionOutcome.SUCCESS and self.quotes_parsed == 0:
            raise ValueError(
                "a SUCCESS attempt must have parsed at least one quote; an attempt that "
                "ran cleanly and found nothing is NO_FLIGHT, STRUCTURAL_MISSING or "
                "TECHNICAL_FAILURE depending on why (spec H.1) — never SUCCESS with zero"
            )
        if self.outcome is not CollectionOutcome.SUCCESS and self.quotes_parsed:
            raise ValueError(
                f"outcome {self.outcome.value} claims {self.quotes_parsed} parsed quotes; "
                "a non-SUCCESS attempt produced no usable fare by definition"
            )
        if len(self.observation_ids) != self.quotes_parsed:
            raise ValueError(
                f"observation_ids has {len(self.observation_ids)} entries but "
                f"quotes_parsed is {self.quotes_parsed}; provenance must be exact"
            )

    @property
    def route(self) -> str:
        """Ordered origin-destination pair. DEL-BOM is not BOM-DEL."""
        return f"{self.origin}-{self.destination}"

    @property
    def lead_time_days(self) -> int:
        """Days between the collection date and departure — spec A.2."""
        return (self.travel_date - self.collection_date).days

    @property
    def apw_bucket(self) -> APWBucket | None:
        """Advance-purchase bucket, or None when the lead time matches none.

        Spec A.3 assigns by **exact** lead time. An attempt at a lead time
        matching no bucket is still recorded — it simply cannot contribute to
        the index, and knowing we made it is how the exclusion rate stays
        honest.
        """
        return APWBucket.from_lead_time(self.lead_time_days)

    @property
    def counts_toward_expected_cells(self) -> bool:
        """Whether this attempt's cell belongs in the spec I coverage denominator.

        False only for ``NO_FLIGHT`` — spec H.1: *"Cell not expected; excluded
        from denominators of coverage."*

        **This is the one predicate AMB-8 needs and the schema could not express
        before.** It does not resolve AMB-8: what the *base* set of expected
        cells is remains an open methodology question. It supplies the exclusion
        the LOCKED text already specifies.
        """
        return not self.outcome.excludes_cell_from_expectation

    @property
    def is_coverage_loss_we_caused(self) -> bool:
        """Whether this absence is our failure rather than the market's.

        Published separately from market absence, because a coverage figure that
        blends the two overstates how thin the market is and understates how
        unreliable the collector is.
        """
        return self.outcome.is_collector_failure


def exclusion_rate(attempts: Sequence[CollectionAttempt]) -> float:
    """Share of attempts that failed for a reason we caused — spec H.1.

    Spec H.1 requires parser failures to *"count toward the exclusion rate
    alarm"*. This is that rate: collector failures over all attempts.

    Deliberately **excludes** market absence. ``NO_FLIGHT`` on a route a carrier
    does not serve is not an exclusion, and counting it would make a correctly
    specified basket look like a broken collector.
    """
    if not attempts:
        return 0.0
    failed = sum(1 for a in attempts if a.outcome.is_collector_failure)
    return failed / len(attempts)


def has_stop_signal(attempts: Sequence[CollectionAttempt]) -> bool:
    """Whether any attempt hit an access challenge.

    True means the run must not be repeated against that source until a human
    has reviewed it. An access challenge is a stop signal, not an obstacle.
    """
    return any(a.outcome.is_stop_signal for a in attempts)


__all__ = [
    "CollectionAttempt",
    "CollectionRun",
    "exclusion_rate",
    "has_stop_signal",
]
