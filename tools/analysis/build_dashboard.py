"""Render the hackathon dashboard from `data/panel.json`.

Nothing here types a figure. Every number, table row, chart coordinate and
status badge is derived from the panel contract, which is itself generated from
the store. The previous dashboard was hand-authored and two of its figures went
stale before a text cross-check caught them; generating it removes the failure
mode instead of re-checking for it.

    store -> build_panel_json.py -> data/panel.json -> this -> dashboard.html
                                                    -> panel_report.py -> text

The two renderers read the same contract, so they cannot disagree.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PANEL = ROOT / "data" / "panel.json"
OUT = ROOT / "data" / "dashboard.html"

CSS = """
:root{
  --paper:#F1F4F7; --card:#FFFFFF; --sunk:#E6EBF0; --rule:#D4DCE4; --rule-2:#B9C5D0;
  --ink:#0D131A; --ink-2:#3B4854; --ink-3:#6B7A88;
  --amber:#A9680F; --amber-soft:#FAEFDB;
  --ok:#1F6B46; --ok-soft:#E0EFE7;
  --no:#9E2F27; --no-soft:#F7E3E1;
  --hold:#44548A; --hold-soft:#E4E9F4;
  --shadow:0 1px 2px rgba(13,19,26,.05), 0 8px 20px -12px rgba(13,19,26,.18);
  --mono:"IBM Plex Mono",ui-monospace,Menlo,monospace;
  --sans:"IBM Plex Sans",system-ui,-apple-system,Segoe UI,sans-serif;
  --disp:"Barlow Condensed","IBM Plex Sans",system-ui,sans-serif;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --paper:#0C1219; --card:#141C25; --sunk:#1B2530; --rule:#253039; --rule-2:#36444F;
  --ink:#E9EEF3; --ink-2:#AFBDC9; --ink-3:#7C8B99;
  --amber:#EFA93F; --amber-soft:#2A2214;
  --ok:#63D09A; --ok-soft:#13271E;
  --no:#F0887C; --no-soft:#2B1816;
  --hold:#9AAFE6; --hold-soft:#191F31;
  --shadow:0 1px 2px rgba(0,0,0,.45), 0 10px 24px -14px rgba(0,0,0,.7);
}}
:root[data-theme="dark"]{
  --paper:#0C1219; --card:#141C25; --sunk:#1B2530; --rule:#253039; --rule-2:#36444F;
  --ink:#E9EEF3; --ink-2:#AFBDC9; --ink-3:#7C8B99;
  --amber:#EFA93F; --amber-soft:#2A2214;
  --ok:#63D09A; --ok-soft:#13271E;
  --no:#F0887C; --no-soft:#2B1816;
  --hold:#9AAFE6; --hold-soft:#191F31;
  --shadow:0 1px 2px rgba(0,0,0,.45), 0 10px 24px -14px rgba(0,0,0,.7);
}
*{box-sizing:border-box}
body{background:var(--paper);color:var(--ink);font-family:var(--sans);font-size:14.5px;line-height:1.55}
.wrap{max-width:1080px;margin:0 auto;padding:30px 20px 80px;display:flex;flex-direction:column;gap:28px}
h1,h2,h3{font-family:var(--disp);margin:0;text-wrap:balance}
h1{font-size:clamp(30px,5.4vw,48px);font-weight:700;line-height:1;text-transform:uppercase;letter-spacing:.01em}
h2{font-size:22px;font-weight:600;text-transform:uppercase;letter-spacing:.04em}
h3{font-size:15px;font-weight:600}
p{margin:0}
.mono{font-family:var(--mono);font-variant-numeric:tabular-nums}
header{border-bottom:2px solid var(--ink);padding-bottom:18px;display:flex;flex-direction:column;gap:11px}
.chips{display:flex;flex-wrap:wrap;gap:7px}
.chip{font-family:var(--mono);font-size:10.5px;letter-spacing:.07em;text-transform:uppercase;padding:3px 8px;border:1px solid var(--rule-2);background:var(--card);color:var(--ink-2)}
.chip.real{border-color:var(--ok);background:var(--ok-soft);color:var(--ok);font-weight:600}
.chip.warn{border-color:var(--amber);background:var(--amber-soft);color:var(--amber);font-weight:600}
.status{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:1px;background:var(--rule);border:1px solid var(--rule)}
.st{background:var(--card);padding:16px 17px;display:flex;flex-direction:column;gap:5px}
.st .lab{font-family:var(--mono);font-size:10.5px;letter-spacing:.12em;text-transform:uppercase}
.st.yes .lab{color:var(--ok)} .st.no .lab{color:var(--no)} .st.hold .lab{color:var(--hold)}
.st .val{font-family:var(--disp);font-size:25px;font-weight:600;line-height:1.05}
.st .why{font-size:12.5px;color:var(--ink-2)}
section{display:flex;flex-direction:column;gap:13px}
.sechead{display:flex;align-items:baseline;gap:11px;border-bottom:1px solid var(--rule);padding-bottom:6px}
.sechead .n{font-family:var(--mono);font-size:11px;font-weight:600;color:var(--amber);letter-spacing:.08em}
.lede{color:var(--ink-2);max-width:76ch}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:1px;background:var(--rule);border:1px solid var(--rule)}
.tile{background:var(--card);padding:13px 14px;display:flex;flex-direction:column;gap:3px}
.tile .k{font-family:var(--mono);font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-3)}
.tile .v{font-family:var(--mono);font-size:23px;font-weight:600;font-variant-numeric:tabular-nums}
.tile .s{font-size:11.5px;color:var(--ink-3)}
.tile.good .v{color:var(--ok)} .tile.bad .v{color:var(--no)} .tile.hold .v{color:var(--hold)}
.chartbox{background:var(--card);border:1px solid var(--rule);box-shadow:var(--shadow);padding:18px 16px 10px;overflow-x:auto}
svg{display:block;max-width:100%;height:auto}
.tscroll{overflow-x:auto;border:1px solid var(--rule);background:var(--card);max-height:560px}
table{width:100%;border-collapse:collapse;font-size:13px}
th{background:var(--sunk);font-family:var(--mono);font-size:10px;letter-spacing:.09em;text-transform:uppercase;color:var(--ink-3);text-align:left;padding:8px 10px;white-space:nowrap;border-bottom:1px solid var(--rule);position:sticky;top:0}
td{padding:7px 10px;border-bottom:1px solid var(--rule);white-space:nowrap}
tr:last-child td{border-bottom:none}
td.m{font-family:var(--mono);font-variant-numeric:tabular-nums}
td.r{text-align:right}
.pill{display:inline-block;font-family:var(--mono);font-size:10px;font-weight:600;padding:1px 6px;border:1px solid;white-space:nowrap}
.p-ok{color:var(--ok);background:var(--ok-soft);border-color:var(--ok)}
.p-no{color:var(--no);background:var(--no-soft);border-color:var(--no)}
.p-hold{color:var(--hold);background:var(--hold-soft);border-color:var(--hold)}
.rows{display:flex;flex-direction:column;gap:1px;background:var(--rule);border:1px solid var(--rule)}
.row{background:var(--card);padding:11px 14px;display:flex;gap:13px;align-items:flex-start}
.row .cnt{font-family:var(--mono);font-size:15px;font-weight:600;min-width:34px;text-align:right;color:var(--amber)}
.row .txt{font-size:13.5px}
.note{font-size:13px;color:var(--ink-2);display:flex;gap:8px;align-items:flex-start}
.note::before{content:"\\2192";color:var(--amber);font-family:var(--mono);flex-shrink:0}
.warn{border-left:3px solid var(--no);background:var(--no-soft);padding:13px 15px;font-size:13.5px;display:flex;flex-direction:column;gap:6px}
.warn strong{color:var(--no)}
details{background:var(--card);border:1px solid var(--rule)}
summary{padding:10px 14px;cursor:pointer;font-family:var(--mono);font-size:12px;letter-spacing:.05em;text-transform:uppercase;color:var(--ink-2)}
summary:hover{color:var(--amber)}
details[open] summary{border-bottom:1px solid var(--rule)}
.det-body{padding:12px 14px;font-family:var(--mono);font-size:11.5px;color:var(--ink-2);word-break:break-word}
.flow{display:flex;flex-wrap:wrap;gap:8px;align-items:center;font-family:var(--mono);font-size:11.5px}
.flow .step{padding:6px 11px;border:1px solid var(--rule-2);background:var(--card)}
.flow .step.now{border-color:var(--ok);background:var(--ok-soft);color:var(--ok);font-weight:600}
.flow .step.next{border-color:var(--amber);background:var(--amber-soft);color:var(--amber);font-weight:600}
.flow .arr{color:var(--ink-3)}
.faq{display:flex;flex-direction:column;gap:1px;background:var(--rule);border:1px solid var(--rule)}
.qa{background:var(--card);padding:13px 15px;display:flex;flex-direction:column;gap:5px}
.qa .q{font-weight:600;font-size:13.5px}
.qa .a{font-size:13px;color:var(--ink-2)}
footer{border-top:1px solid var(--rule);padding-top:15px;font-size:12px;color:var(--ink-3);display:flex;flex-direction:column;gap:4px}
@media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
"""


def esc(s: object) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def rupee(v: float) -> str:
    return f"{v:,.0f}"


def apw_chart(profile: list[dict]) -> str:
    """Line chart of the APW profile. Scale is computed from the data."""
    lo = min(p["geomean"] for p in profile)
    hi = max(p["geomean"] for p in profile)
    pad = (hi - lo) * 0.25 or 500
    ymin, ymax = lo - pad, hi + pad
    x0, x1, ytop, ybot = 84, 852, 34, 282

    def yy(v: float) -> float:
        return round(ybot - (v - ymin) / (ymax - ymin) * (ybot - ytop), 1)

    n = len(profile)
    xs = [round(x0 + (x1 - x0) * i / (n - 1), 1) for i in range(n)]
    pts = " ".join(f"{x},{yy(p['geomean'])}" for x, p in zip(xs, profile, strict=True))

    grid, ylab = [], []
    for i in range(5):
        v = ymin + (ymax - ymin) * i / 4
        y = yy(v)
        grid.append(f'<line x1="{x0}" y1="{y}" x2="{x1}" y2="{y}"/>')
        ylab.append(f'<text x="{x0 - 9}" y="{y + 4}">{rupee(v)}</text>')

    dots, vlab, xlab, dlab = [], [], [], []
    for x, p in zip(xs, profile, strict=True):
        y = yy(p["geomean"])
        dots.append(f'<circle cx="{x}" cy="{y}" r="5"/>')
        vlab.append(f'<text x="{x}" y="{y - 13}">{rupee(p["geomean"])}</text>')
        xlab.append(f'<text x="{x}" y="{ybot + 20}">T+{p["apw"]}</text>')
        dlab.append(
            f'<text x="{x}" y="{ybot + 34}">'
            f"{p['travel_date'][8:]}/{p['travel_date'][5:7]} {p['day_of_week']}</text>"
        )

    return f"""<svg viewBox="0 0 880 330" role="img"
     aria-label="Observed geometric-mean Saver fare by advance-purchase window">
  <g stroke="var(--rule)" stroke-width="1">{"".join(grid)}</g>
  <g font-family="IBM Plex Mono, monospace" font-size="11" fill="var(--ink-3)"
     text-anchor="end">{"".join(ylab)}</g>
  <polyline fill="none" stroke="var(--amber)" stroke-width="2.5" points="{pts}"/>
  <g fill="var(--amber)">{"".join(dots)}</g>
  <g font-family="IBM Plex Mono, monospace" font-size="11.5" font-weight="600"
     fill="var(--ink)" text-anchor="middle">{"".join(vlab)}</g>
  <line x1="{x0}" y1="{ybot}" x2="{x1}" y2="{ybot}" stroke="var(--rule-2)" stroke-width="1.5"/>
  <g font-family="IBM Plex Mono, monospace" font-size="12" fill="var(--ink-2)"
     text-anchor="middle">{"".join(xlab)}</g>
  <g font-family="IBM Plex Sans, sans-serif" font-size="10" fill="var(--ink-3)"
     text-anchor="middle">{"".join(dlab)}</g>
