"""Render `data/dashboard.html` — the jury-facing APIx experience.

    data/panel.json  ->  this module  ->  data/dashboard.html

**One data source, and it is not this file.** Every statistical figure is read
from the panel contract at render time. This module owns narrative, layout and
language; it owns no numbers. `tests/test_observed_panel.py` fails the build if
any headline figure here disagrees with the contract.

**It is a document, not a dashboard.** The page is an editorial sequence —
landing, story, data, confound, evidence, forensics, engine, limitation, index
pending, the unlock, and only then the evidence vault. Chapters change ground
colour rather than stacking cards, because a reader should know which chapter
they are in before reading a word.

Design system: `dashboard_theme.py`. Charts and choreography: `dashboard_viz.py`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dashboard_theme import CSS, FONT_HREF, STATE_COLOURS  # noqa: E402
from dashboard_viz import (  # noqa: E402
    JS,
    apw_chart,
    band_chart,
    confound_chart,
    esc,
    rupee,
)

PANEL = ROOT / "data" / "panel.json"
OUT = ROOT / "data" / "dashboard.html"

#: CDN libraries. Every one is feature-detected in the page script; none is
#: required for the content to render. Pinned so the artifact stays stable.
LIBS = (
    "https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/gsap.min.js",
    "https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/ScrollTrigger.min.js",
    "https://cdn.jsdelivr.net/npm/lenis@1.1.13/dist/lenis.min.js",
)

#: Chapter id -> label. The dot navigation is generated from this, so a chapter
#: cannot exist without a way to reach it.
CHAPTERS = [
    ("observation", "The observation"),
    ("rail", "Seven buckets"),
    ("delta", "The difference"),
    ("confound", "The confound"),
    ("dispersion", "Dispersion"),
    ("evidence", "Evidence"),
    ("forensics", "Forensics"),
    ("engine", "Execution"),
    ("pending", "Index status"),
    ("unlock", "19 September"),
    ("vault", "Evidence vault"),
]


def lines(*parts: str) -> str:
    """A heading whose lines ride up from behind their own clip."""
    inner = "".join(f"<span>{p}</span>" for p in parts)
    return f'<span class="line-mask">{inner}</span>'


def island(p: dict) -> str:
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
            {
                "apw": o["apw"],
                "band": o["band"],
                "total": o["total"],
                "ev": o["evidence"],
                "flight": o["flight"],
                "td": o["travel_date"],
                "observation_id": o["observation_id"],
            }
            for o in p["observations"]
        ],
        "apwOrder": [a["apw"] for a in p["apw_profile"]],
    }
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


def nav(p: dict) -> str:
    dots = "".join(f'<a href="#{i}" aria-label="{esc(label)}"></a>' for i, label in CHAPTERS)
    return (
        '<nav class="nav" aria-label="Chapters">'
        '<span class="brand"><i></i>APIx</span>'
        f'<span class="dots">{dots}</span>'
        '<span class="sp"></span>'
        '<span class="chip">INDEX PENDING</span>'
        "</nav>"
    )


def rail(profile: list[dict]) -> str:
    """The seven advance-purchase buckets as a horizontal journey."""
    widest = max(a["spread_pct"] for a in profile)
    panels = []
    for a in profile:
        pct = a["spread_pct"] / widest * 100
        panels.append(
            f'<article class="rail-panel">'
            f'<p class="meta">bucket {profile.index(a) + 1} of {len(profile)}</p>'
            f'<h3 class="apw">T+{a["apw"]}</h3>'
            f'<p class="when">{esc(a["day_of_week"])} {esc(a["travel_date"])}'
            f" &#183; {a['n']} observations</p>"
            f'<dl class="rail-figs">'
            f"<div><dt>geometric mean</dt><dd>&#8377;{rupee(a['geomean'])}</dd></div>"
            f"<div><dt>spread</dt><dd>{a['spread_pct']}%</dd></div>"
            f"<div><dt>observed min</dt><dd>&#8377;{rupee(a['min'])}</dd></div>"
            f"<div><dt>observed max</dt><dd>&#8377;{rupee(a['max'])}</dd></div>"
            f"</dl>"
            f'<div class="rail-bar"><i style="width:{pct:.1f}%"></i></div>'
            f'<p class="meta" style="margin-top:var(--s3)">spread, relative to the '
            f"widest bucket</p>"
            f"</article>"
        )
    return (
        '<div class="rail-outer"><div class="rail-pin">'
        f'<div class="rail-track">{"".join(panels)}</div>'
        "</div></div>"
    )


def wall(rows: list[dict]) -> str:
    """One tile per real observation, grouped by evidence grade.

    No screenshot thumbnails: the artifacts are not in the repository, and a
    placeholder image would be a fabricated evidence asset.
    """
    prim = [(i, o) for i, o in enumerate(rows) if o["evidence"] == "PRIMARY_HASHED"]
    sec = [(i, o) for i, o in enumerate(rows) if o["evidence"] != "PRIMARY_HASHED"]

    def tiles(group: list[tuple[int, dict]]) -> str:
        return "".join(
            f'<button data-i="{i}" data-ev="{o["evidence"]}" '
            f'aria-label="{esc(o["flight"])} on {esc(o["travel_date"])}, T plus '
            f"{o['apw']}, band {o['band']}, "
            f"{'bound to a hashed screenshot' if o['evidence'] == 'PRIMARY_HASHED' else 'from a chat image, no bytes hashed'}"
            f'"></button>'
            for i, o in group
        )

    return (
        f'<div class="wall">{tiles(prim)}</div>'
        f'<p class="meta" style="margin-top:var(--s5)">'
        f"{len(sec)} observations arrived separately</p>"
        f'<div class="wall" style="max-width:280px">{tiles(sec)}</div>'
        f'<div class="wall-key">'
        f'<span><i style="background:var(--green-wash)"></i>'
        f"{len(prim)} PRIMARY_HASHED &#183; bound to a SHA-256 screenshot</span>"
        f'<span><i style="background:var(--amber-wash)"></i>'
        f"{len(sec)} SECONDARY_CHAT_IMAGE &#183; no bytes hashed</span>"
        f"</div>"
    )


def decomposition(exclusions: list[dict], total: int) -> str:
    """The 122 excluded screenshots, by recorded reason, largest first."""
    mech = ("APW_MATCHES_NO_BUCKET", "OUTSIDE_CONTRACTED_BANDS")
    biggest = max(e["count"] for e in exclusions)
    rows = []
    for e in sorted(exclusions, key=lambda e: -e["count"]):
        is_mech = any(e["reason"].startswith(m) for m in mech)
        label = e["reason"].split(" (")[0]
        rows.append(
            f'<div class="row" data-mech="{1 if is_mech else 0}">'
            f'<span class="n">{e["count"]}</span>'
            f'<span class="track"><i style="width:{e["count"] / biggest * 100:.1f}%"></i></span>'
            f'<span class="lab">{esc(label)}</span></div>'
        )
    return f'<div class="decomp">{"".join(rows)}</div>'


def stages_html(boundary: dict) -> str:
    out = []
    for i, st in enumerate(boundary["stages"]):
        cls = STATE_COLOURS[st["state"]]
        bullets = "".join(f"<li>{esc(e)}</li>" for e in st["evidence"])
        spec = f"spec {esc(st['spec'])}" + (f" &#183; {esc(st['ran'])}" if st["ran"] else "")
        if st["key"] == "matched_set":
            out.append(
                '<p class="stop-line">real data stops here &#183; '
                "spec C.1 needs a t&minus;7 wave</p>"
            )
        out.append(
            f'<button class="stage" data-state="{st["state"]}" aria-expanded="false" '
            f'aria-controls="sb-{i}" id="sbt-{i}">'
            f'<span class="dot"></span>'
            f'<span><span class="nm">{esc(st["name"])}</span>'
            f'<span class="sp">{spec}</span></span>'
            f'<span class="state {cls}">{st["state"]}</span></button>'
            f'<div class="stage-body" id="sb-{i}" data-open="0" role="region" '
            f'aria-labelledby="sbt-{i}"><div>'
            f'<ul>{bullets}</ul><p class="note">{esc(st["note"])}</p>'
            f"</div></div>"
        )
    return f'<div class="stages">{"".join(out)}</div>'


def vault(rows: list[dict], apws: list[int], bands: list[int]) -> str:
    def group(name: str, label: str, values: list, fmt) -> str:
        btns = f'<button data-f="{name}" data-v="all" aria-pressed="true">all</button>'
        btns += "".join(
            f'<button data-f="{name}" data-v="{v}" aria-pressed="false">{fmt(v)}</button>'
            for v in values
        )
        return f'<span class="fset"><span>{label}</span>{btns}</span>'

    filters = (
        '<div class="filters">'
        + group("apw", "APW", apws, lambda v: f"T+{v}")
        + group("band", "Band", bands, str)
        + group(
            "ev",
            "Evidence",
            ["PRIMARY_HASHED", "SECONDARY_CHAT_IMAGE"],
            lambda v: "hashed" if v == "PRIMARY_HASHED" else "chat image",
        )
        + '<span class="vcount" id="obs-count" aria-live="polite"></span></div>'
    )
    body = []
    for o in rows:
        pill = "p" if o["evidence"] == "PRIMARY_HASHED" else "s"
        txt = "HASHED" if o["evidence"] == "PRIMARY_HASHED" else "CHAT IMG"
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
            f'<td><span class="pill {pill}">{txt}</span></td></tr>'
        )
    return (
        filters + '<div class="tscroll"><table id="obs-table">'
        '<caption class="sr">Every real observation, filterable by '
        "advance-purchase bucket, departure band and evidence grade</caption>"
        "<thead><tr><th>APW</th><th>travel date</th><th>dow</th><th>flight</th>"
        '<th>dep</th><th class="r">band</th><th class="r">base</th>'
        '<th class="r">tax</th><th class="r">total</th><th>evidence</th>'
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
    # already rounded to 4dp, and rounding a rounded ratio again turns 38.55%
    # into 38.5%. One rounding, at display time only.
    delta = 100 * (last["geomean"] / first["geomean"] - 1)
    apws = [a["apw"] for a in prof]
    band_ids = [b["band"] for b in bands]
    widest = next(a for a in prof if a["apw"] == disp["widest_apw"])
    # The audit universe, derived two independent ways and asserted to agree.
    # The file corpus is what the collector photographed on the collection date;
    # the T+45 batch arrived separately as chat images and is exactly the
    # SECONDARY_CHAT_IMAGE group. So the exclusion accounting and the provenance
    # split are the same accounting seen from two sides.
    file_corpus = p["exclusions_total"] + ev["PRIMARY_HASHED"]
    chat_batch = ev["SECONDARY_CHAT_IMAGE"]
    # Which buckets the weaker-provenance batch actually belongs to, derived —
    # it is not simply the last bucket, and guessing produced a wrong label once.
    chat_buckets = sorted(
        {o["apw"] for o in p["observations"] if o["evidence"] == "SECONDARY_CHAT_IMAGE"}
    )
    chat_label = ", ".join(f"T+{a}" for a in chat_buckets)
    audited = file_corpus + chat_batch
    if audited != p["exclusions_total"] + q["valid_observations"]:
        raise ValueError(
            f"the audit ladder no longer closes: {file_corpus} + {chat_batch} != "
            f"{p['exclusions_total']} + {q['valid_observations']}"
        )
    libs = "".join(f'<script src="{u}" defer></script>' for u in LIBS)

    return f"""<title>APIx — Airfare Price Index Engine</title>
