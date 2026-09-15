"""Generate ``data/platform.html`` — the platform console, from the API payloads.

The editorial dashboard (``build_dashboard.py``) tells the measurement story.
This page shows the **platform**: what the scheduler did, which sources are
refused and why, the period series, the heatmap, the lead-time profile, the
backtest verdict and the API contract. PS 26056 requirement 6 and 10.

It renders **exactly the payloads the API serves** (:mod:`apix.api.payloads`),
so a number here is a number at an endpoint. Generated, never hand-authored;
inline SVG for every chart; no network; the same vendored fonts and design
tokens as the dashboard.

Every figure carries its output class. A DEMO series is labelled DEMO in the
same type size as the number.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dashboard_theme import CSS, FONT_HREF  # noqa: E402
from dashboard_viz import apw_chart, esc, rupee  # noqa: E402

from apix.api import payloads  # noqa: E402
from apix.series import Frequency  # noqa: E402

OUT = ROOT / "data" / "platform.html"

SECTIONS = [
    ("overview", "Overview"),
    ("trends", "Index trends"),
    ("heatmap", "Routes"),
    ("leadtime", "Lead time"),
    ("acquisition", "Acquisition"),
    ("sources", "Source health"),
    ("runs", "Collection runs"),
    ("quality", "Data quality"),
    ("provenance", "Provenance"),
    ("backtest", "Backtest"),
    ("methodology", "Methodology"),
    ("architecture", "Architecture"),
]

# Platform-specific rules layered on the dashboard tokens. Semantic status
# colours are separate from the amber signal colour, so status never reads as
# emphasis and emphasis never reads as status.
PLATFORM_CSS = """
.pf{max-width:1180px;margin:0 auto;padding:0 20px}
.pf-hero{padding:56px 0 28px;border-bottom:1px solid var(--line)}
.pf-hero .k{font-family:var(--mono);font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--amber-ink)}
.pf-hero h1{font-size:clamp(34px,5vw,58px);line-height:1.02;margin:10px 0 12px;letter-spacing:-.025em}
.pf-hero p{max-width:62ch;color:var(--ink-2);font-size:17px;margin:0}
.pf-status{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:1px;background:var(--line);border:1px solid var(--line);margin:26px 0 0}
.pf-status div{background:var(--card);padding:14px 16px}
.pf-status b{font-family:var(--mono);font-size:22px;display:block;letter-spacing:-.02em;font-variant-numeric:tabular-nums;overflow-wrap:anywhere}
.pf-status b.s{font-size:15px;line-height:1.35;padding-top:4px}
.pf-status span{font-size:12px;color:var(--ink-3)}
.pf-status .blk b{color:var(--red)} .pf-status .ok b{color:var(--green)} .pf-status .wn b{color:var(--amber-ink)}
.pf-nav{position:sticky;top:0;z-index:5;background:var(--paper);border-bottom:1px solid var(--line);display:flex;flex-wrap:wrap;gap:2px 16px;padding:10px 0;font-family:var(--mono);font-size:11.5px;letter-spacing:.06em}
.pf-nav a{color:var(--ink-2);text-decoration:none;padding:4px 0}.pf-nav a:hover{color:var(--amber-ink)}
.pf-nav .tag{margin-left:auto;background:var(--red-wash);color:var(--red);padding:3px 9px;border-radius:2px;font-weight:600}
section.pf-s{padding:44px 0 8px;border-bottom:1px solid var(--line-2)}
section.pf-s>h2{font-size:clamp(22px,2.6vw,28px);letter-spacing:-.02em;margin:0 0 6px}
section.pf-s>h2 small{font-family:var(--mono);font-size:11px;color:var(--amber-ink);letter-spacing:.1em;margin-right:12px;vertical-align:middle}
.sub{color:var(--ink-3);font-size:13.5px;margin:0 0 18px;max-width:72ch}
.cls{display:inline-block;font-family:var(--mono);font-size:10.5px;letter-spacing:.08em;padding:2px 7px;border:1px solid;border-radius:2px;vertical-align:middle}
.cls.DEMO{color:var(--amber-ink);border-color:var(--amber);background:var(--amber-wash)}
.cls.RESEARCH{color:var(--blue);border-color:var(--blue);background:var(--blue-wash)}
.cls.PRODUCTION{color:var(--green);border-color:var(--green);background:var(--green-wash)}
.cls.BLOCKED,.cls.PERMISSION_BLOCKED{color:var(--red);border-color:var(--red);background:var(--red-wash)}
.cls.INCOMPLETE,.cls.NO_DATA,.cls.PROVISIONAL{color:var(--amber-ink);border-color:var(--amber);background:var(--amber-wash)}
.tw{overflow-x:auto;border:1px solid var(--line);background:var(--card);margin:0 0 18px}
table.pf{border-collapse:collapse;width:100%;font-size:13px;min-width:560px}
table.pf th,table.pf td{text-align:left;padding:8px 11px;border-bottom:1px solid var(--line-2);vertical-align:top}
table.pf thead th{font-family:var(--mono);font-size:10.5px;letter-spacing:.09em;text-transform:uppercase;color:var(--ink-3);background:var(--paper-2);white-space:nowrap}
table.pf td.n{font-family:var(--mono);font-variant-numeric:tabular-nums;white-space:nowrap}
table.pf tr:last-child td{border-bottom:none}
.note{border-left:3px solid var(--amber);background:var(--card);padding:12px 16px;margin:0 0 18px;font-size:13.5px;max-width:78ch}
.note.red{border-left-color:var(--red)} .note.green{border-left-color:var(--green)}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:18px;margin:0 0 18px}
svg.pf{width:100%;height:auto;display:block;background:var(--card);border:1px solid var(--line)}
.arch{font-family:var(--mono);font-size:12px;line-height:1.55;background:var(--card);border:1px solid var(--line);padding:16px 18px;overflow-x:auto;white-space:pre;margin:0 0 18px}
.ep{font-family:var(--mono);font-size:12.5px}
ul.tight{margin:0 0 16px;padding-left:20px;max-width:72ch}ul.tight li{margin-bottom:5px}
@media(max-width:700px){.pf-hero{padding:36px 0 22px}}
"""


def cls(v: str) -> str:
    return f'<span class="cls {esc(v)}">{esc(v)}</span>'


def table(cols: list[tuple[str, str]], rows: list[dict], numeric: set[str] = frozenset()) -> str:
    head = "".join(f"<th>{esc(label)}</th>" for _, label in cols)
    body = []
    for r in rows:
        cells = []
        for key, _ in cols:
            v = r.get(key, "")
            if isinstance(v, float):
                v = f"{v:.4f}"
            klass = ' class="n"' if key in numeric else ""
            cells.append(
                f"<td{klass}>{v if isinstance(v, str) and v.startswith('<span') else esc('' if v is None else v)}</td>"
            )
        body.append("<tr>" + "".join(cells) + "</tr>")
    return f'<div class="tw"><table class="pf"><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


def series_svg(points: list[dict], title: str) -> str:
    """A period series as an inline SVG line. One scale, ticks computed."""
    pts = [p for p in points if p["level"] is not None]
    W, H, L, R, T, B = 900, 300, 62, 20, 30, 56
    if not pts:
        return f'<svg class="pf" viewBox="0 0 {W} {H}"><text x="{W / 2}" y="{H / 2}" text-anchor="middle" fill="var(--ink-3)" font-size="14">no computable level</text></svg>'
    lo = min(p["level"] for p in pts)
    hi = max(p["level"] for p in pts)
    pad = (hi - lo) * 0.25 or 1
    lo, hi = lo - pad, hi + pad
    iw, ih = W - L - R, H - T - B
    n = len(pts)

    def x(i: int) -> float:
        return L + (iw * (i + 0.5) / max(n, 1))

    def y(v: float) -> float:
        return T + ih - (v - lo) / (hi - lo) * ih

    ticks = [lo + (hi - lo) * k / 4 for k in range(5)]
    grid = "".join(
        f'<line x1="{L}" x2="{W - R}" y1="{y(t):.1f}" y2="{y(t):.1f}" stroke="var(--line-2)"/>'
        f'<text x="{L - 8}" y="{y(t) + 4:.1f}" text-anchor="end" font-size="11" fill="var(--ink-3)" font-family="var(--mono)">{t:.1f}</text>'
        for t in ticks
    )
    path = " ".join(
        f"{'M' if i == 0 else 'L'}{x(i):.1f},{y(p['level']):.1f}" for i, p in enumerate(pts)
    )
    dots = "".join(
        f'<circle cx="{x(i):.1f}" cy="{y(p["level"]):.1f}" r="3.5" fill="var(--amber)"/>'
        for i, p in enumerate(pts)
    )
    labels = "".join(
        f'<text x="{x(i):.1f}" y="{H - B + 22}" text-anchor="middle" font-size="10.5" fill="var(--ink-3)" font-family="var(--mono)">{esc(p["period"])}</text>'
        for i, p in enumerate(pts)
        if n <= 8 or i % max(1, n // 7) == 0
    )
    return (
        f'<svg class="pf" viewBox="0 0 {W} {H}" role="img" aria-label="{esc(title)}">'
        f'<text x="{L}" y="18" font-size="12" fill="var(--ink-2)" font-family="var(--mono)">{esc(title)}</text>'
        f'{grid}<path d="{path}" fill="none" stroke="var(--amber)" stroke-width="2.2"/>{dots}{labels}</svg>'
    )


def heatmap_svg(routes: list[dict], observed: set[str]) -> str:
    """Origin x destination grid. A cell is filled ONLY where real observations exist.

    Five of six demo routes hold zero observations and are drawn as such. The
    honest heatmap has one cell, and the empty cells are the coverage finding.
    """
    codes = sorted({r["origin"] for r in routes} | {r["destination"] for r in routes})
    n = len(codes)
    cell, L, T = 72, 70, 50
    W, H = L + n * cell + 20, T + n * cell + 20
    idx = {c: i for i, c in enumerate(codes)}
    cells = []
    for r in routes:
        i, j = idx[r["destination"]], idx[r["origin"]]
        has = r["pair"] in observed
        fill = "var(--amber)" if has else "var(--paper-2)"
        txt = f"{r['observations_held']} obs" if has else "no data"
        col = "var(--paper)" if has else "var(--ink-3)"
        cells.append(
            f'<rect x="{L + i * cell + 2}" y="{T + j * cell + 2}" width="{cell - 4}" height="{cell - 4}" fill="{fill}" stroke="var(--line)"/>'
            f'<text x="{L + i * cell + cell / 2}" y="{T + j * cell + cell / 2 + 4}" text-anchor="middle" font-size="11" fill="{col}" font-family="var(--mono)">{esc(txt)}</text>'
        )
    axes = "".join(
        f'<text x="{L + i * cell + cell / 2}" y="{T - 12}" text-anchor="middle" font-size="12" font-family="var(--mono)" fill="var(--ink-2)">{c}</text>'
        f'<text x="{L - 10}" y="{T + i * cell + cell / 2 + 4}" text-anchor="end" font-size="12" font-family="var(--mono)" fill="var(--ink-2)">{c}</text>'
        for i, c in enumerate(codes)
    )
    return (
        f'<svg class="pf" viewBox="0 0 {W} {H}" role="img" aria-label="Route heatmap: observations held per sector">'
        f'<text x="{L}" y="18" font-size="12" fill="var(--ink-2)" font-family="var(--mono)">rows: origin · columns: destination · metric: real observations held</text>'
        f"{axes}{''.join(cells)}</svg>"
    )


def build() -> str:
    sources = payloads.sources()
    routes = payloads.routes()["data"]
    obs = payloads.observations()["data"]
    cov = payloads.coverage()["data"]
    lt = payloads.lead_time()["data"]
    bt = payloads.backtest()["data"]
    cfg = payloads.config()["data"]
    real_idx = payloads.index(Frequency.DAILY)
    demo = {f: payloads.index(f, demo=True)["data"]["series"] for f in Frequency}
    run = cov["scheduled_run"]
    demo_basket = next(b for b in routes["baskets"] if b["status"] == "DEMO")
    observed = set(routes["routes_with_real_observations"])
    src_rows = [
        {
            **s,
            "automation_gate": cls(s["automation_gate"] or "UNKNOWN"),
            "operational_status": cls(s["operational_status"]),
            "data_rights": cls(s.get("data_rights") or "RETENTION_UNKNOWN"),
        }
        for s in sources["data"]["sources"]
    ]
    by_gate: dict[str, int] = {}
    for s in sources["data"]["sources"]:
        by_gate[s["automation_gate"] or "UNKNOWN"] = (
            by_gate.get(s["automation_gate"] or "UNKNOWN", 0) + 1
        )
    nav = "".join(f'<a href="#{i}">{esc(label)}</a>' for i, label in SECTIONS)
    exclusions = payloads.panel()["exclusions"]
    lt_rows = [
        {
            **a,
            "ps": "PS 26056" if a["in_ps_26056_set"] else "APIx research",
            "geomean": rupee(a["geomean"]),
            "min": rupee(a["min"]),
            "max": rupee(a["max"]),
        }
        for a in lt["profile"]
    ]
    prov_rows = [
        {
            "observation_id": f'<span class="ep">{esc(o["observation_id"])}</span>',
            "apw": o["apw"],
            "band": o["band"],
            "flight": o["flight"],
            "dep": o["dep"],
            "total": rupee(o["total"]),
            "evidence": cls(o["evidence"]),
            "api": f'<span class="ep">GET /provenance/{esc(o["observation_id"])}</span>',
        }
        for o in obs["observations"][:12]
    ]
    return f"""<!DOCTYPE html>