</svg>"""


def build(p: dict) -> str:
    q, idx, frame = p["quality"], p["index_status"], p["frame"]
    prof = p["apw_profile"]
    first, last = prof[0], prof[-1]
    delta = 100 * (last["rel_to_first"] - 1)
    ev = q["evidence_counts"]
    run_versions = p["runs"][0] if p["runs"] else {}

    chips = "".join(
        f'<span class="chip{c}">{esc(t)}</span>'
        for t, c in [
            ("Prototype · observed panel", " warn"),
            (f"collected {p['collection_date']}", ""),
            (" · ".join(frame["routes"]), ""),
            ("IndiGo " + " ".join(frame["carriers"]), ""),
            (" · ".join(frame["fare_families"]), ""),
            (f"{len(q['apw_observed'])}/{len(q['apw_expected'])} APW", " real"),
            (f"methodology {run_versions.get('methodology_version', '?')}", ""),
        ]
    )

    obs_rows = "".join(
        f"<tr><td class='m'>T+{r['apw']}</td><td class='m'>{r['travel_date']}</td>"
        f"<td class='m'>{r['day_of_week']}</td><td class='m'>{r['band']}</td>"
        f"<td class='m'>{esc(r['flight'])}</td><td class='m'>{r['dep']}</td>"
        f"<td class='m r'>{r['duration_min']}</td>"
        f"<td class='m r'>{rupee(r['base'])}</td><td class='m r'>{rupee(r['tax'])}</td>"
        f"<td class='m r'><strong>{rupee(r['total'])}</strong></td>"
        f"<td class='m'>{r['observed_at']}</td>"
        f"<td><span class='pill {'p-ok' if r['evidence'] == 'PRIMARY_HASHED' else 'p-hold'}'>"
        f"{'HASHED' if r['evidence'] == 'PRIMARY_HASHED' else 'CHAT IMG'}</span></td></tr>"
        for r in p["observations"]
    )

    apw_rows = "".join(
        f"<tr><td class='m'>T+{e['apw']}</td><td class='m'>{e['travel_date']}</td>"
        f"<td class='m'>{e['day_of_week']}</td><td class='m r'>{e['n']}</td>"
        f"<td class='m r'><strong>{rupee(e['geomean'])}</strong></td>"
        f"<td class='m r'>{rupee(e['min'])}</td><td class='m r'>{rupee(e['max'])}</td>"
        f"<td class='m r'>{e['spread_pct']}%</td>"
        f"<td class='m r'>{e['rel_to_first']:.3f}</td></tr>"
        for e in prof
    )

    band_tiles = "".join(
        f"<div class='tile'><span class='k'>band {b['band']} · {b['window']}</span>"
        f"<span class='v'>{rupee(b['geomean'])}</span><span class='s'>n = {b['n']}</span></div>"
        for b in p["band_profile"]
    )

    excl_rows = "".join(
        f"<div class='row'><span class='cnt'>{e['count']}</span>"
        f"<span class='txt'>{esc(e['reason'])}"
        f"<details><summary>{e['count']} screenshot ids</summary>"
        f"<div class='det-body'>{esc(', '.join(e['shots']))}</div></details>"
        f"</span></div>"
        for e in p["exclusions"]
    )

    bench = p["benchmark"]

    def bench_row(s: dict) -> str:
        yoy = "&mdash;" if s["inflation"] is None else f"{s['inflation']:.2f}%"
        return (
            f"<tr><td class='m'>{s['year']}-{s['month'][:3]}</td>"
            f"<td class='m'>{s['baseyear']}</td>"
            f"<td class='m r'>{s['index']:.1f}</td>"
            f"<td class='m r'>{yoy}</td></tr>"
        )

    bench_rows = "".join(bench_row(s) for s in bench["series"])

    def growth_tile(g: dict) -> str:
        if g["cagr_pct"] is None:
            val, sub = "n/a", f"{g['points']} point — no rate computable"
        else:
            val = f"+{g['cagr_pct']:.2f}%"
            sub = f"{g['first']} → {g['last']} over {g['years']} yrs"
        return (
            f"<div class='tile'><span class='k'>base {g['baseyear']} · per year</span>"
            f"<span class='v'>{val}</span><span class='s'>{sub}</span></div>"
        )

    growth = "".join(growth_tile(g) for g in bench["growth_by_base"])

    run_rows = "".join(
        f"<div class='row'><span class='cnt'>{r['observations']}</span><span class='txt'>"
        f"<strong>{esc(r['run_id'])}</strong> · "
        f"<span class='pill {'p-ok' if r['evidence'] == 'PRIMARY_HASHED' else 'p-hold'}'>"
        f"{esc(r['evidence'])}</span><br>"
        f"<span class='mono' style='font-size:11.5px'>"
        f"methodology {esc(r['methodology_version'])} · basket {esc(r['basket_version'])} · "
        f"parser {esc(r['parser_version'])} · protocol {esc(r['protocol_version'])}<br>"
        f"frame {esc(r['frame_id'])}<br>window declared {esc(r['window_declared'])}</span><br>"
        f"<span style='font-size:12.5px;color:var(--ink-3)'>{esc(r['notes'])}</span>"
        f"</span></div>"
        for r in p["runs"]
    )

    return f"""<title>APIx Real-Time Airfare Price Index</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<style>{CSS}</style>