<meta name="description" content="APIx: an auditable airfare measurement engine
built for CPI augmentation. {q["valid_observations"]} real market observations,
seven advance-purchase buckets, and no published index — because the frozen
methodology requires evidence that does not exist yet.">
<meta charset="utf-8">
<!-- Without this a phone lays the page out at 980px and zooms out, so every
     responsive rule below the tablet breakpoint never fires on real hardware. -->
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="color-scheme" content="light">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{FONT_HREF}">
<style>{CSS}</style>
<script>document.documentElement.className += " js";</script>
{libs}

<a class="skip" href="#observation">Skip to the evidence</a>
{nav(p)}

<main>

<!-- ═══════════════════════════════════════════════ LANDING ═══════════ -->
<header class="hero">
  <canvas id="field" aria-hidden="true"></canvas>
  <div class="wrap">
    <p class="eyebrow">MoSPI problem statement 26056</p>
    <h1>{lines("Airfare.", "Measured", "correctly.")}</h1>
    <p class="sub rv" data-d="2">An auditable airfare measurement engine,
    built for CPI augmentation — and the evidence rules that decide when it
    may publish.</p>
  </div>
  <div class="wrap hero-foot">
    <p class="meta">{esc(frame["routes"][0])} &#183; {esc(frame["carriers"][0])}
    &#183; methodology v{esc(run.get("methodology_version", ""))} frozen</p>
    <p class="cue"><i></i>scroll</p>
  </div>
