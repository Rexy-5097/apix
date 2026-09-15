"""Run orchestration: config -> searches -> rules -> canonical records -> store.

    RUN CONFIG
      -> compliance gate (LIVE only; refuses before any request)
      -> one search per travel date (paced; one retry on a site error; a
         challenge stops the source for the rest of the run)
      -> eligibility -> earliest eligible flight per band -> Saver decision
      -> Observation / UnpricedFlight / exclusion-with-reason
      -> run export + manifest (written first, so evidence survives a refused load)
      -> existing CollectionStore -> verify()

Every search produces a :class:`~apix.schemas.collection.CollectionAttempt`,
including searches that failed and searches never made because an earlier one hit
an access challenge. Missingness is measurable only from a record of attempts.

**Automated runs are never index input.** Their ``frame_id`` ends
``@automated-trial`` (or ``@fixture``), and ``collection-windows.yaml`` admits
only ``@primary`` runs to the index. Adopting automated collection as a
production frame is an owner decision recorded in an ADR, not a default here.
"""

from __future__ import annotations

import time as _time
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from apix.ingestion.collectors.adapter import SourceAdapter
from apix.ingestion.collectors.candidates import Artifact, DisplayedSearch, PageState, SearchResult
from apix.ingestion.collectors.contract import (
    CONTRACT_BANDS,
    CollectionConfig,
    ConfigError,
    SearchParams,
    band_window,
    ist_now,
)
from apix.ingestion.collectors.eligibility import assess_all
from apix.ingestion.collectors.evidence import (
    EvidenceRecord,
    canonical_json,
    sha256_hex,
    write_run_export,
)
from apix.ingestion.collectors.fares import FareExclusion, FareStatus, choose_contract_fare
from apix.ingestion.collectors.gate import CollectionMode, require_live_clearance
from apix.ingestion.collectors.normalize import to_observation, to_unpriced
from apix.ingestion.collectors.selection import select_earliest_per_band
from apix.ingestion.store import CollectionStore, UnpricedFlight
from apix.schemas.collection import CollectionAttempt, CollectionRun
from apix.schemas.enums import Channel, CollectionOutcome, SourceType
from apix.schemas.observation import Observation

COLLECTOR_VERSION = "0.1.0"
#: Not ``acquisition-protocol-2I``: that protocol is manual by definition.
AUTOMATED_PROTOCOL_VERSION = "automated-collection-trial-1"
METHODOLOGY_VERSION = "2.1"
BASKET_VERSION = "2026-Q3"
SOURCE_PRECEDENCE_VERSION = "spike-single-source-v1"
#: acquisition-protocol.md s12: at most one retry, after at least 60 s.
RETRY_DELAY_FLOOR_SECONDS = 60.0

FRAME_SUFFIX = {CollectionMode.LIVE: "@automated-trial", CollectionMode.FIXTURE: "@fixture"}
FRAME_TAG = {CollectionMode.LIVE: "automated-trial", CollectionMode.FIXTURE: "fixture"}
#: Fixture pages are not market observations and are labelled so at the record level.
SOURCE_TYPE = {
    CollectionMode.LIVE: SourceType.LIVE_SCRAPE,
    CollectionMode.FIXTURE: SourceType.SYNTHETIC,
}

#: Exclusions meaning the page could not be read, as opposed to a contract mismatch.
_UNREADABLE = frozenset(
    {
        FareExclusion.REQUIRED_FIELD_UNREADABLE,
        FareExclusion.FARE_UNREADABLE,
        FareExclusion.ENTITLEMENTS_UNDETERMINABLE,
        FareExclusion.FARE_FAMILY_AMBIGUOUS,
    }
)
#: Evidence preferred as the observation's linked artifact, most direct first.
_ARTIFACT_PRIORITY = ("results_screenshot", "extracted_payload", "fixture_payload", "results_dom")


class RunRefused(RuntimeError):
    """A run that must not start. Nothing was requested and nothing was written."""


