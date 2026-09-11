"""Load one day of manual collection into the store.

The bridge between a person with a browser and the canonical stores. Manual
collection is the only mode currently permitted — the Checkpoint 2G automation
gate leaves zero sources ``AUTOMATION_ALLOWED`` — so this is the Day-1 entry
point, not a stopgap.

    python tools/collection/load_manual.py \\
        --store data/collection \\
        --date 2026-09-12 \\
        --window primary \\
        --collector "Your Name" \\
        --fares day01_fares.csv \\
        --attempts day01_attempts.csv \\
        --artifacts day01_screenshots/

It validates before it writes and writes nothing on a validation failure, so a
half-loaded day cannot exist. Then it runs ``verify()`` and prints the quality
report.

**It does not compute an index.** A single-route single-carrier frame cannot
satisfy publication's prerequisites — route weights need more than one route and
AMB-8 gates coverage — so this reports acquisition quality and stops there.
"""

from __future__ import annotations

import argparse
import csv
import json
import mimetypes
import sys
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from apix.ingestion.store import (
    CollectionStore,
    UnpricedFlight,
    open_store,
    summarise,
)
from apix.schemas.collection import CollectionAttempt, CollectionRun
from apix.schemas.enums import (
    Availability,
    ChangePolicy,
    Channel,
    CollectionOutcome,
    SourceType,
)
from apix.schemas.observation import Entitlements, FareBreakdown, Observation

REPO = Path(__file__).resolve().parents[2]
WINDOWS = REPO / "source_registry" / "collection-windows.yaml"
FRAME_BASE = "DEL-BOM/6E/AIRLINE_DIRECT/T7-T15-T21-T30"


class LoadError(Exception):
    """A row that cannot be loaded. Nothing is written when one is raised."""


def _money(value: str, field: str, row: int) -> Decimal | None:
    """Parse a money column. **Blank is None, never zero.**

    A zero asserts the charge does not exist; None says the source did not show
    it (spec A.4). Turning one into the other is the single most damaging thing
    a loader can do quietly.
    """
    text = (value or "").strip().replace(",", "").replace("₹", "")
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise LoadError(f"row {row}: {field}={value!r} is not a number") from exc


def _req(row: dict[str, str], key: str, n: int) -> str:
    value = (row.get(key) or "").strip()
    if not value:
        raise LoadError(f"row {n}: required column {key!r} is empty")
    return value


def _hhmm(value: str, field: str, n: int) -> time:
    try:
        parts = [int(p) for p in value.strip().split(":")]
        return time(parts[0], parts[1])
    except (ValueError, IndexError) as exc:
        raise LoadError(f"row {n}: {field}={value!r} is not HH:MM") from exc


def attempt_id_for(collection_date: date, source_id: str, travel_date: date, window: str) -> str:
    return f"att-{collection_date:%Y%m%d}-{window}-{source_id}-{travel_date:%Y%m%d}"


def load_windows(window_id: str) -> dict[str, object]:
    spec = yaml.safe_load(WINDOWS.read_text(encoding="utf-8"))
    for w in spec["windows"]:
        if w["id"] == window_id:
            return dict(w)
    raise LoadError(f"window {window_id!r} is not declared in {WINDOWS.name}")


def build_run(
    args: argparse.Namespace, window: dict[str, object], started: datetime
) -> CollectionRun:
    d: date = args.date
    start = datetime.combine(d, _hhmm(str(window["start"]), "window.start", 0))
    end = datetime.combine(d, _hhmm(str(window["end"]), "window.end", 0))
    return CollectionRun(
        run_id=f"run-{d:%Y%m%d}-{window['id']}",
        collection_date=d,
        started_ts=started,
        collection_window_start=start,
        collection_window_end=end,
        source_precedence_version=args.precedence,
        basket_version=args.basket,
        parser_version="manual-1.0",
        collector_version="manual",
        collector_identity=args.collector,
        protocol_version=args.protocol,
        methodology_version=args.methodology,
        frame_id=f"{FRAME_BASE}{window['frame_suffix']}",
        notes=args.notes,
    )


