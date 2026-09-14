"""Visual primitives for the jury dashboard — SVG charts, WebGL, interaction.

Two halves:

* **Python** builds every chart as inline SVG. Scales, ticks and labels are all
  derived from the values handed in; no chart has a hardcoded axis, and nothing
  here can invent a figure because nothing here knows where figures come from.
* **JavaScript** (a module-level string) supplies behaviour: the scroll
  choreography, the WebGL evidence field, the boundary accordion and the
  observation explorer.

**The JS reads its data from a JSON island the generator writes**
(``<script type="application/json" id="apix-data">``), which is serialised
straight from ``panel.json``. No statistical value is ever written into a
component. If the island is absent the interactive layers disable themselves
and the static SVG still renders every figure.

**No third-party code.** The WebGL is written against the raw WebGL 1.0 API for
the widest support and zero network dependency; if a context cannot be created
the canvas is removed and the page is unaffected.
"""

from __future__ import annotations

import math


def esc(s: object) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def rupee(v: float) -> str:
    return f"{v:,.0f}"


def _nice_ticks(lo: float, hi: float, count: int = 4) -> list[float]:
    """Round tick values covering [lo, hi] — computed, never hand-listed."""
    if hi <= lo:
        return [lo]
    raw = (hi - lo) / count
    mag = 10 ** math.floor(math.log10(raw))
    step = min((m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw), default=mag)
    start = math.floor(lo / step) * step
    out, v = [], start
    while v <= hi + step * 0.5:
        if v >= lo - step * 0.5:
            out.append(round(v, 6))
        v += step
    return out


def apw_chart(profile: list[dict]) -> str:
    """Geometric-mean fare by advance-purchase bucket, with observed min/max.

    The seven buckets are **seven cross-sections on seven different travel
    dates**, so they are plotted against an ordinal axis, never a time axis.
    Spacing is by bucket index, not by lead-time magnitude, because a
    lead-time-proportional x-axis would invite reading a slope as a trend.
    """
    W, H = 940, 380
    L, R, T, B = 64, 26, 34, 62
    iw, ih = W - L - R, H - T - B

    lo = min(p["min"] for p in profile)
    hi = max(p["max"] for p in profile)
    pad = (hi - lo) * 0.16 or 1
    lo, hi = lo - pad, hi + pad
    n = len(profile)

    def x(i: int) -> float:
        return L + (iw * (i + 0.5) / n)

    def y(v: float) -> float:
        return T + ih - (v - lo) / (hi - lo) * ih

    ticks = _nice_ticks(lo, hi, 4)
    parts = [
        f'<svg viewBox="0 0 {W} {H}" class="apw-svg" role="img" '
        f'aria-label="Geometric mean fare for each of the seven advance-purchase '
        f'buckets, with the observed minimum and maximum in each">'
    ]
    for t in ticks:
        yy = round(y(t), 1)
        parts.append(f'<line class="grid-l" x1="{L}" y1="{yy}" x2="{W - R}" y2="{yy}"/>')
        parts.append(
            f'<text class="tick" x="{L - 10}" y="{yy + 3.5}" text-anchor="end">{rupee(t)}</text>'
        )
    parts.append(f'<line class="axis" x1="{L}" y1="{T + ih}" x2="{W - R}" y2="{T + ih}"/>')

    # min-max whisker per bucket: the observed spread, drawn before the mean so
    # the mean reads as a summary of it rather than as a separate series.
    for i, p in enumerate(profile):
        xx = round(x(i), 1)
        parts.append(
            f'<line x1="{xx}" y1="{y(p["min"]):.1f}" x2="{xx}" y2="{y(p["max"]):.1f}" '
            f'stroke="var(--line-3)" stroke-width="1.5"/>'
            f'<line x1="{xx - 5}" y1="{y(p["max"]):.1f}" x2="{xx + 5}" y2="{y(p["max"]):.1f}" '
            f'stroke="var(--line-3)" stroke-width="1.5"/>'
            f'<line x1="{xx - 5}" y1="{y(p["min"]):.1f}" x2="{xx + 5}" y2="{y(p["min"]):.1f}" '
            f'stroke="var(--line-3)" stroke-width="1.5"/>'
        )

    path = " ".join(
        f"{'M' if i == 0 else 'L'}{x(i):.1f} {y(p['geomean']):.1f}" for i, p in enumerate(profile)
    )
    parts.append(f'<path class="ser" d="{path}"/>')

    for i, p in enumerate(profile):
        xx, yy = x(i), y(p["geomean"])
        parts.append(
            f'<circle class="hit" cx="{xx:.1f}" cy="{yy:.1f}" r="22" tabindex="0" '
            f'role="button" data-apw="{p["apw"]}" '
            f'aria-label="T plus {p["apw"]}, geometric mean {rupee(p["geomean"])} rupees, '
            f"travel date {p['travel_date']}, {p['n']} observations, "
            f'spread {p["spread_pct"]} percent"/>'
            f'<circle class="dot" cx="{xx:.1f}" cy="{yy:.1f}" r="5"/>'
        )
        parts.append(
            f'<text class="tick b" x="{xx:.1f}" y="{T + ih + 22}" '
            f'text-anchor="middle">T+{p["apw"]}</text>'
            f'<text class="tick" x="{xx:.1f}" y="{T + ih + 38}" '
            f'text-anchor="middle">{p["day_of_week"]}</text>'
            f'<text class="tick" x="{xx:.1f}" y="{T + ih + 52}" text-anchor="middle" '
            f'opacity=".65">{p["travel_date"][5:]}</text>'
        )
    parts.append(
        f'<text class="tick" x="{L}" y="{T - 14}">'
        f"₹ geometric mean · whisker = observed min/max</text>"
    )
    parts.append("</svg>")
    return "".join(parts)


