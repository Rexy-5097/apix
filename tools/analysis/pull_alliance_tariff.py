"""Pull Alliance Air's published domestic tariff sheet — a REFERENCE source.

Source: Alliance Air Aviation Limited, "Domestic Fares and Penalties", published
at allianceair.in/tariffsheet as a dated PDF.

**ROLE: REFERENCE ONLY. THIS IS NOT AN AIRFARE OBSERVATION AND CANNOT BECOME ONE.**

A tariff sheet is a *declared fare structure* — basic-fare levels per sector, plus
the taxes and charges that apply. It is not a quote. It carries no flight number,
no departure time, no travel date and no advance-purchase window, so it cannot be
assigned to an APW bucket (spec A.3), cannot be banded (spec B.2.2), and cannot
form a cell key. The source register's own vocabulary rates "declared tariff
categories" INADMISSIBLE, and spec A.1 requires a displayed, transactable offer.

So this module deliberately lives OUTSIDE ``src/apix/``. The statistics layer
imports from ``apix.*``; code that is not in ``apix.*`` cannot be imported by it.
``tests/test_reference_tariff.py`` asserts that boundary rather than trusting it.

What this IS good for:

  * the published tax/fee/charge structure, which bears on **AMB-11** (whether
    ``user_development_fee`` takes departure UDF only, or departure + arrival);
  * a cross-check on the base/tax decomposition of manually collected fares;
  * evidence that automated acquisition from an official source works end to end.

Two honest limits, both recorded in the output rather than papered over:

  * **Table 2, the station-level fee grid, is NOT machine-extractable from this
    document.** Its text layer interleaves adjacent rows at character level, so
    the station-to-fee mapping cannot be recovered. Three strategies were tried;
    see ``STATION_FEES_UNEXTRACTABLE``. Guessing which column a number belongs to
    would be fabrication, so nothing is emitted.
  * Table 1 rows are emitted with a ``suspect`` flag rather than silently
    dropped when they fail a structural check.

Usage::

    python tools/analysis/pull_alliance_tariff.py            # fetch + parse + write
    python tools/analysis/pull_alliance_tariff.py --offline   # re-parse a cached PDF

Requires the ``reference`` extra for the fetch/extract path (``pip install -e
".[reference]"``). The parse functions below are pure and standard-library only,
which is why the tests exercise them without any PDF dependency.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data" / "reference" / "alliance_air_tariff.json"
CACHE = REPO / "data" / "reference" / ".cache" / "alliance_air_tariff.pdf"

#: Published landing page. The PDF URL is versioned and changes with each revision.
LANDING_PAGE = "https://www.allianceair.in/tariffsheet"
PDF_URL = (
    "https://plone.allianceair.in/allianceair/en/assets/"
    "tariff-sheet/alliance-air-domestic-tariff-sheet-01sep26.pdf"
)
USER_AGENT = (
    "APIx-reference-fetch/1.0 (MoSPI PS26056 airfare index research; github.com/Rexy-5097/apix)"
)

#: Spec A.3 / B.2 fields a tariff sheet structurally cannot supply. Asserted absent.
OBSERVATION_FIELDS_ABSENT: tuple[str, ...] = (
    "flight_number",
    "departure_time_local",
    "travel_date",
    "collection_date",
    "apw_bucket",
    "departure_band",
    "payable_fare",
    "fare_family_raw",
    "observation_id",
)

#: Why Table 2 emits no rows. Recorded in the output so the gap is visible.
STATION_FEES_UNEXTRACTABLE = {
    "status": "NOT_MACHINE_EXTRACTABLE",
    "table": "Table 2: Domestic Taxes / Fees / Charges Applicable",
    "columns_named_in_document": [
        "Development Fee",
        "CUTE Fee",
        "User Development Fee",
        "Passenger Service Fee (PSF)",
        "Aviation Security Fee",
        "Goods and Services Tax",
    ],
    "reason": (
        "The document's text layer interleaves adjacent table rows at character level "
        "-- the glyphs of two different station names occupy nearly identical x and y "
        "coordinates -- so no station-to-fee mapping can be recovered. Emitting one "
        "would mean guessing which column a number belongs to, which spec A.4 forbids "
        "('components only where displayed; blank is None, never 0')."
    ),
    "methods_tried": [
        "pypdf extract_text(): emits fee values on separate lines from their station, "
        "in an order that does not correspond to the station column",
        "pdfplumber extract_tables(): returns 2 rows of character-interleaved cells; "
        "the table has no ruling lines",
        "pdfplumber extract_words() clustered by rounded y then sorted by x: adjacent "
        "rows share coordinates, so clusters mix two stations",
    ],
    "consequence": "No station-level fee figure is published by this adapter.",
    "how_to_close": (
        "Read the figures off the PDF by eye and record them as a hand-verified table "
        "with its own provenance, exactly as the 2026-09-12 manual panel was recorded. "
        "Do not infer them."
    ),
}

_ROW = re.compile(r"^(\d{1,3})\s+(.+?)\s+(Direct / Via|Direct|Via)\s+(.+)$")
_CELL = re.compile(r"\d+\s*/\s*\d+|\d+|NA|-")
_EFFECTIVE = re.compile(r"Updated as on\s*([0-9]{2}[A-Z]{3}[0-9]{2})", re.IGNORECASE)
#: A prose remark: at least three words of three-plus letters. Excludes numeric debris.
_PROSE = re.compile(r"(?:\b[A-Za-z]{3,}\b.*){3,}")

#: The document declares eighteen fare levels. More than that means the row was
#: not read cleanly, so it is flagged rather than trusted.
MAX_FARE_LEVELS = 18


def sha256_of(path: Path) -> str:
    """Hex SHA-256 of a file, read in chunks."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(url: str, dest: Path) -> dict[str, Any]:
    """Retrieve one document and record the HTTP metadata.

    Uses ``curl`` for the same reason ``pull_mospi_benchmark.py`` does: the URL and
    headers are fixed constants, so nothing here is shell-interpolated. A single
    request, with an identifying user agent, and no retry -- a refusal is an
    outcome, not an obstacle (collection-control-contract C-0).
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    out = subprocess.run(
        [
            "curl",
            "-sS",
            "--max-time",
            "60",
            "-A",
            USER_AGENT,
            "-o",
            str(dest),
            "-w",
            "%{http_code}\t%{content_type}\t%{size_download}",
            url,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    retrieved_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    parts = out.stdout.strip().split("\t")
    status = int(parts[0]) if parts and parts[0].isdigit() else None
    return {
        "url": url,
        "landing_page": LANDING_PAGE,
        "retrieved_at_utc": retrieved_at,
        "http_status": status,
        "content_type": parts[1] if len(parts) > 1 else None,
        "content_length": int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None,
        "user_agent": USER_AGENT,
        "curl_stderr": out.stderr.strip() or None,
    }


def extract_pages(pdf_path: Path) -> list[str]:
    """Text of each page. Needs the ``reference`` extra."""
    try:
        from pypdf import PdfReader
    except ImportError:  # pragma: no cover - exercised only without the extra
        sys.exit(
            "pypdf is required to extract this document. "
            'Install the reference extra:  pip install -e ".[reference]"'
        )
    return [(page.extract_text() or "") for page in PdfReader(str(pdf_path)).pages]


def parse_fare_cell(token: str) -> int | list[int] | None:
    """One Table 1 cell.

    ``-`` and ``NA`` are **None**, never 0 -- an absent fare level is not a free
    fare. ``a / b`` keeps **both** values: the document publishes two figures for
    some sectors and choosing one would be a silent editorial decision.
    """
    token = token.strip()
    if token in {"-", "NA"}:
        return None
    if "/" in token:
        return [int(part) for part in re.split(r"\s*/\s*", token)]
    return int(token)


def split_sector(sector_raw: str) -> tuple[str | None, str | None]:
    """Origin and destination, only when unambiguous.

    The document's "Routing" column is one field. Splitting it needs a station
    list, so a two-token sector splits and anything else returns ``(None, None)``
    rather than a guess.
    """
    tokens = sector_raw.split()
    if len(tokens) == 2:
        return tokens[0], tokens[1]
    return None, None


def parse_basic_fares(lines: list[str]) -> dict[str, Any]:
    """Table 1 -- per-sector basic fares across the declared fare levels.

    Every numbered line that does not match is kept in ``unparsed``. A row is
    ``suspect`` when it exceeds ``MAX_FARE_LEVELS`` or when its fare levels are not
    non-decreasing; non-decreasing order is the structural check that the columns
    were read in the right order.
    """
    rows: list[dict[str, Any]] = []
    unparsed: list[str] = []
    for raw_line in lines:
        line = raw_line.strip()
        match = _ROW.match(line)
        if match is None:
            if re.match(r"^\d{1,3}\s+\S", line):
                unparsed.append(line)
            continue
        levels = [parse_fare_cell(tok) for tok in _CELL.findall(match.group(4))]
        present = [v[0] if isinstance(v, list) else v for v in levels if v is not None]
        sector_raw = match.group(2).strip()
        origin, destination = split_sector(sector_raw)
        reasons = []
        if len(levels) > MAX_FARE_LEVELS:
            reasons.append(f"{len(levels)} cells exceeds the {MAX_FARE_LEVELS} declared levels")
        if present != sorted(present):
            reasons.append("fare levels are not non-decreasing")
        rows.append(
            {
                "serial": int(match.group(1)),
                "sector_raw": sector_raw,
                "origin": origin,
                "destination": destination,
                "routing": match.group(3),
                "fare_levels": levels,
                "level_count": len(levels),
                "suspect": bool(reasons),
                "suspect_reasons": reasons,
            }
        )
    return {
        "unit": "INR, basic fare per one-way sector, economy class",
        "declared_fare_levels": MAX_FARE_LEVELS,
        "row_count": len(rows),
        "suspect_row_count": sum(1 for r in rows if r["suspect"]),
        "unparsed_numbered_lines": unparsed,
        "rows": rows,
    }


def parse_remarks(pages: list[str]) -> list[str]:
    """Verbatim prose remarks, de-duplicated in document order.

    Kept verbatim because the remarks carry the fee rules -- and the AMB-11
    evidence -- and paraphrasing a published rule would destroy its value.
    """
    seen: set[str] = set()
    remarks: list[str] = []
    for page in pages[1:]:
        for raw_line in page.split("\n"):
            line = " ".join(raw_line.split())
            if len(line) < 25 or line in seen or not _PROSE.search(line):
                continue
            seen.add(line)
            remarks.append(line)
    return remarks


def find_effective_date(pages: list[str]) -> str | None:
    """The document's own effective date, e.g. ``01SEP26``. None if unstated."""
    for page in pages:
        match = _EFFECTIVE.search(page)
        if match:
            return match.group(1).upper()
    return None