</header>

<!-- ═══════════════════════════════════════════════ STORY ═════════════ -->
<section class="ch ch-paper ch-scene" aria-label="Why airfare is hard to measure">
  <div class="wrap scene">
    <div>
      <h2 class="stmt">{lines("Airfare is", "volatile.")}</h2>
      <p class="after rv">A single sector can vary two to four hundred percent
      inside one day. Rail, fuel, telephone, postage — every other line in the
      CPI transport basket is priced from an administrative source with one
      authoritative provider. Airfare is read off a commercial website that
      reprices continuously.</p>
    </div>
  </div>
  <div class="wrap scene right">
    <div>
      <h2 class="stmt">{lines("But volatility", "is not", "<em>inflation</em>.")}</h2>
      <p class="after rv">Most of that movement is product mix — booking
      horizon, fare family, departure time, baggage terms. An index built on
      naive daily averages accumulates it as chain drift. That is a bias, not
      noise, and it does not average out with more data.</p>
    </div>
  </div>
</section>

<!-- ═══════════════════════════════════════════════ OBSERVATION ═══════ -->
<section class="ch ch-paper" id="observation" aria-labelledby="h-obs">
  <div class="wrap">
    <div class="split">
      <div class="stick">
        <p class="eyebrow">Chapter 01</p>
        <h2 id="h-obs">{lines("The", "observation")}</h2>
        <p class="lede rv" style="margin-top:var(--s4)">One route, one carrier,
        one fare family, one collection wave — inside a declared
        {esc(run.get("window_declared", ""))} window under a frozen protocol.</p>
        <p class="meta rv" data-d="1" style="margin-top:var(--s5)">
        {esc(p["data_class"])}</p>
      </div>
      <div>
        <p class="figure-xl rv" data-count="{q["valid_observations"]}">{q["valid_observations"]}</p>
        <p class="figure-note rv" data-d="1">real market observations, collected
        {esc(p["collection_date"])} on {esc(frame["routes"][0])}. Every fare
        reconciles — base plus tax equals total, {q["reconciled"]}/{q["decomposed"]},
        in exact decimal. {q["plan_completion_pct"]}% of the collection plan
        ({q["valid_observations"]}/{q["plan_slots"]} slots) is filled: that is
        plan completion, and it is not statistical coverage.</p>

        <p class="figure-xl amber rv" data-d="2"
           style="margin-top:var(--s8)">{len(apws)}<span
           style="font-size:.34em;letter-spacing:-.02em"> / {len(apws)}</span></p>
        <p class="figure-note rv" data-d="3">frozen advance-purchase buckets,
        T+{apws[0]} through T+{apws[-1]}, assigned by exact lead time. A quote
        matching no bucket is inadmissible and is never rounded into the
        nearest one.</p>
      </div>
    </div>

    <div class="plain rv" style="margin-top:var(--s8)">
      <p class="q">What is an advance-purchase bucket?</p>
      <p class="a">How many days before the flight the ticket was priced. We
      always look {len(apws)} fixed distances ahead — {apws[0]} day, then
      {apws[1]}, then {apws[2]}, out to {apws[-1]} — so we are comparing
      "booked a day early" with "booked a day early", not with "booked two
      months early".</p>
      <details class="tech"><summary>Technical view</summary>
        <p class="body">Spec A.3 assigns a bucket by <strong>exact</strong> lead
        time. A quote whose lead time matches no frozen bucket is inadmissible
        and is never rounded into the nearest one — that rule rejected 24 T+68
        screenshots, and the replay later re-derived all 24 independently.</p>
        <p class="eq">APW = {{{", ".join(f"T+{a}" for a in apws)}}}<br>
        lead_time_days = travel_date &#8722; collection_date<br>
        bucket(q) = APWBucket.from_lead_time(lead_time_days)  &#8594;  None is inadmissible</p>
      </details>
    </div>

    <p class="eyebrow" style="margin-top:var(--s9)">DESCRIPTIVE APW PROFILE —
    NOT AN INDEX</p>
    <p class="lede rv" style="max-width:52ch">{esc(p["apw_profile_disclaimer"].split(". ", 1)[1])}</p>

    <figure class="chart rv">
      <figcaption>
        <h3>Fare by advance-purchase bucket</h3>
        <p class="meta">geometric mean, spec D.2 log form &#183;
        n={q["valid_observations"]}</p>
      </figcaption>
      <div class="cwrap">{apw_chart(prof)}</div>
      <p class="src">Source <span class="mono">data/panel.json &#8594; apw_profile</span>.
      Seven separate cross-sections on seven different travel dates, drawn on an
      ordinal axis.</p>
    </figure>

    <figure class="chart rv" style="margin-top:var(--s8)">
      <figcaption>
        <h3>Departure-band structure</h3>
        <p class="meta">spec B.2 &#183; bands {band_ids[0]}&#8211;{band_ids[-1]},
        3-hour, anchored 00:00 IST</p>
      </figcaption>
      <div class="cwrap">{band_chart(bands)}</div>
      <p class="src">Spread across the day is {p["band_spread_pct"]}% — an order
      of magnitude smaller than the spread inside a single bucket, which is why
      the contract fixes one flight per band rather than sampling the day.</p>
    </figure>
  </div>