def band_chart(bands: list[dict]) -> str:
    """Geometric-mean fare by 3-hour departure band — spec §B.2, bands 2 to 6."""
    W, H = 940, 260
    L, R, T, B = 64, 26, 26, 54
    iw, ih = W - L - R, H - T - B
    vals = [b["geomean"] for b in bands]
    lo, hi = min(vals) * 0.985, max(vals) * 1.015
    n = len(bands)
    bw = iw / n * 0.52

    def y(v: float) -> float:
        return T + ih - (v - lo) / (hi - lo) * ih

    parts = [
        f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Geometric mean fare '
        f'for each of the five contracted departure bands">'
    ]
    for t in _nice_ticks(lo, hi, 3):
        yy = round(y(t), 1)
        parts.append(f'<line class="grid-l" x1="{L}" y1="{yy}" x2="{W - R}" y2="{yy}"/>')
        parts.append(
            f'<text class="tick" x="{L - 10}" y="{yy + 3.5}" text-anchor="end">{rupee(t)}</text>'
        )
    for i, b in enumerate(bands):
        cx = L + iw * (i + 0.5) / n
        yy = y(b["geomean"])
        parts.append(
            f'<rect class="bar" x="{cx - bw / 2:.1f}" y="{yy:.1f}" width="{bw:.1f}" '
            f'height="{T + ih - yy:.1f}" tabindex="0" role="button" '
            f'data-band="{b["band"]}" '
            f'aria-label="Band {b["band"]}, {b["window"]}, geometric mean '
            f'{rupee(b["geomean"])} rupees from {b["n"]} observations"/>'
            f'<text class="tick b" x="{cx:.1f}" y="{T + ih + 20}" text-anchor="middle">'
            f"band {b['band']}</text>"
            f'<text class="tick" x="{cx:.1f}" y="{T + ih + 35}" text-anchor="middle" '
            f'opacity=".7">{b["window"]}</text>'
        )
    parts.append(f'<line class="axis" x1="{L}" y1="{T + ih}" x2="{W - R}" y2="{T + ih}"/>')
    parts.append("</svg>")
    return "".join(parts)


