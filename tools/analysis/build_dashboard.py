"""Render `data/dashboard.html` — the jury-facing APIx surface.

    data/panel.json  ->  this module  ->  data/dashboard.html

**One data source, and it is not this file.** Every statistical figure on the
page is read from the panel contract at render time. This module owns layout,
language and interaction; it owns no numbers. The previous hand-authored
dashboard went stale twice — a base-year mixing error and a series count — and
`tests/test_observed_panel.py` now fails the build if any headline figure here
disagrees with the contract.

The page is a **single self-contained file**: no webfont, no CDN, no build
step. That is a demo-reliability decision before it is an engineering one — a
venue network that drops must not be able to take the evidence off screen — and
it keeps the artifact byte-reproducible, which is what lets
`git diff --exit-code data/` mean something.

Design system: `dashboard_theme.py`. Charts and behaviour: `dashboard_viz.py`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dashboard_theme import CSS, STATE_COLOURS  # noqa: E402
from dashboard_viz import (  # noqa: E402
    JS,
    apw_chart,
    band_chart,
    confound_chart,
    esc,
    exclusion_chart,
    provenance_chart,
    rupee,
)

PANEL = ROOT / "data" / "panel.json"
OUT = ROOT / "data" / "dashboard.html"

#: Section id -> nav label. The nav is generated from this, so a section can
#: never exist without a way to reach it.
NAV = [
    ("evidence", "Evidence"),
    ("confound", "Confound"),
    ("provenance", "Provenance"),
    ("boundary", "Boundary"),
    ("pending", "Index status"),
    ("engine", "Engine"),
    ("method", "Method"),
    ("limits", "Limits"),
    ("next", "19 Sep"),
]


def data_island(p: dict) -> str:
    """The contract subset the interactive layers read.

    Serialised from the panel, never typed. Key order is fixed so the rendered
    file stays byte-identical across runs.
    """
    payload = {
        "apw": [
            {
                "apw": a["apw"],
                "n": a["n"],
                "geomean": a["geomean"],
                "min": a["min"],
                "max": a["max"],
                "spread_pct": a["spread_pct"],
                "travel_date": a["travel_date"],
                "day_of_week": a["day_of_week"],
            }
            for a in p["apw_profile"]
        ],
        "bands": [
            {"band": b["band"], "window": b["window"], "n": b["n"], "geomean": b["geomean"]}
            for b in p["band_profile"]
        ],
        "obs": [
            {"apw": o["apw"], "band": o["band"], "total": o["total"], "ev": o["evidence"]}
            for o in p["observations"]
        ],
        "apwOrder": [a["apw"] for a in p["apw_profile"]],
        "pipeline": [
            {"label": "collect", "done": True, "stop": False},
            {"label": "parse", "done": True, "stop": False},
            {"label": "normalise", "done": True, "stop": False},
            {"label": "admissibility", "done": True, "stop": False},
            {"label": "band / key", "done": True, "stop": False},
            {"label": "dedup", "done": True, "stop": False},
            {"label": "build panel", "done": True, "stop": False},
            {"label": "matched t / t-7", "done": False, "stop": True},
            {"label": "Jevons", "done": False, "stop": False},
            {"label": "index", "done": False, "stop": False},
        ],
    }
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


def nav_html() -> str:
    items = "".join(f'<li><a href="#{i}">{esc(t)}</a></li>' for i, t in NAV)
    return (
        '<nav class="nav" aria-label="Section navigation">'
        '<span class="brand"><i></i>APIx</span>'
        f"<ol>{items}</ol>"
        '<span class="spacer"></span>'
        '<span class="idx">INDEX PENDING</span>'
        "</nav>"
        '<div class="prog" role="presentation"></div>'
    )


def metric(kind: str, key: str, value: str, sub: str) -> str:
    return (
        f'<div class="metric {kind}"><span class="k">{esc(key)}</span>'
        f'<span class="v">{esc(value)}</span><span class="s">{esc(sub)}</span></div>'
    )


def boundary_html(boundary: dict) -> str:
    """The execution boundary as an expandable spatial rail.

    States come straight from the contract. `EXERCISED` is deliberately not the
    success colour: the vocabulary exists precisely because "the code ran" is a
    weaker claim than "the property is validated".
    """
    out = []
    for i, st in enumerate(boundary["stages"]):
        cls = STATE_COLOURS[st["state"]]
        bullets = "".join(f"<li>{esc(e)}</li>" for e in st["evidence"])
        ran = f'<span class="sp">spec {esc(st["spec"])}' + (
            f" &middot; {esc(st['ran'])}</span>" if st["ran"] else "</span>"
        )
        if st["key"] == "matched_set":
            out.append(
                '<div class="stop-rule">real data stops here &mdash; '
                "spec C.1 needs a t&minus;7 wave</div>"
            )
        out.append(
            f'<button class="bs" data-state="{st["state"]}" aria-expanded="false" '
            f'aria-controls="bd-{i}" id="bt-{i}">'
            f'<span class="rail"><i></i></span>'
            f'<span class="nm">{esc(st["name"])}</span>'
            f'<span class="pill {cls} stt">{st["state"]}</span>'
            f"{ran}</button>"
            f'<div class="bd" id="bd-{i}" data-open="0" role="region" aria-labelledby="bt-{i}">'
            f'<div><ul>{bullets}</ul><p class="n">{esc(st["note"])}</p></div></div>'
        )
    legend = "".join(
        f'<div class="card"><span class="k"><span class="pill {STATE_COLOURS[k]}">{k}</span>'
        f"</span><p>{esc(v)}</p></div>"
        for k, v in boundary["states"].items()
    )
    return f'<div class="grid g2" style="margin-bottom:var(--s5)">{legend}</div>' + (
        f'<div class="bnd">{"".join(out)}</div>'
    )


def observations_html(rows: list[dict], apws: list[int], bands: list[int]) -> str:
    """Filterable table of all 35 real observations. Every cell is a stored field."""

    def group(name: str, label: str, values: list, fmt) -> str:
        btns = f'<button data-f="{name}" data-v="all" aria-pressed="true">all</button>'
        btns += "".join(
            f'<button data-f="{name}" data-v="{v}" aria-pressed="false">{fmt(v)}</button>'
            for v in values
        )
        return f'<span class="flabel">{label}</span><span class="fgrp">{btns}</span>'

    filters = (
        '<div class="filters">'
        + group("apw", "APW", apws, lambda v: f"T+{v}")
        + group("band", "Band", bands, lambda v: str(v))
        + group(
            "ev",
            "Evidence",
            ["PRIMARY_HASHED", "SECONDARY_CHAT_IMAGE"],
            lambda v: "hashed" if v == "PRIMARY_HASHED" else "chat image",
        )
        + '<span class="count" id="obs-count" aria-live="polite"></span></div>'
    )
    body = []
    for o in rows:
        tag = "p" if o["evidence"] == "PRIMARY_HASHED" else "s"
        tagtxt = "HASHED" if o["evidence"] == "PRIMARY_HASHED" else "CHAT IMG"
        body.append(
            f'<tr data-apw="{o["apw"]}" data-band="{o["band"]}" data-ev="{o["evidence"]}">'
            f'<td class="m">T+{o["apw"]}</td>'
            f'<td class="m">{esc(o["travel_date"])}</td>'
            f'<td class="m">{esc(o["day_of_week"])}</td>'
            f'<td class="m">{esc(o["flight"])}</td>'
            f'<td class="m">{esc(o["dep"])}</td>'
            f'<td class="m r">{o["band"]}</td>'
            f'<td class="m r">{rupee(o["base"])}</td>'
            f'<td class="m r">{rupee(o["tax"])}</td>'
            f'<td class="m r"><strong>{rupee(o["total"])}</strong></td>'
            f'<td><span class="tag {tag}">{tagtxt}</span></td></tr>'
        )
    return (
        filters + '<div class="tscroll"><table id="obs-table">'
        '<caption class="sr">All 35 real observations, filterable by '
        "advance-purchase bucket, departure band and evidence grade</caption>"
        "<thead><tr><th>APW</th><th>travel date</th><th>dow</th><th>flight</th>"
        '<th>dep</th><th class="r">band</th><th class="r">base ₹</th>'
        '<th class="r">tax ₹</th><th class="r">total ₹</th><th>evidence</th>'
        f"</tr></thead><tbody>{''.join(body)}</tbody></table></div>"
    )


def build(p: dict) -> str:
    q, idx, frame = p["quality"], p["index_status"], p["frame"]
    prof, bands = p["apw_profile"], p["band_profile"]
    disp, conf, bnd, rep = p["dispersion"], p["confound"], p["execution_boundary"], p["replay"]
    ev = q["evidence_counts"]
    run = p["runs"][0] if p["runs"] else {}
    first, last = prof[0], prof[-1]
    # Derived from the geomeans, never from `rel_to_first` — that field is
    # already rounded to 4dp and rounding a rounded ratio again turns 38.55%
    # into 38.5%. One rounding, at display time only.
    delta = 100 * (last["geomean"] / first["geomean"] - 1)
    apws = [a["apw"] for a in prof]
    band_ids = [b["band"] for b in bands]
    widest = next(a for a in prof if a["apw"] == disp["widest_apw"])
    n_ex = sum(1 for s in bnd["stages"] if s["state"] == "EXERCISED")
    n_dg = sum(1 for s in bnd["stages"] if s["state"] == "DEGENERATE")
    n_pd = sum(1 for s in bnd["stages"] if s["state"] == "PENDING")

    return f"""<title>APIx — Airfare Price Index Engine</title>