</section>

<!-- ═══════════════════════════════════════════════ RAIL ══════════════ -->
<section class="ch ch-neutral" id="rail" aria-labelledby="h-rail"
         style="padding-block:var(--s7)">
  <div class="wrap">
    <p class="eyebrow">Chapter 02</p>
    <h2 id="h-rail">{lines("Seven buckets,", "seven travel dates")}</h2>
    <p class="lede rv" style="margin-top:var(--s4)">Each one is a separate
    cross-section. Scroll sideways through them.</p>
  </div>
  {rail(prof)}
</section>

<!-- ═══════════════════════════════════════════════ THE DIFFERENCE ════ -->
<section class="ch ch-neutral ch-scene" id="delta" aria-labelledby="h-delta">
  <div class="wrap scene">
    <div>
      <p class="eyebrow">Chapter 03</p>
      <p class="figure-xl amber rv" data-count="{delta:.1f}" data-dp="1"
         data-pre="+" data-post="%">+{delta:.1f}%</p>
      <h2 id="h-delta" class="sr">The T+{last["apw"]} to T+{first["apw"]} difference</h2>
      <p class="figure-note rv" data-d="1" style="font-size:var(--t-sub);
         font-family:var(--disp);max-width:30ch;line-height:1.4">
      T+{last["apw"]} sits {delta:.1f}% above T+{first["apw"]}.</p>
      <p class="after rv" data-d="2" style="max-width:44ch">
      <strong>The panel shows a descriptive difference between two
      cross-sections. Its cause cannot be established from these
      observations.</strong> It is not a price movement, and it is
      <strong>not airfare inflation</strong> — the two buckets sit on different
      travel dates and different weekdays.</p>
    </div>
  </div>
</section>