def amb11_evidence(remarks: list[str]) -> dict[str, Any]:
    """Remarks bearing on AMB-11 -- arrival versus departure UDF.

    Quoted, never summarised, and explicitly **not** a resolution: AMB-11 is an
    owner ruling and one carrier's tariff sheet is evidence toward it, not a
    decision on it.
    """
    quotes = [r for r in remarks if re.search(r"\bUDF\b|Development Fee", r, re.IGNORECASE)]
    # Station codes are read ONLY from a remark that actually states the arrival-UDF
    # rule. Harvesting every three-letter parenthetical across all fee remarks pulls
    # in fee abbreviations -- the column header yields "(PSF)" -- and a fee acronym
    # presented as an airport would be a fabricated finding.
    arrival_rule = [r for r in quotes if re.search(r"Arrival\s+UDF", r, re.IGNORECASE)]
    stations = sorted({m.upper() for r in arrival_rule for m in re.findall(r"\(([A-Z]{3})\)", r)})
    return {
        "ambiguity": "AMB-11",
        "question": (
            "Does user_development_fee take departure UDF only, or departure + arrival? "
            "Spec A.4's four-way split does not anticipate two UDF lines."
        ),
        "quotes": quotes,
        "arrival_rule_quotes": arrival_rule,
        "arrival_udf_stations_named": stations,
        "bearing": (
            "The document states arrival UDF is charged at the named stations, which is "
            "positive evidence that UDF is NOT departure-only at those airports. DEL and "
            "BOM are both endpoints of the APIx pilot route."
        ),
        "resolves_amb11": False,
        "why_not": (
            "One carrier's published tariff sheet is evidence about that carrier. AMB-11 "
            "is a methodology ruling owned by @Rexy-5097 and cannot be closed by an "
            "adapter. It also says nothing about how any OTHER carrier renders the fee, "
            "nor about what a results page displays, which is what spec A.4 governs."
        ),
    }


