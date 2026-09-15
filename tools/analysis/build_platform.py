"""Generate ``data/platform.html`` — the platform console, from the API payloads.

The editorial dashboard (``build_dashboard.py``) tells the measurement story.
This page shows the **platform**: what the scheduler did, which sources are
refused and why, the period series, the heatmap, the lead-time profile, the
backtest verdict and the API contract. PS 26056 requirements 6 and 10.

It renders **exactly the payloads the API serves** (:mod:`apix.api.payloads`),
so a number here is a number at an endpoint. Generated, never hand-authored;
inline SVG for every chart; no network; the same vendored fonts, design tokens
and motion runtime as the dashboard (:mod:`platform_motion`).

Every figure carries its output class. A DEMO series is labelled DEMO in the
same type size as the number. Figures are *revealed*, never tallied from zero —
see the note in :mod:`platform_motion`.

Determinism: nothing on this page comes from a clock. The scheduled run's
wall-clock ``started_at``/``finished_at`` are deliberately excluded, so
``git diff --exit-code data/`` stays a meaningful reproducibility check.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dashboard_theme import CSS, FONT_HREF  # noqa: E402
from dashboard_viz import apw_chart, esc, rupee  # noqa: E402
from platform_motion import MOTION_CSS, MOTION_JS, island, libs_tags  # noqa: E402

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

#: Wall-clock fields. Rendering them would make every regeneration a diff.
NON_DETERMINISTIC_RUN_FIELDS = ("started_at", "finished_at", "source_status")

#: automation_gate -> permission state. Permission is a *rights* fact and is
#: kept separate from operational status throughout: a refusal is not an outage.
PERMISSION = {
    "AUTOMATION_ALLOWED": "AUTHORIZED",
    "AUTOMATION_ALLOWED_WITH_PERMISSION": "PENDING",
    "AUTOMATION_PROHIBITED": "PROHIBITED",
    "AUTOMATION_UNKNOWN": "UNKNOWN",
}

# Platform-specific rules layered on the dashboard tokens. Semantic status
# colours are separate from the amber signal colour, so status never reads as
# emphasis and emphasis never reads as status.
PLATFORM_CSS = """
.pf{max-width:1180px;margin:0 auto;padding:0 20px}
.pf-hero{padding:56px 0 30px;border-bottom:1px solid var(--line)}
.pf-hero .k{font-family:var(--mono);font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--amber-ink)}
.pf-mark{font-family:var(--mono);font-size:13px;letter-spacing:.42em;color:var(--ink-2);margin:0 0 14px}
.pf-hero h1{font-size:clamp(32px,4.8vw,56px);line-height:1.04;margin:8px 0 14px;letter-spacing:-.028em;max-width:24ch}
.pf-hero h1 .line-mask{display:block;overflow:hidden}
.pf-hero h1 .line-mask>span{display:block}
.pf-hero p{max-width:62ch;color:var(--ink-2);font-size:17px;margin:0}
.pf-status{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:1px;background:var(--line);border:1px solid var(--line);margin:26px 0 0}
.pf-status div{background:var(--card);padding:14px 16px}
.pf-status b{font-family:var(--mono);font-size:22px;display:block;letter-spacing:-.02em;font-variant-numeric:tabular-nums;overflow-wrap:anywhere}
.pf-status b.s{font-size:15px;line-height:1.35;padding-top:4px}
.pf-status span{font-size:12px;color:var(--ink-3)}
.pf-status .blk b{color:var(--red)} .pf-status .ok b{color:var(--green)} .pf-status .wn b{color:var(--amber-ink)}
.pf-nav{position:sticky;top:0;z-index:20;background:var(--paper);border-bottom:1px solid var(--line);display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;column-gap:14px;padding:8px 0;font-family:var(--mono);font-size:11.5px;letter-spacing:.06em}
/* One row that scrolls sideways, never four rows that eat the viewport. */
.pf-links{display:flex;gap:0 16px;overflow-x:auto;white-space:nowrap;padding:3px 0;scrollbar-width:none;-ms-overflow-style:none}
.pf-links::-webkit-scrollbar{height:0;display:none}
.pf-nav a{color:var(--ink-2);text-decoration:none;padding:4px 0;flex:none}.pf-nav a:hover{color:var(--amber-ink)}
.pf-nav .tag{background:var(--red-wash);color:var(--red);padding:3px 9px;border-radius:2px;font-weight:600;white-space:nowrap}
@media(max-width:860px){.pf-nav .tag-l{display:none}}
@media(max-width:560px){.pf-where{display:none}}
section.pf-s{padding:44px 0 8px;border-bottom:1px solid var(--line-2)}
section.pf-s>h2{font-size:clamp(22px,2.6vw,28px);letter-spacing:-.02em;margin:0 0 6px}
section.pf-s>h2 small{font-family:var(--mono);font-size:11px;color:var(--amber-ink);letter-spacing:.1em;margin-right:12px;vertical-align:middle}
.sub{color:var(--ink-3);font-size:13.5px;margin:0 0 18px;max-width:72ch}
.cls{display:inline-block;font-family:var(--mono);font-size:10.5px;letter-spacing:.08em;padding:2px 7px;border:1px solid;border-radius:2px;vertical-align:middle}
.cls.DEMO{color:var(--amber-ink);border-color:var(--amber);background:var(--amber-wash)}
.cls.RESEARCH{color:var(--blue);border-color:var(--blue);background:var(--blue-wash)}
.cls.PRODUCTION{color:var(--green);border-color:var(--green);background:var(--green-wash)}
.cls.REFERENCE{color:var(--ink-2);border-color:var(--line-2);background:var(--paper-2)}
.cls.BLOCKED,.cls.PERMISSION_BLOCKED{color:var(--red);border-color:var(--red);background:var(--red-wash)}
.cls.INCOMPLETE,.cls.NO_DATA,.cls.PROVISIONAL{color:var(--amber-ink);border-color:var(--amber);background:var(--amber-wash)}
.tw{overflow-x:auto;border:1px solid var(--line);background:var(--card);margin:0 0 18px}
table.pf{border-collapse:collapse;width:100%;font-size:13px;min-width:560px}
table.pf th,table.pf td{text-align:left;padding:8px 11px;border-bottom:1px solid var(--line-2);vertical-align:top}
table.pf thead th{font-family:var(--mono);font-size:10.5px;letter-spacing:.09em;text-transform:uppercase;color:var(--ink-3);background:var(--paper-2);white-space:nowrap}
table.pf td.n{font-family:var(--mono);font-variant-numeric:tabular-nums;white-space:nowrap}
table.pf tr:last-child td{border-bottom:none}
table.pf tbody tr:hover{background:var(--paper-2)}
.note{border-left:3px solid var(--amber);background:var(--card);padding:12px 16px;margin:0 0 18px;font-size:13.5px;max-width:78ch}
.note.red{border-left-color:var(--red)} .note.green{border-left-color:var(--green)}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:18px;margin:0 0 18px}
svg.pf{width:100%;height:auto;display:block;background:var(--card);border:1px solid var(--line)}
.arch{font-family:var(--mono);font-size:12px;line-height:1.55;background:var(--card);border:1px solid var(--line);padding:16px 18px;overflow-x:auto;white-space:pre;margin:0 0 18px}
.ep{font-family:var(--mono);font-size:12.5px}
ul.tight{margin:0 0 16px;padding-left:20px;max-width:72ch}ul.tight li{margin-bottom:5px}
.figcap{font-family:var(--mono);font-size:10.5px;letter-spacing:.06em;color:var(--ink-3);margin:7px 0 18px}
@media(max-width:700px){.pf-hero{padding:36px 0 22px}}
"""


def w4(v: object) -> str:
    """Basket weights arrive as Decimal-safe strings. Render them at one precision."""
    return f"{float(v):.4f}"


def cls(v: str) -> str:
    return f'<span class="cls {esc(v)}">{esc(v)}</span>'


def masked(lines: list[str]) -> str:
    """A heading whose lines ride up from behind their own clip."""
    return "".join(f'<span class="line-mask"><span>{esc(ln)}</span></span>' for ln in lines)


def num(value: object, *, stagger: int = 0, klass: str = "") -> str:
    """A measured figure. The text is the truth; motion only uncovers it."""
    k = f' class="{klass}"' if klass else ""
    return f'<b{k} data-count="1" data-s="{stagger}">{esc(value)}</b>'


def table(
    cols: list[tuple[str, str]],
    rows: list[dict],
    numeric: set[str] = frozenset(),
) -> str:
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


def heatmap_svg(routes: list[dict], observed: set[str], carrier: str) -> str:
    """Origin x destination grid. A cell is filled ONLY where real observations exist.

    Five of six demo routes hold zero observations and are drawn as such. The
    honest heatmap has one cell, and the empty cells are the coverage finding.
    Each cell is a focusable button: hover for metadata, activate for detail.
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
            f'<g class="hm-cell" data-anim="1" tabindex="0" role="button" aria-pressed="false"'
            f' data-pair="{esc(r["pair"])}" data-n="{r["observations_held"]}"'
            f' data-weight="{w4(r["weight_normalised"])}" data-src="{esc(r["weight_source"])}"'
            f' data-carrier="{esc(carrier)}"'
            f' aria-label="{esc(r["pair"])}: {esc(txt)}">'
            f'<rect x="{L + i * cell + 2}" y="{T + j * cell + 2}" width="{cell - 4}" height="{cell - 4}" fill="{fill}" stroke="var(--line)"/>'
            f'<text x="{L + i * cell + cell / 2}" y="{T + j * cell + cell / 2 + 4}" text-anchor="middle" font-size="11" fill="{col}" font-family="var(--mono)" pointer-events="none">{esc(txt)}</text>'
            f"</g>"
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


