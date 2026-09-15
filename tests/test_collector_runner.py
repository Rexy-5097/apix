"""Automated collection: the compliance gate, the runner, evidence and failures.

Two kinds of adapter are used, and neither touches a network:

* ``FixtureIndigoAdapter`` over the committed SYNTHETIC fixture -- the real
  fixture-mode code path, end to end into the real store.
* ``ScriptedAdapter``, a test double that replays payloads in order. Where it runs
  in LIVE mode it does so against ``CLEARED``, a **hypothetical** register entry
  that exists only in this file, to exercise pacing, retry and stop-signal
  behaviour that only live mode has. No real source is rated that way.
"""

from __future__ import annotations

import importlib
import json
import sqlite3
import sys
from collections.abc import Iterator
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import ClassVar

import pytest
import yaml

from apix.ingestion.collectors.adapter import SourceAdapter
from apix.ingestion.collectors.candidates import Artifact, SearchResult
from apix.ingestion.collectors.contract import (
    FROZEN_APW,
    CollectionConfig,
    ConfigError,
    SearchParams,
)
from apix.ingestion.collectors.evidence import (
    ExportError,
    canonical_json,
    sha256_hex,
    verify_run_export,
    write_run_export,
)
from apix.ingestion.collectors.gate import (
    LIVE_REQUIREMENTS,
    CollectionMode,
    GateRefused,
    evaluate_live_gate,
    find_source,
)
from apix.ingestion.collectors.indigo.fixture import FixtureError, FixtureIndigoAdapter
from apix.ingestion.collectors.indigo.live import (
    AdapterUnavailable,
    LiveIndigoAdapter,
    challenge_reason,
)
from apix.ingestion.collectors.indigo.parse import parse_extracted
from apix.ingestion.collectors.runner import RunRefused, run_collection
from apix.ingestion.store import CollectionStore, open_store
from apix.schemas.enums import CollectionOutcome, SourceType
from apix.statistics.elementary.admissibility import CollectionWindow, filter_admissible
from tests.fixtures.indigo_synthetic import (
    COLLECTION_DATE,
    build_fixture,
    day_payload,
    non_results_page,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "indigo" / "extract_2026-09-15.json"
REGISTRY = ROOT / "source_registry" / "registry.yaml"

#: HYPOTHETICAL. No source in the real register is rated like this.
CLEARED: dict[str, object] = {
    "source_id": "indigo",
    "automation_gate": "AUTOMATION_ALLOWED",
    "data_admissibility": "ADMISSIBLE",
    "tos_status": "CLEARLY_PERMITTED",
    "automated_collection_status": "CLEARLY_PERMITTED",
    "robots_status": "NO_RELEVANT_DISALLOW",
}


class Clock:
    """Deterministic IST clock inside the 21:00-22:00 primary window."""

    def __init__(self, start: datetime = datetime(2026, 9, 15, 21, 5, 0)) -> None:
        self.now = start

    def __call__(self) -> datetime:
        self.now += timedelta(seconds=2)
        return self.now


class Sleeps(list[float]):
    def __call__(self, seconds: float) -> None:
        self.append(seconds)


class ScriptedAdapter(SourceAdapter):
    """Test double: replays payloads per travel date, in order. No network."""

    source_id: ClassVar[str] = "indigo-direct"
    registry_id: ClassVar[str] = "indigo"
    adapter_version: ClassVar[str] = "test-double"
    parser_version: ClassVar[str] = "indigo-extract-parser/1"

    def __init__(self, script: dict[int, list[object]], mode: CollectionMode, clock: Clock) -> None:
        self.mode = mode
        self.script = {k: list(v) for k, v in script.items()}
        self.clock = clock
        self.calls: list[int] = []

    def search(self, params: SearchParams) -> SearchResult:
        lead = params.lead_time_days
        self.calls.append(lead)
        item = self.script[lead].pop(0)
        if isinstance(item, Exception):
            raise item
        assert isinstance(item, dict)
        started = self.clock()
        parsed = parse_extracted(item, params)
        return SearchResult(
            params=params,
            page_state=parsed.page_state,
            started_ts=started,
            finished_ts=self.clock(),
            displayed=parsed.displayed,
            candidates=parsed.candidates,
            artifacts=(Artifact("extracted_payload", canonical_json(item), "application/json"),),
            http_status=parsed.http_status,
            detail=parsed.detail,
            structural_issues=parsed.structural_issues,
        )


@pytest.fixture
def store(tmp_path: Path) -> Iterator[CollectionStore]:
    s = open_store(tmp_path / "store")
    yield s
    s.close()


def indigo_entry() -> dict[str, object]:
    return dict(find_source(yaml.safe_load(REGISTRY.read_text(encoding="utf-8")), "indigo"))


def run_fixture(
    store: CollectionStore, tmp_path: Path, apw: tuple[int, ...] = (7,), clock: Clock | None = None
):  # type: ignore[no-untyped-def]
    clock = clock or Clock()
    config = CollectionConfig.for_apw("indigo", COLLECTION_DATE, apw)
    adapter = FixtureIndigoAdapter(FIXTURE, clock=clock)
    return run_collection(
        config, adapter, store, export_root=tmp_path / "runs", clock=clock, sleep=Sleeps()
    )


# ── compliance gate ──────────────────────────────────────────────────────────


def test_the_current_register_refuses_live_automated_collection_from_indigo() -> None:
    decision = evaluate_live_gate(indigo_entry())
    assert not decision.allowed
    failures = " | ".join(decision.failures)
    assert "automation_gate=AUTOMATION_PROHIBITED" in failures
    assert "tos_status=NOT_VERIFIED" in failures
    assert "robots_status=NOT_VERIFIED" in failures


def test_no_source_in_the_register_is_cleared_for_live_collection() -> None:
    registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    cleared = [e.get("source_id") for e in registry["sources"] if evaluate_live_gate(e).allowed]
    assert cleared == [], (
        "a source cleared the live gate; update docs/engineering/automated-collection.md"
    )


def test_the_gate_clears_only_when_every_requirement_holds() -> None:
    assert evaluate_live_gate(CLEARED).allowed


@pytest.mark.parametrize("field", [name for name, _ in LIVE_REQUIREMENTS])
def test_failing_any_single_requirement_refuses(field: str) -> None:
    entry = {**CLEARED, field: "NOT_VERIFIED"}
    decision = evaluate_live_gate(entry)
    assert not decision.allowed
    assert decision.failures[0].startswith(f"{field}=")


def test_live_adapter_is_refused_before_playwright_is_even_imported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(name: str, *a: object, **k: object) -> object:
        raise AssertionError(f"imported {name} before the gate refused")

    monkeypatch.setattr(importlib, "import_module", forbidden)
    with pytest.raises(GateRefused, match="AUTOMATION_PROHIBITED"):
        LiveIndigoAdapter(indigo_entry())


def test_live_adapter_reports_missing_playwright_only_after_the_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "playwright", None)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", None)
    with pytest.raises(AdapterUnavailable, match="pip install"):
        LiveIndigoAdapter(CLEARED)