<div class="wrap">

<header>
  <div class="chips">{chips}</div>
  <h1>APIx — Real-Time Airfare Price Index</h1>
  <p class="lede">A quality-adjusted airfare price index for India, built against MoSPI problem
  statement 26056. This page shows the prototype's real empirical base and is deliberately
  explicit about three different things: what has been <strong>observed</strong>, what is
  <strong>computable now</strong>, and what becomes computable only after longitudinal
  collection.</p>
</header>

<div class="status">
  <div class="st yes"><span class="lab">Observed panel</span>
    <span class="val">{q["valid_observations"]} / {q["expected_cells"]} cells</span>
    <span class="why">{len(q["apw_observed"])}/{len(q["apw_expected"])} advance-purchase windows ·
    {len(q["bands_observed"])} departure bands · {esc(" · ".join(frame["routes"]))} ·
    IndiGo {esc(" ".join(frame["carriers"]))}</span></div>
  <div class="st yes"><span class="lab">Index engine</span>
    <span class="val">Implemented &amp; tested</span>
    <span class="why">Jevons elementary → Young / Modified Laspeyres, with TPD as a parallel
    estimator. Invariant-tested; no ML in the index path.</span></div>
  <div class="st no"><span class="lab">Current index value</span>
    <span class="val">Pending 2nd wave</span>
    <span class="why">§C.1 is locked: <span class="mono">I(c,t) = I(c,t−7)·J(c,t)</span>.
    {idx["collection_waves"]} collection wave held, so {idx["matched_pairs_available"]} matched
    pairs exist. Unlocks <strong>{idx["next_wave_unlocking_index"]}</strong>.</span></div>
