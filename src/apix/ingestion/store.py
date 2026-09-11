"""Minimum reproducible collection storage — Checkpoint 2H.

Four stores, one SQLite file and one content-addressed directory. No server, no
cloud, no new dependency: ``sqlite3`` and ``hashlib`` are standard library, and
the whole store is a path you can copy, diff and commit a checksum of.

    collection_run ──► collection_attempt ──► canonical_observation
                                     │       └► unpriced_flight
                                     │                  │
                                     └──► raw_artifact ◄┘

That is deliberate rather than minimal-for-its-own-sake. Spec P.3 requires a
publication to be *"re-run from its recorded version vector and compared bit for
bit"*, and that is a property of being able to find the original bytes again —
not of the database engine. SQLite gives it at zero operational cost, and
`context/tech_stack.md`'s PostgreSQL can replace this file without changing a
single call site, because the calls are the contract and not the storage.

**What this module will not do**

It has no table enumerating expected cells. Storing "the cells we saw" and
reading it back as "the cells we expected" is circular: coverage measured
against our own success can never fall, and would report 100% on a day the
collector was blocked. That is AMB-8, it is an open methodology question, and a
schema is not the place to quietly answer it.
"""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path

from apix.schemas.collection import CollectionAttempt, CollectionRun
from apix.schemas.enums import (
    Availability,
    ChangePolicy,
    Channel,
    CollectionOutcome,
    SourceType,
)
from apix.schemas.observation import Entitlements, FareBreakdown, Observation

SCHEMA_VERSION = 1


class StoreError(RuntimeError):
    """A store operation that cannot be completed. Never silently repaired."""


# ---------------------------------------------------------------------------
# Raw artifacts — content-addressed on local disk
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    """A stored raw artifact, addressed by the hash of its own bytes."""

    sha256: str
    byte_size: int
    content_type: str
    captured_ts: datetime
    source_id: str
    run_id: str
    attempt_id: str
    relative_path: str


class ArtifactStore:
    """Immutable, content-addressed artifact storage on the local filesystem.

    Addressed by SHA-256 of the content, which buys three things at once:
    identical bytes store once, corruption is detectable, and an artifact cannot
    be modified in place without changing its own address. Immutability is a
    property of the naming scheme rather than a rule someone has to follow.

    Layout ``{root}/{sha[:2]}/{sha}`` — the two-character fan-out keeps any one
    directory small enough for ordinary tooling across a 30-day run.
    """

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path_for(self, sha: str) -> Path:
        return self.root / sha[:2] / sha

    def put(
        self,
        content: bytes,
        *,
        content_type: str,
        source_id: str,
        run_id: str,
        attempt_id: str,
        captured_ts: datetime,
    ) -> ArtifactRef:
        """Store bytes and return their reference.

        Writing the same bytes twice is a no-op, not an error: two attempts that
        genuinely produced identical pages should converge on one artifact.
        """
        if not content:
            raise StoreError("refusing to store an empty artifact; record the outcome instead")
        sha = hashlib.sha256(content).hexdigest()
        dest = self._path_for(sha)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            dest.write_bytes(content)
        elif dest.read_bytes() != content:  # pragma: no cover — SHA-256 collision
            raise StoreError(f"hash collision on {sha}; refusing to overwrite")
        return ArtifactRef(
            sha256=sha,
            byte_size=len(content),
            content_type=content_type,
            captured_ts=captured_ts,
            source_id=source_id,
            run_id=run_id,
            attempt_id=attempt_id,
            relative_path=f"{sha[:2]}/{sha}",
        )

    def get(self, sha: str) -> bytes:
        """Read an artifact back, verifying it still hashes to its own address."""
        path = self._path_for(sha)
        if not path.exists():
            raise StoreError(f"artifact {sha} is not in the store at {self.root}")
        content = path.read_bytes()
        actual = hashlib.sha256(content).hexdigest()
        if actual != sha:
            raise StoreError(
                f"artifact {sha} has been modified on disk: content now hashes to "
                f"{actual}. Bit-for-bit reproducibility (spec P.3) is broken for any "
                "publication that used it"
            )
        return content