@dataclass(frozen=True, slots=True)
class BandOutcome:
    band: int
    eligible_count: int
    #: ``OBSERVED`` | ``SOLD_OUT`` | ``EXCLUDED`` | ``EMPTY_BAND`` | ``NOT_EVALUATED``
    status: str
    selected: str | None = None
    record_id: str | None = None
    detail: str = ""

    @property
    def window(self) -> str:
        return band_window(self.band)


@dataclass(frozen=True, slots=True)
class ProcessedSearch:
    """One search after every APIx rule has been applied."""

    params: SearchParams
    attempt: CollectionAttempt
    observations: tuple[Observation, ...] = ()
    unpriced: tuple[UnpricedFlight, ...] = ()
    bands: tuple[BandOutcome, ...] = ()
    ineligible_counts: dict[str, int] = field(default_factory=dict)
    stop: bool = False
    result: SearchResult | None = None

    def counts(self) -> dict[str, int]:
        """expected / found / accepted / sold_out / excluded / missing, per band."""
        status = [b.status for b in self.bands]
        return {
            "expected": len(CONTRACT_BANDS),
            "found": sum(s in ("OBSERVED", "SOLD_OUT", "EXCLUDED") for s in status),
            "accepted": len(self.observations),
            "sold_out": status.count("SOLD_OUT"),
            "excluded": status.count("EXCLUDED"),
            "missing": status.count("EMPTY_BAND"),
            "not_evaluated": status.count("NOT_EVALUATED"),
        }


def echo_mismatches(displayed: DisplayedSearch | None, params: SearchParams) -> list[str]:
    """Differences between the search the contract specifies and the page's echo.

    A field the page did not echo is a mismatch too: a search whose parameters
    cannot be confirmed cannot be recorded as the contracted search.
    """
    if displayed is None:
        return ["search echo not readable"]
    c = params.contract
    expected: dict[str, object] = {
        "origin": c.origin,
        "destination": c.destination,
        "travel_date": params.travel_date,
        "adults": c.adults,
        "currency": c.currency,
        "trip_type": c.trip_type,
    }
    problems = []
    for name, want in expected.items():
        got = getattr(displayed, name)
        if got is None:
            problems.append(f"{name} not displayed")
        elif got != want:
            problems.append(f"{name}={got} expected {want}")
    return problems


def _attempt(
    params: SearchParams,
    *,
    attempt_id: str,
    run_id: str,
    source_type: SourceType,
    outcome: CollectionOutcome,
    detail: str,
    attempt_ts: datetime,
    result: SearchResult | None = None,
    observations: tuple[Observation, ...] = (),
) -> CollectionAttempt:
    return CollectionAttempt(
        attempt_id=attempt_id,
        run_id=run_id,
        collection_date=params.collection_date,
        attempt_ts=attempt_ts,
        source_id=params.source_id,
        channel=Channel.AIRLINE_DIRECT,
        source_type=source_type,
        origin=params.contract.origin,
        destination=params.contract.destination,
        travel_date=params.travel_date,
        outcome=outcome,
        quotes_parsed=len(observations),
        http_status=result.http_status if result else None,
        latency_ms=result.latency_ms if result else None,
        detail=detail,
        observation_ids=tuple(sorted(o.observation_id for o in observations)),
    )