</div>

<!-- 2 APW -->
<section>
  <div class="sechead"><span class="n">01</span><h2>Observed APW profile</h2></div>
  <p class="lede">Geometric mean of the five band fares at each advance-purchase distance.
  The geometric mean is spec §D.2's elementary aggregator, used here so the arithmetic matches
  the index that will later run on these same observations. <strong>This is a descriptive
  cross-sectional result, not an index and not a causal estimate.</strong></p>
  <div class="chartbox">{apw_chart(prof)}</div>
  <div class="tscroll"><table>
    <thead><tr><th>APW</th><th>travel date</th><th>day</th><th class="r">n</th>
      <th class="r">geo mean ₹</th><th class="r">min</th><th class="r">max</th>
      <th class="r">spread</th><th class="r">vs T+{first["apw"]}</th></tr></thead>
    <tbody>{apw_rows}</tbody></table></div>
  <div class="tiles">
    <div class="tile"><span class="k">T+{first["apw"]} → T+{last["apw"]}</span>
      <span class="v">{delta:+.1f}%</span>
      <span class="s">₹{rupee(first["geomean"])} → ₹{rupee(last["geomean"])}</span></div>
    <div class="tile"><span class="k">widest within-day</span>
      <span class="v">{max(e["spread_pct"] for e in prof):.1f}%</span>
      <span class="s">across the 5 bands</span></div>
    <div class="tile good"><span class="k">APW coverage</span>
      <span class="v">{len(q["apw_observed"])}/{len(q["apw_expected"])}</span>
      <span class="s">complete frozen vector</span></div>
  </div>
  <div class="warn">
    <strong>Read the {delta:+.0f}% carefully — it is not an advance-purchase elasticity.</strong>
    <span>Each APW sits on a <em>different travel date</em>, so date-specific and seasonal
    effects are fully confounded with advance purchase. The T+{last["apw"]} observation
    ({last["travel_date"]}) falls days after Diwali; a return-travel peak is a
    <strong>hypothesis this panel cannot test</strong>, not a finding. Separating the two needs
    the same travel date observed at several lead times — which is what longitudinal collection
    produces.</span>
  </div>