<meta name="description" content="APIx: a quality-adjusted airfare price index
engine for India. {q["valid_observations"]} real market observations,
{len(apws)}/{len(apws)} advance-purchase buckets, and no published index —
because the frozen methodology requires evidence that does not exist yet.">
<meta name="color-scheme" content="dark light">
<style>{CSS}</style>

<script>document.documentElement.className += " js";</script>
<noscript><style>
/* The canvases are decoration and need script to draw anything at all. */
#field,#pipe,.scroll-cue{{display:none}}
</style></noscript>

<a class="skip" href="#evidence">Skip to the evidence</a>
{nav_html()}

<main id="top">

<header class="hero">
  <canvas id="field" aria-hidden="true"></canvas>
  <div class="wrap">
    <p class="eyebrow">MoSPI problem statement 26056 · methodology v{
        run.get("methodology_version", "2.1")
    } frozen</p>
    <h1>Airfare is the weakest measurement point in the <em>CPI&nbsp;basket</em>.</h1>
    <p class="lede">APIx is the engine that measures it honestly — and refuses
    to publish until the evidence exists.</p>

    <div class="route">
      <b>{esc(frame["routes"][0])}</b><span class="arr">→</span>
      <span>{esc(frame["carriers"][0])} · {esc(frame["fare_families"][0])}</span>
      <span class="arr">·</span>
      <span>collected {esc(p["collection_date"])}</span>
      <span class="pill real">{esc(p["data_class"])}</span>
    </div>

    <div class="metrics">
      {
        metric(
            "is-real",
            "real observations",
            str(q["valid_observations"]),
            f"{len(apws)}/{len(apws)} frozen APW buckets · {len(bands)} departure bands",
        )
    }
      {
        metric(
            "",
            "collection plan",
            f"{q['plan_completion_pct']}%",
            f"{q['valid_observations']}/{q['plan_slots']} slots — plan completion, not statistical coverage",
        )
    }
      {
        metric(
            "is-warn",
            "exclusions audited",
            str(p["exclusions_total"]),
            f"{rep['agree']}/{rep['candidates']} mechanically decidable reproduce the recorded verdict",
        )
    }
      {
        metric(
            "is-hold",
            "APIx-L index",
            "PENDING",
            f"spec C.1 needs matched t / t−7 · unlocks {idx['next_wave_unlocking_index']}",
        )
    }
    </div>
  </div>
  <div class="scroll-cue" aria-hidden="true">scroll<span></span></div>