# --------------------------------------------------------------- architecture
#: Box geometry for the flow graph. Two lanes: what the live path attempted,
#: and what the evidence actually travelled.
_BW, _BH = 112, 34


def _node(
    x: float,
    y: float,
    label: str,
    *,
    at: float | None = None,
    blocked: bool = False,
    w: float = _BW,
) -> str:
    attrs = f' data-at="{at:.4f}"' if at is not None else ""
    if blocked:
        attrs += ' data-blocked="1"'
    lines = label.split("|")
    text = "".join(
        f'<text x="{x + w / 2:.0f}" y="{y + (_BH / 2) + 4 - (len(lines) - 1) * 5.5 + k * 11:.0f}"'
        f' text-anchor="middle">{esc(ln)}</text>'
        for k, ln in enumerate(lines)
    )
    return (
        f'<g class="ag-node"{attrs}>'
        f'<rect x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{_BH}" rx="2"/>{text}</g>'
    )


def arch_graph_svg(planned: int, requests: int, observations: int) -> str:
    """The pipeline as a system graph, with a real observation travelling it.

    The live lane carries **nothing** past the gate — zero requests were made,
    so a packet there would animate work that never happened. The evidence lane
    carries a recorded observation and the index is drawn as refused, which is
    where the evidence actually stops.
    """
    W, H = 980, 300
    ax_y, bx_y, cx_y = 46, 140, 234
    # evidence lane: six boxes on one row, then API, then the console below it
    xs = [20, 150, 280, 410, 540, 670]
    cxs = [x + _BW / 2 for x in xs]
    seg = 130.0
    total = seg * 6 + (cx_y - bx_y)  # six hops right, then one down
    ats = [0.0] + [seg * k / total for k in range(1, 7)] + [1.0]
    flow = (
        "M"
        + " L".join(f"{cx:.0f},{bx_y + _BH / 2:.0f}" for cx in [*cxs, 800 + _BW / 2])
        + f" L{800 + _BW / 2:.0f},{cx_y + _BH / 2:.0f}"
    )
    edges = "".join(
        f'<path class="ag-edge" d="M{cxs[k] + _BW / 2 - 55:.0f},{bx_y + _BH / 2:.0f} '
        f'L{cxs[k + 1] - _BW / 2 + 55:.0f},{bx_y + _BH / 2:.0f}"/>'
        for k in range(5)
    )
    nodes = [
        # live lane — attempted, refused at the gate
        _node(20, ax_y, "AIRLINE / OTA|30 registered"),
        _node(150, ax_y, "COLLECTOR|Playwright, gated"),
        _node(280, ax_y, "SCHEDULER|" + f"{planned} planned"),
        _node(410, ax_y, "COMPLIANCE GATE|" + f"{requests} requests made", blocked=True, w=150),
        # evidence lane — what the 35 observations travelled
        _node(xs[0], bx_y, "MANUAL EVIDENCE|152 screenshots", at=ats[0]),
        _node(xs[1], bx_y, "RAW ARTIFACTS|@primary, hashed", at=ats[1]),
        _node(xs[2], bx_y, "NORMALIZER|bands, keys, dedup", at=ats[2]),
        _node(xs[3], bx_y, "OBSERVATION STORE|35 rows", at=ats[3]),
        _node(xs[4], bx_y, "QUALITY ENGINE|122 exclusions", at=ats[4]),
        _node(xs[5], bx_y, "STATISTICAL ENGINE|Jevons, chaining", at=ats[5]),
        _node(800, bx_y, "API|13 endpoints", at=ats[6]),
        _node(800, cx_y, "THIS CONSOLE|12 views", at=1.0),
        # the refused branch
        _node(xs[5], cx_y, "INDEX|" + f"{observations} published", blocked=True),
    ]
    dead = (
        f'<path class="ag-edge dead" d="M{560 + 150 - 150 + 150:.0f},{ax_y + _BH / 2:.0f} '
        f'L{790:.0f},{ax_y + _BH / 2:.0f}"/>'
        f'<text class="ag-cap" x="{796}" y="{ax_y + _BH / 2 + 4:.0f}" fill="var(--red)">PERMISSION_BLOCKED</text>'
        f'<path class="ag-edge dead" d="M{cxs[5]:.0f},{bx_y + _BH:.0f} '
        f'L{cxs[5]:.0f},{cx_y:.0f}"/>'
    )
    packet = (
        '<g class="ag-pkt" id="ag-pkt"><rect x="0" y="0" width="110" height="18" rx="2"/>'
        '<text id="ag-pkt-label" x="55" y="12.5" text-anchor="middle">observation</text></g>'
    )
    stop = (
        f'<g class="ag-stop" id="ag-stop">'
        f'<rect x="{xs[5] - 6:.0f}" y="{cx_y + _BH + 8:.0f}" width="196" height="20" rx="2"/>'
        f'<text x="{xs[5] + 92:.0f}" y="{cx_y + _BH + 22:.0f}" text-anchor="middle">'
        f"PUBLICATION GUARD · REFUSED</text></g>"
    )
    return (
        f'<svg class="ag" id="arch-graph" viewBox="0 0 {W} {H}" role="img"'
        f' aria-label="Pipeline graph: the live acquisition lane is refused at the compliance gate;'
        f" the manual evidence lane reaches the API and this console, and the index is refused by the"
        f' publication guard">'
        f'<text class="ag-cap" x="20" y="26">LIVE ACQUISITION LANE · built, gated, never executed</text>'
        f'<text class="ag-cap" x="20" y="122">EVIDENCE LANE · the path the 35 real observations travelled</text>'
        f'<path id="ag-flow" d="{flow}" fill="none" stroke="none"/>'
        f'<path class="ag-edge" d="M{75 + 55:.0f},{ax_y + _BH / 2:.0f} L{205 - 55:.0f},{ax_y + _BH / 2:.0f}"/>'
        f'<path class="ag-edge" d="M{205 + 55:.0f},{ax_y + _BH / 2:.0f} L{335 - 55:.0f},{ax_y + _BH / 2:.0f}"/>'
        f'<path class="ag-edge" d="M{335 + 55:.0f},{ax_y + _BH / 2:.0f} L{410:.0f},{ax_y + _BH / 2:.0f}"/>'
        f'<path class="ag-edge" d="M{cxs[5] + 55:.0f},{bx_y + _BH / 2:.0f} L{800:.0f},{bx_y + _BH / 2:.0f}"/>'
        f'<path class="ag-edge" d="M{800 + _BW / 2:.0f},{bx_y + _BH:.0f} L{800 + _BW / 2:.0f},{cx_y:.0f}"/>'
        f"{edges}{dead}{''.join(nodes)}{packet}{stop}</svg>"
    )