<!-- ═══════════════════════════════════════════════ CONFOUND ══════════ -->
<section class="ch ch-neutral" id="confound" aria-labelledby="h-conf">
  <div class="wrap">
    <p class="eyebrow">Chapter 04</p>
    <h2 id="h-conf">{lines("Lead time is", "confounded with", "travel date")}</h2>
    <p class="lede rv" style="margin-top:var(--s4)">{len(apws)} buckets land on
    {conf["distinct_weekdays"]} distinct weekdays.
    {esc(", ".join(f"{d} appears {n} times" for d, n in conf["repeated_weekdays"].items()))}.</p>
    <div class="plain rv" data-d="1" style="margin-top:var(--s6)">
      <p class="q">Why does that matter?</p>
      <p class="a">Each bucket was priced for a <strong>different day of
      travel</strong>. T+{prof[0]["apw"]} is a {esc(prof[0]["day_of_week"])}
      flight, T+{prof[1]["apw"]} is a {esc(prof[1]["day_of_week"])} flight,
      T+{prof[2]["apw"]} is a {esc(prof[2]["day_of_week"])} flight. So if two
      buckets differ, we cannot tell whether it was the booking horizon that
      moved the price, or simply that one of them is a weekend.</p>
      <p class="a" style="margin-top:var(--s3)">These {len(apws)} numbers are
      <strong>not {len(apws)} days of inflation</strong>. Different booking
      horizons are attached to different travel dates.</p>
    </div>

    <figure class="chart rv" data-d="2">
      <div class="cwrap">{confound_chart(prof)}</div>
      <p class="src">{esc(conf["statement"])}</p>
    </figure>
  </div>
</section>

<!-- ═══════════════════════════════════════════════ DISPERSION ════════ -->
<section class="ch ch-paper" id="dispersion" aria-labelledby="h-disp">
  <div class="wrap split">
    <div class="stick">
      <p class="eyebrow">Chapter 05</p>
      <h2 id="h-disp">{lines("Within-bucket dispersion")}</h2>
    </div>
    <div>
      <p class="lede rv">T+{disp["widest_apw"]} has the widest observed spread —
      {disp["widest_spread_pct"]}%, against {disp["others_max_spread_pct"]}% for
      the next widest bucket.</p>
      <p class="body rv" data-d="1" style="margin-top:var(--s4)">
      <strong>The panel establishes the dispersion; it does not establish its
      cause.</strong> No anomaly-detection definition is in force, so this is
      reported as observed dispersion and <strong>not as an anomaly</strong>.</p>
      <div class="rv" data-d="2" style="margin-top:var(--s6);display:grid;
           grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:var(--s5)">
        <div><p class="meta">cheapest in bucket</p>
          <p class="mono" style="font-size:22px;margin-top:6px">
          {esc(disp["widest_min_obs"]["flight"])}</p>
          <p class="mono" style="color:var(--ink-3);font-size:var(--t-xs)">
          {esc(disp["widest_min_obs"]["dep"])} &#183; band
          {disp["widest_min_obs"]["band"]} &#183;
          &#8377;{rupee(disp["widest_min_obs"]["total"])}</p>
          <p class="mono" style="color:var(--ink-3);font-size:var(--t-2xs);
             margin-top:6px">{esc(disp["widest_min_obs"]["observation_id"])}</p></div>
        <div><p class="meta">dearest in bucket</p>
          <p class="mono" style="font-size:22px;margin-top:6px">
          {esc(disp["widest_max_obs"]["flight"])}</p>
          <p class="mono" style="color:var(--ink-3);font-size:var(--t-xs)">
          {esc(disp["widest_max_obs"]["dep"])} &#183; band
          {disp["widest_max_obs"]["band"]} &#183;
          &#8377;{rupee(disp["widest_max_obs"]["total"])}</p>
          <p class="mono" style="color:var(--ink-3);font-size:var(--t-2xs);
             margin-top:6px">{esc(disp["widest_max_obs"]["observation_id"])}</p></div>
      </div>
      <p class="body rv" data-d="3" style="margin-top:var(--s5)">This is a
      <strong>cross-band</strong> spread across {widest["n"]} flights on a single
      travel date. It is not within-band dispersion, which is degenerate at n=1
      in this panel — a different quantity, and neither substitutes for the
      other.</p>
    </div>
  </div>
</section>

<!-- ═══════════════════════════════════════════════ EVIDENCE ══════════ -->
<section class="ch ch-sky" id="evidence" aria-labelledby="h-ev">
  <div class="wrap split">
    <div class="stick">
      <p class="eyebrow">Chapter 06</p>
      <h2 id="h-ev">{lines("Evidence,", "and where it", "is weaker")}</h2>
      <p class="lede rv" style="margin-top:var(--s4)">Provenance is not uniform
      across the panel, and the data model records that as a derived fact rather
      than a label someone remembered to apply.</p>
    </div>
    <div>
      {wall(p["observations"])}
      <p class="body rv" style="margin-top:var(--s5)">An observation is
      <span class="mono">PRIMARY_HASHED</span> only if its run actually carries a
      content-addressed artifact. The {ev["SECONDARY_CHAT_IMAGE"]} in the second
      group arrived as chat images rather than files, so no bytes could be hashed
      and their capture times are <strong>placeholders, not measurements</strong>.
      They are not scattered through the panel either &#8212; they are the whole
      of {chat_label}, so that bucket rests entirely on weaker evidence. We say
      so before you ask.</p>
      <p class="body rv" data-d="1" style="margin-top:var(--s3)">
      {q["window_flags"]} observations fall outside their run's declared window.
      Spec A.5 keeps them in the store and out of the index — stored and flagged,
      never discarded.</p>
    </div>
  </div>