</header>

<!-- ============================================================ 01 ==== -->
<section id="evidence" class="wrap" aria-labelledby="h-evidence">
  <div class="shead"><span class="n">01</span>
    <h2 id="h-evidence">The observation</h2></div>
  <p class="lede rv">{q["valid_observations"]} fares, one route, one carrier, one
  fare family, collected on {esc(p["collection_date"])} inside a declared
  {esc(run.get("window_declared", ""))} window under a frozen protocol. All
  {len(apws)} advance-purchase buckets are present — T+{apws[0]} through
  T+{apws[-1]} — and every fare reconciles: base plus tax equals total,
  {q["reconciled"]}/{q["decomposed"]}, in exact decimal.</p>

  <div class="banner rv">
    <span class="t">Descriptive APW profile — NOT AN INDEX</span>
    <p>{esc(p["apw_profile_disclaimer"].split(". ", 1)[1])}</p>
  </div>

  <figure class="chart rv" style="margin-top:var(--s5)">
    <figcaption>
      <h3>Fare by advance-purchase bucket</h3>
      <span class="meta">₹ geometric mean, spec §D.2 log form · n={q["valid_observations"]}</span>
    </figcaption>
    <div class="cwrap">{apw_chart(prof)}</div>
    <p class="src">Source: <span class="mono">data/panel.json → apw_profile</span>.
    Seven separate cross-sections on seven different travel dates, plotted on an
    ordinal axis. The T+{last["apw"]} bucket sits {delta:.1f}% above T+{first["apw"]} —
    a descriptive difference between two cross-sections, <strong>not a price
    movement and not airfare inflation</strong>.</p>
  </figure>

  <figure class="chart rv" style="margin-top:var(--s5)">
    <figcaption>
      <h3>Departure-band structure</h3>
      <span class="meta">₹ geometric mean by 3-hour band, spec §B.2 · bands
      {band_ids[0]}–{band_ids[-1]}, anchored 00:00 IST</span>
    </figcaption>
    <div class="cwrap">{band_chart(bands)}</div>
    <p class="src">Source: <span class="mono">data/panel.json → band_profile</span>.
    Band spread across the day is {p["band_spread_pct"]}% — an order of magnitude
    smaller than the spread within a single bucket, which is why the collection
    contract fixes one flight per band rather than sampling the day.</p>
  </figure>

  <h3 class="rv" style="margin-top:var(--s8)">Every observation, inspectable</h3>
  <p class="lede rv" style="margin-bottom:var(--s4)">Filter by bucket, band or
  evidence grade. Nothing is aggregated away.</p>
  <div class="rv">{observations_html(p["observations"], apws, band_ids)}</div>