def test_a_refused_live_run_requests_nothing_and_writes_nothing(
    store: CollectionStore, tmp_path: Path
) -> None:
    clock = Clock()
    adapter = ScriptedAdapter({7: [day_payload(7)]}, CollectionMode.LIVE, clock)
    config = CollectionConfig.for_apw("indigo", COLLECTION_DATE, [7])
    with pytest.raises(GateRefused):
        run_collection(
            config,
            adapter,
            store,
            export_root=tmp_path / "runs",
            registry_entry=indigo_entry(),
            clock=clock,
        )
    assert adapter.calls == []
    assert store.runs() == []
    assert not (tmp_path / "runs").exists()


def test_a_live_run_without_a_register_entry_is_refused(
    store: CollectionStore, tmp_path: Path
) -> None:
    adapter = ScriptedAdapter({7: [day_payload(7)]}, CollectionMode.LIVE, Clock())
    config = CollectionConfig.for_apw("indigo", COLLECTION_DATE, [7])
    with pytest.raises(RunRefused):
        run_collection(config, adapter, store, export_root=tmp_path / "runs")
    assert adapter.calls == []


@pytest.mark.parametrize(
    ("status", "title", "text", "challenged"),
    [
        (403, "", "", True),
        (429, "", "", True),
        (200, "Just a moment", "Please verify you are human", True),
        (200, "Access Denied", "", True),
        (200, "IndiGo", "Flights from Delhi to Mumbai", False),
    ],
)
def test_challenge_detection(status: int, title: str, text: str, challenged: bool) -> None:
    assert (challenge_reason(status, title, text) is not None) is challenged


# ── first goal: one travel date, five bands ──────────────────────────────────


