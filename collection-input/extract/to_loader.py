"""Turn the verified panel into the loader's two CSVs.

Every value here was read off the screenshot by eye and cross-checked against
the arithmetic (base + tax == panel total) and against the fare-family guard
(panel total == Saver card price). Nothing is inferred.

s034 is the one exception and it is handled explicitly: the collector opened the
**Lite** fare's breakdown, so the Saver total is taken from the fare card (which
is displayed) and base/taxes are left EMPTY, because the Saver breakdown was
never shown. Substituting Lite's components would be exactly the silent
fare-family swap the contract forbids.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
OUT = BASE / "loader"
OUT.mkdir(exist_ok=True)

verified = list(csv.DictReader((BASE / "extract" / "verified.csv").open(encoding="utf-8")))
index = json.loads((BASE / "index.json").read_text(encoding="utf-8"))

# crop id -> capture timestamp (the screenshot's own mtime: the observation instant)
cap = {k.replace(".png", ""): v["captured"] for k, v in index.items()}

ATT_HDR = [
    "travel_date",
    "source_id",
    "time_ist",
    "origin",
    "destination",
    "outcome",
    "source_group",
    "notes",
]
FARE_HDR = [
    "travel_date",
    "source_id",
    "time_ist",
    "origin",
    "destination",
    "carrier",
    "flight_number",
    "departure_time",
    "stops",
    "duration_minutes",
    "fare_family_raw",
    "availability",
    "payable_fare",
    "base_fare",
    "taxes",
    "fees",
    "user_development_fee",
    "checked_baggage_kg",
    "change_permitted",
    "cancellation_permitted",
    "source_group",
    "notes",
]

fares, attempts = [], {}
for r in verified:
    shot = r["shot"]
    ts = datetime.strptime(cap[shot], "%Y-%m-%d %H:%M:%S")
    hhmm = ts.strftime("%H:%M")
    td = r["travel_date"]

    # one attempt per (travel_date); its time is the earliest capture for that date
    a = attempts.get(td)
    if a is None or hhmm < a["time_ist"]:
        attempts[td] = {
            "travel_date": td,
            "source_id": "indigo-direct",
            "time_ist": hhmm,
            "origin": "DEL",
            "destination": "BOM",
            "outcome": "SUCCESS",
            "source_group": "",
            "notes": "manual browser capture, screenshots retained",
        }

    family_ok = r["family_ok"] == "1"
    fares.append(
        {
            "travel_date": td,
            "source_id": "indigo-direct",
            "time_ist": hhmm,
            "origin": "DEL",
            "destination": "BOM",
            "carrier": "6E",
            "flight_number": r["flight_no"],
            "departure_time": r["dep"],
            "stops": "0",
            "duration_minutes": r["dur_min"],
            "fare_family_raw": "Saver fare",
            "availability": "AVAILABLE",
            "payable_fare": f"{int(r['saver_card'])}.00",
            # IndiGo renders ONE aggregated "Taxes & Fees / Total Tax" line at this
            # step, so `taxes` carries that aggregate and fees/UDF stay blank --
            # they were not rendered separately. AMB-12, registered not resolved.
            "base_fare": f"{int(r['base'])}.00" if family_ok and r["base"] else "",
            "taxes": f"{int(r['tax'])}.00" if family_ok and r["tax"] else "",
            "fees": "",
            "user_development_fee": "",
            "checked_baggage_kg": "15",
            "change_permitted": "FEE",
            "cancellation_permitted": "FEE",
            "source_group": "",
            "notes": f"{shot}"
            + (
                ""
                if family_ok
                else " | breakdown shown was LITE; Saver total from fare card, "
                "components NOT observed"
            ),
        }
    )


def write(path: Path, hdr: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=hdr)
        w.writeheader()
        w.writerows(rows)


write(OUT / "attempts.csv", ATT_HDR, sorted(attempts.values(), key=lambda a: a["travel_date"]))
write(
    OUT / "fares.csv",
    FARE_HDR,
    sorted(fares, key=lambda r: (r["travel_date"], r["departure_time"])),
)
print(f"attempts: {len(attempts)}  fares: {len(fares)}")
print(
    f"capture window: {min(r['time_ist'] for r in fares)} - {max(r['time_ist'] for r in fares)} IST"
)
print(f"observations without a Saver breakdown: {sum(1 for r in fares if not r['base_fare'])}")
