"""Build the candidate observation panel from OCR text + verified date blocks.

Two rules govern every field here:

1. **Nothing is inferred.** A value OCR could not produce is emitted empty and
   flagged for visual verification. Base/tax are accepted ONLY when they
   arithmetically reconcile to the total, which makes them self-validating: a
   misread digit cannot survive the check.

2. **Dates come from verified blocks.** OCR read the date header in 127 of 152
   files; the 25 it missed sit inside runs whose neighbours agree, and both
   ambiguous boundaries (s021, s067..s082) were confirmed by reading the image.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date, datetime
from itertools import combinations
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
OCR = BASE / "ocr"
COLLECTION_DATE = date(2026, 9, 12)

# Verified by OCR date headers, with both ambiguous boundaries read visually.
BLOCKS = [
    (1, 20, "2026-09-13"),  # T+1
    (21, 41, "2026-09-15"),  # T+3   (s021 confirmed visually)
    (42, 62, "2026-09-19"),  # T+7
    (63, 82, "2026-09-27"),  # T+15  (s067, s082 confirmed visually)
    (83, 105, "2026-10-12"),  # T+30
    (106, 128, "2026-11-11"),  # T+60
    (129, 152, "2026-11-19"),  # T+68 -- NOT a production APW bucket
]

MONEY = re.compile(r"[tTUÜ?₹]?\s?(\d{1,2}[,.]\d{3})\b")
FLIGHT = re.compile(r"\b6E\s?(\d{2,4})\b")
DEP = re.compile(r"\b([0-2]?\d:[0-5]\d)\s+D[EC][ILC]?\b")
DUR = re.compile(r"\b(\d{2})h\s*(\d{2})m\b")


def block_date(n: int) -> str:
    for lo, hi, d in BLOCKS:
        if lo <= n <= hi:
            return d
    raise ValueError(n)


def money(tok: str) -> int:
    return int(tok.replace(",", "").replace(".", ""))


def build() -> list[dict]:
    rows = []
    for path in sorted(OCR.glob("s*.txt")):
        raw = path.read_text(encoding="utf-8-sig")
        head, _, body = raw.partition("\n")
        parts = [p.strip() for p in head.lstrip("#").split("|")]
        shot = parts[0]
        n = int(shot[1:])

        travel = block_date(n)
        tdate = datetime.strptime(travel, "%Y-%m-%d").date()

        m = FLIGHT.search(body)
        flight = m.group(1) if m else ""
        m = DEP.search(body)
        dep = m.group(1) if m else ""
        arr = ""
        for line in body.splitlines():
            if "BOM" in line:
                t = re.search(r"([0-2]?\d:[0-5]\d)", line)
                if t:
                    arr = t.group(1)
                    break
        m = DUR.search(body)
        dur = m.group(1) and int(m.group(1)) * 60 + int(m.group(2)) if m else ""

        toks = [money(t) for t in MONEY.findall(body)]
        vals = [v for v in toks if 1000 <= v <= 60000]
        counts = Counter(vals)
        repeated = [v for v, c in counts.items() if c >= 3]
        total = max(repeated) if repeated else ""

        # base + tax accepted ONLY if a unique pair reconciles to the total.
        base = tax = ""
        if total:
            uniq = sorted(set(vals))
            pairs = [(a, b) for a, b in combinations(uniq, 2) if a + b == total]
            if len(pairs) == 1:
                tax, base = min(pairs[0]), max(pairs[0])

        lead = (tdate - COLLECTION_DATE).days
        hour = int(dep.split(":")[0]) if dep else None
        rows.append(
            {
                "shot": shot,
                "source": parts[1],
                "captured": parts[2],
                "travel_date": travel,
                "lead_time_days": lead,
                "flight_no": flight,
                "dep": dep,
                "arr": arr,
                "dur_min": dur,
                "band": hour // 3 if hour is not None else "",
                "total": total,
                "base": base,
                "tax": tax,
                "non_stop": "Non-stop" in body,
                "checked_bag_15": "15 kg Check-in bag allowance" in body,
                "saver_present": "Saver fare" in body,
                "reconciles": bool(total and base and tax and base + tax == total),
            }
        )
    return rows


def main() -> None:
    rows = build()
    (BASE / "extract" / "panel_raw.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    n = len(rows)
    print(f"{n} shots")
    print(
        "  flight+dep+total complete : "
        f"{sum(1 for r in rows if r['flight_no'] and r['dep'] and r['total'])}"
    )
    print(f"  base/tax reconciled       : {sum(1 for r in rows if r['reconciles'])}")
    print(f"  non-stop flagged          : {sum(1 for r in rows if r['non_stop'])}")
    print(f"  15kg check-in seen        : {sum(1 for r in rows if r['checked_bag_15'])}")
    print()
    print(f"{'travel_date':<14}{'APW':<8}{'n':<5}{'bands present'}")
    print("-" * 60)
    from collections import defaultdict

    by = defaultdict(list)
    for r in rows:
        by[r["travel_date"]].append(r)
    for d in sorted(by):
        rs = by[d]
        lead = rs[0]["lead_time_days"]
        bands = sorted({r["band"] for r in rs if r["band"] != ""})
        print(f"{d:<14}T+{lead:<6}{len(rs):<5}{bands}")
    bad = [r["shot"] for r in rows if not (r["flight_no"] and r["dep"] and r["total"])]
    if bad:
        print(f"\nincomplete ({len(bad)}) -> visual verification required:\n  {bad}")


if __name__ == "__main__":
    main()
