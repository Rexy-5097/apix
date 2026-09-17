"""CSV and JSON export writers.

Column orders are declared as tuples and asserted by tests, because a consumer
that parses by position breaks silently when a column moves. Absent values are
empty strings in CSV and ``null`` in JSON -- never ``0``.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from apix.api import payloads
from apix.series import Frequency

REPO = Path(__file__).resolve().parents[3]
OUT_DIR = REPO / "data" / "exports"

OBSERVATION_COLUMNS: tuple[str, ...] = (
    "observation_id",
    "collection_date",
    "travel_date",
    "apw",
    "band",
    "route",
    "carrier",
    "flight",
    "dep",
    "fare_family",
    "fare_class",
    "total",
    "base_fare",
    "taxes",
    "user_development_fee",
    "fees",
    "currency",
    "evidence",
    "run_id",
    "source_id",
    "channel",
    "data_class",
)

SERIES_COLUMNS: tuple[str, ...] = (
    "output_class",
    "frequency",
    "period",
    "period_start",
    "period_end",
    "level",
    "change_pct",
    "effective_n",
    "coverage_note",
)

SOURCE_COLUMNS: tuple[str, ...] = (
    "source_id",
    "channel",
    "automation_gate",
    "data_admissibility",
    "data_rights",
    "robots_status",
    "tos_status",
    "operational_status",
    "evidence_date",
)

ROUTE_COLUMNS: tuple[str, ...] = (
    "basket_version",
    "basket_status",
    "is_publication_grade",
    "route_id",
    "origin",
    "destination",
    "weight_normalised",
    "weight_source",
    "effective_date",
    "observations_held",
)

PROVENANCE_COLUMNS: tuple[str, ...] = (
    "observation_id",
    "evidence_class",
    "run_id",
    "collector",
    "methodology_version",
    "parser_version",
    "protocol_version",
    "source_precedence_version",
)


def _csv(columns: tuple[str, ...], rows: list[dict[str, Any]]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({c: ("" if r.get(c) is None else r.get(c)) for c in columns})
    return buf.getvalue()


def observations_csv() -> str:
    p = payloads.panel()
    rows = []
    for o in p["observations"]:
        row = dict(o)
        row.setdefault("route", "-".join(p["frame"]["routes"][0].split("-")))
        row.setdefault("carrier", p["frame"]["carriers"][0])
        row.setdefault("channel", p["frame"]["channel"])
        row.setdefault("currency", "INR")
        row.setdefault("data_class", p["data_class"])
        row.setdefault("collection_date", p["collection_date"])
        rows.append(row)
    return _csv(OBSERVATION_COLUMNS, rows)


def series_csv(frequency: Frequency, *, demo: bool) -> str:
    payload = payloads.index(frequency, demo=demo)
    rows = [{"output_class": payload["output_class"], **pt} for pt in payload["data"]["series"]]
    return _csv(SERIES_COLUMNS, rows)


def sources_csv() -> str:
    return _csv(SOURCE_COLUMNS, payloads.sources()["data"]["sources"])


def route_weights_csv() -> str:
    rows = []
    for b in payloads.routes()["data"]["baskets"]:
        for r in b["routes"]:
            rows.append(
                {
                    "basket_version": b["basket_version"],
                    "basket_status": b["status"],
                    "is_publication_grade": b["is_publication_grade"],
                    **r,
                }
            )
    return _csv(ROUTE_COLUMNS, rows)


def provenance_csv() -> str:
    p = payloads.panel()
    runs = {r["run_id"]: r for r in p["runs"]}
    rows = []
    for o in p["observations"]:
        run = runs.get(o.get("run_id"), {})
        rows.append(
            {
                "observation_id": o["observation_id"],
                "evidence_class": o.get("evidence"),
                "run_id": o.get("run_id"),
                "collector": run.get("collector"),
                "methodology_version": run.get("methodology_version"),
                "parser_version": run.get("parser_version"),
                "protocol_version": run.get("protocol_version"),
                "source_precedence_version": run.get("source_precedence_version"),
            }
        )
    return _csv(PROVENANCE_COLUMNS, rows)


#: Every file the export writes, in order. Names are the contract.
EXPORTS: tuple[str, ...] = (
    "observations.csv",
    "observations.json",
    "index_daily_demo.csv",
    "index_weekly_demo.csv",
    "index_monthly_demo.csv",
    "index_daily.json",
    "index_weekly.json",
    "index_monthly.json",
    "sources.csv",
    "sources.json",
    "route_weights.csv",
    "routes.json",
    "provenance.csv",
    "coverage.json",
    "lead_time.json",
    "backtest.json",
    "README.md",
)

_README = """# data/exports/ — generated, never hand-edited