def confound_chart(profile: list[dict]) -> str:
    """Lead time against travel weekday — the confound, drawn rather than asserted.

    Seven buckets land on five distinct weekdays. Repeats are marked, because a
    repeated weekday is the visual form of "these are not interchangeable time
    observations".
    """
    order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    counts: dict[str, int] = {}
    for p in profile:
        counts[p["day_of_week"]] = counts.get(p["day_of_week"], 0) + 1

    W, H = 940, 250
    L, R, T, B = 64, 26, 30, 46
    iw, ih = W - L - R, H - T - B
    n = len(profile)
    parts = [
        f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Each advance-purchase '
        f"bucket plotted against the weekday of its travel date, showing that lead "
        f'time is confounded with day of week">'
    ]
    for j, d in enumerate(order):
        yy = T + ih * (j + 0.5) / len(order)
        parts.append(f'<line class="grid-l" x1="{L}" y1="{yy:.1f}" x2="{W - R}" y2="{yy:.1f}"/>')
        rep = counts.get(d, 0) > 1
        fill = "var(--accent)" if rep else "var(--ink-3)"
        parts.append(
            f'<text class="tick" x="{L - 10}" y="{yy + 3.5}" text-anchor="end" '
            f'fill="{fill}">{d}</text>'
        )
    for i, p in enumerate(profile):
        cx = L + iw * (i + 0.5) / n
        cy = T + ih * (order.index(p["day_of_week"]) + 0.5) / len(order)
        rep = counts[p["day_of_week"]] > 1
        col = "var(--accent)" if rep else "var(--ex)"
        parts.append(
            f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{cx:.1f}" y2="{T + ih}" '
            f'stroke="var(--line-2)" stroke-width="1" stroke-dasharray="2 3"/>'
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="6" fill="{col}" '
            f'stroke="var(--bg)" stroke-width="2" tabindex="0" role="img" '
            f'aria-label="T plus {p["apw"]} travels on {p["travel_date"]}, a '
            f'{p["day_of_week"]}{", a weekday that repeats" if rep else ""}"/>'
            f'<text class="tick b" x="{cx:.1f}" y="{T + ih + 20}" text-anchor="middle">'
            f"T+{p['apw']}</text>"
        )
    parts.append(
        f'<text class="tick" x="{L}" y="{T - 12}" fill="var(--accent)">'
        f"amber = weekday appears more than once</text>"
    )
    parts.append("</svg>")
    return "".join(parts)


def exclusion_chart(exclusions: list[dict], replayed: int, decidable: int) -> str:
    """Composition of the 122 excluded screenshots, and which part was replayed."""
    total = sum(e["count"] for e in exclusions)
    W, H = 940, 132
    L, R = 0, 0
    iw = W - L - R
    parts = [
        f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Composition of the '
        f"{total} excluded screenshots by recorded reason, and the subset the "
        f'engine independently re-adjudicated">'
    ]
    x = 0.0
    mech = {"APW_MATCHES_NO_BUCKET", "OUTSIDE_CONTRACTED_BANDS"}

    # Replayed groups first, so the marker at `decidable` falls exactly on the
    # boundary between them and the rest. Ordered by size the blue segments
    # scatter and the marker then implies a split the bar does not contain --
    # a graphic that contradicts itself is worse than no graphic at all.
    exclusions = sorted(
        exclusions,
        key=lambda e: (not any(e["reason"].startswith(m) for m in mech), -e["count"]),
    )
    for e in exclusions:
        w = iw * e["count"] / total
        is_mech = any(e["reason"].startswith(m) for m in mech)
        fill = "var(--ex)" if is_mech else "var(--line-2)"
        label = e["reason"].split(" (")[0]
        parts.append(
            f'<rect x="{x:.1f}" y="0" width="{max(w - 1, 1):.1f}" height="46" '
            f'fill="{fill}" tabindex="0" role="img" '
            f'aria-label="{esc(label)}: {e["count"]} screenshots'
            f'{", mechanically decidable and replayed" if is_mech else ", not replayed"}"/>'
        )
        if w > 46:
            parts.append(
                f'<text class="tick" x="{x + w / 2:.1f}" y="28" text-anchor="middle" '
                f'fill="var(--bg)" font-weight="700">{e["count"]}</text>'
            )
        x += w
    x2 = iw * decidable / total
    parts.append(
        f'<line x1="{x2:.1f}" y1="0" x2="{x2:.1f}" y2="70" '
        f'stroke="var(--accent)" stroke-width="2"/>'
        f'<text class="tick" x="{x2 + 8:.1f}" y="64" fill="var(--accent)">'
        f"{decidable} mechanically decidable · {replayed} reproduce the recorded verdict</text>"
        f'<text class="tick" x="0" y="92" fill="var(--ink-3)">'
        f"{total - decidable} are collection-contract selection or unreadable-field records — "
        f"the engine has no verdict on them</text>"
        f'<text class="tick" x="0" y="112" fill="var(--ink-3)">'
        f"blue = re-adjudicated through the frozen §A.3 / §B.2 code · grey = not replayed</text>"
    )
    parts.append("</svg>")
    return "".join(parts)