def test_single_date_fixture_run_produces_five_validated_canonical_observations(
    store: CollectionStore, tmp_path: Path
) -> None:
    report = run_fixture(store, tmp_path)
    (search,) = report.searches
    assert search.attempt.outcome is CollectionOutcome.SUCCESS
    assert search.counts() == {
        "expected": 5,
        "found": 5,
        "accepted": 5,
        "sold_out": 0,
        "excluded": 0,
        "missing": 0,
        "not_evaluated": 0,
    }
    assert [b.selected for b in search.bands] == [
        "6E9101@06:05",
        "6E9203@10:30",
        "6E9302@13:00",
        "6E9401@15:05",
        "6E9501@18:30",
    ]
    assert [b.eligible_count for b in search.bands] == [3, 1, 1, 1, 2]
    assert search.ineligible_counts == {
        "AFTER_CONTRACT_BANDS": 1,
        "ALTERNATE_ORIGIN": 1,
        "BEFORE_CONTRACT_BANDS": 1,
        "NOT_NONSTOP": 1,
        "NOT_OPERATED_BY_CARRIER": 1,
    }
    assert report.loaded and report.integrity_problems == () and report.status == "COMPLETE"

    stored = store.observations(COLLECTION_DATE)
    assert len(stored) == 5
    assert {o.fare_family_raw for o in stored} == {"Saver fare"}
    assert {o.source_type for o in stored} == {SourceType.SYNTHETIC}
    assert {o.departure_hour_band for o in stored} == {2, 3, 4, 5, 6}
    assert set(stored) == set(search.observations)

    (run,) = store.runs()
    assert run.frame_id == "DEL-BOM/6E/AIRLINE_DIRECT/T7@fixture"
    assert run.collector_identity == "fixture:FixtureIndigoAdapter"
    assert run.protocol_version == "automated-collection-trial-1"
    assert run.methodology_version == "2.1"

    # The existing admissibility filter accepts them unchanged -- no special path.
    result = filter_admissible(
        stored,
        CollectionWindow(run.collection_window_start.time(), run.collection_window_end.time()),
    )
    assert len(result.admissible) == 5
    assert result.excluded == ()


def test_the_earliest_flight_is_recorded_although_the_page_listed_cheaper_ones_first(
    store: CollectionStore, tmp_path: Path
) -> None:
    report = run_fixture(store, tmp_path)
    band2 = next(o for o in report.searches[0].observations if o.departure_hour_band == 2)
    assert band2.flight_number == "9101"
    page = {f["flight_label"]: f for f in day_payload(7)["flights"]}  # type: ignore[union-attr]
    cheaper = [n for n in ("6E 9102", "6E 9103") if _saver(page[n]) < band2.payable_fare]
    assert cheaper == ["6E 9102", "6E 9103"]


def _saver(card: dict) -> int:  # type: ignore[type-arg]
    tile = next(t for t in card["fares"] if t["family"] == "Saver fare")
    return int("".join(ch for ch in tile["price"] if ch.isdigit()))


# ── evidence ─────────────────────────────────────────────────────────────────


def test_every_observation_links_to_a_hashed_artifact(
    store: CollectionStore, tmp_path: Path
) -> None:
    run_fixture(store, tmp_path)
    with sqlite3.connect(tmp_path / "store" / "collection.sqlite3") as conn:
        links = [r[0] for r in conn.execute("SELECT artifact_sha256 FROM canonical_observation")]
    assert len(links) == 5 and all(links)
    for sha in set(links):
        assert sha256_hex(store.artifacts.get(sha)) == sha


def test_the_manifest_hashes_every_document_and_names_every_artifact(
    store: CollectionStore, tmp_path: Path
) -> None:
    report = run_fixture(store, tmp_path)
    manifest_bytes = (report.export_dir / "manifest.json").read_bytes()
    assert sha256_hex(manifest_bytes) == report.manifest_sha256
    manifest = json.loads(manifest_bytes)
    assert [d["name"] for d in manifest["documents"]] == [
        "attempts.json",
        "observations.json",
        "run.json",
        "selection.json",
    ]
    assert len(manifest["artifacts"]) == 1
    assert verify_run_export(report.export_dir, store.artifacts) == []

    run_doc = json.loads((report.export_dir / "run.json").read_text(encoding="utf-8"))
    assert run_doc["index_input"] is False
    assert run_doc["mode"] == "FIXTURE"
    selection = json.loads((report.export_dir / "selection.json").read_text(encoding="utf-8"))
    assert len(selection[0]["returned_flights"]) == 13