<meta charset="utf-8">
<title>APIx — Platform Console</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<link rel="stylesheet" href="{FONT_HREF}">
<style>{CSS}{PLATFORM_CSS}</style>
<body>
<div class="pf">
<header class="pf-hero">
  <div class="k">MoSPI Problem Statement 26056 · platform console · panel collected {
        esc(obs["collection_date"])
    }</div>
  <h1>Real-time airfare measurement infrastructure for India.</h1>
  <p>Designed for compliant, auditable augmentation of CPI airfare measurement. This console shows the platform — acquisition, scheduling, source health, series, backtest and API — around the one capability that is externally blocked.</p>
  <div class="pf-status">
    <div class="ok"><b>{obs["count"]}</b><span>real observations · 1 route · 1 carrier</span></div>
    <div><b>{run["planned_searches"]}</b><span>searches planned today</span></div>
    <div class="blk"><b>{
        run["requests_made"]
    }</b><span>requests made — every source refused at the gate</span></div>
    <div class="blk"><b>0 / {
        sources["data"]["register_size"]
    }</b><span>sources cleared for live collection</span></div>
    <div class="wn"><b class="s">{
        esc(real_idx["publication_status"])
    }</b><span>production index state</span></div>
    <div class="wn"><b class="s">{
        esc(bt["status"])
    }</b><span>DGCA backtest · benchmark not published</span></div>
  </div>