# ---------------------------------------------------------------------------
# SQLite schema
# ---------------------------------------------------------------------------

_DDL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS collection_run (
    run_id                    TEXT PRIMARY KEY,
    collection_date           TEXT NOT NULL,
    started_ts                TEXT NOT NULL,
    finished_ts               TEXT,
    collection_window_start   TEXT NOT NULL,
    collection_window_end     TEXT NOT NULL,
    collector_identity        TEXT NOT NULL,
    protocol_version          TEXT NOT NULL,
    methodology_version       TEXT NOT NULL,
    source_precedence_version TEXT NOT NULL,
    basket_version            TEXT NOT NULL,
    frame_id                  TEXT NOT NULL,
    parser_version            TEXT NOT NULL,
    collector_version         TEXT NOT NULL,
    notes                     TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS collection_attempt (
    attempt_id      TEXT PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES collection_run(run_id),
    collection_date TEXT NOT NULL,
    attempt_ts      TEXT NOT NULL,
    source_id       TEXT NOT NULL,
    source_group    TEXT,
    channel         TEXT NOT NULL,
    source_type     TEXT NOT NULL,
    origin          TEXT NOT NULL,
    destination     TEXT NOT NULL,
    travel_date     TEXT NOT NULL,
    lead_time_days  INTEGER NOT NULL,
    apw_bucket      INTEGER,
    outcome         TEXT NOT NULL,
    quotes_parsed   INTEGER NOT NULL DEFAULT 0,
    http_status     INTEGER,
    latency_ms      INTEGER,
    detail          TEXT NOT NULL DEFAULT '',
    -- The attempt's OWN claim, recorded independently of what was stored.
    -- verify() compares the two; if this were derived from the observations
    -- table instead, a partial write would be invisible by construction.
    observation_ids TEXT NOT NULL DEFAULT ''
);
-- The two queries that matter are the exclusion rate (spec H.1) and the
-- coverage denominator (spec I, AMB-8). Both scan by date and outcome.
CREATE INDEX IF NOT EXISTS ix_attempt_date_outcome
    ON collection_attempt(collection_date, outcome);

CREATE TABLE IF NOT EXISTS raw_artifact (
    sha256        TEXT PRIMARY KEY,
    byte_size     INTEGER NOT NULL,
    content_type  TEXT NOT NULL,
    captured_ts   TEXT NOT NULL,
    source_id     TEXT NOT NULL,
    run_id        TEXT NOT NULL REFERENCES collection_run(run_id),
    attempt_id    TEXT NOT NULL REFERENCES collection_attempt(attempt_id),
    relative_path TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS canonical_observation (
    observation_id       TEXT PRIMARY KEY,
    run_id               TEXT NOT NULL REFERENCES collection_run(run_id),
    attempt_id           TEXT NOT NULL REFERENCES collection_attempt(attempt_id),
    artifact_sha256      TEXT REFERENCES raw_artifact(sha256),
    origin               TEXT NOT NULL,
    destination          TEXT NOT NULL,
    travel_date          TEXT NOT NULL,
    departure_time_local TEXT NOT NULL,
    observation_ts       TEXT NOT NULL,
    collection_date      TEXT NOT NULL,
    carrier              TEXT NOT NULL,
    flight_number        TEXT NOT NULL,
    stops                INTEGER NOT NULL,
    duration_minutes     INTEGER NOT NULL,
    fare_family_raw      TEXT NOT NULL,
    channel              TEXT NOT NULL,
    source_id            TEXT NOT NULL,
    source_group         TEXT,
    source_type          TEXT NOT NULL,
    availability         TEXT NOT NULL,
    checked_baggage_kg   INTEGER NOT NULL,
    change_permitted     TEXT NOT NULL,
    cancellation_permitted TEXT NOT NULL,
    -- TEXT, never REAL. Notation requires decimal arithmetic before the log
    -- transform; a float here would silently lose the exactness upstream.
    payable_fare         TEXT NOT NULL,
    base_fare            TEXT,
    taxes                TEXT,
    fees                 TEXT,
    user_development_fee TEXT,
    CHECK (CAST(payable_fare AS REAL) > 0)
);
-- Spec D.4's duplicate tuple. `origin`/`destination` carry the route, which is
-- in the tuple deliberately: without it AMB-3 destroyed 95% of a synthetic day.
CREATE UNIQUE INDEX IF NOT EXISTS ux_observation_duplicate
    ON canonical_observation(
        collection_date, source_id, origin, destination, carrier, flight_number,
        travel_date, departure_time_local, fare_family_raw
    );
CREATE INDEX IF NOT EXISTS ix_observation_date ON canonical_observation(collection_date);

-- A flight that was listed but sold no seat at any price. Spec D.6: "a sold-out
-- flight is not a missing price; it is a disappeared item."
--
-- It needs its own table because `canonical_observation` cannot hold it.
-- `Observation.payable_fare` is a non-optional Decimal and this schema requires
-- it positive, so the only ways to store a sold-out flight there are to invent a
-- number or to write a zero — and a zero asserts the fare WAS zero. Dropping the
-- row instead would make "sold out" indistinguishable from "flight not
-- operating", which is exactly the distinction AMB-8's denominator turns on.
--
-- This is observed fact, not expectation: the flight appeared in the schedule
-- the source rendered. It is therefore not the circular basket table that
-- `storage-design.md` rules out.
CREATE TABLE IF NOT EXISTS unpriced_flight (
    unpriced_id          TEXT PRIMARY KEY,
    run_id               TEXT NOT NULL REFERENCES collection_run(run_id),
    attempt_id           TEXT NOT NULL REFERENCES collection_attempt(attempt_id),
    collection_date      TEXT NOT NULL,
    origin               TEXT NOT NULL,
    destination          TEXT NOT NULL,
    travel_date          TEXT NOT NULL,
    carrier              TEXT NOT NULL,
    flight_number        TEXT NOT NULL,
    departure_time_local TEXT NOT NULL,
    observation_ts       TEXT NOT NULL,
    source_id            TEXT NOT NULL,
    availability         TEXT NOT NULL,
    detail               TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_unpriced_date ON unpriced_flight(collection_date);
"""


@dataclass(frozen=True, slots=True)
class UnpricedFlight:
    """A flight that was listed but offered no purchasable fare — spec D.6.

    Carries no price and never will. It exists so that "sold out" and "not
    operating" stay distinguishable, which is what AMB-8's coverage denominator
    turns on: a sold-out flight is an expected cell that produced no quote, and
    a flight that does not operate is not an expected cell at all.
    """

    unpriced_id: str
    run_id: str
    attempt_id: str
    collection_date: date
    origin: str
    destination: str
    travel_date: date
    carrier: str
    flight_number: str
    departure_time_local: time
    observation_ts: datetime
    source_id: str
    availability: Availability = Availability.SOLD_OUT
    detail: str = ""

    def __post_init__(self) -> None:
        if self.availability is Availability.AVAILABLE:
            raise ValueError(
                "an AVAILABLE flight has a purchasable fare and belongs in "
                "canonical_observation; recording it here would lose the price"
            )

    @property
    def route(self) -> str:
        return f"{self.origin}-{self.destination}"


def _dec(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _undec(value: str | None) -> Decimal | None:
    return None if value is None else Decimal(value)


class CollectionStore:
    """The four Day-1 stores behind one object.

    Every write is inside a transaction and every read returns the schema
    dataclasses, so callers never handle rows. The point of that is migration:
    the call sites are the contract, and PostgreSQL can replace SQLite later
    without any of them changing.
    """

    def __init__(self, db_path: Path, artifact_root: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.artifacts = ArtifactStore(artifact_root)
        self._conn = sqlite3.connect(self.db_path, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_DDL)
        self._conn.execute(
            "INSERT OR REPLACE INTO schema_meta(key, value) VALUES ('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> CollectionStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        self._conn.execute("BEGIN")
        try:
            yield self._conn
        except Exception:
            self._conn.execute("ROLLBACK")
            raise
        else:
            self._conn.execute("COMMIT")

    # ── writes ────────────────────────────────────────────────────────────

    def record_run(self, run: CollectionRun) -> None:
        with self._tx() as c:
            c.execute(
                "INSERT INTO collection_run VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    run.run_id,
                    run.collection_date.isoformat(),
                    run.started_ts.isoformat(),
                    run.finished_ts.isoformat() if run.finished_ts else None,
                    run.collection_window_start.isoformat(),
                    run.collection_window_end.isoformat(),
                    run.collector_identity,
                    run.protocol_version,
                    run.methodology_version,
                    run.source_precedence_version,
                    run.basket_version,
                    run.frame_id,
                    run.parser_version,
                    run.collector_version,
                    run.notes,
                ),
            )

    def record_attempt(self, attempt: CollectionAttempt) -> None:
        bucket = attempt.apw_bucket
        with self._tx() as c:
            c.execute(
                "INSERT INTO collection_attempt VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    attempt.attempt_id,
                    attempt.run_id,
                    attempt.collection_date.isoformat(),
                    attempt.attempt_ts.isoformat(),
                    attempt.source_id,
                    attempt.source_group,
                    attempt.channel.value,
                    attempt.source_type.value,
                    attempt.origin,
                    attempt.destination,
                    attempt.travel_date.isoformat(),
                    attempt.lead_time_days,
                    bucket.value if bucket else None,
                    attempt.outcome.value,
                    attempt.quotes_parsed,
                    attempt.http_status,
                    attempt.latency_ms,
                    attempt.detail,
                    ",".join(attempt.observation_ids),
                ),
            )

    def record_artifact(self, ref: ArtifactRef) -> None:
        with self._tx() as c:
            c.execute(
                "INSERT OR IGNORE INTO raw_artifact VALUES (?,?,?,?,?,?,?,?)",
                (
                    ref.sha256,
                    ref.byte_size,
                    ref.content_type,
                    ref.captured_ts.isoformat(),
                    ref.source_id,
                    ref.run_id,
                    ref.attempt_id,
                    ref.relative_path,
                ),
            )

    def record_observation(
        self,
        obs: Observation,
        *,
        run_id: str,
        attempt_id: str,
        artifact_sha256: str | None = None,
    ) -> None:
        """Persist one canonical observation with its provenance.

        Raises on a duplicate (spec D.4) rather than upserting: two quotes that
        collide on the duplicate tuple are the same offer seen twice, and
        silently replacing one with the other would hide a collection error.
        """
        fb = obs.fare_breakdown
        e = obs.entitlements
        try:
            with self._tx() as c:
                c.execute(
                    "INSERT INTO canonical_observation VALUES "
                    "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        obs.observation_id,
                        run_id,
                        attempt_id,
                        artifact_sha256,
                        obs.origin,
                        obs.destination,
                        obs.travel_date.isoformat(),
                        obs.departure_time_local.isoformat(),
                        obs.observation_ts.isoformat(),
                        obs.collection_date.isoformat(),
                        obs.carrier,
                        obs.flight_number,
                        obs.stops,
                        obs.duration_minutes,
                        obs.fare_family_raw,
                        obs.channel.value,
                        obs.source_id,
                        obs.source_group,
                        obs.source_type.value,
                        obs.availability.value,
                        e.checked_baggage_kg,
                        e.change_permitted.value,
                        e.cancellation_permitted.value,
                        _dec(obs.payable_fare),
                        _dec(fb.base_fare),
                        _dec(fb.taxes),
                        _dec(fb.fees),
                        _dec(fb.user_development_fee),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise StoreError(
                f"observation {obs.observation_id} violates a store constraint: {exc}. "
                "A duplicate-tuple collision (spec D.4) means the same offer was "
                "recorded twice; it is not repaired here"
            ) from exc

    def record_unpriced_flight(self, flight: UnpricedFlight) -> None:
        """Persist a flight that was listed but sold no seat — spec D.6."""
        with self._tx() as c:
            c.execute(
                "INSERT INTO unpriced_flight VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    flight.unpriced_id,
                    flight.run_id,
                    flight.attempt_id,
                    flight.collection_date.isoformat(),
                    flight.origin,
                    flight.destination,
                    flight.travel_date.isoformat(),
                    flight.carrier,
                    flight.flight_number,
                    flight.departure_time_local.isoformat(),
                    flight.observation_ts.isoformat(),
                    flight.source_id,
                    flight.availability.value,
                    flight.detail,
                ),
            )

    # ── reads ─────────────────────────────────────────────────────────────

    def runs(self) -> list[CollectionRun]:
        rows = self._conn.execute(
            "SELECT * FROM collection_run ORDER BY collection_date, run_id"
        ).fetchall()
        return [
            CollectionRun(
                run_id=r["run_id"],
                collection_date=date.fromisoformat(r["collection_date"]),
                started_ts=datetime.fromisoformat(r["started_ts"]),
                collection_window_start=datetime.fromisoformat(r["collection_window_start"]),
                collection_window_end=datetime.fromisoformat(r["collection_window_end"]),
                source_precedence_version=r["source_precedence_version"],
                basket_version=r["basket_version"],
                parser_version=r["parser_version"],
                collector_version=r["collector_version"],
                collector_identity=r["collector_identity"],
                protocol_version=r["protocol_version"],
                methodology_version=r["methodology_version"],
                frame_id=r["frame_id"],
                finished_ts=(
                    datetime.fromisoformat(r["finished_ts"]) if r["finished_ts"] else None
                ),
                notes=r["notes"],
            )
            for r in rows
        ]

    def attempts(self, collection_date: date | None = None) -> list[CollectionAttempt]:
        sql = "SELECT * FROM collection_attempt"
        args: tuple[str, ...] = ()
        if collection_date is not None:
            sql += " WHERE collection_date = ?"
            args = (collection_date.isoformat(),)
        sql += " ORDER BY attempt_ts, attempt_id"
        return [
            CollectionAttempt(
                attempt_id=r["attempt_id"],
                run_id=r["run_id"],
                collection_date=date.fromisoformat(r["collection_date"]),
                attempt_ts=datetime.fromisoformat(r["attempt_ts"]),
                source_id=r["source_id"],
                channel=Channel(r["channel"]),
                source_type=SourceType(r["source_type"]),
                origin=r["origin"],
                destination=r["destination"],
                travel_date=date.fromisoformat(r["travel_date"]),
                outcome=CollectionOutcome(r["outcome"]),
                source_group=r["source_group"],
                quotes_parsed=r["quotes_parsed"],
                http_status=r["http_status"],
                latency_ms=r["latency_ms"],
                detail=r["detail"],
                observation_ids=tuple(x for x in r["observation_ids"].split(",") if x),
            )
            for r in self._conn.execute(sql, args).fetchall()
        ]

    def observations(self, collection_date: date | None = None) -> list[Observation]:
        sql = "SELECT * FROM canonical_observation"
        args: tuple[str, ...] = ()
        if collection_date is not None:
            sql += " WHERE collection_date = ?"
            args = (collection_date.isoformat(),)
        sql += " ORDER BY observation_id"
        return [
            Observation(
                observation_id=r["observation_id"],
                origin=r["origin"],
                destination=r["destination"],
                travel_date=date.fromisoformat(r["travel_date"]),
                departure_time_local=datetime.strptime(
                    r["departure_time_local"], "%H:%M:%S"
                ).time(),
                observation_ts=datetime.fromisoformat(r["observation_ts"]),
                collection_date=date.fromisoformat(r["collection_date"]),
                carrier=r["carrier"],
                flight_number=r["flight_number"],
                stops=r["stops"],
                duration_minutes=r["duration_minutes"],
                fare_family_raw=r["fare_family_raw"],
                channel=Channel(r["channel"]),
                source_id=r["source_id"],
                entitlements=Entitlements(
                    checked_baggage_kg=r["checked_baggage_kg"],
                    change_permitted=ChangePolicy(r["change_permitted"]),
                    cancellation_permitted=ChangePolicy(r["cancellation_permitted"]),
                ),
                payable_fare=Decimal(r["payable_fare"]),
                source_type=SourceType(r["source_type"]),
                availability=Availability(r["availability"]),
                source_group=r["source_group"],
                fare_breakdown=FareBreakdown(
                    base_fare=_undec(r["base_fare"]),
                    taxes=_undec(r["taxes"]),
                    fees=_undec(r["fees"]),
                    user_development_fee=_undec(r["user_development_fee"]),
                ),
            )
            for r in self._conn.execute(sql, args).fetchall()
        ]

    def unpriced_flights(self, collection_date: date | None = None) -> list[UnpricedFlight]:
        sql = "SELECT * FROM unpriced_flight"
        args: tuple[str, ...] = ()
        if collection_date is not None:
            sql += " WHERE collection_date = ?"
            args = (collection_date.isoformat(),)
        sql += " ORDER BY unpriced_id"
        return [
            UnpricedFlight(
                unpriced_id=r["unpriced_id"],
                run_id=r["run_id"],
                attempt_id=r["attempt_id"],
                collection_date=date.fromisoformat(r["collection_date"]),
                origin=r["origin"],
                destination=r["destination"],
                travel_date=date.fromisoformat(r["travel_date"]),
                carrier=r["carrier"],
                flight_number=r["flight_number"],
                departure_time_local=datetime.strptime(
                    r["departure_time_local"], "%H:%M:%S"
                ).time(),
                observation_ts=datetime.fromisoformat(r["observation_ts"]),
                source_id=r["source_id"],
                availability=Availability(r["availability"]),
                detail=r["detail"],
            )
            for r in self._conn.execute(sql, args).fetchall()
        ]

    def artifact_refs(self) -> list[ArtifactRef]:
        return [
            ArtifactRef(
                sha256=r["sha256"],
                byte_size=r["byte_size"],
                content_type=r["content_type"],
                captured_ts=datetime.fromisoformat(r["captured_ts"]),
                source_id=r["source_id"],
                run_id=r["run_id"],
                attempt_id=r["attempt_id"],
                relative_path=r["relative_path"],
            )
            for r in self._conn.execute("SELECT * FROM raw_artifact ORDER BY sha256")
        ]

    # ── integrity ─────────────────────────────────────────────────────────

    def verify(self, collection_date: date | None = None) -> list[str]:
        """Check the store against itself. Returns problems, empty when sound.

        Reports rather than raises, because a run that produced one inconsistent
        row should still be inspectable. Silence here is the claim that the
        stored evidence supports whatever is computed from it.
        """
        problems: list[str] = []

        # Raw rows throughout. Reconstructing the dataclasses would raise on the
        # very inconsistency this method exists to report, making a damaged
        # store unreadable exactly when it most needs reading.
        where = " WHERE collection_date = ?" if collection_date else ""
        args = (collection_date.isoformat(),) if collection_date else ()

        stored_counts = {
            r["attempt_id"]: r["n"]
            for r in self._conn.execute(
                "SELECT attempt_id, COUNT(*) AS n FROM canonical_observation"
                + where
                + " GROUP BY attempt_id",
                args,
            )
        }
        for r in self._conn.execute(
            "SELECT attempt_id, quotes_parsed FROM collection_attempt" + where, args
        ):
            stored = stored_counts.get(r["attempt_id"], 0)
            if stored != r["quotes_parsed"]:
                problems.append(
                    f"attempt {r['attempt_id']} claims {r['quotes_parsed']} quotes but "
                    f"{stored} observations are stored against it"
                )

        # Every stored artifact still hashes to its own address.
        for ref in self.artifact_refs():
            try:
                self.artifacts.get(ref.sha256)
            except StoreError as exc:
                problems.append(str(exc))

        # Every observation falls inside its run's declared spec A.5 window.
        windows = {r.run_id: r for r in self.runs()}
        for r in self._conn.execute(
            "SELECT observation_id, run_id, observation_ts FROM canonical_observation" + where,
            args,
        ):
            run = windows.get(r["run_id"])
            seen = datetime.fromisoformat(r["observation_ts"])
            if run and not run.contains(seen):
                problems.append(
                    f"observation {r['observation_id']} at {seen} is outside its "
                    f"run's declared window {run.collection_window_start}"
                    f"..{run.collection_window_end} (spec A.5 — flag, do not discard)"
                )
        return problems


def open_store(root: Path) -> CollectionStore:
    """Open (or create) a store rooted at one directory.

    Layout::

        {root}/collection.sqlite3
        {root}/artifacts/{sha[:2]}/{sha}

    One directory is the whole store: copy it and you have copied the evidence.
    """
    root = Path(root)
    return CollectionStore(root / "collection.sqlite3", root / "artifacts")


def summarise(store: CollectionStore, collection_date: date) -> dict[str, object]:
    """The Day-N quality figures — spec H.1, I.

    Deliberately **not** an index. Publication has prerequisites this cannot
    satisfy (route weights need more than one route; AMB-8 gates coverage), and
    a function that emitted a level here would invite reporting one.
    """
    attempts = store.attempts(collection_date)
    observations = store.observations(collection_date)
    by_outcome: dict[str, int] = {}
    for a in attempts:
        by_outcome[a.outcome.value] = by_outcome.get(a.outcome.value, 0) + 1
    incomplete = sum(1 for o in observations if not o.fare_breakdown.is_complete)
    return {
        "collection_date": collection_date.isoformat(),
        "attempts": len(attempts),
        "successes": by_outcome.get(CollectionOutcome.SUCCESS.value, 0),
        "failures": len(attempts) - by_outcome.get(CollectionOutcome.SUCCESS.value, 0),
        "by_outcome": dict(sorted(by_outcome.items())),
        "collector_failures": sum(1 for a in attempts if a.outcome.is_collector_failure),
        "observations": len(observations),
        "routes": sorted({o.route for o in observations}),
        "carriers": sorted({o.carrier for o in observations}),
        "travel_dates": sorted({o.travel_date.isoformat() for o in observations}),
        "apw_buckets": sorted(
            {o.apw_bucket.value for o in observations if o.apw_bucket is not None}
        ),
        "fare_classes": sorted({o.fare_class.value for o in observations}),
        # Listed but unpurchasable — spec D.6. Read from its own table, because
        # a sold-out flight has no fare and so cannot be a canonical observation.
        "unpriced_flights": len(store.unpriced_flights(collection_date)),
        "sold_out_observations": sum(
            1 for o in observations if o.availability is Availability.SOLD_OUT
        ),
        "incomplete_fare_breakdown": incomplete,
        "artifacts": len(store.artifact_refs()),
        "integrity_problems": store.verify(collection_date),
    }


__all__ = [
    "SCHEMA_VERSION",
    "ArtifactRef",
    "ArtifactStore",
    "CollectionStore",
    "StoreError",
    "UnpricedFlight",
    "open_store",
    "summarise",
]
