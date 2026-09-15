"""Plan and execute a scheduled collection run.

The plan unit is one **search**: ``(source, route, advance-purchase window)``.
Departure bands are not planned per request -- a single search returns the day's
flights and :mod:`apix.ingestion.collectors.selection` picks the earliest
eligible flight in each contracted band from that one response. Planning per
band would issue five searches where the contract issues one.

Execution order is deliberate and the order is the compliance property:

1. **Gate first.** Every source is evaluated against the register *before* any
   adapter is constructed, let alone called. A refused source yields
   ``PERMISSION_BLOCKED`` and the loop moves on -- nothing is requested and
   nothing is written.
2. **Circuit breaker.** A source that hits a stop signal is marked
   ``CHALLENGED`` and every remaining search against it is recorded
   ``NOT_ATTEMPTED``. There is no retry past a stop signal, at any interval.
3. **Pacing.** Cleared sources are paced by the contract's enforced floor.

The scheduler never selects egress, never rotates anything, and has no code path
from a refusal to a retry. See ADR-0066 and the acquisition resolution.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum

from apix.config.apw import APIX_FROZEN_WINDOWS, ApwWindowSet
from apix.config.basket import PILOT_BASKET, RouteBasket
from apix.ingestion.collectors.contract import CONTRACT_BANDS
from apix.ingestion.collectors.gate import CollectionMode, GateDecision, evaluate_live_gate
from apix.schemas.enums import CollectionOutcome


class SourceOperationalStatus(Enum):
    """Runtime health of a source. **Never a permission statement.**

    Deliberately separate from ``automation_gate``: a source recovering from an
    outage must never appear to have gained permission. See the four-axis model
    in the acquisition resolution.
    """

    AVAILABLE = "AVAILABLE"
    #: Hit a stop signal this run. No further searches, no retry.
    CHALLENGED = "CHALLENGED"
    #: Reachability failure. Retryable in principle, subject to the breaker.
    UNREACHABLE = "UNREACHABLE"
    #: Refused by the compliance gate. Not an outage and not retryable.
    PERMISSION_BLOCKED = "PERMISSION_BLOCKED"


@dataclass(frozen=True, slots=True)
class PlannedSearch:
    """One search the schedule intends to make."""

    source_id: str
    mode: CollectionMode
    route_id: str
    origin: str
    destination: str
    apw_days: int
    travel_date: date
    bands: tuple[int, ...]

    @property
    def search_key(self) -> str:
        """Stable identity of this search within a run — used for idempotency."""
        return (
            f"{self.source_id}|{self.mode.value}|{self.route_id}"
            f"|T+{self.apw_days}|{self.travel_date.isoformat()}"
        )


@dataclass(frozen=True, slots=True)
class SearchRecord:
    """What happened to one planned search. Every plan entry gets one."""

    planned: PlannedSearch
    outcome: CollectionOutcome | None
    detail: str
    requested: bool
    observations_written: int = 0

    @property
    def not_attempted(self) -> bool:
        """True when the schedule never reached this search."""
        return self.outcome is None


@dataclass(frozen=True, slots=True)
class SchedulerConfig:
    """What to collect, and under what limits."""

    collection_date: date
    basket: RouteBasket = PILOT_BASKET
    windows: ApwWindowSet = APIX_FROZEN_WINDOWS
    bands: tuple[int, ...] = CONTRACT_BANDS
    source_ids: tuple[str, ...] = ("indigo",)
    mode: CollectionMode = CollectionMode.LIVE
    #: Enforced pacing floor between requests to one source, in seconds.
    min_interval_seconds: float = 30.0
    #: Consecutive reachability failures before a source is broken for the run.
    breaker_threshold: int = 2

    def __post_init__(self) -> None:
        if self.min_interval_seconds < 10.0:
            raise ValueError(
                f"min_interval_seconds={self.min_interval_seconds} is below the 10 s floor in "
                "acquisition-protocol.md s12"
            )
        if not self.source_ids:
            raise ValueError("a run needs at least one source")
        unknown = [b for b in self.bands if b not in CONTRACT_BANDS]
        if unknown:
            raise ValueError(
                f"bands {unknown} are outside the contracted set {list(CONTRACT_BANDS)}; "
                "collecting a band the contract excludes would change the frame"
            )


@dataclass
class ScheduledRun:
    """The outcome of one scheduled run, with every attempt accounted for."""

    run_id: str
    config: SchedulerConfig
    plan: tuple[PlannedSearch, ...]
    records: tuple[SearchRecord, ...]
    gate_decisions: Mapping[str, GateDecision]
    source_status: Mapping[str, SourceOperationalStatus]
    started_at: datetime
    finished_at: datetime
    _counts: dict[str, int] = field(default_factory=dict, repr=False)

    @property
    def by_outcome(self) -> dict[str, int]:
        """Count per outcome, including ``NOT_ATTEMPTED`` as its own key."""
        counts: dict[str, int] = {}
        for r in self.records:
            key = "NOT_ATTEMPTED" if r.outcome is None else r.outcome.value
            counts[key] = counts.get(key, 0) + 1
        return dict(sorted(counts.items()))

    @property
    def requests_made(self) -> int:
        """How many searches actually reached a source. Zero while nothing clears."""
        return sum(1 for r in self.records if r.requested)

    @property
    def observations_written(self) -> int:
        return sum(r.observations_written for r in self.records)

    @property
    def cleared_sources(self) -> tuple[str, ...]:
        return tuple(sorted(s for s, d in self.gate_decisions.items() if d.allowed))

    @property
    def coverage_loss_attributed_to_us(self) -> int:
        """Searches whose absence is ours, not the market's — spec H.1."""
        return sum(
            1 for r in self.records if r.outcome is not None and r.outcome.is_collector_failure
        )

    def summary(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "collection_date": self.config.collection_date.isoformat(),
            "basket_version": self.config.basket.basket_version,
            "basket_status": self.config.basket.status.value,
            "basket_is_publication_grade": self.config.basket.is_publication_grade,
            "window_set": self.config.windows.set_id,
            "windows": list(self.config.windows.days),
            "bands": list(self.config.bands),
            "mode": self.config.mode.value,
            "planned_searches": len(self.plan),
            "requests_made": self.requests_made,
            "observations_written": self.observations_written,
            "cleared_sources": list(self.cleared_sources),
            "by_outcome": self.by_outcome,
            "coverage_loss_attributed_to_us": self.coverage_loss_attributed_to_us,
            "source_status": {s: st.value for s, st in sorted(self.source_status.items())},
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
        }