</header>

<nav class="pf-nav" aria-label="Sections">{
        nav
    }<span class="tag">LIVE AIRFARE CONNECTORS · AUTHORIZATION PENDING</span></nav>

<section class="pf-s" id="overview"><h2><small>01</small>Overview</h2>
<p class="sub">APIx is a complete end-to-end platform with a compliant acquisition boundary. Live automated airfare acquisition is gated pending source authorization; the full downstream pipeline is implemented and demonstrated on verified observations and deterministic replay.</p>
<div class="note red"><b>Live airfare connectors: BLOCKED — authorization pending.</b> Zero of {
        sources["data"]["register_size"]
    } registered sources clear the live compliance gate. APIx has automatically collected <b>zero</b> fares from any airline or travel website. Every refusal is recorded as <code>PERMISSION_BLOCKED</code>, never as an absence of flights.</div>
<div class="note"><b>Output classes on this page.</b> {
        cls("RESEARCH")
    } real observations, descriptive only · {
        cls("DEMO")
    } synthetic fixture, real arithmetic, fictional market · {
        cls("PRODUCTION")
    } an official index — <b>none exists</b>.</div>
</section>

<section class="pf-s" id="trends"><h2><small>02</small>Index trends {cls("DEMO")}</h2>
<p class="sub">Daily, weekly and monthly series derived from the synthetic 14-day engine fixture — the only place an index level is computed. Levels aggregate geometrically. The real panel produces no series: {
        esc(real_idx["data"]["readiness"]["blockers"][0])
    }.</p>
