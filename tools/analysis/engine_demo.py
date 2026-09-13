"""Run the REAL index engine over the controlled 14-day SYNTHETIC fixture.

    ####################################################################
    #  SYNTHETIC FIXTURE - NOT A MARKET MEASUREMENT.                   #
    #  Every number this tool prints or renders is computed from       #
    #  CONTROLLED TEST DATA with hand-checkable prices. None of it is  #
    #  an airfare observation, and none of it is an APIx index value.  #
    ####################################################################

Why this exists. The headline claim is that the index *engine* works; the real
panel cannot demonstrate that, because one collection wave yields no matched
pair and therefore no relative. Running the engine on a fixture is how an
estimator is normally shown to compute -- the same instrument a statistical
office uses -- and it is not a market claim.

The fixture is imported from ``tests/test_pipeline_14_day.py`` rather than
re-declared here, deliberately: the demo then executes the *exact* fixture CI
verifies on every commit, so a passing build and a working demo cannot drift
apart. Observations carry ``SourceType.SYNTHETIC`` in the schema itself.

The real market panel and this fixture are never mixed. This tool reads nothing
from the store, writes nothing into it, and renders to its own file.

    python tools/analysis/engine_demo.py           # live run, console
    python tools/analysis/engine_demo.py --html    # also write the isolated page
"""

from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from apix.schemas.enums import Tier  # noqa: E402
from apix.statistics.elementary.jevons import compute_jevons  # noqa: E402
from apix.statistics.elementary.matching import build_matched_set  # noqa: E402
from apix.statistics.index.apix_l import ApixLError  # noqa: E402
from tests.test_pipeline_14_day import (  # noqa: E402
    APW_DAYS,
    DAYS,
    PRECEDENCE,
    cell_key_for,
    run_pipeline,
    two_healthy_chains,
)

OUT = ROOT / "data" / "engine-validation.html"

BANNER = "SYNTHETIC FIXTURE - NOT A MARKET MEASUREMENT"
#: Index points. Never rupees -- a currency figure here could be mistaken for a
#: fare, and nothing in this file is a fare.
UNIT = "index points (base 100)"


def rule(ch: str = "-", n: int = 78) -> str:
    return ch * n


def run() -> dict:
    """Execute the real engine path and collect what each stage produced.

    Every link with a ``t-7`` counterpart is opened up, not just one. The
    fixture deliberately contains both a link where prices moved and a link
    where they did not, and showing both is what demonstrates that the engine
    distinguishes them -- a single link could be either and prove neither.
    """
    obs = two_healthy_chains()
    results, states = run_pipeline(obs, DAYS, expected_cells=2)

    links = []
    for link_date in sorted(obs):
        prior_date = link_date - timedelta(days=7)
        if prior_date not in obs:
            continue
        now, prior = list(obs[link_date]), list(obs[prior_date])
        target = cell_key_for(now[0])
        matched = build_matched_set(now, prior, target, Tier.TIER_1, source_precedence=PRECEDENCE)
        links.append(
            {
                "t": link_date,
                "t_7": prior_date,
                "matched": matched,
                "jevons": compute_jevons(target, link_date, matched.pairs),
            }
        )

    return {
        "observations": sum(len(v) for v in obs.values()),
        "collection_dates": sorted(obs),
        "links": links,
        "results": results,
        "states": states,
    }


def guard_demo(states: list) -> tuple[str, str]:
    """Show the engine REFUSING, which matters as much as it computing.

    Spec R.3: a cell state collected *after* the period being published cannot
    contribute to it. The engine raises rather than quietly dropping the state
    or dating it back -- either of which would publish a number nobody could
    reproduce. This is the same refusal discipline that keeps the real panel's
    index PENDING, shown on data where it can actually be triggered.
    """
    from apix.schemas.enums import Channel, FareClass
    from apix.statistics.aggregation.within_route import within_route_weights
    from apix.statistics.index.apix_l import calculate_apix_l
    from tests.test_pipeline_14_day import FIXTURE_ALLOCATION, ROUTE, vv

    weights = within_route_weights(
        sorted({s.cell for s in states}, key=lambda c: c.sort_key),
        fare_class_shares={FareClass.STANDARD: 1.0},
        channel_shares={Channel.AIRLINE_DIRECT: 1.0},
        carrier_allocation=FIXTURE_ALLOCATION,
    )
    latest = max(states, key=lambda s: s.collection_date)
    try:
        calculate_apix_l(
            [latest],
            weights,
            {ROUTE: 1.0},
            vv(),
            # One day BEFORE the state was collected -- a future-dated state.
            latest.collection_date - timedelta(days=1),
        )
    except ApixLError as exc:
        return "ApixLError", str(exc).splitlines()[0][:160]
    return "NONE", "engine did NOT refuse - this is a defect, investigate"


