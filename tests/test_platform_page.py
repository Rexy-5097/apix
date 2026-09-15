"""The platform console page — PS 26056 requirements 6 and 10.

Generated from the same payloads the API serves. These tests assert the page
carries every required view, labels every figure by class, states the blocked
capability, and regenerates identically — so `git diff --exit-code data/`
remains meaningful.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "analysis"))

import build_platform  # noqa: E402

REQUIRED_SECTIONS = [
    "overview",
    "trends",
    "heatmap",
    "leadtime",
    "acquisition",
    "sources",
    "runs",
    "quality",
    "provenance",
    "backtest",
    "methodology",
    "architecture",
]


@pytest.fixture(scope="module")
def html() -> str:
    return build_platform.build()


def test_every_required_view_is_present(html: str) -> None:
    for sid in REQUIRED_SECTIONS:
        assert f'id="{sid}"' in html, f"missing section {sid}"
    assert len(REQUIRED_SECTIONS) == 12


def test_the_blocked_capability_is_stated_in_the_header_and_nav(html: str) -> None:
    assert "LIVE AIRFARE CONNECTORS" in html
    assert "AUTHORIZATION PENDING" in html
    assert "PERMISSION_BLOCKED" in html
    assert "zero</b> fares" in html or "<b>zero</b>" in html


def test_no_figure_is_labelled_production(html: str) -> None:
    """The PRODUCTION class appears only in the legend explaining that none exists."""
    occurrences = [m.start() for m in re.finditer(r'class="cls PRODUCTION"', html)]
    assert len(occurrences) == 1, "PRODUCTION may appear once, as the legend entry"
    legend_pos = html.find("none exists")
    assert legend_pos > 0 and abs(occurrences[0] - legend_pos) < 400


def test_demo_series_are_labelled_demo_beside_the_figures(html: str) -> None:
    assert html.count('class="cls DEMO"') >= 3
    assert "synthetic fixture" in html.lower()


def test_heatmap_has_exactly_one_filled_cell(html: str) -> None:
    """Six demo routes, one with real observations. The empty cells are the finding."""
    assert html.count(">35 obs</text>") == 1
    assert html.count(">no data</text>") == 5


def test_lead_time_carries_the_confound_disclaimer(html: str) -> None:
    assert "Not an elasticity" in html
    assert "lead time is confounded" in html.lower() or "confounded" in html.lower()


def test_backtest_is_incomplete_and_names_dgca_not_located(html: str) -> None:
    assert "NOT_LOCATED" in html
    assert 'class="cls INCOMPLETE"' in html


def test_page_is_fully_offline(html: str) -> None:
    urls = set(re.findall(r'(?:src|href)="(https?://[^"]+)"', html))
    assert urls == set(), f"external asset references: {urls}"
    assert 'href="vendor/fonts.css"' in html


def test_page_regenerates_identically() -> None:
    """No timestamp, no randomness — so the committed artifact is checkable."""
    assert build_platform.build() == build_platform.build()
    assert "generated_at" not in build_platform.build()


def test_page_links_to_the_editorial_dashboard(html: str) -> None:
    assert 'href="dashboard.html"' in html


def test_api_contract_is_documented_on_the_page(html: str) -> None:
    for ep in ("/health", "/sources", "/index/daily|weekly|monthly", "/provenance/", "/backtest"):
        assert ep in html


# --------------------------------------------------------------- motion layer
# The console carries the dashboard's motion system. These tests do not check
# that it looks nice; they check the two rules that make animation admissible
# here: no figure is ever rendered at a value it does not hold, and no motion
# depicts work that did not happen.


@pytest.fixture(scope="module")
def data_island(html: str) -> dict:
    import json

    m = re.search(r'<script type="application/json" id="apix-data">(.*?)</script>', html, re.S)
    assert m, "the data island is missing"
    return json.loads(m.group(1))


def test_the_vendored_libraries_are_loaded_and_present_on_disk(html: str) -> None:
    for lib in ("gsap.min.js", "ScrollTrigger.min.js", "lenis.min.js"):
        assert f'<script src="vendor/{lib}" defer></script>' in html
        assert (ROOT / "data" / "vendor" / lib).is_file(), f"{lib} is referenced but not vendored"


def test_rest_states_are_gated_on_the_js_class(html: str) -> None:
    """With the script blocked, nothing is hidden: the content is the fallback."""
    assert 'document.documentElement.className += " js"' in html
    for rule in (".js .lin .step", ".js .hm-cell", ".js tbody tr.rvr"):
        assert rule in html, f"{rule} must hide only when JS is running"


def test_reduced_motion_neutralises_every_component_this_page_adds(html: str) -> None:
    blocks = re.findall(r"@media \(prefers-reduced-motion:reduce\)\{(.*?)\n\}", html, re.S)
    assert blocks, "no reduced-motion block"
    body = "\n".join(blocks)
    for sel in ("#pf-field", ".js .lin .step", ".js .hm-cell", ".track i", ".ag-pkt"):
        assert sel in body, f"{sel} is not neutralised under prefers-reduced-motion"


def test_no_figure_is_tallied_from_zero(html: str) -> None:
    """Every animated figure already reads its true value in the markup.

    A 0 -> 35 count-up renders "20 real observations" for a frame, and any frame
    can be screenshotted. The runtime is allowed to uncover a number, never to
    interpolate one, so no tween may write a figure into the document.
    """
    script = "".join(re.findall(r"<script>(.*?)</script>", html, flags=re.S))
    reveal = re.search(r"number reveals(.*?)\n\}\);", script, re.S)
    assert reveal, "the number-reveal block is gone"
    assert "clipPath" in reveal.group(1)
    for writer in ("textContent", "innerHTML", "innerText"):
        assert writer not in reveal.group(1), (
            f"the reveal writes a figure with {writer}; it may only uncover one"
        )
    # Nothing scroll-driven may write text either: a scrubbed tween would
    # render every intermediate value on the way to the real one.
    for update in re.findall(r"onUpdate:function\([^)]*\)\{(.*?)\}", script, re.S):
        assert "textContent" not in update and "innerHTML" not in update
    counters = re.findall(r'data-count="1" data-s="\d+">([^<]+)<', html)
    assert len(counters) >= 12
    assert "35" in counters and "150" in counters
    assert counters.count("0") >= 2  # requests made, observations written


def test_every_animated_figure_matches_the_payload(html: str) -> None:
    from apix.api import payloads

    obs = payloads.observations()["data"]
    run = payloads.coverage()["data"]["scheduled_run"]
    counters = re.findall(r'data-count="1" data-s="\d+">([^<]+)<', html)
    assert str(obs["count"]) in counters
    assert str(run["planned_searches"]) in counters
    assert str(run["requests_made"]) in counters
    assert "MISSING_PREVIOUS_PERIOD" in counters


def test_the_data_island_carries_only_recorded_values(data_island: dict) -> None:
    from apix.api import payloads

    panel = payloads.panel()
    totals = {o["total"] for o in panel["observations"]}
    assert len(data_island["obs"]) == len(panel["observations"]) == 35
    for point in data_island["obs"]:
        assert point["total"] in totals
        assert point["ev"] in {"PRIMARY_HASHED", "SECONDARY_CHAT_IMAGE"}
    assert data_island["apwOrder"] == [1, 3, 7, 15, 30, 45, 60]


def test_the_travelling_packets_are_real_observations(data_island: dict) -> None:
    """The packet animated through the pipeline is a row from the panel."""
    from apix.api import payloads

    rows = payloads.panel()["observations"]
    labels = {f"{o['route']} · T+{o['apw']} · ₹{int(o['total']):,}" for o in rows}
    assert data_island["packets"]
    for p in data_island["packets"]:
        assert p["label"] in labels, f"{p['label']} is not a recorded observation"


def test_the_live_lane_carries_no_packet_and_the_index_is_drawn_refused(html: str) -> None:
    """Zero requests were made, so nothing may be animated through that lane."""
    nodes = re.findall(r'<g class="ag-node"([^>]*)>', html)
    assert len(nodes) == 13
    with_at = [n for n in nodes if "data-at=" in n]
    blocked = [n for n in nodes if 'data-blocked="1"' in n]
    assert len(with_at) == 8, "the live lane must not sit on the packet's path"
    assert len(blocked) == 2, "the compliance gate and the index are the refused nodes"
    assert "PUBLICATION GUARD · REFUSED" in html
    assert "it is a replay, not a live feed" in html


def test_permission_state_is_rendered_separately_from_operational_state(html: str) -> None:
    cards = re.findall(r'<article class="scard" data-perm="([A-Z]+)"', html)
    assert cards, "no source cards"
    assert set(cards) <= {"AUTHORIZED", "PENDING", "PROHIBITED", "UNKNOWN"}
    assert "Permission state and operational state are different facts" in html
    assert html.count("OPERATIONAL · ") == len(cards)
    assert '.scard[data-perm="PROHIBITED"] .sdot{background:var(--red)' in html
    assert '.scard[data-perm="PENDING"] .sdot{background:var(--amber)' in html


def test_the_index_dependency_chain_shows_exactly_one_satisfied_link(html: str) -> None:
    rows = re.findall(r'<div class="row" data-ok="([01])"><i>', html)
    assert rows == ["1", "0", "0", "0", "0"], rows
    assert "spec C.1 refuses" in html


def test_the_backtest_visual_states_the_missing_benchmark_without_drawing_it(html: str) -> None:
    assert 'class="track dead"' in html
    assert "NOT_LOCATED — never published" in html
    assert "insufficient temporal granularity" in html
    assert "FRAMEWORK READY · EMPIRICAL VALIDATION INCOMPLETE" in html


def test_the_lineage_explorer_traverses_six_hops_of_real_provenance(
    html: str, data_island: dict
) -> None:
    from apix.api import payloads

    steps = re.findall(r'<div class="step" data-k="(\w+)"', html)
    assert steps == ["index", "route", "observation", "run", "source", "artifact"]
    assert len(data_island["lineage"]) == 12
    first = payloads.panel()["observations"][0]
    rec = data_island["lineage"][0]
    assert first["flight"] in rec["observation"]
    assert first["run_id"] in rec["run"]
    assert "no index level" in rec["index"]


def test_the_navigation_is_one_scrollable_row_not_a_stack(html: str) -> None:
    assert 'class="pf-links"' in html
    assert ".pf-links{display:flex" in html and "overflow-x:auto" in html
    assert 'class="pf-prog"' in html
    assert "PIPELINE POSITION" in html


def test_the_flow_graph_scrolls_rather_than_shrinking_on_a_phone(html: str) -> None:
    assert 'class="agwrap"' in html
    assert "svg.ag{min-width:820px" in html


def test_the_page_closes_on_the_evidence_statement(html: str) -> None:
    assert "APIx does not" in html and "manufacture certainty." in html
    assert "It measures only what the evidence supports." in html
    assert "PS 26056 · Airfare measurement infrastructure for India" in html


def test_the_hero_field_is_driven_by_three_declared_beats(html: str) -> None:
    beats = re.findall(r'<div data-on="[01]"><b>\d\d · ([A-Z ]+)</b>', html)
    assert beats == ["QUOTES AS COLLECTED", "KEYED AND NORMALISED", "AGGREGATED"]