</section>

<!-- ═══════════════════════════════════════════════ FORENSICS ═════════ -->
<section class="ch ch-sky" id="forensics" aria-labelledby="h-for">
  <div class="wrap">
    <p class="eyebrow">Chapter 07</p>
    <h2 id="h-for">{lines("Every screenshot", "that did not", "become an observation")}</h2>

    <p class="lede rv" style="margin-top:var(--s5)">Nothing was silently thrown
    away. Here is the whole accounting, and it closes exactly.</p>

    <ol class="ladder rv" data-d="1">
      <li><b data-count="{file_corpus}">{file_corpus}</b>
        <span>screenshots in the {esc(p["collection_date"])} file corpus</span></li>
      <li data-op="&#8722;"><b data-count="{p["exclusions_total"]}">{p["exclusions_total"]}</b>
        <span>excluded &#8212; every one carries a reason and an id</span></li>
      <li data-op="="><b data-count="{ev["PRIMARY_HASHED"]}">{ev["PRIMARY_HASHED"]}</b>
        <span>retained, each bound to a SHA-256 screenshot</span></li>
      <li data-op="+"><b data-count="{chat_batch}">{chat_batch}</b>
        <span>{chat_label} images that arrived as chat files &#8212; no bytes
        to hash</span></li>
      <li data-op="=" data-total="1"><b data-count="{audited}">{audited}</b>
        <span>audited in total, of which <strong>{q["valid_observations"]}</strong>
        became observations</span></li>
    </ol>

    <p class="body rv" data-d="2" style="margin-top:var(--s5)">Those two halves
    are the same fact seen twice: the {ev["PRIMARY_HASHED"]} survivors of the file
    corpus are exactly the {ev["PRIMARY_HASHED"]} hashed observations, and the
    {chat_batch} chat images are exactly the {chat_batch} with weaker provenance.
    The build refuses to render if that sum stops closing.</p>

    {decomposition(p["exclusions"], p["exclusions_total"])}

    <div class="split" style="margin-top:var(--s9)">
      <div class="stick">
        <h3>{lines("Then we asked", "the engine")}</h3>
        <p class="body rv" style="margin-top:var(--s4)">Two of those reasons are
        mechanically decidable. We fed the recorded candidates back through the
        same frozen spec A.3 and spec B.2 code the engine uses, and asked whether
        it independently reaches the recorded verdict.</p>
      </div>
      <div>
        <p class="figure-xl rv" data-count="{rep["agree"]}">{rep["agree"]}</p>
        <p class="figure-note rv" data-d="1">of {rep["candidates"]} mechanically
        decidable exclusions reproduce the recorded verdict.</p>
        <p class="figure-xl amber rv" data-d="2" data-count="{rep["disagree"]}"
           style="margin-top:var(--s7)">{rep["disagree"]}</p>
        <p class="figure-note rv" data-d="3">disagreements. A single one would
        invalidate the audit.</p>
        <p class="figure-xl amber rv" data-d="2"
           data-count="{len(rep["wrongly_rejected"])}"
           style="margin-top:var(--s7)">{len(rep["wrongly_rejected"])}</p>
        <p class="figure-note rv" data-d="3">false rejections among the
        {rep["accepted_rechecked"]} accepted observations — the control arm. A
        rule that also rejected the accepted panel would prove nothing.</p>
        <p class="body rv" data-d="4" style="margin-top:var(--s6)">
        {esc(rep["statement"])}</p>
        <p class="body rv" data-d="4" style="margin-top:var(--s3)">
        {esc(rep["scope_note"])}</p>
      </div>
    </div>
  </div>
</section>

<!-- ═══════════════════════════════════════════════ ENGINE ════════════ -->
<section class="ch ch-night" id="engine" aria-labelledby="h-eng">
  <div class="wrap">
    <p class="eyebrow">Chapter 08</p>
    <h2 id="h-eng">{lines("Real-data execution boundary")}</h2>
    <p class="lede rv" style="margin-top:var(--s4);max-width:46ch">
    {esc(bnd["claim"])}</p>
    {stages_html(bnd)}
    <p class="body rv" style="margin-top:var(--s6);max-width:60ch">
    {esc(bnd["caveat"])}</p>
    <p class="body rv" data-d="1" style="margin-top:var(--s3);max-width:60ch">
    Reconstructed from <span class="mono">{esc(bnd["reconstructed_from"])}</span>.
    {esc(bnd["reconstruction_check"])}.</p>
    <p class="body rv" data-d="2" style="margin-top:var(--s5);max-width:60ch">
    The engine is separately demonstrated end to end on a <strong>controlled
    synthetic test fixture</strong>, rendered to its own file
    <span class="mono">data/engine-validation.html</span> — index points on a
    base of 100, no currency anywhere, and a test asserts it never merges into
    this page. Nothing on that page is an airfare observation.</p>
  </div>