<div class="grid2">{series_svg(demo[Frequency.DAILY], "DAILY · DEMO · synthetic fixture")}{
        series_svg(demo[Frequency.WEEKLY], "WEEKLY · DEMO · geometric aggregation")
    }</div>
{
        table(
            [
                ("period", "Period"),
                ("level", "Level"),
                ("change_pct", "Change %"),
                ("effective_n", "Effective n"),
                ("coverage_note", "Coverage"),
            ],
            [
                {
                    **p,
                    "level": None if p["level"] is None else f"{p['level']:.4f}",
                    "change_pct": None if p["change_pct"] is None else f"{p['change_pct']:+.3f}",
                }
                for p in demo[Frequency.MONTHLY] + demo[Frequency.WEEKLY]
            ],
            {"level", "change_pct", "effective_n"},
        )
    }
<div class="note red"><b>Production index: {esc(real_idx["publication_status"])}.</b> {
        esc(real_idx["data"]["readiness"]["detail"])
    } Next unlock: {esc(real_idx["data"]["next_unlock"])}.</div>
</section>

<section class="pf-s" id="heatmap"><h2><small>03</small>Routes and sector heatmap {
        cls("RESEARCH")
    }</h2>
<p class="sub">The six city-pairs PS 26056 names, with equal <b>placeholder</b> weights ({
        cls("DEMO")
    } basket). The honest heatmap has one filled cell: APIx holds real observations on DEL–BOM only. Empty cells are the coverage finding, not missing rendering.</p>
{heatmap_svg(demo_basket["routes"], observed)}
{
        table(
            [
                ("route_id", "Route"),
                ("weight_normalised", "Weight"),
                ("weight_source", "Weight source"),
                ("observations_held", "Observations"),
            ],
            demo_basket["routes"],
            {"weight_normalised", "observations_held"},
        )
    }
