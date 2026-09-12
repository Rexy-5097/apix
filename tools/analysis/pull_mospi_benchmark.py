"""Pull the official MoSPI CPI airfare series — the external benchmark.

Source: MoSPI eSankhyiki, the Dataset Link named in problem statement 26056.
    GET https://api.mospi.gov.in/api/cpi/getItemIndex
    item "Air Fare (normal): Economy Class(adult)", base 2012 = 100.

**Role: VALIDATION BENCHMARK ONLY.** This is a monthly, All-India index number.
It carries no route, no carrier, no flight, no booking date and no fare in
rupees, so it cannot be an input to APIx and is never mixed with observations.
It exists to answer "does our measurement sit in a plausible relationship to the
official series", and with one collection date even that comparison is
structural rather than statistical.

Two API behaviours are worked around rather than assumed away:
  * it FAILS OPEN — a wrong endpoint returns the portal's HTML with HTTP 200, so
    the body is parsed and the shape checked rather than the status code;
  * only `page` and `year` are honoured. `month`, `item` and `baseyear` are
    silently ignored, so filtering is done client-side.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ENDPOINT = "https://api.mospi.gov.in/api/cpi/getItemIndex"
ITEM = "Air Fare (normal): Economy Class(adult)"
OUT = Path(__file__).resolve().parents[2] / "data" / "mospi_cpi_airfare.json"


def fetch(params: str) -> dict | None:
    """Fetch via curl.

    The host negotiates TLS in a way Python's ssl module refuses
    (UNSAFE_LEGACY_RENEGOTIATION_DISABLED); curl completes the same request. The
    URL and headers are fixed constants, so nothing here is shell-interpolated.
    """
    out = subprocess.run(
        [
            "curl",
            "-sS",
            "--max-time",
            "90",
            "-H",
            "Accept: application/json",
            f"{ENDPOINT}?{params}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    body = out.stdout
    if not body.lstrip().startswith("{"):
        return None  # fail-open: the portal served HTML, not data
    return json.loads(body)


def main() -> None:
    series = {}
    for year in range(2014, 2026):
        payload = fetch(f"year={year}")
        if not payload or "data" not in payload:
            print(f"  {year}: no data")
            continue
        hits = [r for r in payload["data"] if r.get("item") == ITEM]
        for h in hits:
            key = f"{h['year']}-{h['month']}"
            series[key] = {
                "year": h["year"],
                "month": h["month"],
                "baseyear": h["baseyear"],
                "index": float(h["index"]),
                "inflation": None if h["inflation"] is None else float(h["inflation"]),
                "status": h["status"],
            }
            print(
                f"  {key:<18} index={h['index']:>7}  "
                f"yoy={h['inflation']!s:>7}%  base {h['baseyear']}"
            )

    if not series:
        print("no airfare records retrieved")
        return

    vals = sorted(series.values(), key=lambda r: r["year"])
    first, last = vals[0], vals[-1]
    growth = last["index"] / first["index"]
    years = last["year"] - first["year"]
    print(
        f"\nofficial airfare CPI, {first['month']} {first['year']}"
        f" -> {last['month']} {last['year']}"
    )
    print(
        f"  {first['index']} -> {last['index']}  ({growth:.3f}x over {years} years, "
        f"{100 * (growth ** (1 / years) - 1):.2f}%/yr geometric)"
    )

    OUT.write_text(
        json.dumps(
            {
                "source": "MoSPI eSankhyiki api.mospi.gov.in/api/cpi/getItemIndex",
                "item": ITEM,
                "role": "VALIDATION_BENCHMARK_ONLY",
                "is_apix_input": False,
                "frequency": "monthly",
                "geography": "All India",
                "unit": "index (2012=100)",
                "retrieved": "2026-09-12",
                "series": series,
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"written: {OUT}")


if __name__ == "__main__":
    main()