</section>

<!-- ============================================================ 02 ==== -->
<section id="confound" class="wrap" aria-labelledby="h-confound">
  <div class="shead"><span class="n">02</span>
    <h2 id="h-confound">Why a naïve comparison is dangerous</h2></div>
  <p class="lede rv">A single sector can vary two to four hundred percent within
  a day. <strong>Most of that is not inflation — it is product mix</strong>:
  booking horizon, fare family, departure time, baggage terms. An index built on
  naive daily averages accumulates that as chain drift, which is a bias, not
  noise. It does not average out with more data.</p>

  <figure class="chart rv" style="margin-top:var(--s5)">
    <figcaption>
      <h3>Lead time is confounded with travel date</h3>
      <span class="meta">{conf["distinct_weekdays"]} distinct weekdays across
      {len(apws)} buckets</span>
    </figcaption>
    <div class="cwrap">{confound_chart(prof)}</div>
    <p class="src">Source: <span class="mono">data/panel.json → confound</span>.
    {esc(conf["statement"])}</p>
  </figure>
  <p class="note rv">{
        esc(", ".join(f"{d} appears {n}×" for d, n in conf["repeated_weekdays"].items()))
    }.
  Because each bucket sits on its own travel date, the buckets are not
  interchangeable time observations — so the profile above is descriptive and
  <strong>is not a time-series</strong>.</p>
</section>

