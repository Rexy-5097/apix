"""The APIx HTTP API — standard library only, so it runs from a clean checkout.

PS 26056 asks for *"an API that the NSO and RBI can consume"*. This serves it
on the standard library's HTTP server: no dependency to install, nothing that
can fail on a jury laptop, and every response is the same JSON a FastAPI
version would return. FastAPI is the documented production upgrade, not a
prerequisite for demonstrating the contract.

Every response carries the :func:`~apix.api.payloads.envelope` fields, so a
consumer can never receive a number without its ``output_class`` --
``PRODUCTION`` / ``RESEARCH`` / ``DEMO`` -- and its publication state.

Run::

    python -m apix.api            # http://127.0.0.1:8760
    python -m apix.api --port 9000

Endpoints::

    GET /health
    GET /sources
    GET /routes
    GET /observations
    GET /index/daily      GET /index/weekly      GET /index/monthly
        (append ?class=demo for the synthetic fixture series, labelled DEMO)
    GET /coverage
    GET /lead-time
    GET /provenance/{observation_id}
    GET /backtest
    GET /reference
    GET /config
    GET /                 endpoint list
"""

from __future__ import annotations

import argparse
import json
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from apix.api import payloads
from apix.series import Frequency

DEFAULT_PORT = 8760

ENDPOINTS: tuple[str, ...] = (
    "/health",
    "/sources",
    "/routes",
    "/observations",
    "/index/daily",
    "/index/weekly",
    "/index/monthly",
    "/coverage",
    "/lead-time",
    "/provenance/{observation_id}",
    "/backtest",
    "/reference",
    "/config",
)

_PROVENANCE = re.compile(r"^/provenance/(?P<oid>.+)$")
_INDEX = re.compile(r"^/index/(?P<freq>daily|weekly|monthly)$")


def route(path: str, query: dict[str, list[str]]) -> tuple[int, Any]:
    """Resolve a request to ``(status, payload)``. Pure, so tests need no socket."""
    if path in ("", "/"):
        return HTTPStatus.OK, payloads.envelope(
            {"endpoints": list(ENDPOINTS)},
            output_class=payloads.OutputClass.RESEARCH,
            publication_status="NOT_APPLICABLE",
            data_status="INDEX",
            endpoint="/",
        )
    if path == "/health":
        return HTTPStatus.OK, payloads.health()
    if path == "/sources":
        return HTTPStatus.OK, payloads.sources()
    if path == "/routes":
        return HTTPStatus.OK, payloads.routes()
    if path == "/observations":
        return HTTPStatus.OK, payloads.observations()
    if path == "/coverage":
        return HTTPStatus.OK, payloads.coverage()
    if path == "/lead-time":
        return HTTPStatus.OK, payloads.lead_time()
    if path == "/backtest":
        return HTTPStatus.OK, payloads.backtest()
    if path == "/reference":
        return HTTPStatus.OK, payloads.reference()
    if path == "/config":
        return HTTPStatus.OK, payloads.config()

    m = _INDEX.match(path)
    if m:
        demo = query.get("class", [""])[0].lower() == "demo"
        return HTTPStatus.OK, payloads.index(Frequency[m["freq"].upper()], demo=demo)

    m = _PROVENANCE.match(path)
    if m:
        payload = payloads.provenance(unquote(m["oid"]))
        if payload is None:
            return HTTPStatus.NOT_FOUND, {
                "error": "observation not found",
                "observation_id": unquote(m["oid"]),
            }
        return HTTPStatus.OK, payload

    return HTTPStatus.NOT_FOUND, {"error": "no such endpoint", "endpoints": list(ENDPOINTS)}


class Handler(BaseHTTPRequestHandler):
    server_version = f"APIx/{payloads.API_VERSION}"

    def do_GET(self) -> None:  # http.server API name
        parts = urlsplit(self.path)
        status, payload = route(parts.path.rstrip("/") or "/", parse_qs(parts.query))
        body = json.dumps(payload, indent=1, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-APIx-Methodology-Version", payloads.METHODOLOGY_VERSION)
        self.send_header("X-APIx-Live-Acquisition", "BLOCKED-AUTHORIZATION-PENDING")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"  {self.command} {self.path} -> {args[1] if len(args) > 1 else ''}")


def serve(port: int = DEFAULT_PORT, host: str = "127.0.0.1") -> ThreadingHTTPServer:
    """Create a bound server. Caller drives ``serve_forever`` or ``handle_request``."""
    return ThreadingHTTPServer((host, port), Handler)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args(argv)
    httpd = serve(args.port, args.host)
    print(f"APIx API v{payloads.API_VERSION} on http://{args.host}:{args.port}")
    print("live airfare acquisition: BLOCKED — authorization pending")
    for e in ENDPOINTS:
        print(f"  GET {e}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


__all__ = ["DEFAULT_PORT", "ENDPOINTS", "Handler", "main", "route", "serve"]