def read_attempts(path: Path, run: CollectionRun, window_id: str) -> list[dict[str, object]]:
    """Parse the attempt sheet into field dicts, **not** yet into dataclasses.

    ``CollectionAttempt`` rejects a SUCCESS carrying zero quotes at
    construction, and the quote count is not known until the fare sheet has been
    read and reconciled against it. Constructing here would mean either writing
    the count the human typed — reconciling the store against a number the human
    also supplied — or suppressing the validation that makes the record worth
    having. So the rows stay inert until the counts are real.
    """
    out: list[dict[str, object]] = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        for n, row in enumerate(csv.DictReader(f), start=2):
            if not any((v or "").strip() for v in row.values()):
                continue
            travel = date.fromisoformat(_req(row, "travel_date", n))
            source_id = _req(row, "source_id", n)
            outcome_raw = _req(row, "outcome", n).upper()
            try:
                outcome = CollectionOutcome(outcome_raw)
            except ValueError as exc:
                raise LoadError(
                    f"row {n}: outcome {outcome_raw!r} is not one of "
                    f"{[o.value for o in CollectionOutcome]}"
                ) from exc
            out.append(
                {
                    "attempt_id": attempt_id_for(run.collection_date, source_id, travel, window_id),
                    "run_id": run.run_id,
                    "collection_date": run.collection_date,
                    "attempt_ts": datetime.combine(
                        run.collection_date, _hhmm(_req(row, "time_ist", n), "time_ist", n)
                    ),
                    "source_id": source_id,
                    "channel": Channel.AIRLINE_DIRECT,
                    "source_type": SourceType.LIVE_SCRAPE,
                    "origin": _req(row, "origin", n),
                    "destination": _req(row, "destination", n),
                    "travel_date": travel,
                    "outcome": outcome,
                    "source_group": (row.get("source_group") or "").strip() or None,
                    "detail": (row.get("notes") or "").strip(),
                }
            )
    return out