<div class="note"><b>Basket status: {esc(demo_basket["status"])} · publication grade: {
        esc(demo_basket["is_publication_grade"])
    }.</b> {esc(demo_basket["caveat"])}</div>
</section>

<section class="pf-s" id="leadtime"><h2><small>04</small>Lead-time profile {cls("RESEARCH")}</h2>
<p class="sub">Geometric-mean fare by advance-purchase bucket, real observations. PS 26056 names five windows; APIx froze seven and reports the PS five as a strict subset.</p>
{apw_chart(lt["profile"])}
{
        table(
            [
                ("apw", "APW"),
                ("ps", "Set"),
                ("travel_date", "Travel date"),
                ("day_of_week", "Day"),
                ("n", "n"),
                ("geomean", "Geomean ₹"),
                ("spread_pct", "Spread %"),
                ("premium_vs_t1_pct", "vs T+1 %"),
            ],
            lt_rows,
            {"apw", "n", "geomean", "spread_pct", "premium_vs_t1_pct"},
        )
    }
<div class="note red"><b>Not an elasticity.</b> {esc(lt["disclaimer"])} {
        esc(lt["confound"]["statement"])
    }</div>
</section>

<section class="pf-s" id="acquisition"><h2><small>05</small>Data acquisition</h2>
<p class="sub">Four acquisition paths, one canonical observation contract. Only the manual path has ever produced an observation; the live path is built and gated.</p>
<div class="arch">SOURCE REGISTER  (4 axes: automation_gate · data_admissibility · data_rights · operational_status)
      │  gate evaluated BEFORE any adapter is constructed
      ▼
SCHEDULER   basket × APW windows × sources  →  {run["planned_searches"]} searches planned · {
        run["requests_made"]
    } made
      │
      ├── LIVE AUTHORIZED   Playwright adapter · gated · never run          → PERMISSION_BLOCKED
      ├── MANUAL EVIDENCE   person in a browser · @primary · 35 observations → the real panel
      ├── REPLAY FIXTURE    synthetic pages · @fixture · SYNTHETIC           → pipeline proof
      └── REFERENCE DATA    Alliance Air tariff PDF · REFERENCE_ONLY         → never an observation
      ▼
CANONICAL OBSERVATION → store → admissibility → bands → keys → dedup
      ▼
STATISTICS (frozen v2.1) → Jevons → chaining → Young/Laspeyres → publication guards
      ▼
DAILY · WEEKLY · MONTHLY  →  READINESS (allowed to say no)  →  BACKTEST  →  API + this console</div>
<div class="note green"><b>Egress policy: {esc(cfg["egress_policy"]["mode"])} · rotation {
        esc(cfg["egress_policy"]["rotation"])
    }.</b> One declared, attributable egress. No code path from a refusal to egress selection — asserted by a test over every function in the package. CAPTCHA and anti-bot controls are detected and treated as a stop signal: no solver, no stealth, no retry.</div>