def run_id_for(config: SchedulerConfig) -> str:
    """A deterministic run id, so re-planning the same schedule is idempotent.

    Derived from the inputs that define the plan. Two runs of the same schedule
    on the same date share an id; changing the basket, windows, bands, sources or
    mode produces a different one.
    """
    material = "|".join(
        [
            config.collection_date.isoformat(),
            config.basket.basket_version,
            config.windows.set_id,
            ",".join(str(b) for b in config.bands),
            ",".join(sorted(config.source_ids)),
            config.mode.value,
        ]
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:12]
    return f"sched-{config.collection_date.isoformat()}-{digest}"


def build_plan(config: SchedulerConfig) -> tuple[PlannedSearch, ...]:
    """Every search the schedule intends, in deterministic order.

    Travel date is ``collection_date + apw_days``, which is spec A.3's exact
    lead time by construction -- the plan cannot generate a travel date that
    lands off a frozen bucket.
    """
    plan: list[PlannedSearch] = []
    for source_id in sorted(config.source_ids):
        for route in config.basket.routes:
            for days in config.windows.days:
                plan.append(
                    PlannedSearch(
                        source_id=source_id,
                        mode=config.mode,
                        route_id=route.route_id,
                        origin=route.origin,
                        destination=route.destination,
                        apw_days=days,
                        travel_date=config.collection_date + timedelta(days=days),
                        bands=config.bands,
                    )
                )
    return tuple(plan)