def dep_chain(rows: list[tuple[str, bool, str]]) -> str:
    """The index's dependency chain. A missing link is the finding, not an error."""
    out = []
    for i, (label, ok, detail) in enumerate(rows):
        mark = "&#10003;" if ok else "&#10007;"
        out.append(
            f'<div class="row" data-ok="{1 if ok else 0}"><i>{mark}</i>'
            f"<b>{esc(label)}</b><span>{esc(detail)}</span></div>"
        )
        if i < len(rows) - 1:
            out.append('<div class="arrow">&#8595;</div>')
    return f'<div class="dep">{"".join(out)}</div>'


def ladder(items: list[tuple[str, object, bool]]) -> str:
    """Run stages, revealed in pipeline order. Each value is the recorded one."""
    cells = "".join(
        f'<div class="{"zero" if zero else ""}">{num(v, stagger=i)}<span>{esc(label)}</span></div>'
        for i, (label, v, zero) in enumerate(items)
    )
    return f'<div class="ladder">{cells}</div>'


def track_row(label: str, width: float, value: str, *, dead: bool = False) -> str:
    d = " dead" if dead else ""
    fill = "" if dead and width <= 0 else f'<i data-w="{max(0.0, min(1.0, width)):.4f}"></i>'
    return (
        f'<div class="btrow"><span class="lab">{esc(label)}</span>'
        f'<span class="track{d}">{fill}</span>'
        f'<span class="val">{esc(value)}</span></div>'
    )