def test_a_tampered_document_or_artifact_fails_verification(
    store: CollectionStore, tmp_path: Path
) -> None:
    report = run_fixture(store, tmp_path)
    doc = report.export_dir / "observations.json"
    doc.write_bytes(doc.read_bytes().replace(b"6E", b"AI", 1))
    problems = verify_run_export(report.export_dir, store.artifacts)
    assert any("observations.json" in p for p in problems)

    sha = json.loads((report.export_dir / "manifest.json").read_text())["artifacts"][0]["sha256"]
    (tmp_path / "store" / "artifacts" / sha[:2] / sha).write_bytes(b"edited")
    assert any(
        "modified on disk" in p for p in verify_run_export(report.export_dir, store.artifacts)
    )


def test_identical_inputs_produce_byte_identical_exports(tmp_path: Path) -> None:
    exports = []
    for name in ("a", "b"):
        with open_store(tmp_path / name / "store") as s:
            report = run_fixture(s, tmp_path / name)
            exports.append({p.name: p.read_bytes() for p in sorted(report.export_dir.iterdir())})
    assert exports[0] == exports[1]


def test_an_export_is_never_overwritten(tmp_path: Path) -> None:
    write_run_export(tmp_path, "run-x", {"run.json": b"{}\n"}, [])
    with pytest.raises(ExportError, match="never overwritten"):
        write_run_export(tmp_path, "run-x", {"run.json": b"{}\n"}, [])


# ── second goal: the full APW vector ─────────────────────────────────────────


def test_full_apw_run_reports_expected_found_accepted_excluded_missing(
    store: CollectionStore, tmp_path: Path
) -> None:
    report = run_fixture(store, tmp_path, apw=FROZEN_APW)
    by_lead = {s.params.lead_time_days: s for s in report.searches}
    assert [s.attempt.outcome for s in report.searches] == [CollectionOutcome.SUCCESS] * 7

    assert by_lead[1].counts()["sold_out"] == 1
    assert by_lead[1].counts()["accepted"] == 4
    assert by_lead[15].counts()["missing"] == 1
    assert by_lead[15].bands[2].status == "EMPTY_BAND"
    assert by_lead[30].counts()["excluded"] == 1
    assert by_lead[30].bands[3].detail.startswith("FARE_FAMILY_NOT_OFFERED")
    for lead in (3, 7, 45, 60):
        assert by_lead[lead].counts()["accepted"] == 5

    totals = report.totals()
    assert {
        k: totals[k] for k in ("expected", "found", "accepted", "sold_out", "excluded", "missing")
    } == {
        "expected": 35,
        "found": 34,
        "accepted": 32,
        "sold_out": 1,
        "excluded": 1,
        "missing": 1,
    }
    assert report.status == "PARTIAL"
    assert report.integrity_problems == ()

    stored = store.observations(COLLECTION_DATE)
    assert len(stored) == 32
    assert sorted({o.apw_bucket.value for o in stored if o.apw_bucket}) == list(FROZEN_APW)
    # The sold-out band-6 flight on T+1 is not replaced by the later 19:10 flight.
    (unpriced,) = store.unpriced_flights(COLLECTION_DATE)
    assert unpriced.flight_number == "9501"
    t1 = [o for o in stored if o.lead_time_days == 1]
    assert "9502" not in {o.flight_number for o in t1}
    # T+30 band 5: Saver missing, Lite present -- nothing recorded for that band.
    assert 5 not in {o.departure_hour_band for o in stored if o.lead_time_days == 30}


# ── failure handling ─────────────────────────────────────────────────────────


def scripted_run(
    store: CollectionStore,
    tmp_path: Path,
    script: dict[int, list[object]],
    mode: CollectionMode = CollectionMode.FIXTURE,
    **kw: object,
):  # type: ignore[no-untyped-def]
    clock = Clock()
    sleeps = Sleeps()
    adapter = ScriptedAdapter(script, mode, clock)
    config = CollectionConfig.for_apw("indigo", COLLECTION_DATE, sorted(script))
    entry = CLEARED if mode is CollectionMode.LIVE else None
    report = run_collection(
        config,
        adapter,
        store,
        export_root=tmp_path / "runs",
        registry_entry=entry,
        clock=clock,
        sleep=sleeps,
        **kw,  # type: ignore[arg-type]
    )
    return report, adapter, sleeps