def read_fares(
    path: Path, run: CollectionRun, window_id: str
) -> tuple[list[tuple[Observation, str]], list[tuple[UnpricedFlight, str]]]:
    """Split the fare sheet into priced observations and unpriced flights.

    A sold-out flight is not a cheap observation. It has no fare, it cannot be
    given one, and it goes to its own table (spec D.6).
    """
    out: list[tuple[Observation, str]] = []
    unpriced: list[tuple[UnpricedFlight, str]] = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        for n, row in enumerate(csv.DictReader(f), start=2):
            if not any((v or "").strip() for v in row.values()):
                continue
            availability = Availability((row.get("availability") or "AVAILABLE").strip().upper())
            fare = _money(row.get("payable_fare", ""), "payable_fare", n)
            if availability is Availability.AVAILABLE and fare is None:
                raise LoadError(
                    f"row {n}: an AVAILABLE flight needs a payable_fare. If no seat could be "
                    "bought at any price it is SOLD_OUT (spec D.6) — a disappeared item, not "
                    "a missing price"
                )
            if availability is Availability.SOLD_OUT and fare is not None:
                raise LoadError(
                    f"row {n}: SOLD_OUT carries no payable_fare. If a price was displayed, "
                    "a seat was purchasable and the row is AVAILABLE"
                )

            travel = date.fromisoformat(_req(row, "travel_date", n))
            source_id = _req(row, "source_id", n)
            carrier = _req(row, "carrier", n)
            flight = _req(row, "flight_number", n)
            if not flight.isdigit():
                raise LoadError(
                    f"row {n}: flight_number={flight!r} must be digits only — '2045', "
                    "never '6E2045' (spec A.2)"
                )
            dep = _hhmm(_req(row, "departure_time", n), "departure_time", n)
            fare_class_row = _req(row, "fare_family_raw", n)
            attempt_id = attempt_id_for(run.collection_date, source_id, travel, window_id)
            seen_at = datetime.combine(
                run.collection_date, _hhmm(_req(row, "time_ist", n), "time_ist", n)
            )

            if availability is Availability.SOLD_OUT:
                unpriced.append(
                    (
                        UnpricedFlight(
                            unpriced_id=(
                                f"{run.collection_date:%Y%m%d}-{window_id}-{source_id}"
                                f"-{carrier}{flight}-{travel:%Y%m%d}-{fare_class_row}"
                            ),
                            run_id=run.run_id,
                            attempt_id=attempt_id,
                            collection_date=run.collection_date,
                            origin=_req(row, "origin", n),
                            destination=_req(row, "destination", n),
                            travel_date=travel,
                            carrier=carrier,
                            flight_number=flight,
                            departure_time_local=dep,
                            observation_ts=seen_at,
                            source_id=source_id,
                            availability=availability,
                            detail=(row.get("notes") or "").strip(),
                        ),
                        attempt_id,
                    )
                )
                continue

            assert fare is not None  # narrowed: AVAILABLE without a fare raised above
            obs = Observation(
                observation_id=(
                    f"{run.collection_date:%Y%m%d}-{window_id}-{source_id}-{carrier}{flight}"
                    f"-{travel:%Y%m%d}-{fare_class_row}"
                ),
                origin=_req(row, "origin", n),
                destination=_req(row, "destination", n),
                travel_date=travel,
                departure_time_local=dep,
                observation_ts=seen_at,
                collection_date=run.collection_date,
                carrier=carrier,
                flight_number=flight,
                stops=int(_req(row, "stops", n)),
                duration_minutes=int(_req(row, "duration_minutes", n)),
                fare_family_raw=fare_class_row,
                channel=Channel.AIRLINE_DIRECT,
                source_id=source_id,
                entitlements=Entitlements(
                    checked_baggage_kg=int(_req(row, "checked_baggage_kg", n)),
                    change_permitted=ChangePolicy(_req(row, "change_permitted", n).upper()),
                    cancellation_permitted=ChangePolicy(
                        _req(row, "cancellation_permitted", n).upper()
                    ),
                ),
                payable_fare=fare,
                source_type=SourceType.LIVE_SCRAPE,
                availability=availability,
                source_group=(row.get("source_group") or "").strip() or None,
                fare_breakdown=FareBreakdown(
                    base_fare=_money(row.get("base_fare", ""), "base_fare", n),
                    taxes=_money(row.get("taxes", ""), "taxes", n),
                    fees=_money(row.get("fees", ""), "fees", n),
                    user_development_fee=_money(
                        row.get("user_development_fee", ""), "user_development_fee", n
                    ),
                ),
            )
            out.append((obs, attempt_id))
    return out, unpriced