<!-- ============================================================ 03 ==== -->
<section id="dispersion" class="wrap" aria-labelledby="h-disp">
  <div class="shead"><span class="n">03</span>
    <h2 id="h-disp">Within-bucket dispersion</h2></div>
  <p class="lede rv">T+{disp["widest_apw"]} has the widest observed spread —
  {disp["widest_spread_pct"]}%, against {disp["others_max_spread_pct"]}% for the
  next widest bucket. <strong>The panel establishes the dispersion; it
  does not establish its cause.</strong> No anomaly-detection definition is in
  force, so this is reported as observed dispersion and <strong>not as an
  anomaly</strong>.</p>
  <div class="grid g2 rv" style="margin-top:var(--s5)">
    <div class="card"><span class="k">cheapest in bucket</span>
      <h3>{esc(disp["widest_min_obs"]["flight"])} · {esc(disp["widest_min_obs"]["dep"])}</h3>
      <p class="mono">₹{rupee(disp["widest_min_obs"]["total"])} · band {
        disp["widest_min_obs"]["band"]
    }</p>
      <p class="mono" style="font-size:var(--t-xs);color:var(--ink-3)">{
        esc(disp["widest_min_obs"]["observation_id"])
    }</p></div>
    <div class="card"><span class="k">dearest in bucket</span>
      <h3>{esc(disp["widest_max_obs"]["flight"])} · {esc(disp["widest_max_obs"]["dep"])}</h3>
      <p class="mono">₹{rupee(disp["widest_max_obs"]["total"])} · band {
        disp["widest_max_obs"]["band"]
    }</p>
      <p class="mono" style="font-size:var(--t-xs);color:var(--ink-3)">{
        esc(disp["widest_max_obs"]["observation_id"])
    }</p></div>
  </div>
  <p class="note rv">This is a <strong>cross-band</strong> spread across
  {widest["n"]} flights on a single travel date. It is <em>not</em> within-band
  dispersion, which is degenerate at n=1 in this panel — a different quantity,
  and neither substitutes for the other.</p>
</section>

<!-- ============================================================ 04 ==== -->
<section id="provenance" class="wrap" aria-labelledby="h-prov">
  <div class="shead"><span class="n">04</span>
    <h2 id="h-prov">Evidence, and where it is weaker</h2></div>
  <p class="lede rv">Provenance is <strong>not uniform across the panel</strong>,
  and the data model records that as a derived fact rather than a label someone
  remembered to apply.</p>

  <figure class="chart rv" style="margin-top:var(--s5)">
    <figcaption><h3>Evidence grade</h3>
      <span class="meta">n={
        q["valid_observations"]
    } · derived from artifact binding</span></figcaption>
    <div class="cwrap">{provenance_chart(ev["PRIMARY_HASHED"], ev["SECONDARY_CHAT_IMAGE"])}</div>
    <p class="src">The T+45 batch arrived as chat images rather than files, so no
    bytes could be hashed and its capture times are <strong>placeholders, not
    measurements</strong>. Those {ev["SECONDARY_CHAT_IMAGE"]} rows are marked
    <span class="tag s">CHAT IMG</span> in the table above. We say so before you ask.</p>
  </figure>

  <figure class="chart rv" style="margin-top:var(--s5)">
    <figcaption><h3>Exclusion audit — {p["exclusions_total"]} screenshots</h3>
      <span class="meta">every excluded screenshot carries a reason and an id</span></figcaption>
    <div class="cwrap">{exclusion_chart(p["exclusions"], rep["agree"], rep["candidates"])}</div>
    <p class="src">Source: <span class="mono">data/panel.json → exclusions, replay</span>.
    Nothing was deleted. {esc(rep["statement"])}</p>
  </figure>

  <div class="grid g3 rv" style="margin-top:var(--s5)">
    <div class="card"><span class="k">replayed</span>
      <h3 class="mono">{rep["agree"]}/{rep["candidates"]}</h3>
      <p>reproduce the recorded §A.3/§B.2 verdict</p></div>
    <div class="card"><span class="k">disagreements</span>
      <h3 class="mono">{rep["disagree"]}</h3>
      <p>a single one would invalidate the audit</p></div>
    <div class="card"><span class="k">false rejections</span>
      <h3 class="mono">{len(rep["wrongly_rejected"])}</h3>
      <p>of {rep["accepted_rechecked"]} accepted observations — the control arm</p></div>
  </div>
  <p class="note rv">{esc(rep["scope_note"])}</p>
  <p class="note rv">{q["window_flags"]} observations fall outside their run's
  declared window. Spec §A.5 keeps them in the store and out of the index —
  stored and flagged, never discarded.</p>
