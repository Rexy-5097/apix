"""The Day-1 collection store — reproducibility, provenance and integrity.

The store's whole purpose is that a published number can be walked back to the
bytes that produced it (spec P.3). These tests exercise that walk, and the ways
it can silently break: an artifact edited on disk, an attempt whose claimed
count disagrees with what was stored, a duplicate offer recorded twice.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from apix.ingestion.store import (
    ArtifactStore,
    CollectionStore,
    StoreError,
    open_store,
    summarise,
)
from apix.schemas.collection import CollectionAttempt, CollectionRun
from apix.schemas.enums import (
    APWBucket,
    ChangePolicy,
    Channel,
    CollectionOutcome,
    FareClass,
    SourceType,
)
from apix.schemas.observation import Entitlements, FareBreakdown, Observation

T = date(2026, 9, 12)
W_START = datetime(2026, 9, 12, 21, 0)
W_END = datetime(2026, 9, 12, 22, 0)
RUN_ID = "run-2026-09-12-2100"


def a_run(**kw: object) -> CollectionRun:
    base: dict[str, object] = {
        "run_id": RUN_ID,
        "collection_date": T,
        "started_ts": W_START,
        "collection_window_start": W_START,
        "collection_window_end": W_END,
        "source_precedence_version": "spike-single-source-v1",
        "basket_version": "2026-Q3",
        "parser_version": "manual-1.0",
        "collector_version": "manual",
        "collector_identity": "slazyverse (manual, browser)",
        "protocol_version": "acquisition-protocol-2G",
        "methodology_version": "2.1",
        "frame_id": "DEL-BOM/6E/AIRLINE_DIRECT/T7-T15-T21-T30",
    }
    base.update(kw)
    return CollectionRun(**base)  # type: ignore[arg-type]


def an_attempt(outcome: CollectionOutcome, aid: str = "att-1", **kw: object) -> CollectionAttempt:
    base: dict[str, object] = {
        "attempt_id": aid,
        "run_id": RUN_ID,
        "collection_date": T,
        "attempt_ts": W_START,
        "source_id": "indigo-direct",
        "channel": Channel.AIRLINE_DIRECT,
        "source_type": SourceType.LIVE_SCRAPE,
        "origin": "DEL",
        "destination": "BOM",
        "travel_date": T + timedelta(days=7),
        "outcome": outcome,
    }
    base.update(kw)
    return CollectionAttempt(**base)  # type: ignore[arg-type]


def an_obs(oid: str = "o1", **kw: object) -> Observation:
    base: dict[str, object] = {
        "observation_id": oid,
        "origin": "DEL",
        "destination": "BOM",
        "travel_date": T + timedelta(days=7),
        "departure_time_local": time(6, 10),
        "observation_ts": datetime(2026, 9, 12, 21, 15),
        "collection_date": T,
        "carrier": "6E",
        "flight_number": "2045",
        "stops": 0,
        "duration_minutes": 125,
        "fare_family_raw": "SAVER",
        "channel": Channel.AIRLINE_DIRECT,
        "source_id": "indigo-direct",
        "entitlements": Entitlements(15, ChangePolicy.FEE, ChangePolicy.FEE),
        "payable_fare": Decimal("5432.00"),
        "source_type": SourceType.LIVE_SCRAPE,
    }
    base.update(kw)
    return Observation(**base)  # type: ignore[arg-type]


@pytest.fixture
def store(tmp_path: Path) -> CollectionStore:
    s = open_store(tmp_path / "day1")
    s.record_run(a_run())
    return s


# ─── Round trip ──────────────────────────────────────────────────────────────


def test_run_round_trips_with_every_identifier(store: CollectionStore) -> None:
    (back,) = store.runs()
    assert back.run_id == RUN_ID
    assert back.collector_identity == "slazyverse (manual, browser)"
    assert back.protocol_version == "acquisition-protocol-2G"
    assert back.methodology_version == "2.1"
    assert back.frame_id == "DEL-BOM/6E/AIRLINE_DIRECT/T7-T15-T21-T30"
    assert back.collection_window_start == W_START


def test_observation_round_trips_exactly(store: CollectionStore) -> None:
    """Decimal in, Decimal out. A float round-trip would lose exactness before
    the log transform, which Notation forbids."""
    store.record_attempt(
        an_attempt(CollectionOutcome.SUCCESS, quotes_parsed=1, observation_ids=("o1",))
    )
    original = an_obs(
        fare_breakdown=FareBreakdown(
            base_fare=Decimal("4600.00"),
            taxes=Decimal("532.00"),
            fees=Decimal("150.00"),
            user_development_fee=Decimal("150.00"),
        )
    )
    store.record_observation(original, run_id=RUN_ID, attempt_id="att-1")

    (back,) = store.observations(T)
    assert back == original
    assert isinstance(back.payable_fare, Decimal)
    assert back.payable_fare == Decimal("5432.00")
    assert back.fare_breakdown.is_complete
    assert back.apw_bucket is APWBucket.T_PLUS_7
    assert back.fare_class is FareClass.STANDARD


def test_unrendered_components_stay_none_through_storage(store: CollectionStore) -> None:
    """NULL in the database must come back as None, never 0. A zero would assert
    the charge does not exist."""
    store.record_attempt(
        an_attempt(CollectionOutcome.SUCCESS, quotes_parsed=1, observation_ids=("o1",))
    )
    store.record_observation(an_obs(), run_id=RUN_ID, attempt_id="att-1")
    (back,) = store.observations(T)
    assert back.fare_breakdown.base_fare is None
    assert back.fare_breakdown.declared_total is None
    assert back.source_group is None


# ─── Provenance ──────────────────────────────────────────────────────────────


def test_observation_walks_back_to_its_bytes(store: CollectionStore, tmp_path: Path) -> None:
    """The spec P.3 walk: published value -> observation -> attempt -> raw bytes."""
    store.record_attempt(
        an_attempt(CollectionOutcome.SUCCESS, quotes_parsed=1, observation_ids=("o1",))
    )
    page = b"<html>DEL-BOM 6E2045 INR 5432.00</html>"
    ref = store.artifacts.put(
        page,
        content_type="text/html",
        source_id="indigo-direct",
        run_id=RUN_ID,
        attempt_id="att-1",
        captured_ts=datetime(2026, 9, 12, 21, 15),
    )
    store.record_artifact(ref)
    store.record_observation(
        an_obs(), run_id=RUN_ID, attempt_id="att-1", artifact_sha256=ref.sha256
    )

    assert store.artifacts.get(ref.sha256) == page
    assert [r.sha256 for r in store.artifact_refs()] == [ref.sha256]
    assert store.verify(T) == []


def test_identical_bytes_store_once(store: CollectionStore) -> None:
    """Content addressing means two attempts returning the same page converge."""
    kw = dict(
        content_type="text/html",
        source_id="indigo-direct",
        run_id=RUN_ID,
        attempt_id="att-1",
        captured_ts=W_START,
    )
    a = store.artifacts.put(b"same", **kw)  # type: ignore[arg-type]
    b = store.artifacts.put(b"same", **kw)  # type: ignore[arg-type]
    assert a.sha256 == b.sha256


def test_empty_artifact_is_refused(store: CollectionStore) -> None:
    """An empty page is an outcome, not an artifact."""
    with pytest.raises(StoreError, match="empty artifact"):
        store.artifacts.put(
            b"",
            content_type="text/html",
            source_id="s",
            run_id=RUN_ID,
            attempt_id="att-1",
            captured_ts=W_START,
        )


def test_tampered_artifact_is_detected(tmp_path: Path) -> None:
    """The property the whole store exists for. If the bytes change, spec P.3's
    bit-for-bit re-run is broken and it must be loud, not silent."""
    arts = ArtifactStore(tmp_path / "a")
    ref = arts.put(
        b"original",
        content_type="text/html",
        source_id="s",
        run_id=RUN_ID,
        attempt_id="att-1",
        captured_ts=W_START,
    )
    (tmp_path / "a" / ref.sha256[:2] / ref.sha256).write_bytes(b"tampered")
    with pytest.raises(StoreError, match="modified on disk"):
        arts.get(ref.sha256)


# ─── Integrity ───────────────────────────────────────────────────────────────


def test_duplicate_offer_is_rejected_not_upserted(store: CollectionStore) -> None:
    """Spec D.4. Two quotes colliding on the duplicate tuple are the same offer
    seen twice; replacing one with the other would hide a collection error."""
    store.record_attempt(
        an_attempt(CollectionOutcome.SUCCESS, quotes_parsed=1, observation_ids=("o1",))
    )
    store.record_observation(an_obs("o1"), run_id=RUN_ID, attempt_id="att-1")
    with pytest.raises(StoreError, match=r"duplicate-tuple|constraint"):
        store.record_observation(an_obs("o2"), run_id=RUN_ID, attempt_id="att-1")


def test_verify_catches_a_count_that_disagrees_with_storage(store: CollectionStore) -> None:
    """An attempt claiming two quotes with one stored is a silent data loss."""
    store.record_attempt(
        an_attempt(CollectionOutcome.SUCCESS, quotes_parsed=2, observation_ids=("o1", "o2"))
    )
    store.record_observation(an_obs("o1"), run_id=RUN_ID, attempt_id="att-1")
    problems = store.verify(T)
    assert any("claims 2 quotes but 1 observations" in p for p in problems)


def test_verify_flags_an_observation_outside_the_declared_window(store: CollectionStore) -> None:
    """Spec A.5 — outside the window is flagged, never discarded."""
    store.record_attempt(
        an_attempt(CollectionOutcome.SUCCESS, quotes_parsed=1, observation_ids=("o1",))
    )
    store.record_observation(
        an_obs(observation_ts=datetime(2026, 9, 12, 3, 0)),
        run_id=RUN_ID,
        attempt_id="att-1",
    )
    problems = store.verify(T)
    assert any("outside its run's declared window" in p for p in problems)
    # flagged, not dropped
    assert len(store.observations(T)) == 1


def test_failures_persist_and_are_not_observations(store: CollectionStore) -> None:
    """The point of the attempt store: a blocked attempt is recorded, is not a
    fare, and keeps its cell in the coverage denominator."""
    store.record_attempt(an_attempt(CollectionOutcome.CAPTCHA_OR_ANTIBOT_STOP, "att-block"))
    store.record_attempt(an_attempt(CollectionOutcome.NO_FLIGHT, "att-none"))
    attempts = {a.attempt_id: a for a in store.attempts(T)}
    assert len(attempts) == 2
    assert store.observations(T) == []
    assert attempts["att-block"].counts_toward_expected_cells
    assert attempts["att-block"].is_coverage_loss_we_caused
    assert not attempts["att-none"].counts_toward_expected_cells


# ─── Summary ─────────────────────────────────────────────────────────────────


def test_summary_reports_quality_not_an_index(store: CollectionStore) -> None:
    """Deliberately emits no level. Publication has prerequisites a single-route
    single-carrier frame cannot satisfy, and a function returning a number here
    would invite reporting one."""
    store.record_attempt(
        an_attempt(CollectionOutcome.SUCCESS, "att-1", quotes_parsed=1, observation_ids=("o1",))
    )
    store.record_attempt(an_attempt(CollectionOutcome.NO_FLIGHT, "att-2"))
    store.record_attempt(an_attempt(CollectionOutcome.PARSER_FAILURE, "att-3"))
    store.record_observation(an_obs(), run_id=RUN_ID, attempt_id="att-1")

    s = summarise(store, T)
    assert s["attempts"] == 3
    assert s["successes"] == 1
    assert s["failures"] == 2
    assert s["collector_failures"] == 1  # NO_FLIGHT is the market's, not ours
    assert s["observations"] == 1
    assert s["routes"] == ["DEL-BOM"]
    assert s["apw_buckets"] == [7]
    assert s["incomplete_fare_breakdown"] == 1
    assert s["integrity_problems"] == []
    assert "level" not in s and "index" not in s


def test_store_reopens_with_its_data(tmp_path: Path) -> None:
    """A 30-day run is 30 separate sessions. The store is a directory you can
    copy, and reopening it must find everything."""
    root = tmp_path / "day1"
    with open_store(root) as s:
        s.record_run(a_run())
        s.record_attempt(
            an_attempt(CollectionOutcome.SUCCESS, quotes_parsed=1, observation_ids=("o1",))
        )
        s.record_observation(an_obs(), run_id=RUN_ID, attempt_id="att-1")

    with open_store(root) as s2:
        assert len(s2.runs()) == 1
        assert len(s2.attempts(T)) == 1
        assert len(s2.observations(T)) == 1
        assert s2.verify(T) == []