def load_day(args: argparse.Namespace) -> dict[str, object]:
    window = load_windows(args.window)
    started = datetime.now() if args.started is None else args.started
    run = build_run(args, window, started)

    # Parse and validate EVERYTHING before opening the store. A day is loaded
    # whole or not at all: a half-loaded day is worse than an unloaded one,
    # because it looks complete.
    attempts = read_attempts(Path(args.attempts), run, args.window)
    fares, unpriced = read_fares(Path(args.fares), run, args.window)

    known = {str(a["attempt_id"]) for a in attempts}
    for _, aid in [*fares, *unpriced]:
        if aid not in known:
            raise LoadError(
                f"a fare row references attempt {aid}, which is not in "
                f"{Path(args.attempts).name}. Every row must belong to a recorded attempt — "
                "that link is what makes coverage measurable"
            )

    by_attempt: dict[str, list[Observation]] = {}
    for obs, aid in fares:
        by_attempt.setdefault(aid, []).append(obs)

    # The count written to the store is derived from the observations actually
    # parsed, never from a column the collector filled in. verify() then
    # compares that claim against what was stored — a check that means nothing
    # if both sides come from the same typed number.
    reconciled: list[CollectionAttempt] = []
    for fields in attempts:
        aid = str(fields["attempt_id"])
        outcome = fields["outcome"]
        assert isinstance(outcome, CollectionOutcome)
        produced = by_attempt.get(aid, [])
        if outcome is CollectionOutcome.SUCCESS and not produced:
            raise LoadError(
                f"attempt {aid} is SUCCESS but no fares reference it. An attempt that ran "
                "cleanly and found nothing is NO_FLIGHT, STRUCTURAL_MISSING or "
                "TECHNICAL_FAILURE depending on why (spec H.1)"
            )
        if outcome is not CollectionOutcome.SUCCESS and produced:
            raise LoadError(
                f"attempt {aid} is {outcome.value} but {len(produced)} fares reference it. "
                "A non-SUCCESS attempt produced no usable fare by definition"
            )
        reconciled.append(
            CollectionAttempt(
                **{  # type: ignore[arg-type]
                    **fields,
                    "quotes_parsed": len(produced),
                    "observation_ids": tuple(sorted(o.observation_id for o in produced)),
                }
            )
        )

    # Resolve every screenshot to exactly one attempt, still before any write.
    # Doing this inside the store block would leave a run and its attempts
    # committed with the observations missing — the half-loaded day the
    # validate-first ordering exists to prevent.
    pending: list[tuple[Path, str]] = []
    if args.artifacts:
        for path in sorted(Path(args.artifacts).iterdir()):
            if not path.is_file():
                continue
            matches = [
                a.attempt_id for a in reconciled if a.travel_date.strftime("%Y%m%d") in path.name
            ]
            if len(matches) != 1:
                # Never guess. A screenshot is the evidence that the typed
                # numbers were the numbers on screen, and one filed against the
                # wrong attempt is worse than none at all: it makes a false
                # provenance claim that looks checkable.
                raise LoadError(
                    f"artifact {path.name!r} matches {len(matches)} attempts; it must match "
                    "exactly one. Name it {YYYYMMDD}-{window}-{travel_date}.png, using a "
                    "travel date that appears in the attempt sheet"
                )
            pending.append((path, matches[0]))

    store: CollectionStore = open_store(Path(args.store))
    try:
        store.record_run(run)
        for a in reconciled:
            store.record_attempt(a)

        artifacts: dict[str, str] = {}
        for path, attempt_id in pending:
            ref = store.artifacts.put(
                path.read_bytes(),
                content_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                source_id="indigo-direct",
                run_id=run.run_id,
                attempt_id=attempt_id,
                captured_ts=started,
            )
            store.record_artifact(ref)
            artifacts[attempt_id] = ref.sha256

        for aid, observations in sorted(by_attempt.items()):
            for obs in observations:
                store.record_observation(
                    obs, run_id=run.run_id, attempt_id=aid, artifact_sha256=artifacts.get(aid)
                )
        for flight, _aid in unpriced:
            store.record_unpriced_flight(flight)
        return summarise(store, run.collection_date)
    finally:
        store.close()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--store", required=True, help="store root directory")
    p.add_argument("--date", required=True, type=date.fromisoformat, help="collection date")
    p.add_argument("--window", default="primary", help="window id from collection-windows.yaml")
    p.add_argument("--collector", required=True, help="who performed the run (a person)")
    p.add_argument("--fares", required=True)
    p.add_argument("--attempts", required=True)
    p.add_argument("--artifacts", default=None, help="directory of screenshots/pages")
    p.add_argument("--precedence", default="spike-single-source-v1")
    p.add_argument("--basket", default="2026-Q3")
    p.add_argument("--protocol", default="acquisition-protocol-2G")
    p.add_argument("--methodology", default="2.1")
    p.add_argument("--notes", default="")
    p.add_argument("--started", default=None, type=datetime.fromisoformat)
    args = p.parse_args(argv)

    try:
        report = load_day(args)
    except LoadError as exc:
        print(f"LOAD FAILED — nothing was written.\n  {exc}", file=sys.stderr)
        return 1

    print(json.dumps(report, indent=2))
    if report["integrity_problems"]:
        print("\nINTEGRITY PROBLEMS — investigate before the next run.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