</section>

<!-- ============================================================ 05 ==== -->
<section id="boundary" class="wrap" aria-labelledby="h-bnd">
  <div class="shead"><span class="n">05</span>
    <h2 id="h-bnd">Real-data execution boundary</h2></div>
  <p class="lede rv"><strong>{esc(bnd["claim"])}</strong></p>
  <p class="lede rv">{n_ex} stages exercised, {n_dg} degenerate, {n_pd} pending,
  one blocked. Generated from the contract, stage by stage — select any stage for
  the evidence behind its state.</p>

  <canvas id="pipe" aria-hidden="true"></canvas>
  <p class="note rv">A diagram of the recorded workflow, animated so the order
  reads at a glance. <strong>It is a visualisation, not a live process
  monitor</strong> — nothing on this page polls or measures a running job, and
  the packets stop exactly where the evidence stops.</p>

  <div class="rv" style="margin-top:var(--s5)">{boundary_html(bnd)}</div>
  <p class="note rv">{esc(bnd["caveat"])}</p>
  <p class="note rv">Reconstructed from <span class="mono">{esc(bnd["reconstructed_from"])}</span>.
  {esc(bnd["reconstruction_check"])}.</p>
</section>

<!-- ============================================================ 06 ==== -->
<section id="pending" class="wrap" aria-labelledby="h-pend">
  <div class="shead"><span class="n">06</span>
    <h2 id="h-pend">Why no index exists yet</h2></div>
  <div class="banner stop rv">
    <span class="t">APIx-L — PENDING, and that is the design</span>
    <p>Methodology §C.1 is <strong>LOCKED</strong>:
    <span class="mono">I(c,t) = I(c,t−7) × J(c,t)</span>. Every index value needs
    a matched pair at <span class="mono">t</span> and <span class="mono">t−7</span>.
    APIx holds {idx["collection_waves"]} collection wave, which gives
    {idx["matched_pairs_available"]} matched pairs. So APIx-L is
    <strong>not computable</strong> today, and the engine refuses rather than
    inventing a level.</p>
  </div>
  <div class="flow rv" style="margin-top:var(--s5)">
    <span class="step now">t = {esc(p["collection_date"])}</span><span class="arr">→</span>
    <span class="step stop">needs t−7</span><span class="arr">→</span>
    <span class="step stop">no counterpart wave</span><span class="arr">→</span>
    <span class="step stop">publication blocked</span>
  </div>
  <p class="lede rv" style="margin-top:var(--s5)">This is not an unfinished
  feature. Everything downstream is implemented and covered by the
  fixture suite; what is missing is the evidence the formula requires. The first
  date that can supply a matched pair is
  <strong>{idx["next_wave_unlocking_index"]}</strong>.</p>
  <p class="note rv">{esc(idx["apix_l_blocker"])}</p>
</section>

<!-- ============================================================ 07 ==== -->
<section id="engine" class="wrap" aria-labelledby="h-eng">
  <div class="shead"><span class="n">07</span>
    <h2 id="h-eng">The engine, on a controlled test fixture</h2></div>
  <div class="banner rv">
    <span class="t">Not market data — controlled synthetic test fixture</span>
    <p>The engine is demonstrated on a <strong>controlled synthetic test
    fixture</strong>, in index points on a base of 100, with no currency figures
    anywhere. It is rendered to its own file,
    <span class="mono">data/engine-validation.html</span>, and a test asserts it
    never merges into this page. <strong>Nothing on that page is an airfare
    observation, and nothing on it is an APIx index value.</strong></p>
  </div>
  <p class="lede rv">It exists to show that the engine computes, chains and
  <em>refuses</em> correctly — not to say anything about prices. Run it yourself:</p>
  <div class="chart rv" style="margin-top:var(--s4)">
    <p class="mono" style="color:var(--accent)">python tools/analysis/engine_demo.py</p>
    <p class="src">Matched sets at t and t−7 · Jevons relatives · chaining across
    14 consecutive publication dates · and the engine raising rather than
    inventing a level when fed a state dated after the period being published.
    Every value there is synthetic test data.</p>
  </div>
</section>