def provenance_chart(primary: int, secondary: int) -> str:
    """Evidence grade split. Derived, not labelled: an observation is
    PRIMARY_HASHED only if its run actually carries a content-addressed artifact."""
    total = primary + secondary
    W, H = 940, 92
    parts = [
        f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Provenance split: '
        f"{primary} observations bound to hashed screenshots, {secondary} from "
        f'chat images with no hashable bytes">'
    ]
    pw = W * primary / total
    parts.append(
        f'<rect x="0" y="0" width="{pw - 1:.1f}" height="40" fill="var(--real)"/>'
        f'<rect x="{pw:.1f}" y="0" width="{W - pw:.1f}" height="40" fill="var(--dg)"/>'
        f'<text class="tick" x="12" y="26" fill="var(--bg)" font-weight="700">'
        f"{primary} PRIMARY_HASHED</text>"
        f'<text class="tick" x="{pw + 12:.1f}" y="26" fill="var(--bg)" font-weight="700">'
        f"{secondary} SECONDARY</text>"
        f'<text class="tick" x="0" y="62" fill="var(--ink-2)">'
        f"{primary} bound to a SHA-256 screenshot</text>"
        f'<text class="tick" x="{pw:.1f}" y="62" fill="var(--dg)">'
        f"{secondary} arrived as chat images — no bytes hashed, capture times nominal</text>"
        f'<text class="tick" x="0" y="82" fill="var(--ink-3)">'
        f"Derived from whether each run carries a content-addressed artifact, "
        f"not from a label</text>"
    )
    parts.append("</svg>")
    return "".join(parts)


# ────────────────────────────────────────────────────────────────────────────
# Behaviour. Reads only from the JSON island; degrades to static SVG without it.
# ────────────────────────────────────────────────────────────────────────────