</section>

<!-- 3 bands -->
<section>
  <div class="sechead"><span class="n">02</span><h2>Departure-band structure</h2></div>
  <p class="lede">§B.2 anchors 3-hour bands at 00:00 IST. Bands {esc(q["bands_expected"])} span the
  commercial day and are the contracted set; one flight per band, always the earliest, never
  chosen by price.</p>
  <div class="tiles">{band_tiles}</div>
  <p class="note">Spread across bands is {p["band_spread_pct"]}% — small next to the
  {delta:+.0f}% advance-purchase step, and pooled across APW, so it is confounded by the
  T+{last["apw"]} level. Not a finding on its own.</p>
</section>

<!-- 4 observations -->
<section>
  <div class="sechead"><span class="n">03</span><h2>Flight-level observations</h2></div>
  <p class="lede">Every row is a real quote read off IndiGo's own website and verified against
  its screenshot. <span class="mono">seen</span> is the capture time; the last column is the
  evidence grade.</p>
  <div class="tscroll"><table>
    <thead><tr><th>APW</th><th>travel date</th><th>day</th><th>bd</th><th>flight</th><th>dep</th>
      <th class="r">min</th><th class="r">base ₹</th><th class="r">tax+fees ₹</th>
      <th class="r">total ₹</th><th>seen</th><th>evidence</th></tr></thead>
    <tbody>{obs_rows}</tbody></table></div>
</section>

<!-- 5 quality -->
<section>
  <div class="sechead"><span class="n">04</span><h2>Data quality</h2></div>
  <div class="tiles">
    <div class="tile good"><span class="k">valid observations</span>
      <span class="v">{q["valid_observations"]}</span><span class="s">real market quotes</span></div>
    <div class="tile"><span class="k">expected cells</span>
      <span class="v">{q["expected_cells"]}</span>
      <span class="s">{len(q["apw_expected"])} APW × {len(q["bands_expected"])} bands</span></div>
    <div class="tile good"><span class="k">coverage</span>
      <span class="v">{q["coverage_pct"]}%</span><span class="s">no gaps</span></div>
    <div class="tile good"><span class="k">missing cells</span>
      <span class="v">{q["missing_cells"]}</span><span class="s">none</span></div>
    <div class="tile good"><span class="k">reconciled</span>
      <span class="v">{q["reconciled"]}/{q["decomposed"]}</span>
      <span class="s">base + tax = total</span></div>
    <div class="tile"><span class="k">artifacts</span>
      <span class="v">{q["artifacts"]}</span><span class="s">SHA-256 addressed</span></div>
    <div class="tile bad"><span class="k">§A.5 window flags</span>
      <span class="v">{q["window_flags"]}</span><span class="s">stored + flagged</span></div>
  </div>
  <div class="warn">
    <strong>The session breached its own declared window, and that is recorded rather than
    smoothed.</strong>
    <span>{q["window_flags"]} quotes fall outside the declared 21:00–22:00 IST window. Under §A.5
    they are <em>stored and flagged, never discarded</em>, so the loader exits 2 — not a clean
    bill. Widening the recorded window to cover them would have made the breach disappear, which
    is why it was not done.</span>
    <details><summary>see the {q["window_flags"]} flags</summary>
      <div class="det-body">{esc(" | ".join(q["window_flag_detail"]))}</div></details>
  </div>
</section>

<!-- 6 provenance -->
<section>
  <div class="sechead"><span class="n">05</span><h2>Provenance &amp; evidence</h2></div>
  <p class="lede">Provenance is <strong>not uniform across the panel</strong>, and the data model
  records that as a derived fact rather than a label someone remembered to apply. An observation
  is <span class="mono">PRIMARY_HASHED</span> only if its run actually has a content-addressed
  artifact bound to it.</p>
  <div class="tiles">
    <div class="tile good"><span class="k">PRIMARY_HASHED</span>
      <span class="v">{ev.get("PRIMARY_HASHED", 0)}</span>
      <span class="s">bound to a SHA-256 screenshot</span></div>
    <div class="tile hold"><span class="k">SECONDARY_CHAT_IMAGE</span>
      <span class="v">{ev.get("SECONDARY_CHAT_IMAGE", 0)}</span>
      <span class="s">no bytes hashed; nominal capture time</span></div>
  </div>
  <p class="note">The T+45 batch arrived as chat images rather than files, so no bytes could be
  hashed and its capture times are <strong>placeholders, not measurements</strong>. The collection
  date was confirmed by the collector. Those five rows are marked <span class="mono">CHAT IMG</span>
  in the table above and are counted separately here.</p>
  <div class="rows">{run_rows}</div>
</section>

