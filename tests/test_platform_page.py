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