Regenerate: `python -m apix.export`

Every JSON file is the API envelope verbatim, including `output_class`
(PRODUCTION / RESEARCH / DEMO) and `publication_status`. Every CSV has a fixed
column order asserted by `tests/test_exports.py`.

| File | Class | What it is |
|---|---|---|
| observations.csv / .json | RESEARCH | The 35 real observations, manual collection, @primary |
| index_*_demo.csv | **DEMO** | Period series from the SYNTHETIC fixture. Not a measurement |
| index_*.json | RESEARCH | The real panel's index endpoint: empty series + readiness verdict |
| sources.csv / .json | — | The 30-source compliance register with operational status |
| route_weights.csv / routes.json | — | Provisional and demo baskets. None publication grade |
| provenance.csv | — | Observation → run → collector → parser → methodology |
| coverage.json | — | Plan completion, AMB-8 blocker, scheduled-run refusals |
| lead_time.json | RESEARCH | Descriptive APW profile with the confound. Not an elasticity |
| backtest.json | — | INCOMPLETE: DGCA fare benchmark not located |

**No file here contains a production index value.** None exists.
"""


def write_all(out_dir: Path = OUT_DIR) -> list[Path]:
    """Write every export. Returns the paths written, in EXPORTS order."""
    out_dir.mkdir(parents=True, exist_ok=True)
    text: dict[str, str] = {
        "observations.csv": observations_csv(),
        "observations.json": json.dumps(payloads.observations(), indent=1, default=str),
        "index_daily_demo.csv": series_csv(Frequency.DAILY, demo=True),
        "index_weekly_demo.csv": series_csv(Frequency.WEEKLY, demo=True),
        "index_monthly_demo.csv": series_csv(Frequency.MONTHLY, demo=True),
        "index_daily.json": json.dumps(payloads.index(Frequency.DAILY), indent=1, default=str),
        "index_weekly.json": json.dumps(payloads.index(Frequency.WEEKLY), indent=1, default=str),
        "index_monthly.json": json.dumps(payloads.index(Frequency.MONTHLY), indent=1, default=str),
        "sources.csv": sources_csv(),
        "sources.json": json.dumps(payloads.sources(), indent=1, default=str),
        "route_weights.csv": route_weights_csv(),
        "routes.json": json.dumps(payloads.routes(), indent=1, default=str),
        "provenance.csv": provenance_csv(),
        "coverage.json": json.dumps(payloads.coverage(), indent=1, default=str),
        "lead_time.json": json.dumps(payloads.lead_time(), indent=1, default=str),
        "backtest.json": json.dumps(payloads.backtest(), indent=1, default=str),
        "README.md": _README,
    }
    written = []
    for name in EXPORTS:
        path = out_dir / name
        path.write_text(text[name] + ("" if text[name].endswith("\n") else "\n"), encoding="utf-8")
        written.append(path)
    return written


def main() -> int:
    for p in write_all():
        print(f"  {p.relative_to(REPO)}")
    return 0


__all__ = [
    "EXPORTS",
    "OBSERVATION_COLUMNS",
    "PROVENANCE_COLUMNS",
    "ROUTE_COLUMNS",
    "SERIES_COLUMNS",
    "SOURCE_COLUMNS",
    "observations_csv",
    "provenance_csv",
    "route_weights_csv",
    "series_csv",
    "sources_csv",
    "write_all",
]