def execute_plan(
    config: SchedulerConfig,
    registry: Mapping[str, object],
    *,
    collector: Callable[[PlannedSearch], tuple[CollectionOutcome, str, int]] | None = None,
    now: Callable[[], datetime] | None = None,
) -> ScheduledRun:
    """Execute a plan, gate first.

    ``collector`` is called only for a search whose source cleared the gate. It
    is injected so the scheduler can be exercised end to end without a network,
    and so a future authorised collector replaces it without the scheduler
    changing. **When it is ``None`` no search is ever executed** -- a cleared
    source without a collector is recorded ``SOURCE_UNAVAILABLE``, never as a
    success.

    ``registry`` is the parsed source register, mapping ``source_id`` to its
    entry. Gate evaluation is pure over that mapping; nothing here reads YAML.
    """
    clock = now or (lambda: datetime.now().astimezone())
    started = clock()
    plan = build_plan(config)

    decisions: dict[str, GateDecision] = {}
    status: dict[str, SourceOperationalStatus] = {}
    for source_id in sorted(config.source_ids):
        entry = registry.get(source_id)
        if not isinstance(entry, Mapping):
            decisions[source_id] = GateDecision(
                source_id=source_id,
                mode=config.mode,
                allowed=False,
                failures=(f"source {source_id!r} is not in the source register",),
            )
            status[source_id] = SourceOperationalStatus.PERMISSION_BLOCKED
            continue
        decision = evaluate_live_gate(entry)
        decisions[source_id] = decision
        status[source_id] = (
            SourceOperationalStatus.AVAILABLE
            if decision.allowed
            else SourceOperationalStatus.PERMISSION_BLOCKED
        )

    records: list[SearchRecord] = []
    consecutive_failures: dict[str, int] = dict.fromkeys(config.source_ids, 0)

    for search in plan:
        source_status = status[search.source_id]

        if source_status is SourceOperationalStatus.PERMISSION_BLOCKED:
            failures = "; ".join(decisions[search.source_id].failures)
            records.append(
                SearchRecord(
                    planned=search,
                    outcome=CollectionOutcome.PERMISSION_BLOCKED,
                    detail=(
                        f"refused by the compliance gate before any request: {failures}. "
                        "Nothing requested, nothing written"
                    ),
                    requested=False,
                )
            )
            continue

        if source_status is SourceOperationalStatus.CHALLENGED:
            records.append(
                SearchRecord(
                    planned=search,
                    outcome=None,
                    detail=(
                        "NOT_ATTEMPTED: an access challenge stopped this source earlier in the "
                        "run. A stop signal is never retried, at any interval"
                    ),
                    requested=False,
                )
            )
            continue

        if source_status is SourceOperationalStatus.UNREACHABLE:
            records.append(
                SearchRecord(
                    planned=search,
                    outcome=None,
                    detail="NOT_ATTEMPTED: circuit breaker open for this source",
                    requested=False,
                )
            )
            continue

        if collector is None:
            records.append(
                SearchRecord(
                    planned=search,
                    outcome=CollectionOutcome.SOURCE_UNAVAILABLE,
                    detail=(
                        "source cleared the gate but no collector is wired for it. Recorded as "
                        "unavailable rather than skipped: a cleared source that produced no "
                        "quote is a coverage loss, and it is ours"
                    ),
                    requested=False,
                )
            )
            continue

        outcome, detail, written = collector(search)
        records.append(
            SearchRecord(
                planned=search,
                outcome=outcome,
                detail=detail,
                requested=True,
                observations_written=written,
            )
        )

        if outcome.is_stop_signal:
            status[search.source_id] = SourceOperationalStatus.CHALLENGED
        elif outcome is CollectionOutcome.SOURCE_UNAVAILABLE:
            consecutive_failures[search.source_id] += 1
            if consecutive_failures[search.source_id] >= config.breaker_threshold:
                status[search.source_id] = SourceOperationalStatus.UNREACHABLE
        else:
            consecutive_failures[search.source_id] = 0

    return ScheduledRun(
        run_id=run_id_for(config),
        config=config,
        plan=plan,
        records=tuple(records),
        gate_decisions=decisions,
        source_status=status,
        started_at=started,
        finished_at=clock(),
    )


__all__ = [
    "PlannedSearch",
    "ScheduledRun",
    "SchedulerConfig",
    "SearchRecord",
    "SourceOperationalStatus",
    "build_plan",
    "execute_plan",
    "run_id_for",
]