def source_cards(sources: list[dict], run_status: dict[str, str]) -> str:
    """Cards for the acquisition frontier: what was attempted, and what could unlock.

    Every one of the 30 registered sources stays in the table below; a card is
    for a source that is either scheduled or whose gate is not unknown, because
    those are the ones a reader can act on.
    """
    picked: dict[str, dict] = {}
    for s in sources:
        gate = s["automation_gate"] or "AUTOMATION_UNKNOWN"
        if s["source_id"] in run_status or gate in (
            "AUTOMATION_ALLOWED",
            "AUTOMATION_ALLOWED_WITH_PERMISSION",
        ):
            picked[s["source_id"]] = s
    cards = []
    for s in sorted(
        picked.values(), key=lambda s: (s["source_id"] not in run_status, s["source_id"])
    ):
        gate = s["automation_gate"] or "AUTOMATION_UNKNOWN"
        perm = PERMISSION.get(gate, "UNKNOWN")
        op = run_status.get(s["source_id"], s["operational_status"])
        last = "today, at the gate" if s["source_id"] in run_status else "never scheduled"
        cards.append(
            f'<article class="scard" data-perm="{perm}" data-anim="0">'
            f'<h4><i class="sdot"></i>{esc(s["display_name"])}</h4>'
            f'<p class="ch">{esc(s["channel"])}</p>'
            f"<dl>"
            f"<dt>permission</dt><dd>{esc(perm)}</dd>"
            f"<dt>gate</dt><dd>{esc(gate.replace('AUTOMATION_', ''))}</dd>"
            f"<dt>data rights</dt><dd>{esc((s.get('data_rights') or 'UNKNOWN').replace('RETENTION_', ''))}</dd>"
            f"<dt>robots.txt</dt><dd>{esc(s['robots_status'])}</dd>"
            f"<dt>coverage</dt><dd>0 fares</dd>"
            f"</dl>"
            f'<p class="ops">OPERATIONAL · {esc(op)} · {esc(last)}</p>'
            f"</article>"
        )
    return f'<div class="scards">{"".join(cards)}</div>'


