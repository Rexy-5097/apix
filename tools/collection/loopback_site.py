"""A synthetic airline search page, served on 127.0.0.1, for exercising the browser path.

This is the page :mod:`apix.ingestion.collectors.indigo.loopback` drives. It
implements the *selector contract* written in ``navigation.SELECTORS`` and
``live.EXTRACT_SELECTORS`` -- the ``data-testid`` attributes, the form controls,
the results markup -- so the contracted navigation plan can be executed by a
real browser against a real DOM.

Three scenarios, chosen with ``?scenario=``:

``results``     a normal results page with three flights (the default)
``challenge``   a bot-check page, to prove the stop signal fires in a browser
``dom_change``  a results page whose container was renamed, to prove a selector
                mismatch surfaces as UNRECOGNISED rather than as a guess

Every fare here is invented. The flight numbers (``6E 9001``+) and the amounts
are deliberately unlike anything in ``data/panel.json``, so no output of this
page can be mistaken for a real observation, and the page says so on its face.

Run standalone: ``python tools/collection/loopback_site.py --port 8765``
"""

from __future__ import annotations

import argparse
import threading
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

SCENARIOS = ("results", "challenge", "dom_change")

#: Calendar range rendered on the home page. Wide enough for any APW window.
CALENDAR_FROM = date(2026, 1, 1)
CALENDAR_DAYS = 760

#: Three invented flights. Base + tax reconciles to the displayed total, because
#: the parser's reconciliation check is part of what we are exercising.
FLIGHTS: tuple[dict[str, object], ...] = (
    {
        "number": "6E 9001",
        "departure": "06:40",
        "arrival": "08:55",
        "duration": "02h 15m",
        "base": 4100,
        "tax": 1221,
    },
    {
        "number": "6E 9002",
        "departure": "11:15",
        "arrival": "13:25",
        "duration": "02h 10m",
        "base": 3880,
        "tax": 1221,
    },
    {
        "number": "6E 9003",
        "departure": "19:05",
        "arrival": "21:20",
        "duration": "02h 15m",
        "base": 5240,
        "tax": 1221,
    },
)

_STYLE = (
    "body{font:14px system-ui;margin:24px;max-width:900px}"
    ".synthetic{background:#fde9e7;border:2px solid #b4442f;color:#7d2d1e;"
    "padding:10px 14px;font-weight:700;margin-bottom:18px}"
    ".card{border:1px solid #ccc;padding:12px;margin:10px 0}"
    ".tile{border:1px dashed #999;padding:8px;margin-top:8px}"
    "label{display:inline-block;min-width:130px}"
)

_BANNER = (
    '<div class="synthetic">SYNTHETIC FIXTURE PAGE — served by this repository on the '
    "loopback interface. Every fare below is invented. Nothing here is a real "
    "airfare and nothing collected from it may enter the index.</div>"
)


def _calendar() -> str:
    days = (CALENDAR_FROM + timedelta(days=i) for i in range(CALENDAR_DAYS))
    return "".join(
        f'<button type="button" data-date="{d.isoformat()}" '
        f"onclick=\"document.getElementById('travel_date').value=this.dataset.date\">"
        f"{d.isoformat()}</button>"
        for d in days
    )


def home_page(scenario: str) -> str:
    """The search form. Implements every selector the navigation plan uses."""
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>APIx loopback fixture — search</title>
<style>{_STYLE}</style></head><body>
{_BANNER}
<button data-testid="cookie-reject" onclick="this.remove()">Reject non-essential cookies</button>
<h1>Book a flight (synthetic)</h1>
<form action="/results" method="get">
  <input type="hidden" name="scenario" value="{scenario}">
  <p><label>Trip type</label>
     <button type="button" data-testid="trip-type-oneway">One Way</button></p>
  <p><label>From</label>
     <input data-testid="origin-input" name="origin" placeholder="From" autocomplete="off">
     <button type="button" data-testid="airport-option-DEL"
             onclick="document.querySelector('[data-testid=origin-input]').value='DEL'">DEL Delhi</button>
     <button type="button" data-testid="airport-option-BOM"
             onclick="document.querySelector('[data-testid=destination-input]').value='BOM'">BOM Mumbai</button></p>
  <p><label>To</label>
     <input data-testid="destination-input" name="destination" placeholder="To" autocomplete="off"></p>
  <p><label>Departure date</label>
     <input data-testid="departure-date" id="travel_date" name="travel_date" readonly
            onclick="document.getElementById('cal').hidden=false">
     <span id="cal" hidden>{_calendar()}</span></p>
  <p><label>Adults</label><input data-testid="pax-adult-count" name="adults" value="1"></p>
  <p><label>Children</label><input data-testid="pax-child-count" name="children" value="0"></p>
  <p><label>Infants</label><input data-testid="pax-infant-count" name="infants" value="0"></p>
  <p><label>Fare type</label>
     <button type="button" data-testid="special-fare-none">Regular</button></p>
  <p><label>Currency</label>
     <select data-testid="currency-select" name="currency">
       <option value="INR" selected>INR</option><option value="USD">USD</option></select></p>
  <p><label>Nearby airports</label>
     <input type="checkbox" data-testid="nearby-airports" name="nearby"></p>
  <p><button type="submit" data-testid="search-flights">Search</button></p>
