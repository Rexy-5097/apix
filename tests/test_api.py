"""The APIx HTTP API — PS 26056 requirement 6D.

Routing is tested purely (no socket) because it is a function; one test binds
a real server on an ephemeral port to prove the wire format. The load-bearing
assertions are the honesty ones: every payload carries an ``output_class``,
the production index endpoints return an EMPTY series with a readiness verdict,
and nothing served is labelled PRODUCTION.
"""

from __future__ import annotations

import json
import threading
import urllib.request
from http import HTTPStatus

import pytest

from apix.api import ENDPOINTS, payloads, route, serve
from apix.series import Frequency

REQUIRED_ENVELOPE = {
    "api_version",
    "endpoint",
    "generated_at",
    "methodology_version",
    "output_class",
    "publication_status",
    "data_status",
    "live_airfare_acquisition",
    "data",
}


@pytest.mark.parametrize(
    "path",
    [
        "/health",
        "/sources",
        "/routes",
        "/observations",
        "/index/daily",
        "/index/weekly",
        "/index/monthly",
        "/coverage",
        "/lead-time",
        "/backtest",
        "/reference",
        "/config",
    ],
)
def test_every_endpoint_returns_an_envelope(path: str) -> None:
    status, payload = route(path, {})
    assert status == HTTPStatus.OK
    assert set(payload) >= REQUIRED_ENVELOPE, f"{path} missing {REQUIRED_ENVELOPE - set(payload)}"
    assert payload["methodology_version"] == "2.1"
    assert payload["output_class"] in {"PRODUCTION", "RESEARCH", "DEMO"}
    json.dumps(payload, default=str)  # serialisable


def test_nothing_served_is_labelled_production() -> None:
    """No production index exists, so no endpoint may say it does."""
    for path in [e for e in ENDPOINTS if "{" not in e]:
        _, payload = route(path, {})
        assert payload["output_class"] != "PRODUCTION", f"{path} claims PRODUCTION"


def test_every_envelope_states_live_acquisition_is_blocked() -> None:
    for path in [e for e in ENDPOINTS if "{" not in e]:
        _, payload = route(path, {})
        assert "BLOCKED" in payload["live_airfare_acquisition"]


@pytest.mark.parametrize("freq", ["daily", "weekly", "monthly"])
def test_production_index_endpoints_return_an_empty_series_with_the_reason(freq: str) -> None:
    """The real panel has zero matched pairs. The endpoint says so; it does not invent."""
    status, payload = route(f"/index/{freq}", {})
    assert status == HTTPStatus.OK
    assert payload["output_class"] == "RESEARCH"
    assert payload["data"]["series"] == []
    assert payload["data"]["readiness"]["publishable"] is False
    assert any("C.1" in b for b in payload["data"]["readiness"]["blockers"])


@pytest.mark.parametrize("freq", ["daily", "weekly", "monthly"])
def test_demo_index_is_labelled_demo_and_never_publishable(freq: str) -> None:
    _, payload = route(f"/index/{freq}", {"class": ["demo"]})
    assert payload["output_class"] == "DEMO"
    assert "SYNTHETIC" in payload["publication_status"]
    assert len(payload["data"]["series"]) >= 1
    assert payload["data"]["source"].startswith("synthetic")


def test_demo_series_lengths_are_consistent_across_frequencies() -> None:
    d = len(route("/index/daily", {"class": ["demo"]})[1]["data"]["series"])
    w = len(route("/index/weekly", {"class": ["demo"]})[1]["data"]["series"])
    m = len(route("/index/monthly", {"class": ["demo"]})[1]["data"]["series"])
    assert d >= w >= m >= 1


def test_sources_endpoint_clears_nothing_and_names_permission_blocked() -> None:
    _, payload = route("/sources", {})
    data = payload["data"]
    assert data["cleared_for_live"] == []
    if data["sources"]:  # register parsed
        assert data["register_size"] == 30
        blocked = {
            s["operational_status"]
            for s in data["sources"]
            if s["operational_status"] != "NOT_SCHEDULED"
        }
        assert blocked == {"PERMISSION_BLOCKED"}


def test_routes_endpoint_has_no_publication_grade_basket() -> None:
    _, payload = route("/routes", {})
    for basket in payload["data"]["baskets"]:
        assert basket["is_publication_grade"] is False
    assert payload["data"]["routes_with_real_observations"] == ["DEL-BOM"]