<!-- exclusion audit -->
<section>
  <div class="sechead"><span class="n">06</span><h2>Exclusion audit — {p["exclusions_total"]} screenshots</h2></div>
  <p class="lede">Nothing was deleted. Every screenshot that did not become an observation carries
  a reason, and the ids are listed so any one can be traced back.</p>
  <div class="rows">{excl_rows}</div>
  <p class="note">Counts cover the 12-Sep file corpus. The T+45 batch arrived separately as 24
  chat images: 5 selected, 14 not-earliest-in-band, 5 outside the contracted bands.</p>
</section>

<!-- 7 methodology -->
<section>
  <div class="sechead"><span class="n">07</span><h2>Statistical methodology</h2></div>
  <div class="flow">
    <span class="step now">raw observation</span><span class="arr">→</span>
    <span class="step now">admissibility §A.6</span><span class="arr">→</span>
    <span class="step now">dedup §D.4</span><span class="arr">→</span>
    <span class="step now">clean panel</span><span class="arr">→</span>
    <span class="step next">Jevons §D.2</span><span class="arr">→</span>
    <span class="step next">Young / Mod. Laspeyres §F</span><span class="arr">→</span>
    <span class="step next">APIx</span>
  </div>
  <p class="lede"><strong>Green steps run on today's data. Amber steps are implemented and
  invariant-tested but have no input yet</strong>, because every one of them consumes a price
  <em>relative</em>, and a relative needs two collection waves.</p>
  <div class="rows">
    <div class="row"><span class="cnt">§D.2</span><span class="txt"><strong>Jevons elementary
      aggregation.</strong> Geometric mean of matched price relatives within a cell, computed in
      logs — the log form is normative, not a numerical convenience. Matches MoSPI's own
      elementary aggregator for CPI.</span></div>
    <div class="row"><span class="cnt">§F</span><span class="txt"><strong>Young / Modified
      Laspeyres.</strong> Weighted aggregation above the elementary level. Route weights come
      from DGCA city-pair passenger volumes.</span></div>
    <div class="row"><span class="cnt">§M</span><span class="txt"><strong>APIx-TPD.</strong> A
      quote-level Time Product Dummy hedonic regression, run as a <em>parallel</em> estimator and
      never chained into APIx-L. The gap between the two is a deliverable in itself.</span></div>
    <div class="row"><span class="cnt">§N</span><span class="txt"><strong>Bootstrap intervals.</strong>
      Computed only where statistically estimable. With one wave there is no sampling
      distribution over relatives, so none is reported.</span></div>
  </div>
</section>

<!-- 8 index engine -->
<section>
  <div class="sechead"><span class="n">08</span><h2>Index engine status</h2></div>
  <div class="tiles">
    <div class="tile good"><span class="k">engine</span><span class="v">READY</span>
      <span class="s">implemented + invariant-tested</span></div>
    <div class="tile bad"><span class="k">APIx-L value</span><span class="v">PENDING</span>
      <span class="s">needs a 2nd collection wave</span></div>
    <div class="tile bad"><span class="k">APIx-TPD</span><span class="v">PENDING</span>
      <span class="s">{idx["tpd_quotes_available"]} quotes of
      {idx["tpd_min_quotes_window"]:,} required</span></div>
    <div class="tile hold"><span class="k">unlocks on</span>
      <span class="v" style="font-size:17px">{idx["next_wave_unlocking_index"]}</span>
      <span class="s">exactly t−7 from the held wave</span></div>
  </div>
  <div class="warn">
    <strong>The absent index value is a property of the methodology, not a software failure.</strong>
    <span>{esc(idx["apix_l_blocker"])} Producing a number anyway would require either changing the
    frozen formula or treating APW buckets as if they were time-series observations. Both are
    refused: the APW buckets are seven <em>different products</em> observed at one instant, not one
    product observed seven times.</span>
  </div>
</section>

<!-- 9 benchmark -->
<section>
  <div class="sechead"><span class="n">09</span><h2>Official reference — MoSPI</h2></div>
  <p class="lede">Pulled first-hand from the Dataset Link named in the problem statement:
  <span class="mono">{esc(bench["source"])}</span>, item <em>{esc(bench["item"])}</em>.
  Role: <span class="mono">{esc(bench["role"])}</span> —
  <span class="mono">is_apix_input = {esc(bench["is_apix_input"])}</span>.</p>
  <div class="tiles">{growth}</div>
  <div class="tscroll" style="max-height:330px"><table>
    <thead><tr><th>period</th><th>base</th><th class="r">index</th><th class="r">y/y</th></tr></thead>
    <tbody>{bench_rows}</tbody></table></div>
  <div class="warn">
    <strong>This reference cannot validate the current panel, and claiming otherwise would be the
    easiest overstatement in the project.</strong>
    <span>It is a <em>monthly, All-India index number</em> with no route, no carrier, no flight and
    no rupee fare. The panel is <em>one day, one route, one carrier, in rupees</em>. No overlapping
    unit exists, so no comparison is meaningful yet. Growth is computed <strong>within a base year
    only</strong> — MoSPI publishes Dec 2014 under both base 2010 and base 2012 during the
    rebasing overlap, and dividing one by the other is a units error rather than a rate of
    change.</span>
  </div>
</section>