def lineage_block(records: list[dict[str, str]]) -> str:
    """The provenance chain, one step per hop, painted from the data island."""
    steps = [
        ("index", "Index"),
        ("route", "Route contribution"),
        ("observation", "Observation"),
        ("run", "Collection run"),
        ("source", "Source"),
        ("artifact", "Raw artifact"),
    ]
    body = "".join(
        f'<div class="step" data-k="{k}" data-on="0">'
        f'<div class="k">{esc(label)}</div><div class="v">{records[0][k] if records else ""}</div>'
        f"</div>"
        for k, label in steps
    )
    return f'<div class="lin">{body}</div>'


def build() -> str:
    sources = payloads.sources()
    routes = payloads.routes()["data"]
    obs = payloads.observations()["data"]
    cov = payloads.coverage()["data"]
    lt = payloads.lead_time()["data"]
    bt = payloads.backtest()["data"]
    cfg = payloads.config()["data"]
    panel = payloads.panel()
    real_idx = payloads.index(Frequency.DAILY)
    demo = {f: payloads.index(f, demo=True)["data"]["series"] for f in Frequency}
    run = cov["scheduled_run"]
    demo_basket = next(b for b in routes["baskets"] if b["status"] == "DEMO")
    observed = set(routes["routes_with_real_observations"])
    carrier = sorted({o["carrier"] for o in panel["observations"]})[0]
    demo_weight = {r["pair"]: r["weight_normalised"] for r in demo_basket["routes"]}
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
    exclusions = panel["exclusions"]
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
    shown = obs["observations"][:12]
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
        for o in shown
    ]

    # ------------------------------------------------------------ data island
    # Only recorded values. The runtime computes layouts, never numbers.
    lineage: list[dict[str, str]] = []
    for o in shown:
        pr = payloads.provenance(o["observation_id"])
        r = (pr or {}).get("data", {}).get("collection_run") or {}
        lineage.append(
            {
                "index": "<em>no index level — 0 matched t/t−7 pairs (spec C.1)</em>",
                "route": (
                    f"{esc(o['route'])} · basket weight "
                    f"{w4(demo_weight.get(o['route'], 0))} <em>(DEMO placeholder, equal weights)</em>"
                ),
                "observation": (
                    f"{esc(o['flight'])} · T+{o['apw']} · band {o['band']} · "
                    f"{rupee(o['total'])} <em>(base {rupee(o['base'])} + tax {rupee(o['tax'])})</em>"
                ),
                "run": (
                    f"{esc(r.get('run_id', '—'))} · {esc(r.get('collection_date', '—'))} · "
                    f"parser {esc(r.get('parser_version', '—'))} · methodology "
                    f"{esc(r.get('methodology_version', '—'))}"
                ),
                "source": f"IndiGo web · {esc(o['evidence'])} <em>(manual protocol, not automated)</em>",
                "artifact": f"<em>screenshot corpus → @primary → </em>{esc(o['observation_id'])}",
            }
        )
    picker = "".join(
        f'<button type="button" data-i="{i}" aria-pressed="false">'
        f"T+{o['apw']} · {esc(o['flight'])}</button>"
        for i, o in enumerate(shown)
    )
    apw_order = [a["apw"] for a in lt["profile"]]
    data: dict[str, Any] = {
        "obs": [
            {"apw": o["apw"], "total": o["total"], "ev": o["evidence"]}
            for o in panel["observations"]
        ],
        "apwOrder": apw_order,
        "geomeanByApw": {a["apw"]: a["geomean"] for a in lt["profile"]},
        "apw": lt["profile"],
        "packets": [
            {"label": f"{o['route']} · T+{o['apw']} · ₹{int(o['total']):,}".replace(",", ",")}
            for o in shown[:6]
        ],
        "lineage": lineage,
    }

    return f"""<!DOCTYPE html>
<meta charset="utf-8">
<title>APIx — Platform Console</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<meta name="description" content="APIx platform console: acquisition boundary, scheduler,
source health, period series, lead-time profile, provenance and API for MoSPI PS 26056.
{obs["count"]} real observations, zero automated fares, no published index.">
<link rel="stylesheet" href="{FONT_HREF}">
<style>{CSS}{PLATFORM_CSS}{MOTION_CSS}</style>
<script>document.documentElement.className += " js";</script>
{libs_tags()}
<body>
<div class="pf">
<header class="pf-hero">
  <div class="k">MoSPI Problem Statement 26056 · platform console · panel collected {
        esc(obs["collection_date"])
    }</div>
  <p class="pf-mark">APIX</p>
  <h1>{masked(["Real-time airfare", "measurement infrastructure", "for India."])}</h1>
  <p class="rv" data-d="1">Designed for compliant, auditable augmentation of CPI airfare measurement. This console shows the platform — acquisition, scheduling, source health, series, backtest and API — around the one capability that is externally blocked.</p>
  <div class="pf-fieldwrap rv" data-d="2">
    <canvas id="pf-field" aria-hidden="true"></canvas>
    <div class="pf-beats">
      <div data-on="1"><b>01 · QUOTES AS COLLECTED</b>{
        obs["count"]
    } real observations, one route, one carrier</div>
      <div data-on="0"><b>02 · KEYED AND NORMALISED</b>seven advance-purchase buckets, five departure bands</div>
      <div data-on="0"><b>03 · AGGREGATED</b>geometric mean per bucket — the profile, not an index</div>
    </div>
  </div>
  <div class="pf-status">
    <div class="ok">{
        num(obs["count"], stagger=0)
    }<span>real observations · 1 route · 1 carrier</span></div>
    <div>{num(run["planned_searches"], stagger=1)}<span>searches planned today</span></div>
    <div class="blk">{
        num(run["requests_made"], stagger=2)
    }<span>requests made — every source refused at the gate</span></div>
    <div class="blk">{
        num(f"0 / {sources['data']['register_size']}", stagger=3)
    }<span>sources cleared for live collection</span></div>
    <div class="wn">{
        num(real_idx["publication_status"], stagger=4, klass="s")
    }<span>production index state</span></div>
    <div class="wn">{
        num(bt["status"], stagger=5, klass="s")
    }<span>DGCA backtest · benchmark not published</span></div>
  </div>
</header>

<nav class="pf-nav" aria-label="Sections"><span class="pf-prog" aria-hidden="true"></span>
  <span class="pf-links">{nav}</span>
  <span class="tag"><span class="tag-l">LIVE AIRFARE CONNECTORS · </span>AUTHORIZATION PENDING</span>
  <span class="pf-where">PIPELINE POSITION · <b>Overview</b></span></nav>

<section class="pf-s" id="overview"><h2><small>01</small>Overview</h2>
<p class="sub rv">APIx is a complete end-to-end platform with a compliant acquisition boundary. Live automated airfare acquisition is gated pending source authorization; the full downstream pipeline is implemented and demonstrated on verified observations and deterministic replay.</p>
<div class="note red rv"><b>Live airfare connectors: BLOCKED — authorization pending.</b> Zero of {
        sources["data"]["register_size"]
    } registered sources clear the live compliance gate. APIx has automatically collected <b>zero</b> fares from any airline or travel website. Every refusal is recorded as <code>PERMISSION_BLOCKED</code>, never as an absence of flights.</div>
<div class="note rv" data-d="1"><b>Output classes on this page.</b> {
        cls("RESEARCH")
    } real observations, descriptive only · {
        cls("DEMO")
    } synthetic fixture, real arithmetic, fictional market · {
        cls("REFERENCE")
    } published tariff, inadmissible as an observation · {
        cls("PRODUCTION")
    } an official index — <b>none exists</b>.</div>
</section>

<section class="pf-s" id="trends"><h2><small>02</small>Index trends {cls("DEMO")}</h2>
<p class="sub rv">Daily, weekly and monthly series derived from the synthetic 14-day engine fixture — the only place an index level is computed. Levels aggregate geometrically. The real panel produces no series: {
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
<h3 style="font-size:16px;margin:26px 0 4px">Production index status: {
        esc(real_idx["publication_status"])
    }</h3>
<p class="sub">Not a gap in the engine. The chain below is evaluated every run, and one link is missing — so the guard refuses rather than inventing a level.</p>
{
        dep_chain(
            [
                ("CURRENT PERIOD", True, f"{obs['count']} observations, 7 buckets, 5 bands"),
                ("PREVIOUS PERIOD", False, "no t−7 collection wave exists"),
                ("MATCHED PAIR", False, "0 pairs survive the longitudinal match"),
                ("PRICE RELATIVE", False, "Jevons needs a pair; none available"),
                ("INDEX LEVEL", False, "spec C.1 refuses: I(c,t) = I(c,t−7) · J(c,t)"),
            ]
        )
    }
<div class="note red"><b>Production index: {esc(real_idx["publication_status"])}.</b> {
        esc(real_idx["data"]["readiness"]["detail"])
    } Next unlock: {esc(real_idx["data"]["next_unlock"])}.</div>
</section>

<section class="pf-s" id="heatmap"><h2><small>03</small>Routes and sector heatmap {
        cls("RESEARCH")
    }</h2>
<p class="sub rv">The six city-pairs PS 26056 names, with equal <b>placeholder</b> weights ({
        cls("DEMO")
    } basket). The honest heatmap has one filled cell: APIx holds real observations on DEL–BOM only. Empty cells are the coverage finding, not missing rendering. Hover a cell for metadata; activate it for detail.</p>
{heatmap_svg(demo_basket["routes"], observed, carrier)}
<div class="hm-detail" data-has="0"><div class="hm-body"><em>Select a sector above.</em></div></div>
{
        table(
            [
                ("route_id", "Route"),
                ("weight_normalised", "Weight"),
                ("weight_source", "Weight source"),
                ("observations_held", "Observations"),
            ],
            [{**r, "weight_normalised": w4(r["weight_normalised"])} for r in demo_basket["routes"]],
            {"weight_normalised", "observations_held"},
        )
    }
<div class="note"><b>Basket status: {esc(demo_basket["status"])} · publication grade: {
        esc(demo_basket["is_publication_grade"])
    }.</b> {esc(demo_basket["caveat"])}</div>
</section>

<section class="pf-s" id="leadtime"><h2><small>04</small>Lead-time profile {cls("RESEARCH")}</h2>
<p class="sub rv">Geometric-mean fare by advance-purchase bucket, real observations. PS 26056 names five windows; APIx froze seven and reports the PS five as a strict subset. The curve draws on entry and each bucket carries its recorded values on hover.</p>
{apw_chart(lt["profile"])}
<p class="figcap">seven cross-sections on seven travel dates · ordinal axis, never a time axis</p>
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
<p class="sub rv">Two lanes, one canonical observation contract. The live lane is built and gated; only the manual lane has ever produced an observation. The graph animates a <b>recorded</b> observation through the path it actually travelled — it is a replay, not a live feed.</p>
<div class="agwrap">{
        arch_graph_svg(
            run["planned_searches"],
            run["requests_made"],
            len(real_idx["data"]["series"]),
        )
    }</div>
<p class="figcap">packet = one real row from data/panel.json · the live lane carries none, because no request was ever made</p>
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
<p class="sub rv">{
        sources["data"]["register_size"]
    } registered sources. <b>Permission state and operational state are different facts</b> and never share a colour: a refusal is not an outage. Gate distribution: {
        esc(", ".join(f"{k} {v}" for k, v in sorted(by_gate.items())))
    }.</p>
{source_cards(sources["data"]["sources"], run["source_status"])}
<p class="figcap">cards = the acquisition frontier (scheduled, or gate not unknown) · all {
        sources["data"]["register_size"]
    } registered sources are in the table</p>
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
<p class="sub rv">Run <code>{
        esc(run["run_id"])
    }</code> against the real register, executed today with no network. Every planned search has exactly one record. The stages below are the recorded values, revealed in pipeline order.</p>
{
        ladder(
            [
                ("routes in basket", len(demo_basket["routes"]), False),
                ("APW windows", len(run["windows"]), False),
                ("departure bands", len(run["bands"]), False),
                ("sources scheduled", len(run["source_status"]), False),
                ("searches planned", run["planned_searches"], False),
                ("requests made", run["requests_made"], True),
                ("observations written", run["observations_written"], True),
            ]
        )
    }
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
                if k not in NON_DETERMINISTIC_RUN_FIELDS
            ],
        )
    }
<div class="note"><b>Coverage loss attributed to us: {run["coverage_loss_attributed_to_us"]} of {
        run["planned_searches"]
    }.</b> A permission refusal keeps its cell in the coverage denominator (spec H.1). Reading it as <code>NO_FLIGHT</code> would make our lack of authorisation look like an absence of service — ADR-0066.</div>
<p class="figcap">run timestamps are deliberately not rendered: this page must regenerate byte-identically</p>
</section>

<section class="pf-s" id="quality"><h2><small>08</small>Data quality {cls("RESEARCH")}</h2>
<p class="sub rv">Plan completion {cov["plan_completion"]["plan_completion_pct"]}% — {
        cov["plan_completion"]["valid_observations"]
    } of {cov["plan_completion"]["plan_slots"]} slots. Statistical coverage: <b>{
        esc(cov["statistical_coverage"])
    }</b>.</p>
{
        track_row(
            "PLAN COMPLETION",
            cov["plan_completion"]["plan_completion_pct"] / 100.0,
            f"{cov['plan_completion']['valid_observations']} of {cov['plan_completion']['plan_slots']} slots"
            f" · {cov['plan_completion']['plan_basis']}",
        )
    }
{track_row("STATISTICAL COVERAGE", 0.0, "NOT_ESTABLISHED — AMB-8 open", dead=True)}
<div class="note red">{esc(cov["blocker"])}</div>
{
        table(
            [("label", "Exclusion group"), ("reason", "Reason"), ("count", "Count")],
            exclusions,
            {"count"},
        )
    }
<p class="sub">{
        panel["exclusions_total"]
    } screenshots excluded with a reason each; the replay reproduces the recorded verdict on {
        panel["replay"]["agree"]
    } of {panel["replay"]["candidates"]} mechanically decidable cases with {
        panel["replay"]["disagree"]
    } disagreements.</p>
</section>

<section class="pf-s" id="provenance"><h2><small>09</small>Provenance explorer {
        cls("RESEARCH")
    }</h2>
<p class="sub rv">Every observation resolves through the API to its collection run, collector, parser version and methodology version. Pick an observation to traverse its lineage from the index it cannot reach back to the raw artifact.</p>
<div class="picker" data-for="lineage" role="group" aria-label="Choose an observation">{
        picker
    }</div>
{lineage_block(lineage)}
<p class="figcap">lineage reveals in pipeline order · first 12 of {obs["count"]} shown here, all {
        obs["count"]
    } served at GET /provenance/&#123;observation_id&#125;</p>
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
<p class="sub rv">Framework complete — alignment, Pearson, MAE, MAPE, RMSE, directional agreement, all verified against known series. The PS names DGCA monthly average-fare data as the benchmark. The chart below is not fabricated: it shows what each series actually offers.</p>
{
        track_row(
            "APIx SERIES",
            1 / 30,
            f"{len(demo[Frequency.MONTHLY])} monthly point · DEMO input · 0 real",
        )
    }
{track_row("DGCA AVERAGE FARE", 0.0, "NOT_LOCATED — never published", dead=True)}
{
        track_row(
            "MoSPI CPI AIRFARE",
            1 / 12,
            f"{bt['fallback_benchmark']['points']} points · December only"
            f" · insufficient temporal granularity",
            dead=True,
        )
    }
<p class="figcap">a 30-day backtest needs 30 aligned days · FRAMEWORK READY · EMPIRICAL VALIDATION INCOMPLETE</p>
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
<p class="sub rv">Frozen v{esc(payloads.METHODOLOGY_VERSION)}. Nothing on this page changes it.</p>
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
<p class="sub rv">Standard-library HTTP, JSON, every response wrapped with methodology version, output class and publication state. <code>python -m apix.api --port 8760</code></p>
<div class="eps">
  <div class="epc"><code>GET /health</code><p>liveness, files present, egress policy</p></div>
  <div class="epc"><code>GET /sources</code><p>30-source register with gates and operational status</p></div>
  <div class="epc"><code>GET /routes</code><p>declared baskets; none publication grade</p></div>
  <div class="epc"><code>GET /observations</code><p>the {
        obs["count"]
    } real observations, RESEARCH</p></div>
  <div class="epc"><code>GET /index/daily|weekly|monthly</code><p>empty series + readiness verdict; <code>?class=demo</code> for the fixture, labelled DEMO</p></div>
  <div class="epc"><code>GET /coverage</code><p>plan completion, AMB-8 blocker, scheduled-run refusals</p></div>
  <div class="epc"><code>GET /lead-time</code><p>descriptive APW profile with confound; not an elasticity</p></div>
  <div class="epc"><code>GET /provenance/&#123;observation_id&#125;</code><p>observation → run → collector → parser → methodology</p></div>
  <div class="epc"><code>GET /backtest</code><p>framework verdict: INCOMPLETE, reasons named</p></div>
  <div class="epc"><code>GET /reference</code><p>Alliance Air tariff, REFERENCE_ONLY, INADMISSIBLE</p></div>
  <div class="epc"><code>GET /config</code><p>APW window sets, bands, egress policy</p></div>
</div>
<p class="sub">Exports: <code>python -m apix.export</code> writes CSV and JSON to <code>data/exports/</code> with fixed column orders. The editorial dashboard is <a href="dashboard.html">dashboard.html</a>. The one-command demo is <code>python -m apix.demo</code>.</p>
<div class="note red"><b>The externally blocked capability, stated once:</b> authorized live airfare acquisition. Everything else on this page runs today.</div>
</section>

<section class="pf-close">
  <blockquote class="line-mask-group">{
        masked(
            [
                "APIx does not",
                "manufacture certainty.",
            ]
        )
    }</blockquote>
  <p class="rv" style="max-width:44ch;margin:0 auto 30px;color:var(--ink-2)">It measures only what the evidence supports.</p>
  <p class="k rv" data-d="1">PS 26056 · Airfare measurement infrastructure for India</p>
</section>
</div>
<div id="tip" role="status" aria-live="polite"></div>
<script type="application/json" id="apix-data">{island(data)}</script>
<script>{MOTION_JS}</script>
</body>
"""


def main() -> None:
    html = build()
    OUT.write_text(html, encoding="utf-8")
    print(f"platform console written: {OUT.relative_to(ROOT)}  ({len(html):,} bytes)")


if __name__ == "__main__":
    main()