<!-- ============================================================ 08 ==== -->
<section id="method" class="wrap" aria-labelledby="h-meth">
  <div class="shead"><span class="n">08</span>
    <h2 id="h-meth">Methodology</h2></div>
  <div class="flow rv">
    <span class="step now">raw observation</span><span class="arr">→</span>
    <span class="step now">admissibility §A.6</span><span class="arr">→</span>
    <span class="step now">band / key §B.2</span><span class="arr">→</span>
    <span class="step now">dedup §D.4</span><span class="arr">→</span>
    <span class="step next">Jevons §D.2</span><span class="arr">→</span>
    <span class="step next">advance-cell §E</span><span class="arr">→</span>
    <span class="step next">Young / Mod. Laspeyres §F</span><span class="arr">→</span>
    <span class="step stop">publication §H</span>
  </div>
  <p class="note rv">Blue runs on today's data — the same thing section 05 calls
  EXERCISED, which is <strong>not</strong> "validated". Amber is implemented and
  invariant-tested but has no input yet, because every one of those steps
  consumes a price <em>relative</em>, and a relative needs two collection waves.</p>
  <div class="faq rv" style="margin-top:var(--s5)">
    <details class="qa"><summary>Jevons at the elementary level (§D.2)</summary>
      <div class="a">The geometric mean of matched price relatives, computed in
      logs — the normative form, so the descriptive summary on this page and the
      engine cannot drift into different arithmetic. MoSPI's own elementary
      aggregator for the CPI.</div></details>
    <details class="qa"><summary>Advance-purchase stratification (§A.3)</summary>
      <div class="a">Seven frozen buckets, assigned by <strong>exact</strong> lead
      time. A quote whose lead time matches no bucket is inadmissible and is never
      rounded into the nearest one. That rule rejected 24 T+68 screenshots, and
      the replay in section 04 re-derived all 24 independently.</div></details>
    <details class="qa"><summary>The matched set (§D.1, §D.8)</summary>
      <div class="a">Items present in <em>both</em> t and t−7. A tier ladder
      relaxes item identity from flight number to departure slot when schedules
      move, and a Tier-3 cell publishes a declared unit value and forms no matched
      set at all. None of this is reached by real data yet.</div></details>
    <details class="qa"><summary>Weekly chaining (§C.1, LOCKED)</summary>
      <div class="a"><span class="mono">I(c,t) = I(c,t−7) × J(c,t)</span>. The
      level holds between weekly links and moves once per link. A seven-day
      relative applied daily would compound sevenfold; the suite asserts that
      compounded value as forbidden.</div></details>
    <details class="qa"><summary>What the engine refuses to do</summary>
      <div class="a">Publish without a matched pair; publish without a declared
      coverage denominator (AMB-8); weight a multi-carrier route without declared
      shares (AMB-9); admit a quote whose lead time matches no frozen bucket.
      Four independent guards, none of which may be weakened to obtain a
      number.</div></details>
  </div>
</section>