def console(d: dict) -> None:
    w = print
    w(rule("#"))
    w(f"#  {BANNER}")
    w("#  APIx INDEX ENGINE - live execution over the controlled 14-day fixture")
    w("#  Controlled test data. Not airfare. Not an APIx index value.")
    w(rule("#"))
    w("")

    w("1. FIXTURE (synthetic, hand-checkable)")
    w(rule())
    w(f"   observations           {d['observations']} (SourceType.SYNTHETIC)")
    w(f"   collection dates       {len(d['collection_dates'])}")
    w(f"   publication dates      {len(DAYS)}  {DAYS[0]} .. {DAYS[-1]}")
    w(f"   APW                    {APW_DAYS} days (so travel weekday == collection weekday)")
    w("")

    w("2. MATCHED SETS + JEVONS RELATIVES   (spec D.1, D.3, D.2)")
    w(rule())
    w(f"   {'t':<13}{'t-7':<13}{'tier':<9}{'|M|':>4}{'J(c,t)':>12}")
    for link in d["links"]:
        j = link["jevons"]
        rel = "UNDEFINED" if j.relative is None else f"{j.relative:.6f}"
        w(
            f"   {link['t'].isoformat():<13}{link['t_7'].isoformat():<13}"
            f"{link['matched'].tier.name:<9}{len(link['matched'].pairs):>4}{rel:>12}"
        )
    w("")
    w("   spec D.3 requires |M| >= 3 before a relative is defined.")
    moved = [k for k in d["links"] if k["jevons"].relative not in (None, 1.0)]
    flat = [k for k in d["links"] if k["jevons"].relative == 1.0]
    if moved:
        w(
            f"   {len(moved)} link(s) moved: the fixture scales every price by x1.04 and the"
        )
        w("     Jevons of items all scaled by k is exactly k (INV-4b) - hand-checkable.")
    if flat:
        w(f"   {len(flat)} link(s) flat at exactly 1.000000: unchanged prices give J = 1")
        w("     (INV-3). Note the engine reports 1.0, NOT 'undefined' - a measured")
        w("     no-change and an absent measurement are different statements.")
    w("")

    w("3. CHAINING + PUBLICATION   (spec C.1, E.2/E.4, F.2-F.4)")
    w(rule())
    w(f"   {'publication date':<20}{'level':>12}   {UNIT}")
    for r in d["results"]:
        lvl = f"{r.level:.4f}" if r.level is not None else "SUPPRESSED"
        w(f"   {r.collection_date.isoformat():<20}{lvl:>12}")
    w("")
    w("   The level HOLDS between weekly links and moves ONCE per link.")
    w("   A 7-day relative applied daily would compound 1.04 sevenfold; the")
    w("   test suite asserts that compounded value as FORBIDDEN.")
    w("")

    w("4. REFUSAL / GUARD BEHAVIOUR")
    w(rule())
    exc, msg = guard_demo(d["states"])
    w(f"   future-dated state  ->  {exc}")
    w(f"   {msg}")
    w("   The engine refuses rather than inventing a level. Same discipline")
    w("   that keeps the REAL panel's index PENDING.")
    w("")

    w(rule("#"))
    w(f"#  {BANNER}")
    w(rule("#"))