def build_record(provenance: dict[str, Any], pages: list[str], sha256: str) -> dict[str, Any]:
    """Assemble the reference record. Declares its own inadmissibility."""
    remarks = parse_remarks(pages)
    return {
        "reference_id": "alliance_air_domestic_tariff",
        "role": "REFERENCE_ONLY",
        "is_apix_input": False,
        "data_class": "DECLARED_TARIFF",
        "admissibility": "INADMISSIBLE",
        "admissibility_basis": (
            "A declared tariff structure, not a displayed transactable offer (spec A.1). "
            "It carries no flight, departure time, travel date or advance-purchase window, "
            "so it cannot be assigned an APW bucket (A.3), banded (B.2.2) or keyed to a "
            "cell. The source register rates declared tariff categories INADMISSIBLE."
        ),
        "must_never": [
            "become an Observation or an UnpricedFlight",
            "enter an APW cell or a departure band",
            "contribute to a price relative, a Jevons index or any aggregate",
            "be written to the primary collection store or any @primary run",
            "be presented as an airfare observation or as a fare a traveller paid",
        ],
        "observation_fields_absent": list(OBSERVATION_FIELDS_ABSENT),
        "publisher": "Alliance Air Aviation Limited",
        "document_title": "Domestic Fares and Penalties (Tariff Sheet)",
        "effective_date_declared": find_effective_date(pages),
        "page_count": len(pages),
        "provenance": {**provenance, "sha256": sha256},
        "basic_fares": parse_basic_fares(pages[0].split("\n") if pages else []),
        "station_fees": STATION_FEES_UNEXTRACTABLE,
        "remarks_verbatim": remarks,
        "amb11_evidence": amb11_evidence(remarks),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="re-parse the cached PDF instead of retrieving it",
    )
    args = parser.parse_args(argv)

    if args.offline:
        if not CACHE.exists():
            print(f"no cached document at {CACHE}; run without --offline first")
            return 1
        provenance: dict[str, Any] = {
            "url": PDF_URL,
            "landing_page": LANDING_PAGE,
            "retrieved_at_utc": None,
            "note": "re-parsed from cache; retrieval metadata not re-established",
        }
    else:
        provenance = fetch(PDF_URL, CACHE)
        if provenance["http_status"] != 200:
            print(f"retrieval failed: HTTP {provenance['http_status']} — nothing written")
            return 1

    record = build_record(provenance, extract_pages(CACHE), sha256_of(CACHE))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")

    fares = record["basic_fares"]
    print(f"effective date : {record['effective_date_declared']}")
    print(f"sha256         : {record['provenance']['sha256']}")
    print(f"sectors parsed : {fares['row_count']} ({fares['suspect_row_count']} suspect)")
    print(f"unparsed lines : {len(fares['unparsed_numbered_lines'])}")
    print(f"remarks        : {len(record['remarks_verbatim'])}")
    print(f"station fees   : {record['station_fees']['status']}")
    print(f"AMB-11 stations: {record['amb11_evidence']['arrival_udf_stations_named']}")
    print(f"written        : {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