def test_an_access_challenge_stops_the_source_for_the_rest_of_the_run(
    store: CollectionStore, tmp_path: Path
) -> None:
    report, adapter, sleeps = scripted_run(
        store,
        tmp_path,
        {
            7: [day_payload(7)],
            15: [non_results_page("challenge", "verify you are human", 403)],
            30: [day_payload(30)],
        },
        CollectionMode.LIVE,
    )
    assert adapter.calls == [7, 15]  # T+30 was never requested
    outcomes = [s.attempt.outcome for s in report.searches]
    assert outcomes == [
        CollectionOutcome.SUCCESS,
        CollectionOutcome.CAPTCHA_OR_ANTIBOT_STOP,
        CollectionOutcome.CAPTCHA_OR_ANTIBOT_STOP,
    ]
    assert report.searches[2].attempt.detail.startswith("NOT_ATTEMPTED")
    assert sleeps == [30.0]  # paced once between searches; a challenge is never retried
    assert report.status == "STOPPED"


def test_live_searches_are_paced(store: CollectionStore, tmp_path: Path) -> None:
    _, adapter, sleeps = scripted_run(
        store,
        tmp_path,
        {7: [day_payload(7)], 15: [day_payload(15)], 30: [day_payload(30)]},
        CollectionMode.LIVE,
    )
    assert adapter.calls == [7, 15, 30]
    assert sleeps == [30.0, 30.0]


def test_a_site_error_is_retried_once_then_recorded_as_source_unavailable(
    store: CollectionStore, tmp_path: Path
) -> None:
    error = non_results_page("error", "503 Service Unavailable", 503)
    report, adapter, sleeps = scripted_run(store, tmp_path, {7: [error, error]})
    assert adapter.calls == [7, 7]
    assert sleeps == [60.0]
    attempt = report.searches[0].attempt
    assert attempt.outcome is CollectionOutcome.SOURCE_UNAVAILABLE
    assert "retried once" in attempt.detail


def test_a_site_error_that_clears_on_retry_is_a_success(
    store: CollectionStore, tmp_path: Path
) -> None:
    report, _, _ = scripted_run(
        store, tmp_path, {7: [non_results_page("error", "timeout"), day_payload(7)]}
    )
    assert report.searches[0].attempt.outcome is CollectionOutcome.SUCCESS


def test_the_retry_delay_cannot_undercut_the_protocol(
    store: CollectionStore, tmp_path: Path
) -> None:
    with pytest.raises(ConfigError, match="60 s"):
        scripted_run(store, tmp_path, {7: [day_payload(7)]}, retry_delay_seconds=5.0)


@pytest.mark.parametrize(
    ("echo", "fragment"),
    [
        ({"currency": "USD"}, "currency=USD"),
        ({"passengers": "2 Passengers"}, "adults=2"),
        ({"destination": "NMI"}, "destination=NMI"),
        ({"origin": "HDO"}, "origin=HDO"),
        ({"trip": "Round Trip"}, "trip_type=ROUND_TRIP"),
    ],
)
def test_a_search_the_page_does_not_echo_as_contracted_is_not_recorded(
    store: CollectionStore, tmp_path: Path, echo: dict[str, str], fragment: str
) -> None:
    from tests.fixtures.indigo_synthetic import results_page, standard_flights

    payload = results_page(COLLECTION_DATE + timedelta(days=7), standard_flights(6500), **echo)
    report, _, _ = scripted_run(store, tmp_path, {7: [payload]})
    attempt = report.searches[0].attempt
    assert attempt.outcome is CollectionOutcome.PARSER_FAILURE
    assert attempt.detail.startswith("SEARCH_PARAMETER_MISMATCH") and fragment in attempt.detail
    assert store.observations() == []


def test_a_date_the_page_does_not_echo_is_not_recorded(
    store: CollectionStore, tmp_path: Path
) -> None:
    payload = day_payload(7)
    payload["search_echo"]["date_label"] = "23rd Sep"  # type: ignore[index]
    report, _, _ = scripted_run(store, tmp_path, {7: [payload]})
    assert "travel_date=2026-09-23" in report.searches[0].attempt.detail


def test_a_layout_change_is_a_parser_failure_not_a_partial_guess(
    store: CollectionStore, tmp_path: Path
) -> None:
    payload = day_payload(7)
    del payload["flights"][0]["fares"]  # type: ignore[index]
    report, _, _ = scripted_run(store, tmp_path, {7: [payload]})
    attempt = report.searches[0].attempt
    assert attempt.outcome is CollectionOutcome.PARSER_FAILURE
    assert attempt.detail.startswith("DOM_CHANGED")