def test_observations_endpoint_serves_the_real_panel() -> None:
    _, payload = route("/observations", {})
    assert payload["data"]["count"] == 35
    assert payload["data"]["data_class"] == "REAL_MARKET_OBSERVATION"
    assert payload["data"]["evidence_counts"] == {"PRIMARY_HASHED": 30, "SECONDARY_CHAT_IMAGE": 5}


def test_provenance_resolves_a_real_observation_and_404s_an_unknown_one() -> None:
    oid = payloads.panel()["observations"][0]["observation_id"]
    status, payload = route(f"/provenance/{oid}", {})
    assert status == HTTPStatus.OK
    assert payload["data"]["observation"]["observation_id"] == oid
    assert payload["data"]["collection_run"]["methodology_version"] == "2.1"
    assert payload["data"]["parser_version"] == "manual-1.0"
    status, payload = route("/provenance/does-not-exist", {})
    assert status == HTTPStatus.NOT_FOUND
    assert payload["error"] == "observation not found"


def test_lead_time_is_descriptive_not_an_elasticity() -> None:
    _, payload = route("/lead-time", {})
    assert payload["publication_status"] == "DESCRIPTIVE_ONLY"
    assert "not an elasticity" in payload["data_status"]
    ps = [r["apw"] for r in payload["data"]["profile"] if r["in_ps_26056_set"]]
    assert ps == [1, 7, 15, 30, 45]
    assert payload["data"]["confound"]["lead_time_confounded"] is True


def test_backtest_is_incomplete_with_reasons() -> None:
    _, payload = route("/backtest", {})
    assert payload["data"]["status"] == "INCOMPLETE"
    assert payload["data"]["dgca_fare_benchmark"]["status"] == "NOT_LOCATED"
    assert len(payload["data"]["reasons"]) == 3
    assert payload["data"]["fallback_benchmark"]["months_actually_published"] == ["December"]


def test_reference_is_inadmissible_and_never_an_observation() -> None:
    _, payload = route("/reference", {})
    if payload["data"].get("present", True):
        assert payload["data"]["admissibility"] == "INADMISSIBLE"
        assert payload["data"]["is_apix_input"] is False
    assert (
        "REFERENCE_ONLY" in payload["data_status"] or "REFERENCE_ABSENT" in payload["data_status"]
    )


def test_unknown_path_is_404_with_the_endpoint_list() -> None:
    status, payload = route("/nope", {})
    assert status == HTTPStatus.NOT_FOUND
    assert payload["endpoints"] == list(ENDPOINTS)


def test_root_lists_endpoints() -> None:
    status, payload = route("/", {})
    assert status == HTTPStatus.OK
    assert "/provenance/{observation_id}" in payload["data"]["endpoints"]


def test_server_speaks_json_over_a_real_socket() -> None:
    """One wire test on an ephemeral port; everything else is pure routing."""
    httpd = serve(port=0)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as resp:
            assert resp.status == 200
            assert resp.headers["Content-Type"].startswith("application/json")
            assert resp.headers["X-APIx-Methodology-Version"] == "2.1"
            assert resp.headers["X-APIx-Live-Acquisition"] == "BLOCKED-AUTHORIZATION-PENDING"
            body = json.loads(resp.read())
            assert body["data"]["status"] == "ok"
            assert body["data"]["observations_held"] == 35
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/index/monthly?class=demo", timeout=5
        ) as resp:
            body = json.loads(resp.read())
            assert body["output_class"] == "DEMO"
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_period_aggregation_used_by_the_api_is_geometric() -> None:
    """The API's monthly DEMO level equals the geometric mean of its daily points."""
    import math

    daily = route("/index/daily", {"class": ["demo"]})[1]["data"]["series"]
    monthly = route("/index/monthly", {"class": ["demo"]})[1]["data"]["series"]
    assert len(monthly) == 1
    levels = [p["level"] for p in daily if p["level"] is not None]
    geo = math.exp(sum(math.log(v) for v in levels) / len(levels))
    assert monthly[0]["level"] == pytest.approx(geo)
    assert Frequency.MONTHLY.value == monthly[0]["frequency"]
