"""Statistical QA on the **real** observed panel.

Every other test file exercises the engine on synthetic fixtures. This one
asserts properties of the actual 35 observations collected on 2026-09-12, so a
change that corrupts the dataset — a mis-banded flight, a Lite fare creeping in,
a fabricated cell — fails the build rather than reaching a dashboard.

It reads `data/panel.json`, which is generated from the store and committed. The
store itself is gitignored, and no single hand-maintained file holds the whole
panel — `verified.csv` carries the 30 primary rows while the T+45 batch arrived
separately — so the generated contract is the only complete view, and it is the
same one the dashboard renders.

The invariants asserted here are independent of how the data got there: band is
derivable from the departure hour, base + tax must equal the total, the grid
must be 7x5. They catch corruption regardless of the path it took. The
hand-calculated values (specific flights, specific fares, read off the
screenshots) are the anchor that catches silent drift.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from apix.schemas.enums import APWBucket

DATA = Path(__file__).resolve().parents[1] / "data"
PANEL = DATA / "panel.json"
COLLECTION_DATE = date(2026, 9, 12)

#: Frozen Day-1 contract. Bands are spec B.2, anchored at 00:00 IST.
CONTRACT_BANDS = (2, 3, 4, 5, 6)
EXPECTED_ROUTE = "DEL-BOM"
EXPECTED_CARRIER = "6E"
EXPECTED_FAMILY = "Saver fare"
EXPECTED_BAGGAGE_KG = 15
EXPECTED_N = 35

#: Hand-calculated from the screenshots — the frozen expectation for this panel.
EXPECTED_APW_DATES = {
    1: "2026-09-13",
    3: "2026-09-15",
    7: "2026-09-19",
    15: "2026-09-27",
    30: "2026-10-12",
    45: "2026-10-27",
    60: "2026-11-11",
}


@pytest.fixture(scope="module")
def panel() -> dict:
    return json.loads(PANEL.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def rows(panel: dict) -> list[dict]:
    return panel["observations"]


def oid(r: dict) -> str:
    return r["observation_id"]


# ── 1. APW mapping ───────────────────────────────────────────────────────────


def test_every_travel_date_maps_to_a_production_apw_bucket(rows: list[dict]) -> None:
    """Spec A.3 assigns by EXACT lead time. A cell in no bucket is inadmissible."""
    for r in rows:
        td = datetime.strptime(r["travel_date"], "%Y-%m-%d").date()
        lead = (td - COLLECTION_DATE).days
        assert APWBucket.from_lead_time(lead) is not None, (
            f"{oid(r)}: travel {td} is T+{lead}, which matches no A.3 bucket"
        )
        assert r["apw"] == lead


def test_the_seven_frozen_apw_buckets_are_all_present(rows: list[dict]) -> None:
    assert {r["apw"] for r in rows} == set(EXPECTED_APW_DATES)


def test_each_apw_maps_to_its_hand_calculated_travel_date(rows: list[dict]) -> None:
    for r in rows:
        assert r["travel_date"] == EXPECTED_APW_DATES[r["apw"]], oid(r)


def test_apw_bucket_enum_still_holds_the_seven_frozen_values() -> None:
    """If A.3 is ever edited, this fails before any panel claim can go stale."""
    assert [b.value for b in APWBucket] == [1, 3, 7, 15, 30, 45, 60]


# ── 2-3. Band mapping and earliest-flight selection ──────────────────────────


def test_band_equals_departure_hour_floor_divided_by_three(rows: list[dict]) -> None:
    """Spec B.2. The band must be derivable, never a typed label."""
    for r in rows:
        hour = int(r["dep"].split(":")[0])
        assert r["band"] == hour // 3, f"{oid(r)}: dep {r['dep']} band {r['band']}"


def test_every_band_is_inside_the_contracted_set(rows: list[dict]) -> None:
    for r in rows:
        assert r["band"] in CONTRACT_BANDS, f"{oid(r)}: band {r['band']} is not collected"


def test_exactly_one_flight_per_apw_band_cell(rows: list[dict]) -> None:
    """The selection contract takes ONE flight per band — the earliest."""
    cells = Counter((r["travel_date"], r["band"]) for r in rows)
    assert not [k for k, v in cells.items() if v > 1], f"duplicate cells: {cells}"
    assert len(cells) == EXPECTED_N


def test_each_date_covers_exactly_the_five_contracted_bands(rows: list[dict]) -> None:
    by_date: dict[str, list[int]] = defaultdict(list)
    for r in rows:
        by_date[r["travel_date"]].append(r["band"])
    for d, bands in by_date.items():
        assert sorted(bands) == list(CONTRACT_BANDS), f"{d}: bands {sorted(bands)}"


def test_the_selected_flight_departs_inside_its_own_band_window(rows: list[dict]) -> None:
    for r in rows:
        lo, hi = r["band_window"].split("-")
        assert lo <= r["dep"] <= hi, f"{oid(r)}: dep {r['dep']} outside {r['band_window']}"


# ── 4. Saver vs Lite ─────────────────────────────────────────────────────────


def test_every_observation_is_the_saver_fare_family(rows: list[dict]) -> None:
    """Spec B.4. A Lite fare is hand-baggage-only — a different product, not a
    cheaper version of the same one. Its components sum cleanly to its own
    total, so a swapped family is internally consistent and silently wrong."""
    for r in rows:
        assert r["fare_family_raw"] == EXPECTED_FAMILY, f"{oid(r)}: {r['fare_family_raw']!r}"


def test_every_observation_carries_checked_baggage(rows: list[dict]) -> None:
    """The entitlement that distinguishes Saver from Lite, and the one the
    canonical fare class is derived from."""
    for r in rows:
        assert r["checked_baggage_kg"] == EXPECTED_BAGGAGE_KG, oid(r)


def test_fare_class_derives_to_standard_not_hand_only(rows: list[dict]) -> None:
    """Spec B.4: class comes from entitlements, never the marketing label.
    A Lite fare would derive to HAND_ONLY, so this catches a swap even if the
    label were edited."""
    for r in rows:
        assert r["fare_class"] == "STANDARD", f"{oid(r)}: {r['fare_class']}"


# ── 5-7. Route, non-stop, alternate airports ─────────────────────────────────


def test_route_is_exactly_del_bom_on_every_row(rows: list[dict]) -> None:
    """AMB-3: route sits in the spec D.4 duplicate tuple, so it must be exact."""
    for r in rows:
        assert r["route"] == EXPECTED_ROUTE, f"{oid(r)}: route {r['route']}"


def test_no_alternate_airport_leaked_in(panel: dict, rows: list[dict]) -> None:
    """Navi Mumbai (NMI) is a different airport, not a nearby substitute."""
    assert panel["frame"]["routes"] == [EXPECTED_ROUTE]
    banned = {"NMI", "PNQ", "IXU", "HDO", "DXN"}
    for r in rows:
        o, d = r["route"].split("-")
        assert o not in banned and d not in banned, f"{oid(r)}: {r['route']}"


def test_every_flight_is_non_stop(rows: list[dict]) -> None:
    """A one-stop DEL-BOM is a different product, not a slower version."""
    for r in rows:
        assert r["stops"] == 0, f"{oid(r)}: {r['stops']} stops"


def test_carrier_is_indigo_on_every_row(rows: list[dict]) -> None:
    for r in rows:
        assert r["carrier"] == EXPECTED_CARRIER, oid(r)


def test_flight_numbers_are_digits_only(rows: list[dict]) -> None:
    """Spec A.2: '2045', never '6E2045' — two spellings defeat deduplication."""
    for r in rows:
        number = r["flight"].split()[-1]
        assert number.isdigit(), f"{oid(r)}: flight {r['flight']!r}"


def test_durations_are_plausible_for_a_non_stop_del_bom(rows: list[dict]) -> None:
    for r in rows:
        assert 120 <= r["duration_min"] <= 165, f"{oid(r)}: {r['duration_min']} min"


# ── 8. Fare reconciliation ───────────────────────────────────────────────────


def test_base_plus_tax_equals_total_for_every_observation(rows: list[dict]) -> None:
    """Decimal, not float — spec Notation requires exact monetary arithmetic
    before the log transform."""
    for r in rows:
        base = Decimal(str(r["base"]))
        tax = Decimal(str(r["tax"]))
        total = Decimal(str(r["total"]))
        assert base + tax == total, f"{oid(r)}: {base} + {tax} != {total}"
        assert r["reconciles"] is True


def test_no_fare_component_is_missing(rows: list[dict]) -> None:
    for r in rows:
        assert r["base"] is not None and r["tax"] is not None, oid(r)


def test_every_fare_is_strictly_positive(rows: list[dict]) -> None:
    """Spec A.6: a non-positive fare is a parse failure, and ln(p) is undefined."""
    for r in rows:
        assert r["total"] > 0 and r["base"] > 0 and r["tax"] > 0, oid(r)


def test_a_worked_example_matches_the_screenshot_by_hand(rows: list[dict]) -> None:
    """T+1 band 2 — read off the image: 6E 6218, 06:05, 5,065 + 1,465 = 6,530."""
    r = next(x for x in rows if x["apw"] == 1 and x["band"] == 2)
    assert r["flight"] == "6E 6218"
    assert r["dep"] == "06:05"
    assert (r["base"], r["tax"], r["total"]) == (5065.0, 1465.0, 6530.0)


def test_a_second_worked_example_from_the_t45_batch(rows: list[dict]) -> None:
    """T+45 band 6 — 6E 329, 18:30, 5,673 + 1,496 = 7,169."""
    r = next(x for x in rows if x["apw"] == 45 and x["band"] == 6)
    assert r["flight"] == "6E 329"
    assert r["dep"] == "18:30"
    assert (r["base"], r["tax"], r["total"]) == (5673.0, 1496.0, 7169.0)


# ── 9. Duplicates ────────────────────────────────────────────────────────────


def test_no_duplicate_on_the_spec_d4_tuple(rows: list[dict]) -> None:
    key = Counter(
        (r["travel_date"], r["route"], r["carrier"], r["flight"], r["dep"], r["fare_family_raw"])
        for r in rows
    )
    assert not [k for k, v in key.items() if v > 1], "spec D.4 tuple collision"


def test_observation_ids_are_unique(rows: list[dict]) -> None:
    ids = Counter(oid(r) for r in rows)
    assert not [i for i, n in ids.items() if n > 1]


# ── 10. Provenance completeness ──────────────────────────────────────────────


def test_every_observation_carries_an_evidence_grade(rows: list[dict]) -> None:
    for r in rows:
        assert r["evidence"] in {"PRIMARY_HASHED", "SECONDARY_CHAT_IMAGE"}, oid(r)


def test_the_weaker_t45_provenance_is_visible_not_hidden(rows: list[dict]) -> None:
    """The T+45 batch arrived as chat images: no bytes could be hashed. That is
    recorded as a derived fact, and this test stops it being quietly upgraded."""
    t45 = [r for r in rows if r["apw"] == 45]
    assert len(t45) == 5
    assert all(r["evidence"] == "SECONDARY_CHAT_IMAGE" for r in t45)
    primary = [r for r in rows if r["apw"] != 45]
    assert all(r["evidence"] == "PRIMARY_HASHED" for r in primary)


def test_evidence_counts_match_the_rows(panel: dict, rows: list[dict]) -> None:
    counts = panel["quality"]["evidence_counts"]
    assert counts == dict(Counter(r["evidence"] for r in rows))
    assert counts["PRIMARY_HASHED"] == 30
    assert counts["SECONDARY_CHAT_IMAGE"] == 5


def test_every_observation_names_the_run_that_produced_it(rows: list[dict]) -> None:
    for r in rows:
        assert r["run_id"], oid(r)


# ── 11. Missing-cell detection ───────────────────────────────────────────────


def test_panel_is_exactly_the_expected_size(rows: list[dict]) -> None:
    assert len(rows) == EXPECTED_N


def test_no_cell_is_missing_from_the_seven_by_five_grid(rows: list[dict]) -> None:
    present = {(r["travel_date"], r["band"]) for r in rows}
    missing = [
        (d, b) for d in EXPECTED_APW_DATES.values() for b in CONTRACT_BANDS if (d, b) not in present
    ]
    assert not missing, f"missing cells: {missing}"


def test_reported_plan_completion_agrees_with_the_rows(panel: dict, rows: list[dict]) -> None:
    q = panel["quality"]
    assert q["valid_observations"] == len(rows)
    assert q["plan_slots"] == len(EXPECTED_APW_DATES) * len(CONTRACT_BANDS)
    assert q["plan_completion_pct"] == 100.0
    assert q["plan_slots_unfilled"] == 0
    assert q["apw_missing"] == []


def test_statistical_coverage_is_never_claimed(panel: dict) -> None:
    """35/35 is collection-plan completion, not spec I coverage.

    Spec I gates a route at 60% of *expected cells* and AMB-8 records that
    nothing defines an expected cell. Reporting 100% "coverage" would borrow a
    statistical meaning this number cannot carry, and would read as the §I gate
    being satisfied when no denominator has been chosen.
    """
    q = panel["quality"]
    assert q["statistical_coverage"] == "NOT_ESTABLISHED"
    assert "AMB-8" in q["statistical_coverage_blocker"]
    # The optimistic field name must not come back under any spelling.
    assert "coverage_pct" not in q
    assert "expected_cells" not in q
    assert "missing_cells" not in q


def test_no_renderer_calls_plan_completion_coverage() -> None:
    """Regression guard for the exact phrasing that had to be removed.

    The dashboard once showed a green tile reading `coverage 100% / no gaps`.
    That is the claim AMB-8 forbids, so the word is reserved: anywhere
    "coverage" appears in a rendered artifact it must be qualified as APW
    buckets, as NOT ESTABLISHED, or as the spec's own `min_route_coverage`.
    """
    import re

    for name in ("dashboard.html", "panel_report.txt"):
        # Normalise first: rendered prose wraps across lines, and a line break
        # mid-sentence would otherwise look like an unqualified use.
        text = " ".join((DATA / name).read_text(encoding="utf-8").split())
        for match in re.finditer(r".{0,80}coverage.{0,80}", text, re.IGNORECASE):
            line = match.group(0)
            allowed = (
                "APW coverage" in line
                or "statistical coverage" in line.lower()
                or "min_route_coverage" in line
                or "not coverage" in line.lower()
                or "Coverage denominator" in line
                or "AMB-8" in line
            )
            assert allowed, f"unqualified 'coverage' in {name}: {line!r}"
        assert "100% coverage" not in text
        assert "100.0% coverage" not in text


# ── 12-14. Why the index cannot run, asserted so it cannot be forgotten ──────


def test_the_panel_holds_exactly_one_collection_wave(panel: dict) -> None:
    assert panel["index_status"]["collection_waves"] == 1


def test_no_t_minus_7_counterpart_exists(panel: dict) -> None:
    """Spec C.1 LOCKED: I(c,t) = I(c,t-7) x J(c,t). With one wave the matched
    set M(c,t) is empty for every cell, so no Jevons relative exists. Producing
    a number anyway would mean changing the formula."""
    i = panel["index_status"]
    assert i["matched_pairs_available"] == 0
    assert i["apix_l_computable"] is False


def test_the_index_gate_names_its_own_unlock_date(panel: dict) -> None:
    """2026-09-19 is exactly seven days after the wave we hold."""
    assert panel["index_status"]["next_wave_unlocking_index"] == "2026-09-19"


def test_tpd_threshold_is_not_met_and_is_not_lowered(panel: dict) -> None:
    """min_quotes_window = 1,500 per spec M. 35 quotes is two orders short, and
    the threshold is reported rather than relaxed to obtain a number."""
    i = panel["index_status"]
    assert i["tpd_min_quotes_window"] == 1500
    assert i["tpd_quotes_available"] == EXPECTED_N
    assert i["tpd_computable"] is False


# ── The APW profile must never read as an index ──────────────────────────────


def test_apw_profile_is_declared_descriptive_not_an_index(panel: dict) -> None:
    assert panel["apw_profile_class"] == "DESCRIPTIVE_CROSS_SECTION"
    d = panel["apw_profile_disclaimer"].upper()
    assert "NOT AN INDEX" in d


def test_renderers_label_the_profile_as_not_an_index() -> None:
    dash = (DATA / "dashboard.html").read_text(encoding="utf-8").upper()
    report = (DATA / "panel_report.txt").read_text(encoding="utf-8").upper()
    for text in (dash, report):
        assert "NOT AN INDEX" in text


def test_the_38_percent_is_never_called_inflation() -> None:
    """The T+1 -> T+60 difference is a ratio of two cross-sections."""
    dash = (DATA / "dashboard.html").read_text(encoding="utf-8")
    low = dash.lower()
    for phrase in ("fares increased", "fares rose", "airfare inflation of", "inflation rate of"):
        assert phrase not in low, f"dashboard implies a price movement: {phrase!r}"
    assert "not airfare inflation" in low or "not a time-series" in low


# ── Lead time is confounded, and that must be visible ────────────────────────


def test_confound_between_lead_time_and_weekday_is_recorded(panel: dict) -> None:
    c = panel["confound"]
    assert c["lead_time_confounded"] is True
    assert c["distinct_weekdays"] < len(c["weekday_by_apw"])
    assert c["repeated_weekdays"], "at least one weekday must repeat for the confound to bind"


def test_confound_weekdays_agree_with_the_observed_rows(panel: dict, rows: list[dict]) -> None:
    """Derived from the rows, so the disclosure cannot drift from the data."""
    from datetime import date as _date

    for apw, dow in panel["confound"]["weekday_by_apw"].items():
        travel = {r["travel_date"] for r in rows if r["apw"] == int(apw)}
        assert len(travel) == 1
        assert _date.fromisoformat(travel.pop()).strftime("%a") == dow


def test_both_renderers_disclose_the_confound() -> None:
    dash = (DATA / "dashboard.html").read_text(encoding="utf-8").lower()
    report = (DATA / "panel_report.txt").read_text(encoding="utf-8").lower()
    for text in (dash, report):
        assert "confounded" in text


# ── Dispersion is observed, never called an anomaly ──────────────────────────


def test_dispersion_traces_to_real_observation_ids(panel: dict, rows: list[dict]) -> None:
    """A spread nobody can audit is a claim, not a measurement."""
    d = panel["dispersion"]
    ids = {r["observation_id"] for r in rows}
    for side in ("widest_min_obs", "widest_max_obs"):
        assert d[side]["observation_id"] in ids
        row = next(r for r in rows if r["observation_id"] == d[side]["observation_id"])
        assert row["total"] == d[side]["total"]
        assert row["flight"] == d[side]["flight"]


def test_widest_dispersion_bucket_is_actually_the_widest(panel: dict) -> None:
    spreads = {a["apw"]: a["spread_pct"] for a in panel["apw_profile"]}
    assert panel["dispersion"]["widest_apw"] == max(spreads, key=lambda k: spreads[k])
    assert panel["dispersion"]["widest_spread_pct"] == max(spreads.values())


def test_dispersion_claims_no_cause(panel: dict) -> None:
    """No anomaly-detection definition is in force, so 'anomaly' is unearned."""
    assert panel["dispersion"]["cause_established"] is False
    dash = " ".join((DATA / "dashboard.html").read_text(encoding="utf-8").split()).lower()
    assert "does not establish its cause" in dash
    # The dispersion section must *disclaim* the word rather than avoid it:
    # "anomaly" implies a detection rule, and none is in force.
    section = dash.split("within-bucket dispersion")[1].split("<section")[0]
    assert "no anomaly-detection definition is in force" in section
    assert "not as an anomaly" in section


# ── TPD and uncertainty: specified is not implemented ────────────────────────


def test_tpd_and_uncertainty_packages_are_genuinely_empty() -> None:
    """The documentation says these are empty. Assert it, so it stays true."""
    src = Path(__file__).resolve().parents[1] / "src" / "apix" / "statistics"
    for pkg in ("tpd", "uncertainty"):
        modules = [p for p in (src / pkg).glob("*.py") if p.name != "__init__.py"]
        assert not modules, f"{pkg}/ now has code; update the docs that call it EMPTY"
        assert (src / pkg / "__init__.py").read_text(encoding="utf-8").strip() == ""


def test_dashboard_states_tpd_is_specified_but_not_implemented() -> None:
    dash = (DATA / "dashboard.html").read_text(encoding="utf-8")
    assert "NOT IMPLEMENTED" in dash
    assert "not implemented" in dash.lower()
    assert "1,500" in dash or "1500" in dash


def test_no_confidence_interval_is_reported_anywhere() -> None:
    dash = (DATA / "dashboard.html").read_text(encoding="utf-8").lower()
    report = (DATA / "panel_report.txt").read_text(encoding="utf-8").lower()
    for text in (dash, report):
        for phrase in ("95% ci", "confidence interval of", "± ", "std. error", "standard error"):
            assert phrase not in text, f"an interval leaked into a renderer: {phrase!r}"


# ── The synthetic fixture must never touch the real panel ────────────────────


def test_real_panel_declares_itself_real_and_synthetic_free(panel: dict) -> None:
    assert panel["data_class"] == "REAL_MARKET_OBSERVATION"
    assert panel["synthetic_data_present"] is False


def test_dashboard_carries_no_synthetic_fixture_content() -> None:
    """The engine demo lives in its own file. If its banner ever appears in the
    real-market dashboard, the boundary has been crossed."""
    dash = (DATA / "dashboard.html").read_text(encoding="utf-8")
    assert "SYNTHETIC FIXTURE" not in dash.upper()


def test_engine_validation_page_is_separate_and_carries_no_currency() -> None:
    page = DATA / "engine-validation.html"
    if not page.exists():
        pytest.skip("engine-validation.html not generated in this checkout")
    html = page.read_text(encoding="utf-8")
    assert "₹" not in html, "a currency figure in the synthetic page could read as a fare"
    assert html.upper().count("SYNTHETIC FIXTURE - NOT A MARKET MEASUREMENT") >= 3
    assert "base 100" in html
    assert "test_pipeline_14_day" in html


# ── The index stays PENDING on every surface ─────────────────────────────────


def test_every_renderer_says_the_index_is_pending() -> None:
    dash = (DATA / "dashboard.html").read_text(encoding="utf-8")
    assert "PENDING" in dash
    assert "2026-09-19" in dash
    report = (DATA / "panel_report.txt").read_text(encoding="utf-8")
    assert "NOT ESTABLISHED" in report


def test_amb_8_and_amb_9_stay_visible(panel: dict) -> None:
    dash = (DATA / "dashboard.html").read_text(encoding="utf-8")
    assert "AMB-8" in dash
    assert "AMB-9" in dash
    assert panel["quality"]["statistical_coverage"] == "NOT_ESTABLISHED"


# ── 15-16. Version vector and reproducibility ────────────────────────────────


def test_every_run_carries_the_full_version_vector(panel: dict) -> None:
    """Spec P.1: a published value must be recomputable from its versions."""
    required = (
        "methodology_version",
        "basket_version",
        "parser_version",
        "collector_version",
        "protocol_version",
        "source_precedence_version",
        "frame_id",
    )
    for run in panel["runs"]:
        for field in required:
            assert run.get(field), f"{run['run_id']} missing {field}"


def test_methodology_version_is_the_frozen_one(panel: dict) -> None:
    assert {r["methodology_version"] for r in panel["runs"]} == {"2.1"}


def test_run_observation_counts_sum_to_the_panel(panel: dict, rows: list[dict]) -> None:
    assert sum(r["observations"] for r in panel["runs"]) == len(rows)


def test_the_panel_declares_itself_real_and_synthetic_free(panel: dict) -> None:
    """Synthetic data must never be presented as observed."""
    assert panel["data_class"] == "REAL_MARKET_OBSERVATION"
    assert panel["synthetic_data_present"] is False


def test_apw_profile_geomeans_recompute_from_the_rows(panel: dict, rows: list[dict]) -> None:
    """The dashboard renders these figures; they must follow from the data."""
    import math

    by_apw: dict[int, list[float]] = defaultdict(list)
    for r in rows:
        by_apw[r["apw"]].append(r["total"])
    for entry in panel["apw_profile"]:
        vals = by_apw[entry["apw"]]
        expected = math.exp(sum(math.log(v) for v in vals) / len(vals))
        assert entry["n"] == len(vals)
        assert abs(entry["geomean"] - expected) < 0.01, entry["apw"]


# ── 17. The dashboard must agree with the contract it renders ────────────────


DASHBOARD = Path(__file__).resolve().parents[1] / "data" / "dashboard.html"


@pytest.fixture(scope="module")
def dashboard() -> str:
    return DASHBOARD.read_text(encoding="utf-8")


def test_dashboard_headline_figures_come_from_the_contract(panel: dict, dashboard: str) -> None:
    """The previous dashboard was hand-authored and two figures went stale — a
    base-year mixing error and a series count — before a manual cross-check
    caught them. This makes the check automatic."""
    q, idx = panel["quality"], panel["index_status"]
    for label, value in [
        ("valid observations", str(q["valid_observations"])),
        ("plan slots", str(q["plan_slots"])),
        ("plan completion", f"{q['plan_completion_pct']}%"),
        ("reconciled", f"{q['reconciled']}/{q['decomposed']}"),
        ("primary hashed", str(q["evidence_counts"]["PRIMARY_HASHED"])),
        ("secondary chat image", str(q["evidence_counts"]["SECONDARY_CHAT_IMAGE"])),
        ("window flags", str(q["window_flags"])),
        ("unlock date", idx["next_wave_unlocking_index"]),
    ]:
        assert value in dashboard, f"dashboard is missing {label} = {value}"


def test_dashboard_shows_every_apw_geomean(panel: dict, dashboard: str) -> None:
    for e in panel["apw_profile"]:
        assert f"{e['geomean']:,.0f}" in dashboard, f"T+{e['apw']} geomean absent"


def test_dashboard_lists_every_observed_flight(panel: dict, dashboard: str) -> None:
    for o in panel["observations"]:
        assert o["flight"] in dashboard, f"{o['flight']} absent from the dashboard"


def test_dashboard_never_claims_an_index_value(dashboard: str) -> None:
    """The one overstatement that would matter. The page must say the index is
    pending, and must not print an index level."""
    lowered = dashboard.lower()
    assert "pending" in lowered
    assert "not computable" in lowered
    # The formula is rendered with a typographic minus; match it by codepoint
    # so the assertion does not itself depend on which dash was used.
    minus = chr(0x2212)  # typographic minus, as rendered
    assert f"i(c,t{minus}7)" in lowered or "i(c,t-7)" in lowered


def test_dashboard_declares_the_data_class_and_no_synthetic_data(
    panel: dict, dashboard: str
) -> None:
    assert panel["data_class"] in dashboard
    assert "synthetic_data_present = False" in dashboard