def process_search(
    result: SearchResult,
    *,
    run_id: str,
    attempt_id: str,
    frame_tag: str,
    source_type: SourceType,
    note: str = "",
) -> ProcessedSearch:
    """Classify one search and turn its selected flights into canonical records.

    Pure: no I/O, no clock. Given the same ``SearchResult`` it returns the same
    records every time.
    """
    params = result.params
    prefix = f"{note}; " if note else ""
    not_evaluated = tuple(BandOutcome(b, 0, "NOT_EVALUATED") for b in CONTRACT_BANDS)

    def failed(outcome: CollectionOutcome, detail: str, stop: bool = False) -> ProcessedSearch:
        attempt = _attempt(
            params,
            attempt_id=attempt_id,
            run_id=run_id,
            source_type=source_type,
            outcome=outcome,
            detail=prefix + detail,
            attempt_ts=result.started_ts,
            result=result,
        )
        return ProcessedSearch(params, attempt, bands=not_evaluated, stop=stop, result=result)

    state = result.page_state
    if state is PageState.ACCESS_CHALLENGE:
        return failed(
            CollectionOutcome.CAPTCHA_OR_ANTIBOT_STOP,
            f"ACCESS_CHALLENGE: {result.detail}. Stop signal: not retried, not worked "
            "around, no further searches against this source in this run",
            stop=True,
        )
    if state is PageState.SITE_ERROR:
        return failed(CollectionOutcome.SOURCE_UNAVAILABLE, f"SITE_ERROR: {result.detail}")
    if state is PageState.UNRECOGNISED:
        issues = "; ".join(result.structural_issues)
        return failed(
            CollectionOutcome.PARSER_FAILURE, f"UNRECOGNISED_PAGE: {result.detail} {issues}".strip()
        )
    if result.structural_issues:
        return failed(
            CollectionOutcome.PARSER_FAILURE,
            "DOM_CHANGED: " + "; ".join(result.structural_issues),
        )
    if state is PageState.NO_FLIGHTS_MESSAGE:
        return failed(
            CollectionOutcome.TECHNICAL_FAILURE,
            f"SITE_REPORTED_NO_FLIGHTS: {result.detail}. NO_FLIGHT is never inferred by "
            "the automated collector (procedure s8: never guess NO_FLIGHT)",
        )
    mismatches = echo_mismatches(result.displayed, params)
    if mismatches:
        return failed(
            CollectionOutcome.PARSER_FAILURE, "SEARCH_PARAMETER_MISMATCH: " + "; ".join(mismatches)
        )
    if not result.candidates:
        return failed(CollectionOutcome.PARSER_FAILURE, "RESULTS_PAGE_WITHOUT_FLIGHT_CARDS")

    selection = select_earliest_per_band(assess_all(result.candidates, params))
    observations: list[Observation] = []
    unpriced: list[UnpricedFlight] = []
    bands: list[BandOutcome] = []
    unreadable = False
    for band in selection.bands:
        chosen = band.selected
        if chosen is None:
            bands.append(
                BandOutcome(band.band, 0, "EMPTY_BAND", detail="no eligible flight in band")
            )
            continue
        decision = choose_contract_fare(chosen, params.contract)
        if decision.status is FareStatus.PRICED:
            obs = to_observation(
                decision,
                params,
                frame_tag=frame_tag,
                source_type=source_type,
                observed_at=result.finished_ts,
            )
            observations.append(obs)
            bands.append(
                BandOutcome(
                    band.band,
                    band.eligible_count,
                    "OBSERVED",
                    chosen.flight_key,
                    obs.observation_id,
                )
            )
        elif decision.status is FareStatus.SOLD_OUT:
            flight = to_unpriced(
                decision,
                params,
                frame_tag=frame_tag,
                run_id=run_id,
                attempt_id=attempt_id,
                observed_at=result.finished_ts,
            )
            unpriced.append(flight)
            bands.append(
                BandOutcome(
                    band.band,
                    band.eligible_count,
                    "SOLD_OUT",
                    chosen.flight_key,
                    flight.unpriced_id,
                    decision.detail,
                )
            )
        else:
            assert decision.exclusion is not None
            unreadable = unreadable or decision.exclusion in _UNREADABLE
            bands.append(
                BandOutcome(
                    band.band,
                    band.eligible_count,
                    "EXCLUDED",
                    chosen.flight_key,
                    detail=f"{decision.exclusion.value}: {decision.detail}",
                )
            )

    summary = ", ".join(f"b{b.band}={b.status}" for b in bands)
    if observations:
        outcome, detail = (
            CollectionOutcome.SUCCESS,
            f"observed {len(observations)}/{len(bands)} bands [{summary}]",
        )
    elif unreadable:
        outcome, detail = (
            CollectionOutcome.PARSER_FAILURE,
            f"no contract fare could be read [{summary}]",
        )
    elif unpriced:
        outcome, detail = (
            CollectionOutcome.TECHNICAL_FAILURE,
            f"every selected flight sold out [{summary}]",
        )
    else:
        outcome, detail = (
            CollectionOutcome.TECHNICAL_FAILURE,
            f"no recordable contract fare [{summary}]",
        )

    attempt = _attempt(
        params,
        attempt_id=attempt_id,
        run_id=run_id,
        source_type=source_type,
        outcome=outcome,
        detail=prefix + detail,
        attempt_ts=result.started_ts,
        result=result,
        observations=tuple(observations),
    )
    return ProcessedSearch(
        params=params,
        attempt=attempt,
        observations=tuple(observations),
        unpriced=tuple(unpriced),
        bands=tuple(bands),
        ineligible_counts=selection.ineligible_counts(),
        result=result,
    )