</section>

<!-- ═══════════════════════════════════════════════ PENDING ═══════════ -->
<section class="ch ch-neutral" id="pending" aria-labelledby="h-pend">
  <div class="wrap">
    <p class="eyebrow">Chapter 09</p>
    <h2 id="h-pend" style="font-size:var(--t-hero);font-weight:700;
        letter-spacing:-.052em;line-height:.86;max-width:none">
    {lines("INDEX", "PENDING")}</h2>
    <div class="plain rv" style="margin-top:var(--s7)">
      <p class="q">Why can't you just publish the prices you have?</p>
      <p class="a">Because an index measures <strong>change</strong>, and change
      needs two moments. We have one. Today's fares are a photograph; an index
      needs two photographs of the <em>same thing</em> a week apart, so that what
      moved is the price and not the product.</p>
    </div>

    <div class="steps rv" data-d="1">
      <div><b>1</b><span>take one flight's fare today</span></div>
      <i></i>
      <div><b>2</b><span>divide it by the same flight's fare seven days ago</span></div>
      <i></i>
      <div><b>3</b><span>do that for every flight that appears in both weeks</span></div>
      <i></i>
      <div><b>4</b><span>take the middle of those changes, multiplying rather
      than adding</span></div>
      <i></i>
      <div><b>5</b><span>that middle is the week's <strong>price relative</strong></span></div>
    </div>

    <details class="tech rv" data-d="2" style="max-width:62ch">
      <summary>Technical view</summary>
      <p class="body">Step 4 is the <strong>Jevons</strong> elementary
      aggregator — the geometric mean of matched price relatives, computed in
      logs. Multiplying rather than adding is what makes it symmetric: a fare
      that doubles and one that halves cancel exactly, which an arithmetic mean
      would not do. It is MoSPI's own elementary aggregator for the CPI.</p>
      <p class="eq">J(c,t) = exp( (1/n) &#183; &#8721;&#8341; ln( p&#8341;(t) / p&#8341;(t&#8722;7) ) )<br>
      I(c,t) = I(c,t&#8722;7) &#215; J(c,t)&nbsp;&nbsp;&nbsp;&#8212; spec C.1, LOCKED</p>
      <p class="body" style="margin-top:var(--s3)">The matched set is items
      present in <em>both</em> periods. With one wave that set is empty, so
      J(c,t) has no denominator and the chain has nothing to multiply.</p>
    </details>

    <div class="split" style="margin-top:var(--s7)">
      <div>
        <p class="lede rv">Methodology C.1 is <strong>locked</strong>:
        <span class="mono">I(c,t) = I(c,t&minus;7) &#215; J(c,t)</span>.</p>
      </div>
      <div>
        <p class="body rv">Every index value needs a matched pair at
        <span class="mono">t</span> and <span class="mono">t&minus;7</span>.
        APIx holds {idx["collection_waves"]} collection wave, which gives
        {idx["matched_pairs_available"]} matched pairs. So APIx-L is
        <strong>not computable</strong> today, and the engine refuses rather
        than inventing a level.</p>
        <p class="body rv" data-d="1" style="margin-top:var(--s4)">This is not an
        unfinished feature. Everything downstream is implemented and covered by
        the fixture suite. What is missing is the evidence the formula requires.</p>
        <p class="body rv" data-d="2" style="margin-top:var(--s4);
           font-family:var(--mono);font-size:var(--t-xs)">
        {esc(idx["apix_l_blocker"])}</p>
      </div>
    </div>
  </div>
</section>

<!-- ═══════════════════════════════════════════════ UNLOCK ════════════ -->
<section class="ch ch-paper" id="unlock" aria-labelledby="h-unlock">
  <div class="wrap">
    <p class="eyebrow">Chapter 10</p>
    <h2 id="h-unlock">{lines("The condition", "that changes", "the state")}</h2>
    <p class="lede rv" style="margin-top:var(--s4)">Seven days after the wave we
    hold. Same route, same carrier, same five bands, same selection rule, same
    window — because each of those is part of the cell key, and a cell that
    changes has no counterpart to match against.</p>

    <div class="timeline rv" data-d="1">
      <span class="node" data-now="1"><i></i><b>{esc(p["collection_date"])}</b>
        <span>wave 1 &#183; held</span></span>
      <span class="link dash"></span>
      <span class="node" data-key="1"><i></i><b>{idx["next_wave_unlocking_index"]}</b>
        <span>wave 2 &#183; required</span></span>
      <span class="link"></span>
      <span class="node"><i></i><b>matched t / t&minus;7</b>
        <span>spec D.1</span></span>
      <span class="link"></span>
      <span class="node"><i></i><b>Jevons relative</b><span>spec D.2</span></span>
      <span class="link"></span>
      <span class="node"><i></i><b>index calculation</b><span>spec C.1</span></span>
    </div>

    <p class="body rv" data-d="2" style="margin-top:var(--s7)">A 7-day shift
    preserves the travel date's weekday for all {len(apws)} buckets, which is why
    the cell keys line up. No future value is predicted here — the procedure is
    written down, and whether it produces a result is a question for the data.</p>

    <div style="margin-top:var(--s9);max-width:860px">
      <h3 class="rv">What a first index value would still not clear</h3>
      <details class="qa rv"><summary>Statistical coverage — AMB-8, open</summary>
        <div class="a">{esc(q["statistical_coverage_blocker"])} The
        {q["plan_completion_pct"]}% above is collection-plan completion
        ({q["valid_observations"]}/{q["plan_slots"]} slots), which is a different
        quantity.</div></details>
      <details class="qa rv"><summary>Carrier weighting — AMB-9, open</summary>
        <div class="a">Spec G.3/G.5 carry no carrier term in the within-route
        weight formula. At one carrier the allocation is mathematically
        degenerate; beyond one carrier
        <span class="mono">within_route_weights</span> raises rather than
        guessing. An owner ruling is required before any carrier expansion.</div></details>
      <details class="qa rv"><summary>The collection window — OQ-1, open</summary>
        <div class="a">Spec A.5 locks the rule that all collection runs inside a
        fixed daily window; the window's published value is not yet fixed. So no
        single admissible count is normative — {q["window_flags"]} observations
        sit outside the runs' declared window and are flagged, not discarded.</div></details>
      <details class="qa rv"><summary>APIx-TPD — specified, NOT IMPLEMENTED</summary>
        <div class="a">The quote-level Time Product Dummy estimator is specified
        in spec M and the package is empty — a test fails the build if that stops
        being true. The panel also holds {idx["tpd_quotes_available"]} quotes
        against a <span class="mono">min_quotes_window</span> of
        {idx["tpd_min_quotes_window"]:,}. Both are true and both are stated.</div></details>
      <details class="qa rv"><summary>Uncertainty — specified, not implemented</summary>
        <div class="a">The bootstrap is specified and not implemented, and the
        collection design does not yet record the admissible-flight universe per
        band, so it does not carry the sampling-design information an interval
        would need. Observed dispersion is reported instead, which assumes
        nothing.</div></details>
      <details class="qa rv"><summary>National representativeness — not established</summary>
        <div class="a">One route of the DGCA city-pair frame, one carrier, one
        channel, one day. Route and carrier weighting are implemented and not
        exercised. MoSPI has not endorsed APIx.</div></details>
    </div>
  </div>
</section>

<!-- ═══════════════════════════════════════════════ VAULT ═════════════ -->
<section class="ch ch-paper" id="vault" aria-labelledby="h-vault">
  <div class="wrap">
    <p class="eyebrow">Chapter 11</p>
    <h2 id="h-vault">{lines("Inspect every", "observation")}</h2>
    <p class="lede rv" style="margin-top:var(--s4);margin-bottom:var(--s7)">
    The evidence vault. Nothing is aggregated away.</p>
    <div class="rv">{vault(p["observations"], apws, band_ids)}</div>
  </div>
</section>

</main>

<footer>
  <div class="wrap cols">
    <div>
      <p><b>APIx</b></p>
      <p style="margin-top:var(--s2)">An auditable airfare measurement engine,
      built for CPI augmentation. MoSPI problem statement 26056. No market index
      is published, and the panel is not nationally representative.</p>
      <p style="margin-top:var(--s3)">Every statistical figure on this page is
      generated from <span class="mono">data/panel.json</span>. Contextual frame
      figures are typed and name their source inline.</p>
    </div>
    <div>
      <p><b>data class</b></p>
      <p class="mono" style="margin-top:var(--s2)">{esc(p["data_class"])}<br>
      synthetic_data_present = {p["synthetic_data_present"]}<br>
      generated from {esc(p["generated_from"])}</p>
    </div>
    <div>
      <p><b>version vector</b></p>
      <p class="mono" style="margin-top:var(--s2)">
      methodology {esc(run.get("methodology_version", ""))}<br>
      basket {esc(run.get("basket_version", ""))}<br>
      protocol {esc(run.get("protocol_version", ""))}<br>
      precedence {esc(run.get("source_precedence_version", ""))}</p>
    </div>
  </div>
</footer>

<div id="tip" role="status" aria-live="polite"></div>
<script type="application/json" id="apix-data">{island(p)}</script>
<script>{JS}</script>
"""


def main() -> None:
    panel = json.loads(PANEL.read_text(encoding="utf-8"))
    html = build(panel)
    OUT.write_text(html, encoding="utf-8")
    print(f"dashboard written: {OUT.relative_to(ROOT)}  ({len(html):,} bytes)")


if __name__ == "__main__":
    main()