</section>

<section class="pf-s" id="sources"><h2><small>06</small>Source health</h2>
<p class="sub">{
        sources["data"]["register_size"]
    } registered sources. <code>PERMISSION_BLOCKED</code> is a permission fact and is visually distinct from an outage, a challenge or an empty result. Gate distribution: {
        esc(", ".join(f"{k} {v}" for k, v in sorted(by_gate.items())))
    }.</p>
{
        table(
            [
                ("source_id", "Source"),
                ("channel", "Channel"),
                ("automation_gate", "Automation gate"),
                ("data_admissibility", "Admissibility"),
                ("data_rights", "Data rights"),
                ("robots_status", "robots.txt"),
                ("operational_status", "Operational"),
                ("evidence_date", "Evidence"),
            ],
            src_rows,
        )
    }
</section>

<section class="pf-s" id="runs"><h2><small>07</small>Collection runs</h2>
<p class="sub">The scheduled run against the real register, executed today with no network. Every planned search has exactly one record.</p>
{
        table(
            [("k", "Field"), ("v", "Value")],
            [
                {
                    "k": k,
                    "v": esc(v)
                    if not isinstance(v, dict)
                    else esc(", ".join(f"{a}={b}" for a, b in v.items())),
                }
                for k, v in run.items()
                if k not in ("source_status",)
            ],
        )
    }
<div class="note"><b>Coverage loss attributed to us: {run["coverage_loss_attributed_to_us"]} of {
        run["planned_searches"]
    }.</b> A permission refusal keeps its cell in the coverage denominator (spec H.1). Reading it as <code>NO_FLIGHT</code> would make our lack of authorisation look like an absence of service — ADR-0066.</div>
</section>

<section class="pf-s" id="quality"><h2><small>08</small>Data quality {cls("RESEARCH")}</h2>
<p class="sub">Plan completion {cov["plan_completion"]["plan_completion_pct"]}% — {
        cov["plan_completion"]["valid_observations"]
    } of {cov["plan_completion"]["plan_slots"]} slots. Statistical coverage: <b>{
        esc(cov["statistical_coverage"])
    }</b>.</p>
<div class="note red">{esc(cov["blocker"])}</div>
{
        table(
            [("label", "Exclusion group"), ("reason", "Reason"), ("count", "Count")],
            exclusions,
            {"count"},
        )
    }
<p class="sub">{
        payloads.panel()["exclusions_total"]
    } screenshots excluded with a reason each; the replay reproduces the recorded verdict on {
        payloads.panel()["replay"]["agree"]
    } of {payloads.panel()["replay"]["candidates"]} mechanically decidable cases with {
        payloads.panel()["replay"]["disagree"]
    } disagreements.</p>
</section>

<section class="pf-s" id="provenance"><h2><small>09</small>Provenance explorer {
        cls("RESEARCH")
    }</h2>
<p class="sub">Every observation resolves through the API to its collection run, collector, parser version and methodology version. First 12 of {
        obs["count"]
    } shown; all are served.</p>
{
        table(
            [
                ("observation_id", "Observation"),
                ("apw", "APW"),
                ("band", "Band"),
                ("flight", "Flight"),
                ("dep", "Dep"),
                ("total", "Total ₹"),
                ("evidence", "Evidence"),
                ("api", "Endpoint"),
            ],
            prov_rows,
            {"apw", "band", "total"},
        )
    }
</section>

<section class="pf-s" id="backtest"><h2><small>10</small>Backtest {cls(bt["status"])}</h2>
<p class="sub">Framework complete — alignment, Pearson, MAE, MAPE, RMSE, directional agreement, all verified against known series. The PS names DGCA monthly average-fare data as the benchmark.</p>
<div class="note red"><b>DGCA fare benchmark: {esc(bt["dgca_fare_benchmark"]["status"])}.</b> {
        esc(bt["dgca_fare_benchmark"]["detail"][:260])
    }…</div>
{
        table(
            [("k", "Field"), ("v", "Value")],
            [{"k": k, "v": esc(v)} for k, v in bt["fallback_benchmark"].items()],
        )
    }