@dataclass(frozen=True, slots=True)
class RunReport:
    run: CollectionRun
    mode: CollectionMode
    searches: tuple[ProcessedSearch, ...]
    export_dir: Path
    manifest_sha256: str
    loaded: bool
    not_loaded_reason: str = ""
    integrity_problems: tuple[str, ...] = ()

    @property
    def stopped(self) -> bool:
        return any(s.stop for s in self.searches)

    @property
    def status(self) -> str:
        outcomes = [s.attempt.outcome for s in self.searches]
        if self.stopped:
            return "STOPPED"
        if all(o is CollectionOutcome.SUCCESS for o in outcomes) and all(
            s.counts()["accepted"] == len(CONTRACT_BANDS) for s in self.searches
        ):
            return "COMPLETE"
        if CollectionOutcome.SUCCESS in outcomes:
            return "PARTIAL"
        return "FAILED"

    def totals(self) -> dict[str, int]:
        total: dict[str, int] = {}
        for s in self.searches:
            for k, v in s.counts().items():
                total[k] = total.get(k, 0) + v
        total["searches"] = len(self.searches)
        return total


def _safe_search(
    adapter: SourceAdapter, params: SearchParams, clock: Callable[[], datetime]
) -> SearchResult:
    """An exception from an adapter is a collector defect, recorded -- not a fare."""
    started = clock()
    try:
        return adapter.search(params)
    except Exception as exc:  # the adapter contract forbids raising for source problems
        return SearchResult(
            params=params,
            page_state=PageState.UNRECOGNISED,
            started_ts=started,
            finished_ts=clock(),
            detail=f"COLLECTOR_EXCEPTION: {type(exc).__name__}: {exc}",
        )


def _duplicate_key(o: Observation) -> tuple[object, ...]:
    return (
        o.collection_date,
        o.source_id,
        o.origin,
        o.destination,
        o.carrier,
        o.flight_number,
        o.travel_date,
        o.departure_time_local,
        o.fare_family_raw,
    )


def _documents(
    run: CollectionRun,
    config: CollectionConfig,
    adapter: SourceAdapter,
    searches: list[ProcessedSearch],
    gate_summary: Mapping[str, object],
) -> dict[str, bytes]:
    run_doc = {
        "run": asdict(run),
        "mode": adapter.mode.value,
        "index_input": False,
        "environment": adapter.environment(),
        "gate": dict(gate_summary),
        "config": {
            "source": config.source,
            "collection_date": config.collection_date,
            "lead_times": list(config.lead_times),
            "off_frame_lead_times": list(config.off_frame_lead_times),
            "window_id": config.window_id,
            "window": [config.window_start, config.window_end],
            "min_interval_seconds": config.min_interval_seconds,
            "contract": asdict(config.contract),
        },
    }
    attempts_doc = [
        {"attempt": asdict(s.attempt), "counts": s.counts(), "search": s.params.as_record()}
        for s in searches
    ]
    selection_doc = []
    for s in searches:
        r = s.result
        selection_doc.append(
            {
                "attempt_id": s.attempt.attempt_id,
                "page_state": r.page_state.value if r else None,
                "structural_issues": list(r.structural_issues) if r else [],
                "displayed_search": asdict(r.displayed) if r and r.displayed else None,
                "returned_flights": [asdict(c) for c in r.candidates] if r else [],
                "bands": [{**asdict(b), "window": b.window} for b in s.bands],
                "ineligible_counts": s.ineligible_counts,
            }
        )
    observations_doc = {
        "observations": [asdict(o) for s in searches for o in s.observations],
        "unpriced_flights": [asdict(u) for s in searches for u in s.unpriced],
        "excluded_selections": [
            {"attempt_id": s.attempt.attempt_id, **asdict(b)}
            for s in searches
            for b in s.bands
            if b.status == "EXCLUDED"
        ],
    }
    return {
        "run.json": canonical_json(run_doc),
        "attempts.json": canonical_json(attempts_doc),
        "selection.json": canonical_json(selection_doc),
        "observations.json": canonical_json(observations_doc),
    }