</form>
</body></html>"""


def challenge_page() -> str:
    """A bot check. The adapter must stop here, capture evidence and not retry."""
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Checking your browser</title>
<style>{_STYLE}</style></head><body>
{_BANNER}
<h1>Verify you are human</h1>
<p>Unusual traffic has been detected from your network. Please complete the
challenge below to continue.</p>
<div id="captcha">[synthetic captcha widget]</div>
</body></html>"""


def _fare_tile(base: int, tax: int) -> str:
    total = base + tax
    return f"""<div class="tile" data-testid="fare-tile">
      <span data-testid="fare-name">Saver fare</span>
      <span data-testid="fare-price">&#8377; {total:,}</span>
      <div data-testid="fare-baggage">15 kg check-in baggage</div>
      <div data-testid="fare-baggage">7 kg cabin baggage</div>
      <div data-testid="fare-policy">Change and cancellation charges: Standard</div>
      <div data-testid="fare-breakdown-row">
        <span data-testid="fare-breakdown-label">Base airfare</span>
        <span data-testid="fare-breakdown-value">&#8377; {base:,}</span></div>
      <div data-testid="fare-breakdown-row">
        <span data-testid="fare-breakdown-label">Total tax</span>
        <span data-testid="fare-breakdown-value">&#8377; {tax:,}</span></div>
    </div>"""


def _flight_card(f: dict[str, object]) -> str:
    return f"""<div class="card" data-testid="flight-card">
      <span data-testid="flight-number">{f["number"]}</span>
      <span data-testid="departure-time">{f["departure"]}</span>
      <span data-testid="arrival-time">{f["arrival"]}</span>
      <span data-testid="departure-airport">DEL</span>
      <span data-testid="arrival-airport">BOM</span>
      <span data-testid="duration">{f["duration"]}</span>
      <span data-testid="stops">Non-stop</span>
      <span data-testid="operated-by">IndiGo</span>
      {_fare_tile(int(f["base"]), int(f["tax"]))}
    </div>"""


def results_page(params: dict[str, list[str]], scenario: str) -> str:
    """The results page. ``dom_change`` renames the container the plan waits for."""
    travel = (params.get("travel_date") or [""])[0]
    origin = (params.get("origin") or ["DEL"])[0]
    destination = (params.get("destination") or ["BOM"])[0]
    currency = (params.get("currency") or ["INR"])[0]
    try:
        label = date.fromisoformat(travel).strftime("%d %b %Y")
    except ValueError:
        label = travel
    # The DOM-change scenario is exactly one renamed attribute. That is what a
    # real site redesign looks like to a selector, and the plan must not guess.
    results_testid = "flight-results-v2" if scenario == "dom_change" else "flight-results"
    cards = "".join(_flight_card(f) for f in FLIGHTS)
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>APIx loopback fixture — results</title>
<style>{_STYLE}</style></head><body>
{_BANNER}
<div>
  <span data-testid="summary-origin">{origin}</span>
  <span data-testid="summary-destination">{destination}</span>
  <span data-testid="summary-date">{label}</span>
  <span data-testid="summary-pax">1 Adult</span>
  <span data-testid="summary-currency">{currency}</span>
  <span data-testid="summary-trip">One Way</span>
</div>
<button type="button" data-testid="sort-departure-earliest">Departure: earliest first</button>
<div data-testid="{results_testid}">{cards}</div>
</body></html>"""


class LoopbackSiteHandler(BaseHTTPRequestHandler):
    """Serves the fixture. Binds loopback only; see :func:`serve`."""

    server_version = "APIxLoopbackFixture/1.0"

    def do_GET(self) -> None:  # http.server API name
        parts = urlsplit(self.path)
        params = parse_qs(parts.query)
        scenario = (params.get("scenario") or ["results"])[0]
        if scenario not in SCENARIOS:
            scenario = "results"
        if scenario == "challenge":
            body, status = challenge_page(), 200
        elif parts.path.rstrip("/") in ("", "/index.html"):
            body, status = home_page(scenario), 200
        elif parts.path.rstrip("/") == "/results":
            body, status = results_page(params, scenario), 200
        else:
            body, status = "<h1>not found</h1>", 404
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args: object) -> None:
        """Quiet by default; the test asserts on the adapter, not on the log."""


def serve(port: int = 0, host: str = "127.0.0.1") -> ThreadingHTTPServer:
    """Start the fixture site. Loopback only -- it is not for anyone else to reach."""
    if host not in ("127.0.0.1", "::1", "localhost"):
        raise ValueError(f"the loopback fixture binds loopback only, not {host!r}")
    return ThreadingHTTPServer((host, port), LoopbackSiteHandler)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args(argv)
    httpd = serve(args.port)
    host, port = httpd.server_address[0], httpd.server_address[1]
    print(f"loopback fixture site: http://{host}:{port}/  (scenarios: {', '.join(SCENARIOS)})")
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        httpd.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