<ul class="tight">{"".join(f"<li>{esc(r)}</li>" for r in bt["reasons"])}</ul>
<p class="sub">Comparison against the fallback: {esc(bt["comparison"]["status"])}, {
        bt["comparison"]["n_aligned"]
    } aligned period(s). {esc(bt["comparison"]["comparability"])}</p>
</section>

<section class="pf-s" id="methodology"><h2><small>11</small>Methodology</h2>
<p class="sub">Frozen v{esc(payloads.METHODOLOGY_VERSION)}. Nothing on this page changes it.</p>
{
        table(
            [("k", "Parameter"), ("v", "Value")],
            [
                {"k": "APW frozen vector (spec A.3, LOCKED)", "v": esc(cfg["frozen_vector"])},
                {
                    "k": "APW PS 26056 vector",
                    "v": esc(cfg["ps_26056_vector"])
                    + " — strict subset: "
                    + esc(cfg["ps_is_subset_of_frozen"]),
                },
                {
                    "k": "Departure bands",
                    "v": esc(", ".join(f"{k}: {v}" for k, v in cfg["departure_bands"].items())),
                },
                {"k": "Selection", "v": "earliest eligible flight per band — never the cheapest"},
                {"k": "Elementary index", "v": "Jevons, log form; band price = geometric mean"},
                {"k": "Chaining (spec C.1, LOCKED)", "v": "I(c,t) = I(c,t−7) · J(c,t)"},
                {"k": "Higher aggregation", "v": "Young / Modified Laspeyres, §G.5 sum-to-one"},
                {
                    "k": "Open blocking ambiguities",
                    "v": "AMB-8 (expected cells), AMB-9 (carrier allocation)",
                },
            ],
        )
    }
</section>

<section class="pf-s" id="architecture"><h2><small>12</small>System architecture and API</h2>
<p class="sub">Standard-library HTTP, JSON, every response wrapped with methodology version, output class and publication state. <code>python -m apix.api</code></p>
{
        table(
            [("e", "Endpoint"), ("d", "Returns")],
            [
                {
                    "e": '<span class="ep">GET /health</span>',
                    "d": "liveness, files present, egress policy",
                },
                {
                    "e": '<span class="ep">GET /sources</span>',
                    "d": "30-source register with gates and operational status",
                },
                {
                    "e": '<span class="ep">GET /routes</span>',
                    "d": "declared baskets; none publication grade",
                },
                {
                    "e": '<span class="ep">GET /observations</span>',
                    "d": "the 35 real observations, RESEARCH",
                },
                {
                    "e": '<span class="ep">GET /index/daily|weekly|monthly</span>',
                    "d": "empty series + readiness verdict; ?class=demo for the fixture, labelled DEMO",
                },
                {
                    "e": '<span class="ep">GET /coverage</span>',
                    "d": "plan completion, AMB-8 blocker, scheduled-run refusals",
                },
                {
                    "e": '<span class="ep">GET /lead-time</span>',
                    "d": "descriptive APW profile with confound; not an elasticity",
                },
                {
                    "e": '<span class="ep">GET /provenance/&#123;observation_id&#125;</span>',
                    "d": "observation → run → collector → parser → methodology",
                },
                {
                    "e": '<span class="ep">GET /backtest</span>',
                    "d": "framework verdict: INCOMPLETE, reasons named",
                },
                {
                    "e": '<span class="ep">GET /reference</span>',
                    "d": "Alliance Air tariff, REFERENCE_ONLY, INADMISSIBLE",
                },
                {
                    "e": '<span class="ep">GET /config</span>',
                    "d": "APW window sets, bands, egress policy",
                },
            ],
        )
    }
<p class="sub">Exports: <code>python -m apix.export</code> writes CSV and JSON to <code>data/exports/</code> with fixed column orders. The editorial dashboard is <a href="dashboard.html">dashboard.html</a>. The one-command demo is <code>python -m apix.demo</code>.</p>
<div class="note red"><b>The externally blocked capability, stated once:</b> authorized live airfare acquisition. Everything else on this page runs today.</div>
</section>
</div>
</body>
"""


def main() -> None:
    html = build()
    OUT.write_text(html, encoding="utf-8")
    print(f"platform console written: {OUT.relative_to(ROOT)}  ({len(html):,} bytes)")


if __name__ == "__main__":
    main()