def run_collection(
    config: CollectionConfig,
    adapter: SourceAdapter,
    store: CollectionStore,
    *,
    export_root: Path,
    registry_entry: Mapping[str, object] | None = None,
    clock: Callable[[], datetime] = ist_now,
    sleep: Callable[[float], None] = _time.sleep,
    collector_version: str = COLLECTOR_VERSION,
    retry_delay_seconds: float = RETRY_DELAY_FLOOR_SECONDS,
) -> RunReport:
    """Execute one collection run end to end."""
    mode = adapter.mode
    gate_summary: dict[str, object] = {"mode": mode.value}
    if mode is CollectionMode.LIVE:
        if registry_entry is None:
            raise RunRefused(
                "a LIVE run requires the source's registry entry for the compliance gate"
            )
        decision = require_live_clearance(registry_entry)  # raises GateRefused
        gate_summary.update(allowed=decision.allowed, evidence=dict(decision.evidence))
    else:
        gate_summary.update(allowed=True, note="fixture mode makes no request to any source")
    if config.source != adapter.registry_id:
        raise ConfigError(
            f"config source {config.source!r} does not match adapter {adapter.registry_id!r}"
        )
    if retry_delay_seconds < RETRY_DELAY_FLOOR_SECONDS:
        raise ConfigError(f"retry delay below the {RETRY_DELAY_FLOOR_SECONDS:.0f} s protocol floor")

    frame_tag, suffix, source_type = FRAME_TAG[mode], FRAME_SUFFIX[mode], SOURCE_TYPE[mode]
    started = clock()
    run_id = f"run-{config.collection_date:%Y%m%d}-{frame_tag}-{adapter.source_id}-{started:%H%M%S}"

    searches: list[ProcessedSearch] = []
    captured: list[tuple[str, Artifact, datetime]] = []
    stopped = False
    requests = 0
    for params in config.search_params(adapter.source_id):
        attempt_id = f"att-{run_id.removeprefix('run-')}-{params.travel_date:%Y%m%d}"
        if stopped:
            attempt = _attempt(
                params,
                attempt_id=attempt_id,
                run_id=run_id,
                source_type=source_type,
                outcome=CollectionOutcome.CAPTCHA_OR_ANTIBOT_STOP,
                detail="NOT_ATTEMPTED: an access challenge earlier in this run stops the "
                "source for the rest of the run (procedure s8 step 4)",
                attempt_ts=clock(),
            )
            not_evaluated = tuple(BandOutcome(b, 0, "NOT_EVALUATED") for b in CONTRACT_BANDS)
            searches.append(ProcessedSearch(params, attempt, bands=not_evaluated))
            continue

        if mode is CollectionMode.LIVE and requests:
            sleep(config.min_interval_seconds)
        result = _safe_search(adapter, params, clock)
        requests += 1
        captured.extend((attempt_id, a, result.finished_ts) for a in result.artifacts)
        note = ""
        if result.page_state is PageState.SITE_ERROR:
            sleep(retry_delay_seconds)
            first = result.detail
            result = _safe_search(adapter, params, clock)
            requests += 1
            captured.extend((attempt_id, a, result.finished_ts) for a in result.artifacts)
            note = f"retried once after {retry_delay_seconds:.0f} s (first: {first})"

        processed = process_search(
            result,
            run_id=run_id,
            attempt_id=attempt_id,
            frame_tag=frame_tag,
            source_type=source_type,
            note=note,
        )
        searches.append(processed)
        stopped = processed.stop

    finished = clock()
    window_start, window_end = config.declared_window()
    frame_id = config.frame_id(suffix)
    run = CollectionRun(
        run_id=run_id,
        collection_date=config.collection_date,
        started_ts=started,
        collection_window_start=window_start,
        collection_window_end=window_end,
        source_precedence_version=SOURCE_PRECEDENCE_VERSION,
        basket_version=BASKET_VERSION,
        parser_version=adapter.parser_version,
        collector_version=collector_version,
        collector_identity=f"{mode.value.lower()}:{type(adapter).__name__}",
        protocol_version=AUTOMATED_PROTOCOL_VERSION,
        methodology_version=METHODOLOGY_VERSION,
        frame_id=frame_id,
        finished_ts=finished,
        notes=(
            f"{mode.value} automated-collector run; NOT index input ({suffix}); "
            f"declared window {config.window_id} "
            f"{config.window_start:%H:%M}-{config.window_end:%H:%M}; "
            f"actual {started:%H:%M:%S}-{finished:%H:%M:%S}"
        ),
    )

    records = [
        EvidenceRecord(
            attempt_id=aid,
            role=art.role,
            sha256=sha256_hex(art.content),
            byte_size=len(art.content),
            content_type=art.content_type,
            captured_ts=ts,
            store_path=f"{sha256_hex(art.content)[:2]}/{sha256_hex(art.content)}",
        )
        for aid, art, ts in captured
        if art.content
    ]
    documents = _documents(run, config, adapter, searches, gate_summary)
    export_dir, manifest_sha = write_run_export(Path(export_root), run_id, documents, records)

    observations = [o for s in searches for o in s.observations]
    unpriced = [u for s in searches for u in s.unpriced]
    existing = {_duplicate_key(o) for o in store.observations(config.collection_date)}
    clashes = sorted(o.observation_id for o in observations if _duplicate_key(o) in existing)
    known_unpriced = {u.unpriced_id for u in store.unpriced_flights(config.collection_date)}
    clashes += sorted(u.unpriced_id for u in unpriced if u.unpriced_id in known_unpriced)
    if clashes:
        return RunReport(
            run=run,
            mode=mode,
            searches=tuple(searches),
            export_dir=export_dir,
            manifest_sha256=manifest_sha,
            loaded=False,
            not_loaded_reason=(
                f"{len(clashes)} records duplicate offers already in the store (spec D.4): "
                f"{clashes[:3]}. Nothing was written to the store; "
                "the run export holds the evidence"
            ),
        )

    store.record_run(run)
    for s in searches:
        store.record_attempt(s.attempt)
    sha_by_attempt: dict[str, dict[str, str]] = {}
    for aid, art, ts in captured:
        if not art.content:
            continue
        ref = store.artifacts.put(
            art.content,
            content_type=art.content_type,
            source_id=adapter.source_id,
            run_id=run_id,
            attempt_id=aid,
            captured_ts=ts,
        )
        store.record_artifact(ref)
        sha_by_attempt.setdefault(aid, {}).setdefault(art.role, ref.sha256)
    for s in searches:
        roles = sha_by_attempt.get(s.attempt.attempt_id, {})
        link = next((roles[r] for r in _ARTIFACT_PRIORITY if r in roles), None)
        for obs in s.observations:
            store.record_observation(
                obs, run_id=run_id, attempt_id=s.attempt.attempt_id, artifact_sha256=link
            )
        for flight in s.unpriced:
            store.record_unpriced_flight(flight)

    return RunReport(
        run=run,
        mode=mode,
        searches=tuple(searches),
        export_dir=export_dir,
        manifest_sha256=manifest_sha,
        loaded=True,
        integrity_problems=tuple(store.verify(config.collection_date)),
    )


__all__ = [
    "AUTOMATED_PROTOCOL_VERSION",
    "COLLECTOR_VERSION",
    "FRAME_SUFFIX",
    "BandOutcome",
    "ProcessedSearch",
    "RunRefused",
    "RunReport",
    "echo_mismatches",
    "process_search",
    "run_collection",
]