def html(d: dict) -> str:
    results = [r for r in d["results"] if r.level is not None]
    lo = min(r.level for r in results)
    hi = max(r.level for r in results)
    pad = (hi - lo) * 0.4 or 1.0
    ymin, ymax = lo - pad, hi + pad
    x0, x1, ytop, ybot = 70, 840, 40, 250

    def yy(v: float) -> float:
        return round(ybot - (v - ymin) / (ymax - ymin) * (ybot - ytop), 1)

    n = len(results)
    xs = [round(x0 + (x1 - x0) * i / (n - 1), 1) for i in range(n)]
    pts = " ".join(f"{x},{yy(r.level)}" for x, r in zip(xs, results, strict=True))
    dots = "".join(
        f'<circle cx="{x}" cy="{yy(r.level)}" r="4"/>'
        for x, r in zip(xs, results, strict=True)
    )
    xlab = "".join(
        f'<text x="{x}" y="{ybot + 18}">{r.collection_date.strftime("%d/%m")}</text>'
        for x, r in zip(xs, results, strict=True)
    )
    ylab = "".join(
        f'<text x="{x0 - 8}" y="{yy(ymin + (ymax - ymin) * i / 4) + 4}">'
        f"{ymin + (ymax - ymin) * i / 4:.2f}</text>"
        for i in range(5)
    )
    grid = "".join(
        f'<line x1="{x0}" y1="{yy(ymin + (ymax - ymin) * i / 4)}" '
        f'x2="{x1}" y2="{yy(ymin + (ymax - ymin) * i / 4)}"/>'
        for i in range(5)
    )
    # Watermark is INSIDE the plot area, repeated, so it survives a crop or a
    # screenshot of any part of the chart.
    marks = "".join(
        f'<text x="{x0 + 8 + (i % 2) * 300}" y="{ytop + 45 + (i // 2) * 68}" '
        f'transform="rotate(-15 {x0 + 8 + (i % 2) * 300} {ytop + 45 + (i // 2) * 68})">'
        f"{BANNER}</text>"
        for i in range(6)
    )
    rows = "".join(
        f"<tr><td>{r.collection_date.isoformat()}</td>"
        f"<td class='r'>{'' if r.level is None else f'{r.level:.4f}'}</td>"
        f"<td class='r'>{'yes' if r.published else 'no'}</td></tr>"
        for r in d["results"]
    )
    def link_row(k: dict) -> str:
        rel = k["jevons"].relative
        rel_txt = "undefined" if rel is None else f"{rel:.6f}"
        return (
            f"<tr><td>{k['t']}</td><td>{k['t_7']}</td>"
            f"<td>{k['matched'].tier.name}</td>"
            f"<td class='r'>{len(k['matched'].pairs)}</td>"
            f"<td class='r'>{rel_txt}</td></tr>"
        )

    link_rows = "".join(link_row(k) for k in d["links"])
    moved = sum(1 for k in d["links"] if k["jevons"].relative not in (None, 1.0))
    flat = sum(1 for k in d["links"] if k["jevons"].relative == 1.0)
    guard_exc, guard_msg = guard_demo(d["states"])
    return f"""<title>APIx Engine Validation — Synthetic Fixture</title>
<style>
:root{{--paper:#1A1206;--card:#241A0B;--rule:#4A3714;--ink:#F6EEDF;--ink-2:#C9B48C;
--warn:#F0B429;--mono:ui-monospace,Menlo,monospace}}
*{{box-sizing:border-box}}
body{{background:var(--paper);color:var(--ink);font-family:var(--mono);font-size:14px;line-height:1.6}}
.wrap{{max-width:960px;margin:0 auto;padding:26px 18px 70px;
display:flex;flex-direction:column;gap:22px}}
.band{{background:var(--warn);color:#1A1206;padding:14px 16px;font-weight:700;letter-spacing:.04em;
text-transform:uppercase;border:3px solid #1A1206}}
h1{{font-size:26px;margin:0;text-transform:uppercase;letter-spacing:.03em}}
h2{{font-size:15px;margin:0;color:var(--warn);text-transform:uppercase;letter-spacing:.08em}}
p{{margin:0;color:var(--ink-2);max-width:78ch}}
section{{display:flex;flex-direction:column;gap:10px;border:1px solid var(--rule);
background:var(--card);padding:16px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th,td{{text-align:left;padding:5px 9px;border-bottom:1px solid var(--rule)}}
td.r,th.r{{text-align:right}}
svg{{display:block;max-width:100%;height:auto}}
.kv{{display:grid;grid-template-columns:auto 1fr;gap:4px 16px;font-size:13px}}
.kv b{{color:var(--warn);font-weight:600}}
</style>
<div class="wrap">

<div class="band">{BANNER}</div>

<h1>Engine validation — synthetic fixture</h1>
<p><b>This page contains no market data and no APIx index value.</b> It exists to
show that the index <em>engine</em> computes. Every figure below is derived from
<strong>controlled test data</strong> defined in
<span style="color:var(--warn)">tests/test_pipeline_14_day.py</span>, the fixture CI runs on
every commit. Prices in the fixture are chosen so the arithmetic is hand-checkable.
Values are <strong>{UNIT}</strong> — there are no currency figures anywhere on this page.</p>

<section>
  <h2>What the fixture is</h2>
  <div class="kv">
    <b>observations</b><span>{d["observations"]} synthetic quotes (SourceType.SYNTHETIC)</span>
    <b>collection dates</b><span>{len(d["collection_dates"])}</span>
    <b>publication dates</b><span>{len(DAYS)} consecutive ({DAYS[0]} → {DAYS[-1]})</span>
    <b>advance-purchase</b><span>{APW_DAYS} days</span>
    <b>construction</b><span>two interleaved weekday chains; every price scaled ×1.04 on the
      second link</span>
  </div>
</section>

<section>
  <h2>Matched sets and Jevons relatives — spec D.1, D.3, D.2</h2>
  <table>
    <thead><tr><th>t</th><th>t − 7</th><th>tier</th><th class="r">|M(c,t)|</th>
      <th class="r">J(c,t)</th></tr></thead>
    <tbody>{link_rows}</tbody>
  </table>
  <p>Spec D.3 requires <strong>|M| ≥ 3</strong> before a relative is defined.
  <strong>{moved}</strong> link(s) moved and <strong>{flat}</strong> were flat. The Jevons index
  of items all scaled by <em>k</em> is exactly <em>k</em> (INV-4b), and the fixture scales every
  price by 1.04 — so the moved relatives are verifiable by hand. The flat links report exactly
  1.000000 rather than "undefined": a measured no-change and an absent measurement are different
  statements, and the engine keeps them apart.</p>
</section>

<section>
  <h2>Refusal behaviour — spec R.3</h2>
  <div class="kv">
    <b>input</b><span>a cell state collected <em>after</em> the period being published</span>
    <b>result</b><span>{guard_exc}</span>
    <b>message</b><span>{guard_msg}</span>
  </div>
  <p>The engine raises rather than dropping the state or quietly re-dating it. This is the same
  refusal discipline that keeps the real panel's index <strong>PENDING</strong> — shown here on
  input where it can actually be triggered.</p>
</section>

<section>
  <h2>Chained level over {len(DAYS)} publication dates — {UNIT}</h2>
  <svg viewBox="0 0 880 290" role="img" aria-label="Synthetic fixture index level, base 100">
    <g stroke="var(--rule)" stroke-width="1">{grid}</g>
    <g font-size="11" fill="var(--ink-2)" text-anchor="end">{ylab}</g>
    <polyline fill="none" stroke="var(--warn)" stroke-width="2.5" points="{pts}"/>
    <g fill="var(--warn)">{dots}</g>
    <line x1="{x0}" y1="{ybot}" x2="{x1}" y2="{ybot}" stroke="var(--rule)" stroke-width="1.5"/>
    <g font-size="11" fill="var(--ink-2)" text-anchor="middle">{xlab}</g>
    <g font-size="14" font-weight="700" fill="#F0B429" fill-opacity="0.32"
       text-anchor="start" letter-spacing="1">{marks}</g>
  </svg>
  <p>The level <strong>holds</strong> between weekly links and moves <strong>once</strong> per
  link. A seven-day relative applied daily would compound ×1.04 sevenfold; the test suite
  asserts that compounded value as a forbidden result.</p>
  <table>
    <thead><tr><th>publication date</th><th class="r">level ({UNIT})</th>
      <th class="r">published</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</section>

<section>
  <h2>Why this is not an APIx result</h2>
  <p>APIx's real DEL–BOM panel holds <strong>one</strong> collection wave. Spec §C.1 is locked at
  <em>I(c,t) = I(c,t−7)·J(c,t)</em>, so no matched pair exists and <strong>no real index value is
  computed or published</strong>. This page demonstrates the machinery on controlled input; it
  makes no claim about airfare.</p>
</section>

<div class="band">{BANNER}</div>
</div>"""


def main() -> None:
    d = run()
    console(d)
    if "--html" in sys.argv:
        OUT.write_text(html(d), encoding="utf-8")
        print(f"\nisolated page written: {OUT.relative_to(ROOT)} ({OUT.stat().st_size:,} bytes)")
        print("NOTE: separate file by design - never merged into the real-market dashboard.")


if __name__ == "__main__":
    main()
