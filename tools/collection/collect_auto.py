"""Run the automated collector -- fixture mode, or live mode behind the compliance gate.

    # FIXTURE: replays SYNTHETIC page payloads. No request is made to any site.
    python tools/collection/collect_auto.py --mode fixture \\
        --fixture tests/fixtures/indigo/extract_2026-09-15.json \\
        --collection-date 2026-09-15 --travel-date 2026-09-22

    python tools/collection/collect_auto.py --mode fixture \\
        --fixture tests/fixtures/indigo/extract_2026-09-15.json \\
        --collection-date 2026-09-15 --apw 1,3,7,15,30,45,60

    # LIVE: evaluated against source_registry/registry.yaml BEFORE anything else.
    # Refused today -- IndiGo is AUTOMATION_PROHIBITED -- and nothing is requested.
    python tools/collection/collect_auto.py --mode live --apw 7

    # INDIGO NDC (official API). Sandbox needs the register entry indigo_ndc and keys
    # issued by IndiGo's developer registration, in INDIGO_NDC_* environment variables.
    # Exits 5 today: the official request model is unconfirmed, so nothing is sent.
    python tools/collection/collect_auto.py --source indigo-ndc --mode sandbox \\
        --collection-date 2026-09-15 --travel-date 2026-09-22 --apw 7

The collector writes into its own store (default ``data/collection-automated/``,
gitignored), never into the manual study's ``data/collection/``, and its runs are
labelled ``@fixture`` / ``@automated-trial`` so they are never index input.

After the run it feeds the stored observations through the existing
``filter_admissible`` and ``CollectionStore.verify`` and prints the result. It
does not compute an index.

Exit codes: ``0`` clean -- ``1`` configuration error -- ``2`` integrity problems
or not loaded -- ``3`` refused by the compliance gate (nothing requested, nothing
written) -- ``4`` stopped by an access challenge -- ``5`` blocked pending official
source documentation (nothing requested, nothing written).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import date, time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from apix.ingestion.collectors.adapter import SourceAdapter
from apix.ingestion.collectors.contract import (
    CollectionConfig,
    CollectionContract,
    ConfigError,
    band_window,
    ist_now,
    parse_apw,
    validate_travel_date_apw,
)
from apix.ingestion.collectors.gate import (
    CollectionMode,
    evaluate_live_gate,
    evaluate_sandbox_gate,
    find_source,
)
from apix.ingestion.collectors.indigo.fixture import FixtureError, FixtureIndigoAdapter
from apix.ingestion.collectors.runner import COLLECTOR_VERSION, RunReport, run_collection
from apix.ingestion.store import open_store
from apix.statistics.elementary.admissibility import CollectionWindow, filter_admissible

REPO = Path(__file__).resolve().parents[2]
REGISTRY = REPO / "source_registry" / "registry.yaml"
WINDOWS = REPO / "source_registry" / "collection-windows.yaml"
DEFAULT_STORE = REPO / "data" / "collection-automated"

#: CLI source name -> source_id in registry.yaml.
SOURCES = {"indigo": "indigo", "indigo-ndc": "indigo_ndc"}

EXIT_OK, EXIT_CONFIG, EXIT_INTEGRITY, EXIT_GATE, EXIT_STOPPED, EXIT_BLOCKED = 0, 1, 2, 3, 4, 5


def git_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return "unknown"
    return out.stdout.strip() or "unknown"


def load_window(window_id: str) -> tuple[time, time]:
    spec = yaml.safe_load(WINDOWS.read_text(encoding="utf-8"))
    for w in spec["windows"]:
        if w["id"] == window_id:
            return time.fromisoformat(str(w["start"])), time.fromisoformat(str(w["end"]))
    raise ConfigError(f"window {window_id!r} is not declared in {WINDOWS.name}")


def build_config(args: argparse.Namespace) -> CollectionConfig:
    contract = CollectionContract(origin=args.origin, destination=args.destination)
    start, end = load_window(args.window)
    common: dict[str, object] = {
        "window_id": args.window,
        "window_start": start,
        "window_end": end,
        "min_interval_seconds": args.min_interval,
    }
    source = SOURCES[args.source]
    if args.travel_date and args.apw:
        buckets = parse_apw(args.apw)
        if len(buckets) != 1:
            raise ConfigError("--travel-date takes exactly one --apw value to check it against")
        validate_travel_date_apw(args.collection_date, args.travel_date, buckets[0])
    if args.travel_date:
        return CollectionConfig(
            source, args.collection_date, (args.travel_date,), contract, **common
        )  # type: ignore[arg-type]
    return CollectionConfig.for_apw(
        source, args.collection_date, parse_apw(args.apw), contract, **common
    )


def validation_summary(report: RunReport, store_root: Path) -> dict[str, object]:
    """Feed what was stored through the EXISTING admissibility filter."""
    ids = {o.observation_id for s in report.searches for o in s.observations}
    with open_store(store_root) as store:
        stored = [
            o for o in store.observations(report.run.collection_date) if o.observation_id in ids
        ]
    window = CollectionWindow(
        report.run.collection_window_start.time(), report.run.collection_window_end.time()
    )
    result = filter_admissible(stored, window)
    reasons: dict[str, int] = {}
    for item in result.excluded:
        reasons[item.reason.value] = reasons.get(item.reason.value, 0) + 1
    return {
        "stored_observations_read_back": len(stored),
        "admissible": len(result.admissible),
        "excluded": len(result.excluded),
        "excluded_by_reason": dict(sorted(reasons.items())),
    }


def render(report: RunReport, validation: dict[str, object] | None) -> str:
    label = {
        CollectionMode.FIXTURE: "FIXTURE -- SYNTHETIC PAGES, NOT MARKET DATA, NO REQUEST MADE",
        CollectionMode.SANDBOX: "SANDBOX -- OFFICIAL API TEST ENVIRONMENT, NOT MARKET PRICES",
        CollectionMode.LIVE: "LIVE",
    }[report.mode]
    lines = [
        f"RUN      {report.run.run_id}",
        f"MODE     {label}",
        f"STATUS   {report.status}",
        f"FRAME    {report.run.frame_id}   (not index input)",
        f"VERSIONS collector {report.run.collector_version} | parser {report.run.parser_version} | "
        f"protocol {report.run.protocol_version} | methodology {report.run.methodology_version}",
        f"EVIDENCE {report.export_dir}",
        f"MANIFEST sha256 {report.manifest_sha256}",
        "",
        f"{'APW':>4}  {'travel':<10}  {'outcome':<24} exp found acc sold excl miss",
    ]
    for s in report.searches:
        c = s.counts()
        lines.append(
            f"T+{s.params.lead_time_days:<2}  {s.params.travel_date.isoformat():<10}  "
            f"{s.attempt.outcome.value:<24} {c['expected']:>3} {c['found']:>5} {c['accepted']:>3} "
            f"{c['sold_out']:>4} {c['excluded']:>4} {c['missing']:>4}"
        )
        for b in s.bands:
            if b.status == "NOT_EVALUATED":
                continue
            lines.append(
                f"        b{b.band} {band_window(b.band)} eligible={b.eligible_count} "
                f"{b.status:<9} {b.selected or '-'} {b.detail}".rstrip()
            )
        if s.attempt.outcome.value != "SUCCESS":
            lines.append(f"        {s.attempt.detail}")
    t = report.totals()
    lines += [
        f"TOTAL {t['searches']} searches: expected {t['expected']}, found {t['found']}, "
        f"accepted {t['accepted']}, sold_out {t['sold_out']}, excluded {t['excluded']}, "
        f"missing {t['missing']}",
        "",
    ]
    if not report.loaded:
        lines.append(f"NOT LOADED  {report.not_loaded_reason}")
    else:
        problems = report.integrity_problems
        lines.append(f"STORE VERIFY  {'clean' if not problems else f'{len(problems)} PROBLEMS'}")
        lines += [f"  - {p}" for p in problems[:3]]
        if len(problems) > 3:
            lines.append(f"  ... {len(problems) - 3} more of the same kind; see store.verify()")
    if validation is not None:
        lines.append(
            f"ADMISSIBILITY (existing filter_admissible)  {json.dumps(validation, sort_keys=True)}"
        )
    lines.append(
        "INDEX  not computed. Automated runs are not index input; publication guards unchanged."
    )
    return "\n".join(lines)


def run_indigo_ndc(args: argparse.Namespace) -> int:
    """IndiGo NDC: gate and credentials are checked; no request model exists yet."""
    from apix.ingestion.collectors.indigo.ndc import (
        NDC_BLOCKER,
        REQUIRED_ENV,
        CredentialError,
        NdcCredentials,
        credentials_present,
    )

    print("SOURCE: INDIGO NDC (official API channel, not the goindigo.in website)")
    print(f"MODE: {args.mode.upper()}")
    if args.mode == "fixture":
        print(
            "BLOCKED: no IndiGo NDC fixture exists. It must be derived from IndiGo's official "
            f"AirShopping schema or sample responses; {NDC_BLOCKER}.",
            file=sys.stderr,
        )
        return EXIT_BLOCKED

    registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    try:
        entry = find_source(registry, SOURCES[args.source])
    except KeyError:
        print(
            "REFUSED BY THE COMPLIANCE GATE -- nothing was requested, nothing was written.\n"
            f"  - {SOURCES[args.source]!r} is not in {REGISTRY.relative_to(REPO)}",
            file=sys.stderr,
        )
        return EXIT_GATE
    present = credentials_present(os.environ)
    decision = (
        evaluate_live_gate(entry)
        if args.mode == "live"
        else evaluate_sandbox_gate(entry, credentials_present=present)
    )
    if not decision.allowed:
        print(
            "REFUSED BY THE COMPLIANCE GATE -- nothing was requested, nothing was written.",
            file=sys.stderr,
        )
        for failure in decision.failures:
            print(f"  - {failure}", file=sys.stderr)
        if not present:
            print(f"  credentials are read only from: {', '.join(REQUIRED_ENV)}", file=sys.stderr)
        return EXIT_GATE
    try:
        creds = NdcCredentials.from_env(os.environ)
    except CredentialError as exc:
        print(f"CREDENTIAL ERROR -- nothing was requested.\n  {exc}", file=sys.stderr)
        return EXIT_CONFIG
    print(f"ENDPOINT: {creds.base_url}   CREDENTIALS: present ({creds!r})")
    print(f"BLOCKED: {NDC_BLOCKER}.", file=sys.stderr)
    return EXIT_BLOCKED


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--source", default="indigo", choices=sorted(SOURCES))
    p.add_argument("--origin", default="DEL")
    p.add_argument("--destination", default="BOM")
    p.add_argument("--travel-date", type=date.fromisoformat)
    p.add_argument(
        "--apw",
        help="comma-separated lead times from the frozen vector; with --travel-date, "
        "exactly one value, which must match it",
    )
    p.add_argument("--collection-date", type=date.fromisoformat, default=None)
    p.add_argument("--mode", required=True, choices=["fixture", "live", "sandbox"])
    p.add_argument("--fixture", type=Path, help="SYNTHETIC fixture file (fixture mode)")
    p.add_argument("--store", type=Path, default=DEFAULT_STORE)
    p.add_argument("--window", default="primary")
    p.add_argument("--min-interval", type=float, default=30.0)
    p.add_argument("--headless", action="store_true", help="live mode only")
    args = p.parse_args(argv)
    if not args.travel_date and not args.apw:
        p.error("give --travel-date, --apw, or both")
    if args.collection_date is None:
        args.collection_date = ist_now().date()

    try:
        config = build_config(args)
    except ConfigError as exc:
        print(f"CONFIG ERROR -- nothing was requested.\n  {exc}", file=sys.stderr)
        return 1
    if config.off_frame_lead_times:
        print(
            f"NOTE lead times {list(config.off_frame_lead_times)} match no frozen APW bucket; "
            "they will be collected and then excluded by spec A.3",
            file=sys.stderr,
        )

    if args.source == "indigo-ndc":
        return run_indigo_ndc(args)
    if args.mode == "sandbox":
        print(
            "SANDBOX mode applies only to official API sources such as --source indigo-ndc; "
            "the goindigo.in website has no sandbox.",
            file=sys.stderr,
        )
        return EXIT_CONFIG

    registry_entry = None
    adapter: SourceAdapter
    if args.mode == "live":
        registry_entry = find_source(
            yaml.safe_load(REGISTRY.read_text(encoding="utf-8")), args.source
        )
        decision = evaluate_live_gate(registry_entry)
        if not decision.allowed:
            print(
                "REFUSED BY THE COMPLIANCE GATE -- nothing was requested, nothing was written.",
                file=sys.stderr,
            )
            for failure in decision.failures:
                print(f"  - {failure}", file=sys.stderr)
            print(
                f"  register: {REGISTRY.relative_to(REPO)} (source {args.source!r})",
                file=sys.stderr,
            )
            return 3
        from apix.ingestion.collectors.indigo.live import AdapterUnavailable, LiveIndigoAdapter

        try:
            adapter = LiveIndigoAdapter(registry_entry, headless=args.headless)
        except AdapterUnavailable as exc:
            print(str(exc), file=sys.stderr)
            return 1
    else:
        if args.fixture is None:
            print("--fixture is required in fixture mode", file=sys.stderr)
            return 1
        try:
            adapter = FixtureIndigoAdapter(args.fixture, clock=ist_now)
        except FixtureError as exc:
            print(f"FIXTURE ERROR: {exc}", file=sys.stderr)
            return 1

    store = open_store(args.store)
    try:
        report = run_collection(
            config,
            adapter,
            store,
            export_root=Path(args.store) / "runs",
            registry_entry=registry_entry,
            clock=ist_now,
            collector_version=f"{COLLECTOR_VERSION}+{git_sha()}",
        )
    finally:
        store.close()
        adapter.close()

    validation = validation_summary(report, Path(args.store)) if report.loaded else None
    print(render(report, validation))
    if report.stopped:
        return 4
    if not report.loaded or report.integrity_problems:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