def test_a_no_flights_message_is_never_recorded_as_no_flight(
    store: CollectionStore, tmp_path: Path
) -> None:
    report, _, _ = scripted_run(
        store, tmp_path, {7: [non_results_page("no_flights", "No flights found")]}
    )
    attempt = report.searches[0].attempt
    assert attempt.outcome is CollectionOutcome.TECHNICAL_FAILURE
    assert attempt.outcome is not CollectionOutcome.NO_FLIGHT
    assert attempt.counts_toward_expected_cells


def test_an_adapter_exception_is_recorded_as_our_failure(
    store: CollectionStore, tmp_path: Path
) -> None:
    report, _, _ = scripted_run(store, tmp_path, {7: [RuntimeError("selector exploded")]})
    attempt = report.searches[0].attempt
    assert attempt.outcome is CollectionOutcome.PARSER_FAILURE
    assert "COLLECTOR_EXCEPTION: RuntimeError" in attempt.detail
    assert attempt.is_coverage_loss_we_caused


def test_a_page_with_every_selected_flight_sold_out(store: CollectionStore, tmp_path: Path) -> None:
    payload = day_payload(7)
    for card in payload["flights"]:  # type: ignore[union-attr]
        card["sold_out"] = True
    report, _, _ = scripted_run(store, tmp_path, {7: [payload]})
    search = report.searches[0]
    assert search.attempt.outcome is CollectionOutcome.TECHNICAL_FAILURE
    assert search.attempt.quotes_parsed == 0
    assert len(store.unpriced_flights(COLLECTION_DATE)) == 5


def test_a_page_whose_fares_cannot_be_read_is_a_parser_failure(
    store: CollectionStore, tmp_path: Path
) -> None:
    payload = day_payload(7)
    for card in payload["flights"]:  # type: ignore[union-attr]
        for tile in card["fares"]:
            tile["price"] = "--"
    report, _, _ = scripted_run(store, tmp_path, {7: [payload]})
    assert report.searches[0].attempt.outcome is CollectionOutcome.PARSER_FAILURE
    assert store.observations() == []


def test_a_fixture_without_a_page_for_the_date_is_a_recorded_failure(
    store: CollectionStore, tmp_path: Path
) -> None:
    clock = Clock()
    fixture = {**build_fixture(), "pages": {}}
    config = CollectionConfig.for_apw("indigo", COLLECTION_DATE, [7])
    report = run_collection(
        config,
        FixtureIndigoAdapter(fixture, clock=clock),
        store,
        export_root=tmp_path / "runs",
        clock=clock,
    )
    assert "FIXTURE_HAS_NO_PAGE_FOR_DATE" in report.searches[0].attempt.detail


def test_a_fixture_must_declare_itself_synthetic() -> None:
    with pytest.raises(FixtureError, match="SYNTHETIC_FIXTURE"):
        FixtureIndigoAdapter({**build_fixture(), "data_class": "REAL"})


def test_a_second_run_of_the_same_offers_is_not_loaded_twice(
    store: CollectionStore, tmp_path: Path
) -> None:
    run_fixture(store, tmp_path)
    second = run_fixture(store, tmp_path, clock=Clock(datetime(2026, 9, 15, 21, 30, 0)))
    assert not second.loaded
    assert "spec D.4" in second.not_loaded_reason
    assert second.export_dir.exists()
    assert len(store.observations(COLLECTION_DATE)) == 5
    assert len(store.runs()) == 1


def test_fixture_observations_are_never_labelled_as_live(
    store: CollectionStore, tmp_path: Path
) -> None:
    report = run_fixture(store, tmp_path, apw=FROZEN_APW)
    assert all(s.attempt.source_type is SourceType.SYNTHETIC for s in report.searches)
    assert SourceType.LIVE_SCRAPE not in {o.source_type for o in store.observations()}


def test_config_source_must_match_the_adapter(store: CollectionStore, tmp_path: Path) -> None:
    clock = Clock()
    config = replace(CollectionConfig.for_apw("indigo", COLLECTION_DATE, [7]), source="akasa_air")
    with pytest.raises(ConfigError, match="does not match adapter"):
        run_collection(
            config,
            FixtureIndigoAdapter(FIXTURE, clock=clock),
            store,
            export_root=tmp_path,
            clock=clock,
        )