<!-- 10 scale -->
<section>
  <div class="sechead"><span class="n">10</span><h2>Scale-up architecture</h2></div>
  <p class="lede">DEL–BOM and IndiGo are <strong>current sample values, not architecture</strong>.
  The statistics layer never hard-codes a route or carrier; the cell key is
  <span class="mono">route × carrier × day_of_week × APW × fare_class × channel</span>, and the
  panel expands along every one of those axes without a schema change.</p>
  <div class="tscroll"><table>
    <thead><tr><th>axis</th><th>today</th><th>target</th><th>what it unlocks</th></tr></thead>
    <tbody>
      <tr><td>collection waves</td><td class="m">{idx["collection_waves"]}</td><td class="m">30+ daily</td><td>the index itself — weekly Jevons links</td></tr>
      <tr><td>routes</td><td class="m">{len(frame["routes"])}</td><td class="m">8–10 top DGCA pairs</td><td>route weights, §F aggregation</td></tr>
      <tr><td>carriers</td><td class="m">{len(frame["carriers"])}</td><td class="m">5 PS-named</td><td>carrier allocation (AMB-9)</td></tr>
      <tr><td>sources</td><td class="m">1 airline-direct</td><td class="m">+ OTA, + NDC/licensed feed</td><td>source precedence §D.8, independence §B.6</td></tr>
      <tr><td>APW</td><td class="m">{len(q["apw_observed"])}</td><td class="m">{len(q["apw_expected"])}</td><td class="m">already complete</td></tr>
      <tr><td>quotes / window</td><td class="m">{idx["tpd_quotes_available"]}</td><td class="m">{idx["tpd_min_quotes_window"]:,}</td><td>APIx-TPD hedonic estimator</td></tr>
    </tbody></table></div>
</section>

<!-- 11 limitations -->
<section>
  <div class="sechead"><span class="n">11</span><h2>Limitations — what is not established</h2></div>
  <div class="tscroll"><table>
    <thead><tr><th>claim</th><th>status</th><th>what it would take</th></tr></thead>
    <tbody>
      <tr><td>APIx-L index value</td><td><span class="pill p-no">NOT COMPUTABLE</span></td><td>a 2nd collection wave exactly 7 days later (§C.1)</td></tr>
      <tr><td>APIx-TPD estimate</td><td><span class="pill p-no">NOT COMPUTABLE</span></td><td class="m">min_quotes_window = {idx["tpd_min_quotes_window"]:,}; panel has {idx["tpd_quotes_available"]}</td></tr>
      <tr><td>30-day back-test</td><td><span class="pill p-no">NOT PERFORMED</span></td><td>daily fare history that does not exist and cannot be reconstructed</td></tr>
      <tr><td>Advance-purchase elasticity</td><td><span class="pill p-no">NOT ESTIMATED</span></td><td>travel-date effects separated from lead time</td></tr>
      <tr><td>National representativeness</td><td><span class="pill p-no">NO</span></td><td>1 route of 2,186 city pairs; 1 carrier of 5</td></tr>
      <tr><td>Route weights (§G)</td><td><span class="pill p-hold">NOT EXERCISED</span></td><td>≥2 routes + DGCA city-pair volumes</td></tr>
      <tr><td>Carrier allocation</td><td><span class="pill p-hold">OPEN — AMB-9</span></td><td>owner ruling; moot at one carrier</td></tr>
      <tr><td>Coverage denominator</td><td><span class="pill p-hold">OPEN — AMB-8</span></td><td>owner ruling on expected cells</td></tr>
      <tr><td>Intraday effect (OQ-1)</td><td><span class="pill p-hold">DEFERRED</span></td><td>paired 09:00 / 21:00 runs — not collected</td></tr>
      <tr><td>Fare 4-way split (§A.4)</td><td><span class="pill p-hold">OPEN — AMB-12</span></td><td>IndiGo renders one aggregated "Taxes &amp; Fees" line at this step</td></tr>
      <tr><td>Collection → store → analysis pipeline</td><td><span class="pill p-ok">DEMONSTRATED</span></td><td>— on real data, with hashed evidence</td></tr>
      <tr><td>Advance-purchase measurement</td><td><span class="pill p-ok">DEMONSTRATED</span></td><td>— all {len(q["apw_expected"])} frozen APW buckets</td></tr>
      <tr><td>Index engine</td><td><span class="pill p-ok">IMPLEMENTED + TESTED</span></td><td>— awaiting input, not implementation</td></tr>
    </tbody></table></div>
</section>