JS = r"""
(function(){
"use strict";
var RM = matchMedia('(prefers-reduced-motion: reduce)');
var D = null;
try { D = JSON.parse(document.getElementById('apix-data').textContent); } catch(e) { D = null; }

/* ---------------------------------------------------------------- tooltip */
var tip = document.getElementById('tip');
function showTip(html, x, y){
  if(!tip) return;
  tip.innerHTML = html;
  tip.style.left = x + 'px';
  tip.style.top  = y + 'px';
  tip.classList.add('on');
}
function hideTip(){ if(tip) tip.classList.remove('on'); }
function rows(pairs){
  var s = '<dl>';
  for(var i=0;i<pairs.length;i++){
    s += '<dt>'+pairs[i][0]+'</dt><dd>'+pairs[i][1]+'</dd>';
  }
  return s + '</dl>';
}
// Whole rupees, matching the axis labels and the observation table. The
// contract keeps full precision; only the display rounds, and it rounds in
// exactly one place so two surfaces cannot disagree.
function inr(v){ return '₹' + Math.round(Number(v)).toLocaleString('en-IN'); }

/* ------------------------------------------------------- reveal on scroll */
var rv = document.querySelectorAll('.rv');
if(RM.matches || !('IntersectionObserver' in window)){
  rv.forEach(function(el){ el.classList.add('in'); });
} else {
  var ro = new IntersectionObserver(function(es){
    es.forEach(function(e){
      if(e.isIntersecting){ e.target.classList.add('in'); ro.unobserve(e.target); }
    });
  }, {rootMargin:'0px 0px -12% 0px', threshold:.08});
  rv.forEach(function(el){ ro.observe(el); });
}

/* ------------------------------------------- scroll progress + section spy */
var nav = document.querySelector('.nav');
var prog = document.querySelector('.prog');
var links = [].slice.call(document.querySelectorAll('.nav a[href^="#"]'));
var targets = links.map(function(a){
  return document.getElementById(a.getAttribute('href').slice(1));
});
var ticking = false;
function onScroll(){
  if(ticking) return; ticking = true;
  requestAnimationFrame(function(){
    var y = window.scrollY;
    if(nav) nav.dataset.stuck = y > 24 ? '1' : '0';
    var h = document.documentElement.scrollHeight - innerHeight;
    if(prog) prog.style.width = (h > 0 ? (y / h) * 100 : 0) + '%';
    var best = -1;
    for(var i=0;i<targets.length;i++){
      if(targets[i] && targets[i].getBoundingClientRect().top <= innerHeight * 0.38) best = i;
    }
    links.forEach(function(a,i){
      if(i === best) a.setAttribute('aria-current','true'); else a.removeAttribute('aria-current');
    });
    ticking = false;
  });
}
addEventListener('scroll', onScroll, {passive:true});
addEventListener('resize', onScroll, {passive:true});
onScroll();

/* ------------------------------------------------------ boundary accordion */
document.querySelectorAll('.bs').forEach(function(btn){
  btn.addEventListener('click', function(){
    var open = btn.getAttribute('aria-expanded') === 'true';
    var body = document.getElementById(btn.getAttribute('aria-controls'));
    btn.setAttribute('aria-expanded', open ? 'false' : 'true');
    if(body) body.dataset.open = open ? '0' : '1';
  });
});

/* --------------------------------------------------------- APW chart hover */
if(D && D.apw){
  var byApw = {};
  D.apw.forEach(function(p){ byApw[p.apw] = p; });
  document.querySelectorAll('.hit[data-apw]').forEach(function(h){
    function show(ev){
      var p = byApw[h.dataset.apw]; if(!p) return;
      var r = h.getBoundingClientRect();
      showTip('<div class="h">T+'+p.apw+' · '+p.day_of_week+' '+p.travel_date+'</div>' +
        rows([['geometric mean', inr(p.geomean)],
              ['observed min', inr(p.min)],
              ['observed max', inr(p.max)],
              ['spread', p.spread_pct+'%'],
              ['observations', p.n]]),
        r.left + r.width/2, r.top);
    }
    h.addEventListener('mouseenter', show);
    h.addEventListener('focus', show);
    h.addEventListener('mouseleave', hideTip);
    h.addEventListener('blur', hideTip);
  });
}

/* -------------------------------------------------------- band chart hover */
if(D && D.bands){
  var byBand = {};
  D.bands.forEach(function(b){ byBand[b.band] = b; });
  document.querySelectorAll('.bar[data-band]').forEach(function(el){
    function show(){
      var b = byBand[el.dataset.band]; if(!b) return;
      var r = el.getBoundingClientRect();
      showTip('<div class="h">Band '+b.band+' · '+b.window+'</div>' +
        rows([['geometric mean', inr(b.geomean)], ['observations', b.n]]),
        r.left + r.width/2, r.top);
    }
    el.addEventListener('mouseenter', show);
    el.addEventListener('focus', show);
    el.addEventListener('mouseleave', hideTip);
    el.addEventListener('blur', hideTip);
  });
}

/* ---------------------------------------------------- observation explorer */
(function(){
  var table = document.getElementById('obs-table');
  if(!table) return;
  var rowsEl = [].slice.call(table.querySelectorAll('tbody tr'));
  var out = document.getElementById('obs-count');
  var state = {apw:'all', band:'all', ev:'all'};
  function apply(){
    var shown = 0;
    rowsEl.forEach(function(tr){
      var ok = (state.apw === 'all' || tr.dataset.apw === state.apw) &&
               (state.band === 'all' || tr.dataset.band === state.band) &&
               (state.ev  === 'all' || tr.dataset.ev  === state.ev);
      tr.hidden = !ok; if(ok) shown++;
    });
    if(out) out.innerHTML = '<b>' + shown + '</b> of ' + rowsEl.length + ' observations';
  }
  document.querySelectorAll('.fgrp button[data-f]').forEach(function(b){
    b.addEventListener('click', function(){
      var f = b.dataset.f, v = b.dataset.v;
      state[f] = v;
      b.parentNode.querySelectorAll('button').forEach(function(o){
        o.setAttribute('aria-pressed', o === b ? 'true' : 'false');
      });
      apply();
    });
  });
  apply();
})();

/* ============================================ WebGL real-observation field
   35 nodes, one per real observation. Every axis is a recorded field:
       x  advance-purchase bucket index   (lead time)
       y  payable fare, min-max normalised (price)
       z  departure band                  (time of day)
   colour  evidence grade (hashed screenshot vs chat image)
   Nothing is encoded that is not in panel.json. If WebGL is unavailable the
   canvas is removed and the page loses only decoration.                     */
(function(){
  var cv = document.getElementById('field');
  if(!cv || !D || !D.obs || RM.matches){ if(cv) cv.remove(); return; }
  var gl = null;
  try { gl = cv.getContext('webgl', {alpha:true, antialias:true, depth:true}); } catch(e){}
  if(!gl){ cv.remove(); return; }

  var VS = 'attribute vec3 p; attribute vec3 c; attribute float s;' +
    'uniform mat4 mvp; varying vec3 vc; varying float vs;' +
    'void main(){ vec4 q = mvp * vec4(p,1.0); gl_Position = q;' +
    ' float d = clamp(1.8 / max(q.w,0.35), 0.25, 2.4);' +
    ' gl_PointSize = s * d; vc = c; vs = d; }';
  var FS = 'precision mediump float; varying vec3 vc; varying float vs;' +
    'void main(){ vec2 d = gl_PointCoord - vec2(0.5);' +
    ' float r = length(d); if(r > 0.5) discard;' +
    ' float core = smoothstep(0.5, 0.06, r);' +
    ' float halo = smoothstep(0.5, 0.28, r) * 0.5;' +
    ' gl_FragColor = vec4(vc, core * 0.9 + halo * 0.35); }';

  function sh(t, src){
    var o = gl.createShader(t); gl.shaderSource(o, src); gl.compileShader(o);
    return gl.getShaderParameter(o, gl.COMPILE_STATUS) ? o : null;
  }
  var vs = sh(gl.VERTEX_SHADER, VS), fs = sh(gl.FRAGMENT_SHADER, FS);
  if(!vs || !fs){ cv.remove(); return; }
  var pr = gl.createProgram();
  gl.attachShader(pr, vs); gl.attachShader(pr, fs); gl.linkProgram(pr);
  if(!gl.getProgramParameter(pr, gl.LINK_STATUS)){ cv.remove(); return; }
  gl.useProgram(pr);

  var obs = D.obs;
  var apws = D.apwOrder;
  var fares = obs.map(function(o){ return o.total; });
  var flo = Math.min.apply(null, fares), fhi = Math.max.apply(null, fares);
  var P = [], C = [], S = [];
  var PRIM = [0.37, 0.83, 0.63], SEC = [0.94, 0.66, 0.24];
  obs.forEach(function(o){
    var xi = apws.indexOf(o.apw);
    var x = (xi / Math.max(apws.length - 1, 1) - 0.5) * 3.4;
    var y = ((o.total - flo) / Math.max(fhi - flo, 1) - 0.5) * 1.5;
    var z = ((o.band - 2) / 4 - 0.5) * 2.2;
    P.push(x, y, z);
    var c = (o.ev === 'PRIMARY_HASHED') ? PRIM : SEC;
    C.push(c[0], c[1], c[2]);
    S.push(o.ev === 'PRIMARY_HASHED' ? 19.0 : 25.0);
  });
  // The lattice IS the collection plan: 7 advance-purchase buckets x 5
  // departure bands, every cell filled. Joining along BOTH axes is what makes
  // it read as a grid rather than as scattered points — across bands within a
  // bucket, and across buckets within a band. A gap in this mesh would be a
  // slot the collector did not fill, so the shape carries the same information
  // as the 35/35 figure beside it.
  var LP = [], LC = [];
  function at(o){
    var xi = apws.indexOf(o.apw);
    return [(xi / Math.max(apws.length - 1, 1) - 0.5) * 3.4,
            ((o.total - flo) / Math.max(fhi - flo, 1) - 0.5) * 1.5,
            ((o.band - 2) / 4 - 0.5) * 2.2];
  }
  function edge(a, b){
    var p = at(a), q = at(b);
    LP.push(p[0], p[1], p[2], q[0], q[1], q[2]);
    LC.push(0.16, 0.24, 0.34, 0.16, 0.24, 0.34);
  }
  var bandsSeen = [];
  obs.forEach(function(o){ if(bandsSeen.indexOf(o.band) < 0) bandsSeen.push(o.band); });
  bandsSeen.sort(function(m,n){ return m - n; });
  apws.forEach(function(a){                       // rungs: bands within a bucket
    var g = obs.filter(function(o){ return o.apw === a; })
               .sort(function(m,n){ return m.band - n.band; });
    for(var i=0;i<g.length-1;i++) edge(g[i], g[i+1]);
  });
  bandsSeen.forEach(function(b){                  // rails: buckets within a band
    var g = obs.filter(function(o){ return o.band === b; })
               .sort(function(m,n){ return apws.indexOf(m.apw) - apws.indexOf(n.apw); });
    for(var i=0;i<g.length-1;i++) edge(g[i], g[i+1]);
  });

  function buf(data){
    var b = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, b);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(data), gl.STATIC_DRAW);
    return b;
  }
  var bP = buf(P), bC = buf(C), bS = buf(S), bLP = buf(LP), bLC = buf(LC);
  var aP = gl.getAttribLocation(pr,'p'), aC = gl.getAttribLocation(pr,'c'),
      aS = gl.getAttribLocation(pr,'s'), uM = gl.getUniformLocation(pr,'mvp');

  function bind(b, loc, n){
    gl.bindBuffer(gl.ARRAY_BUFFER, b);
    gl.enableVertexAttribArray(loc);
    gl.vertexAttribPointer(loc, n, gl.FLOAT, false, 0, 0);
  }
  function mul(a, b){
    var o = new Float32Array(16);
    for(var i=0;i<4;i++) for(var j=0;j<4;j++){
      var s = 0; for(var k=0;k<4;k++) s += a[k*4+j] * b[i*4+k];
      o[i*4+j] = s;
    }
    return o;
  }
  function persp(fov, asp, n, f){
    var t = 1 / Math.tan(fov/2);
    return new Float32Array([t/asp,0,0,0, 0,t,0,0, 0,0,(f+n)/(n-f),-1, 0,0,2*f*n/(n-f),0]);
  }
  function view(ang, dist, lift){
    var c = Math.cos(ang), s = Math.sin(ang);
    var ex = s*dist, ey = lift, ez = c*dist;
    var zx = ex, zy = ey, zz = ez, L = Math.hypot(zx,zy,zz);
    zx/=L; zy/=L; zz/=L;
    var xx = zz, xy = 0, xz = -zx, L2 = Math.hypot(xx,xy,xz);
    xx/=L2; xy/=L2; xz/=L2;
    var yx = zy*xz - zz*xy, yy = zz*xx - zx*xz, yz = zx*xy - zy*xx;
    return new Float32Array([
      xx,yx,zx,0, xy,yy,zy,0, xz,yz,zz,0,
      -(xx*ex+xy*ey+xz*ez), -(yx*ex+yy*ey+yz*ez), -(zx*ex+zy*ey+zz*ez), 1]);
  }

  var running = true, t0 = performance.now(), raf = 0, pointer = 0, target = 0;
  cv.addEventListener('pointermove', function(e){
    target = (e.clientX / innerWidth - 0.5) * 0.7;
  }, {passive:true});

  function size(){
    var dpr = Math.min(devicePixelRatio || 1, 2);
    var w = cv.clientWidth, h = cv.clientHeight;
    if(cv.width !== (w*dpr|0) || cv.height !== (h*dpr|0)){
      cv.width = w*dpr|0; cv.height = h*dpr|0;
    }
    gl.viewport(0, 0, cv.width, cv.height);
  }
  function frame(now){
    if(!running) return;
    size();
    pointer += (target - pointer) * 0.045;
    var ang = (now - t0) * 0.000085 + pointer;
    var mvp = mul(persp(1.02, cv.width / Math.max(cv.height,1), 0.1, 60),
                  view(ang, 4.1, 0.95));
    gl.clearColor(0,0,0,0);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE);
    gl.uniformMatrix4fv(uM, false, mvp);
    if(LP.length){
      bind(bLP, aP, 3); bind(bLC, aC, 3);
      gl.disableVertexAttribArray(aS); gl.vertexAttrib1f(aS, 1.0);
      gl.drawArrays(gl.LINES, 0, LP.length/3);
    }
    bind(bP, aP, 3); bind(bC, aC, 3); bind(bS, aS, 1);
    gl.drawArrays(gl.POINTS, 0, P.length/3);
    raf = requestAnimationFrame(frame);
  }
  // Only animate while the hero is actually on screen.
  var io = new IntersectionObserver(function(es){
    es.forEach(function(e){
      if(e.isIntersecting && !running){
        running = true; t0 = performance.now(); raf = requestAnimationFrame(frame);
      }
      else if(!e.isIntersecting && running){ running = false; cancelAnimationFrame(raf); }
    });
  }, {threshold:0.01});
  io.observe(cv);
  raf = requestAnimationFrame(frame);
  addEventListener('resize', size, {passive:true});
})();

/* ====================================== pipeline flow (2D, documented) ====
   A diagram of the workflow recorded in the repository, animated so the
   ORDER of the stages reads at a glance. It is a visualisation of a
   documented sequence, NOT a live process monitor: nothing here polls,
   measures or reports a running job.                                       */
(function(){
  var cv = document.getElementById('pipe');
  if(!cv || RM.matches){ if(cv) cv.remove(); return; }
  var ctx = cv.getContext('2d');
  if(!ctx){ cv.remove(); return; }
  var stages = (D && D.pipeline) || [];
  if(!stages.length){ cv.remove(); return; }
  var dots = [], running = true, raf = 0;
  for(var i=0;i<26;i++) dots.push({t: i/26, v: 0.00042 + Math.random()*0.00022});

  function draw(){
    if(!running) return;
    var dpr = Math.min(devicePixelRatio || 1, 2);
    var w = cv.clientWidth, h = cv.clientHeight;
    if(cv.width !== (w*dpr|0)){ cv.width = w*dpr|0; cv.height = h*dpr|0; }
    ctx.setTransform(dpr,0,0,dpr,0,0);
    ctx.clearRect(0,0,w,h);
    var n = stages.length, pad = 18, y = h*0.52;
    var step = (w - pad*2) / Math.max(n-1,1);
    var cs = getComputedStyle(document.documentElement);
    var line = cs.getPropertyValue('--line-2').trim() || '#2A3742';
    var ink  = cs.getPropertyValue('--ink-3').trim() || '#6C7E8E';
    var acc  = cs.getPropertyValue('--accent').trim() || '#F0A93C';
    var stop = cs.getPropertyValue('--bl').trim() || '#F0887C';

    ctx.strokeStyle = line; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(pad, y); ctx.lineTo(w-pad, y); ctx.stroke();

    for(var i=0;i<n;i++){
      var x = pad + step*i, s = stages[i];
      ctx.beginPath(); ctx.arc(x, y, s.stop ? 6 : 4, 0, Math.PI*2);
      ctx.fillStyle = s.stop ? stop : (s.done ? acc : line);
      ctx.fill();
      ctx.fillStyle = s.stop ? stop : ink;
      ctx.font = '500 9.5px ui-monospace, monospace';
      ctx.textAlign = 'center';
      ctx.save(); ctx.translate(x, y + 20); ctx.rotate(-Math.PI/9);
      ctx.fillText(s.label, 0, 0); ctx.restore();
    }
    // Packets travel only as far as the stop stage — the animation obeys the
    // same boundary the statistics do.
    var stopAt = 1;
    for(var k=0;k<n;k++) if(stages[k].stop){ stopAt = k/Math.max(n-1,1); break; }
    dots.forEach(function(d){
      d.t += d.v * 16;
      if(d.t > stopAt) d.t = 0;
      var x = pad + (w - pad*2) * d.t;
      var a = Math.min(1, Math.sin(d.t/stopAt * Math.PI) * 1.6);
      ctx.beginPath(); ctx.arc(x, y, 1.8, 0, Math.PI*2);
      ctx.fillStyle = acc; ctx.globalAlpha = a * 0.75; ctx.fill(); ctx.globalAlpha = 1;
    });
    raf = requestAnimationFrame(draw);
  }
  var io = new IntersectionObserver(function(es){
    es.forEach(function(e){
      if(e.isIntersecting && !running){ running = true; raf = requestAnimationFrame(draw); }
      else if(!e.isIntersecting && running){ running = false; cancelAnimationFrame(raf); }
    });
  }, {threshold:0.05});
  io.observe(cv);
  raf = requestAnimationFrame(draw);
})();
})();
"""
