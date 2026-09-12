"""Parse the Windows-OCR text dumps into structured candidate observations.

OCR is reliable for flight number, date, times, duration and the repeated total,
and unreliable for the fare-breakdown panel (the rupee glyph is read as t/U/l and
occasionally eats a leading digit). So this parser takes only what OCR reads
consistently and leaves the rest to verification.

Nothing here infers a value. A field OCR could not produce is emitted empty.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

OCR = Path(__file__).resolve().parents[1] / "ocr"
MONTHS = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}

# ₹ is OCR'd as t, U, Ü, ?, or dropped entirely.
MONEY = re.compile(r"[tTUÜ?₹]?\s?(\d{1,2}[,.]\d{3})\b")
FLIGHT = re.compile(r"\b6E\s?(\d{2,4})\b")
DATE = re.compile(r"(\d{1,2})(?:th|st|nd|rd)\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)")
# "06:05 DEI, Tl" / "13:00 DEC, Tl" -- OCR mangles DEL but the time is clean.
DEP = re.compile(r"\b([0-2]?\d:[0-5]\d)\s+D[EC][ILC]?\b")
ARR = re.compile(r"BOM,?\s*T\S?\s*([0-2]?\d:[0-5]\d)|\b([0-2]?\d:[0-5]\d)\s*$")
DUR = re.compile(r"\b(\d{2})h\s*(\d{2})m\b")


def money(tok: str) -> int:
    return int(tok.replace(",", "").replace(".", ""))


def parse(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    head, _, body = raw.partition("\n")
    parts = [p.strip() for p in head.lstrip("#").split("|")]
    rec: dict[str, object] = {
        "shot": parts[0],
        "source": parts[1],
        "captured": parts[2],
    }

    m = DATE.search(body)
    rec["travel_date"] = f"2026-{MONTHS[m.group(2)]:02d}-{int(m.group(1)):02d}" if m else ""

    m = FLIGHT.search(body)
    rec["flight_no"] = m.group(1) if m else ""

    m = DEP.search(body)
    rec["dep"] = m.group(1) if m else ""

    # arrival: the time token appearing on/near the BOM line
    arr = ""
    for line in body.splitlines():
        if "BOM" in line:
            t = re.search(r"([0-2]?\d:[0-5]\d)", line)
            if t:
                arr = t.group(1)
                break
    rec["arr"] = arr

    m = DUR.search(body)
    rec["dur_min"] = int(m.group(1)) * 60 + int(m.group(2)) if m else ""

    rec["non_stop"] = "Non-stop" in body
    rec["checked_bag_15"] = "15 kg Check-in bag allowance" in body
    rec["saver_seen"] = "Saver fare" in body

    # The total is the money value OCR repeats most often: it appears on the
    # Saver card, in TOTAL FARE and again in Total price. Base and tax appear
    # twice each; everything else once.
    tokens = [money(t) for t in MONEY.findall(body)]
    plausible = [v for v in tokens if 1000 <= v <= 60000]
    counts = Counter(plausible)
    rec["total_candidates"] = sorted(counts.items(), key=lambda kv: (-kv[1], -kv[0]))[:4]
    best = [v for v, c in counts.items() if c >= 3]
    rec["total"] = max(best) if best else ""
    rec["all_money"] = sorted(set(plausible))
    return rec


def main() -> None:
    rows = [parse(p) for p in sorted(OCR.glob("s*.txt"))]
    out = OCR.parent / "extract" / "ocr_parsed.json"
    out.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    ok = sum(1 for r in rows if r["travel_date"] and r["flight_no"] and r["dep"] and r["total"])
    print(f"parsed {len(rows)} files; {ok} complete on (date, flight, dep, total)")
    print(f"dates: {Counter(r['travel_date'] for r in rows).most_common()}")
    missing = [
        r["shot"]
        for r in rows
        if not (r["travel_date"] and r["flight_no"] and r["dep"] and r["total"])
    ]
    if missing:
        print(f"incomplete -> needs visual check: {missing}")


if __name__ == "__main__":
    main()