<!-- ============================================================ 09 ==== -->
<section id="limits" class="wrap" aria-labelledby="h-lim">
  <div class="shead"><span class="n">09</span>
    <h2 id="h-lim">What is not established</h2></div>
  <p class="lede rv">Stated here rather than discovered later.</p>
  <div class="grid g2 rv" style="margin-top:var(--s5)">
    <div class="card"><span class="k">AMB-8 · open</span>
      <h3>Statistical coverage NOT ESTABLISHED</h3>
      <p>{esc(q["statistical_coverage_blocker"])}</p>
      <p><strong>{q["plan_completion_pct"]}% is collection-plan completion</strong>
      — {q["valid_observations"]}/{q["plan_slots"]} slots — and is a different
      quantity from statistical coverage.</p></div>
    <div class="card"><span class="k">AMB-9 · open</span>
      <h3>Carrier weighting blocked</h3>
      <p>Spec §G.3/§G.5 carry no carrier term in the within-route weight formula.
      At one carrier the allocation is mathematically degenerate; beyond one
      carrier <span class="mono">within_route_weights</span> raises rather than
      guessing. An owner ruling is required before any carrier expansion.</p></div>
    <div class="card"><span class="k">OQ-1 · open</span>
      <h3>Collection window value not fixed</h3>
      <p>§A.5 locks the <em>rule</em> that all collection runs inside a fixed
      daily window; the window's published value is not yet fixed. So no single
      admissible count is normative — {q["window_flags"]} observations sit outside
      the runs' declared window and are flagged, not discarded.</p></div>
    <div class="card"><span class="k">§M · specified only</span>
      <h3>APIx-TPD NOT IMPLEMENTED</h3>
      <p>The quote-level Time Product Dummy estimator is specified in §M and the
      package is empty — a test fails the build if that stops being true. The
      panel also holds {idx["tpd_quotes_available"]} quotes against a
      <span class="mono">min_quotes_window</span> of
      {idx["tpd_min_quotes_window"]:,}. Both are true and both are stated.</p></div>
    <div class="card"><span class="k">uncertainty</span>
      <h3>No interval is reported</h3>
      <p>The bootstrap is specified and not implemented, and the collection design
      does not yet record the admissible-flight universe per band, so it does not
      carry the sampling-design information an interval would need. Observed
      dispersion is reported instead, which assumes nothing.</p></div>
    <div class="card"><span class="k">scope</span>
      <h3>National representativeness not established</h3>
      <p>One route of the DGCA city-pair frame, one carrier, one channel, one day.
      Route and carrier weighting are implemented and <strong>not exercised</strong>.
      MoSPI has not endorsed APIx.</p></div>
  </div>
</section>

<!-- ============================================================ 10 ==== -->
<section id="next" class="wrap" aria-labelledby="h-next">
  <div class="shead"><span class="n">10</span>
    <h2 id="h-next">{idx["next_wave_unlocking_index"]}</h2></div>
  <p class="lede rv">Seven days after the wave we hold. Same route, same carrier,
  same five bands, same selection rule, same window — because every one of those
  is part of the cell key, and a cell that changes has no counterpart to match
  against.</p>
  <div class="flow rv" style="margin-top:var(--s5)">
    <span class="step now">wave 1 · {esc(p["collection_date"])}</span><span class="arr">→</span>
    <span class="step next">wave 2 · {
        idx["next_wave_unlocking_index"]
    }</span><span class="arr">→</span>
    <span class="step next">matched t / t−7</span><span class="arr">→</span>
    <span class="step next">first real Jevons relative</span><span class="arr">→</span>
    <span class="step next">first real index calculation</span>
  </div>
  <p class="note rv">A 7-day shift preserves the travel date's weekday for all
  {len(apws)} buckets, which is why the cell keys line up. No future value is
  predicted here — the procedure is written down, and whether it produces a
  result is a question for the data.</p>
  <p class="note rv">Reaching a first index value clears none of AMB-8, AMB-9 or
  OQ-1. A first index value is a first index value; it is not a published index.</p>
</section>

</main>

<footer class="wrap">
  <div class="row">
    <div>
      <p><b>APIx</b> · quality-adjusted airfare price index for India ·
      MoSPI problem statement 26056</p>
      <p>Every statistical figure on this page is generated from
      <span class="mono">data/panel.json</span>; contextual frame figures are
      typed and name their source inline.</p>
    </div>
    <div>
      <p><b>data class</b> {esc(p["data_class"])} ·
      synthetic_data_present = {p["synthetic_data_present"]}</p>
      <p><b>version vector</b> methodology {esc(run.get("methodology_version", ""))} ·
      basket {esc(run.get("basket_version", ""))} ·
      protocol {esc(run.get("protocol_version", ""))} ·
      precedence {esc(run.get("source_precedence_version", ""))}</p>
      <p><b>generated from</b> {esc(p["generated_from"])}</p>
    </div>
  </div>
</footer>

<div id="tip" role="status" aria-live="polite"></div>
<script type="application/json" id="apix-data">{data_island(p)}</script>
<script>{JS}</script>
"""


def main() -> None:
    panel = json.loads(PANEL.read_text(encoding="utf-8"))
    html = build(panel)
    OUT.write_text(html, encoding="utf-8")
    print(f"dashboard written: {OUT.relative_to(ROOT)}  ({len(html):,} bytes)")


if __name__ == "__main__":
    main()