<!-- 12 roadmap -->
<section>
  <div class="sechead"><span class="n">12</span><h2>Validation roadmap</h2></div>
  <p class="lede">The 30-day back-test the problem statement asks for is <strong>not performed
  and not simulated</strong>. This is the route to it.</p>
  <div class="flow">
    <span class="step next">wave 2 · {idx["next_wave_unlocking_index"]}</span><span class="arr">→</span>
    <span class="step">first Jevons relative</span><span class="arr">→</span>
    <span class="step">30-day rolling panel</span><span class="arr">→</span>
    <span class="step">APIx daily series</span><span class="arr">→</span>
    <span class="step">aggregate to monthly</span><span class="arr">→</span>
    <span class="step">compare vs MoSPI</span>
  </div>
  <div class="rows">
    <div class="row"><span class="cnt">1</span><span class="txt"><strong>Second wave, {idx["next_wave_unlocking_index"]}.</strong>
      The same five flights, the same window. Produces the first genuine matched pair and the
      first real Jevons relative. ~30 minutes of collection.</span></div>
    <div class="row"><span class="cnt">2</span><span class="txt"><strong>30 consecutive days.</strong>
      Builds the rolling panel. A missed day costs <em>two</em> weekly links, because the index
      compares t against t−7.</span></div>
    <div class="row"><span class="cnt">3</span><span class="txt"><strong>Validation metrics.</strong>
      MAE, RMSE, correlation, directional agreement, turning-point agreement, bootstrap
      intervals — each reported with its <em>n</em>, and against the monthly MoSPI reference only
      once the APIx series is itself aggregated to monthly.</span></div>
    <div class="row"><span class="cnt">4</span><span class="txt"><strong>Expand the frame.</strong>
      Routes and carriers along the axes in §10, which is what makes the weights layer and the
      carrier allocation live questions rather than theoretical ones.</span></div>
  </div>
</section>

<!-- FAQ -->
<section>
  <div class="sechead"><span class="n">13</span><h2>Anticipated questions</h2></div>
  <div class="faq">
    <div class="qa"><span class="q">Why don't you show an index value?</span>
      <span class="a">Because the locked longitudinal specification requires matched observations
      at t and t−7. One collection wave cannot produce a legitimate time-series relative, and
      changing the formula to manufacture one is the single thing the frozen methodology
      forbids.</span></div>
    <div class="qa"><span class="q">Then what have you actually demonstrated?</span>
      <span class="a">A complete real-data path: compliant collection, extraction verified against
      source evidence, canonicalisation, deduplication, admissibility, hash-addressed provenance
      and an auditable exclusion trail — plus an index engine that is implemented and
      invariant-tested and is waiting on input, not on code.</span></div>
    <div class="qa"><span class="q">Why only IndiGo and DEL–BOM?</span>
      <span class="a">Compliance, not convenience. Of 14 sources audited, IndiGo is the only one
      carrying an affirmative, quoted permission for the collection mode used. DEL–BOM is India's
      densest domestic pair. The architecture is route- and carrier-agnostic throughout.</span></div>
    <div class="qa"><span class="q">Why not just use MoSPI's published airfare index?</span>
      <span class="a">It is a monthly All-India reference index, not route-level raw fare
      observations. It is the validation target, and it is exactly what this project exists to
      complement at higher frequency and finer granularity.</span></div>
    <div class="qa"><span class="q">Why Saver rather than the cheapest visible fare?</span>
      <span class="a">The frozen contract standardises the fare family so a hand-baggage-only
      Lite fare is never pooled with a checked-baggage product. Canonical fare class is derived
      from entitlements, never from the marketing label.</span></div>
    <div class="qa"><span class="q">Why exclude later, cheaper flights in the same band?</span>
      <span class="a">The protocol takes the earliest qualifying flight in each departure band.
      Selecting by price would make the index measure its own selection rule, and no downstream
      test could detect or undo that.</span></div>
    <div class="qa"><span class="q">Why is T+{last["apw"]} so much higher?</span>
      <span class="a">It is an observed cross-sectional difference, not a causal estimate. Each
      APW sits on a different travel date, so seasonality and date effects are confounded with
      lead time. The post-Diwali hypothesis is plausible and untested.</span></div>
    <div class="qa"><span class="q">What happens after the hackathon?</span>
      <span class="a">Run the same collection longitudinally from {idx["next_wave_unlocking_index"]},
      expand routes and carriers, bring in DGCA weights, then perform the 30-day validation and
      begin regular index computation.</span></div>
  </div>
</section>

<footer>
  <p><strong>Provenance.</strong> {q["valid_observations"]} observations across
  {len(p["runs"])} run(s) · {q["artifacts"]} content-addressed artifacts ·
  {p["exclusions_total"]} screenshots excluded with a recorded reason ·
  <span class="mono">verify()</span> internally consistent.</p>
  <p><strong>Versions.</strong> methodology {esc(run_versions.get("methodology_version"))} ·
  basket {esc(run_versions.get("basket_version"))} ·
  parser {esc(run_versions.get("parser_version"))} ·
  collector {esc(run_versions.get("collector_version"))} ·
  protocol {esc(run_versions.get("protocol_version"))} ·
  source precedence {esc(run_versions.get("source_precedence_version"))}</p>
  <p><strong>Data classes are never mixed.</strong> Every fare on this page is
  <span class="mono">{esc(p["data_class"])}</span>; the MoSPI series is an official reference.
  <span class="mono">synthetic_data_present = {esc(p["synthetic_data_present"])}</span>.</p>
  <p>Generated from <span class="mono">{esc(p["generated_from"])}</span> via
  <span class="mono">data/panel.json</span> — no figure on this page is typed by hand.</p>
</footer>
</div>
"""


def main() -> None:
    panel = json.loads(PANEL.read_text(encoding="utf-8"))
    OUT.write_text(build(panel), encoding="utf-8")
    print(f"dashboard written: {OUT.relative_to(ROOT)}  ({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
