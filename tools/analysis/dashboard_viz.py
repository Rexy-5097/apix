"""Visual primitives for the jury dashboard — SVG charts, WebGL, choreography.

Two halves:

* **Python** builds every chart as inline SVG. Scales, ticks and labels are
  derived from the values handed in; no chart carries a hardcoded axis, and
  nothing here can invent a figure because nothing here knows where figures
  come from. Colour is referenced through CSS custom properties, so the charts
  belong to the design system rather than owning a palette of their own.
* **JavaScript** (a module-level string) supplies behaviour: smooth scroll,
  scroll-linked choreography, the WebGL observation field, the evidence wall,
  the boundary accordion and the evidence vault.

**The JS reads its data from a JSON island the generator writes**
(``<script type="application/json" id="apix-data">``), serialised straight from
``panel.json``. No statistical value is ever written into a component.

**Libraries are optional, not required.** GSAP, ScrollTrigger and Lenis are
loaded from a CDN and every one of them is feature-detected. If the network is
down, if a CSP blocks them, or if they simply fail, the page falls back to
IntersectionObserver reveals and native scrolling and loses nothing but motion.
The WebGL field is hand-written against raw WebGL 1.0 rather than pulling in a
scene graph: it draws 35 points and 56 line vertices, and a 600 KB dependency
to do that would be dependency theatre.
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


def _ticks(lo: float, hi: float, count: int = 4) -> list[float]:
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
    """Geometric-mean fare per advance-purchase bucket, with observed min/max.

    The seven buckets are **seven cross-sections on seven different travel
    dates**, so they sit on an ordinal axis, never a time axis. Spacing is by
    bucket index rather than by lead-time magnitude, because a proportional
    x-axis would invite reading the slope as a trend through time.
    """
    W, H = 1000, 420
    L, R, T, B = 76, 24, 40, 74
    iw, ih = W - L - R, H - T - B
    lo = min(p["min"] for p in profile)
    hi = max(p["max"] for p in profile)
    pad = (hi - lo) * 0.18 or 1
    lo, hi = lo - pad, hi + pad
    n = len(profile)

    def x(i: int) -> float:
        return L + (iw * (i + 0.5) / n)

    def y(v: float) -> float:
        return T + ih - (v - lo) / (hi - lo) * ih

    parts = [
        f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Geometric mean fare for '
        f"each of the seven advance-purchase buckets, with the observed minimum and "
        f'maximum in each bucket">'
    ]
    for t in _ticks(lo, hi, 4):
        yy = round(y(t), 1)
        parts.append(f'<line class="grid-l" x1="{L}" y1="{yy}" x2="{W - R}" y2="{yy}"/>')
        parts.append(
            f'<text class="tick" x="{L - 14}" y="{yy + 4}" text-anchor="end">{rupee(t)}</text>'
        )
    for i, p in enumerate(profile):
        xx = round(x(i), 1)
        parts.append(
            f'<line x1="{xx}" y1="{y(p["min"]):.1f}" x2="{xx}" y2="{y(p["max"]):.1f}" '
            f'stroke="var(--line-2)" stroke-width="1.5" stroke-linecap="round"/>'
        )
    path = " ".join(
        f"{'M' if i == 0 else 'L'}{x(i):.1f} {y(p['geomean']):.1f}" for i, p in enumerate(profile)
    )
    parts.append(f'<path class="ser" d="{path}"/>')
    for i, p in enumerate(profile):
        xx, yy = x(i), y(p["geomean"])
        parts.append(
            f'<circle class="hit" cx="{xx:.1f}" cy="{yy:.1f}" r="24" tabindex="0" '
            f'role="button" data-apw="{p["apw"]}" aria-label="T plus {p["apw"]}, '
            f"geometric mean {rupee(p['geomean'])} rupees, travel date "
            f'{p["travel_date"]}, {p["n"]} observations, spread {p["spread_pct"]} percent"/>'
            f'<circle class="dot" cx="{xx:.1f}" cy="{yy:.1f}" r="5.5"/>'
            f'<text class="tick b" x="{xx:.1f}" y="{T + ih + 26}" '
            f'text-anchor="middle">T+{p["apw"]}</text>'
            f'<text class="tick" x="{xx:.1f}" y="{T + ih + 44}" text-anchor="middle" '
            f'opacity=".8">{p["day_of_week"]}</text>'
            f'<text class="tick" x="{xx:.1f}" y="{T + ih + 60}" text-anchor="middle" '
            f'opacity=".55">{p["travel_date"][5:]}</text>'
        )
    parts.append(
        f'<text class="tick" x="{L}" y="{T - 16}">'
        f"rupees, geometric mean &#183; vertical rule = observed min to max</text>"
    )
    parts.append("</svg>")
    return "".join(parts)


def band_chart(bands: list[dict]) -> str:
    """Geometric-mean fare per 3-hour departure band — spec B.2, bands 2 to 6."""
    W, H = 1000, 280
    L, R, T, B = 76, 24, 28, 62
    iw, ih = W - L - R, H - T - B
    vals = [b["geomean"] for b in bands]
    lo, hi = min(vals) * 0.98, max(vals) * 1.02
    n = len(bands)
    bw = iw / n * 0.46

    def y(v: float) -> float:
        return T + ih - (v - lo) / (hi - lo) * ih

    parts = [
        f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Geometric mean fare for '
        f'each of the five contracted departure bands">'
    ]
    for t in _ticks(lo, hi, 3):
        yy = round(y(t), 1)
        parts.append(f'<line class="grid-l" x1="{L}" y1="{yy}" x2="{W - R}" y2="{yy}"/>')
        parts.append(
            f'<text class="tick" x="{L - 14}" y="{yy + 4}" text-anchor="end">{rupee(t)}</text>'
        )
    for i, b in enumerate(bands):
        cx = L + iw * (i + 0.5) / n
        yy = y(b["geomean"])
        parts.append(
            f'<rect class="bar" x="{cx - bw / 2:.1f}" y="{yy:.1f}" width="{bw:.1f}" '
            f'height="{T + ih - yy:.1f}" rx="4" tabindex="0" role="button" '
            f'data-band="{b["band"]}" aria-label="Band {b["band"]}, {b["window"]}, '
            f'geometric mean {rupee(b["geomean"])} rupees from {b["n"]} observations"/>'
            f'<text class="tick b" x="{cx:.1f}" y="{T + ih + 24}" '
            f'text-anchor="middle">band {b["band"]}</text>'
            f'<text class="tick" x="{cx:.1f}" y="{T + ih + 41}" text-anchor="middle" '
            f'opacity=".7">{b["window"]}</text>'
        )
    parts.append(f'<line class="axis" x1="{L}" y1="{T + ih}" x2="{W - R}" y2="{T + ih}"/>')
    parts.append("</svg>")
    return "".join(parts)


def confound_chart(profile: list[dict]) -> str:
    """Lead time against travel weekday — the confound drawn, not asserted.

    Seven buckets land on five distinct weekdays. Repeats are marked, because a
    repeated weekday is the visible form of "these are not interchangeable time
    observations".
    """
    order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    counts: dict[str, int] = {}
    for p in profile:
        counts[p["day_of_week"]] = counts.get(p["day_of_week"], 0) + 1

    W, H = 1000, 300
    L, R, T, B = 76, 24, 34, 52
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
        fill = "var(--amber-ink)" if rep else "var(--ink-3)"
        weight = ' font-weight="500"' if rep else ""
        parts.append(
            f'<text class="tick" x="{L - 14}" y="{yy + 4}" text-anchor="end" '
            f'fill="{fill}"{weight}>{d}</text>'
        )
    for i, p in enumerate(profile):
        cx = L + iw * (i + 0.5) / n
        cy = T + ih * (order.index(p["day_of_week"]) + 0.5) / len(order)
        rep = counts[p["day_of_week"]] > 1
        col = "var(--amber)" if rep else "var(--ex)"
        parts.append(
            f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{cx:.1f}" y2="{T + ih}" '
            f'stroke="var(--line-2)" stroke-width="1"/>'
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="7" fill="{col}" '
            f'stroke="var(--paper)" stroke-width="2.5" tabindex="0" role="img" '
            f'aria-label="T plus {p["apw"]} travels on {p["travel_date"]}, a '
            f'{p["day_of_week"]}{", a weekday that repeats" if rep else ""}"/>'
            f'<text class="tick b" x="{cx:.1f}" y="{T + ih + 24}" '
            f'text-anchor="middle">T+{p["apw"]}</text>'
        )
    parts.append(
        f'<text class="tick" x="{L}" y="{T - 14}" fill="var(--amber-ink)">'
        f"amber = this weekday appears more than once</text>"
    )
    parts.append("</svg>")
    return "".join(parts)


# ────────────────────────────────────────────────────────────────────────────
# Behaviour. Reads only from the JSON island; degrades without it, and without
# any of the three libraries.
# ────────────────────────────────────────────────────────────────────────────

JS = r"""
(function(){
"use strict";
var RM = matchMedia('(prefers-reduced-motion: reduce)').matches;
var D = null;
try { D = JSON.parse(document.getElementById('apix-data').textContent); } catch(e) { D = null; }
var G = window.gsap, ST = window.ScrollTrigger, LenisCtor = window.Lenis;
var hasGSAP = !!(G && ST);
if(hasGSAP){ try { G.registerPlugin(ST); } catch(e){ hasGSAP = false; } }

/* ------------------------------------------------- smooth scroll (Lenis) */
var lenis = null;
if(LenisCtor && !RM){
  try {
    lenis = new LenisCtor({ duration:1.05,
      easing:function(t){ return Math.min(1, 1.001 - Math.pow(2, -10*t)); } });
    function raf(t){ lenis.raf(t); requestAnimationFrame(raf); }
    requestAnimationFrame(raf);
    if(hasGSAP){ lenis.on('scroll', ST.update); }
  } catch(e){ lenis = null; }
}

/* ------------------------------------------------------------- tooltips */
var tip = document.getElementById('tip');
function showTip(html, x, y){
  if(!tip) return;
  tip.innerHTML = html; tip.style.left = x+'px'; tip.style.top = y+'px';
  tip.classList.add('on');
}
function hideTip(){ if(tip) tip.classList.remove('on'); }
function rows(p){
  var s='<dl>';
  for(var i=0;i<p.length;i++){ s += '<dt>'+p[i][0]+'</dt><dd>'+p[i][1]+'</dd>'; }
  return s+'</dl>';
}
function inr(v){ return '₹' + Math.round(Number(v)).toLocaleString('en-IN'); }

/* -------------------------------------------------------------- reveals */
/* Two implementations of one idea. GSAP gives line-masked, staggered entry;
   the fallback gives a plain fade. Neither is required for the content. */
function revealFallback(){
  var rv = document.querySelectorAll('.rv, .line-mask');
  if(RM || !('IntersectionObserver' in window)){
    rv.forEach(function(el){ el.style.opacity='1'; el.style.transform='none';
      el.querySelectorAll('span').forEach(function(s){ s.style.transform='none'; }); });
    return;
  }
  var io = new IntersectionObserver(function(es){
    es.forEach(function(e){
      if(!e.isIntersecting) return;
      var el = e.target;
      el.style.transition = 'opacity .7s cubic-bezier(.16,1,.3,1),' +
                            ' transform .7s cubic-bezier(.16,1,.3,1)';
      el.style.opacity='1'; el.style.transform='none';
      el.querySelectorAll('span').forEach(function(s,i){
        s.style.transition = 'transform .8s cubic-bezier(.16,1,.3,1) '+(i*0.06)+'s';
        s.style.transform='none';
      });
      io.unobserve(el);
    });
  }, {rootMargin:'0px 0px -10% 0px', threshold:.06});
  rv.forEach(function(el){ io.observe(el); });
}

if(!hasGSAP || RM){
  revealFallback();
} else {
  /* Line-mask reveal for headings: each line rides up from behind its own
     clip. Bodies get a shorter fade. The two are deliberately different so a
     heading reads as an event and a paragraph does not. */
  document.querySelectorAll('.line-mask').forEach(function(el){
    G.to(el.querySelectorAll('span'), {
      yPercent:0, duration:1.15, ease:'expo.out', stagger:0.07,
      scrollTrigger:{ trigger:el, start:'top 88%' }
    });
  });
  document.querySelectorAll('.rv').forEach(function(el, i){
    G.to(el, { opacity:1, y:0, duration:0.9, ease:'expo.out',
      delay:(el.dataset.d ? +el.dataset.d * 0.08 : 0),
      scrollTrigger:{ trigger:el, start:'top 90%' } });
  });
  /* Vanishing: a statement dissolves as it leaves, rather than cutting. */
  document.querySelectorAll('.scene .stmt').forEach(function(el){
    G.to(el, { opacity:0.08, y:-40, ease:'none',
      scrollTrigger:{ trigger:el, start:'bottom 42%', end:'bottom top', scrub:0.6 } });
  });
}

/* Failsafe. The reveal is an enhancement, so it must not be the only path to
   visible content. If after 2.5s NOTHING has revealed, the mechanism is dead —
   a library half-loaded, an observer that never fired, a layout the browser
   measured as zero-height — and everything is shown outright. If even one
   element revealed, the mechanism works and the animation is left alone. */
setTimeout(function(){
  var all = [].slice.call(document.querySelectorAll('.rv'));
  var shown = all.filter(function(el){
    return parseFloat(getComputedStyle(el).opacity) > 0.5;
  }).length;
  if(all.length && shown > 0) return;
  all.forEach(function(el){ el.style.opacity='1'; el.style.transform='none'; });
  [].slice.call(document.querySelectorAll('.line-mask > span')).forEach(function(s){
    s.style.transform='none';
  });
}, 2500);

/* ------------------------------------------------------- number counters */
document.querySelectorAll('[data-count]').forEach(function(el){
  var target = parseFloat(el.dataset.count);
  var dp = el.dataset.dp ? +el.dataset.dp : 0;
  var pre = el.dataset.pre || '', post = el.dataset.post || '';
  function render(v){ el.textContent = pre + v.toFixed(dp) + post; }
  if(RM){ render(target); return; }
  if(hasGSAP){
    var o = {v:0};
    G.to(o, { v:target, duration:1.6, ease:'expo.out',
      scrollTrigger:{ trigger:el, start:'top 86%' },
      onUpdate:function(){ render(o.v); } });
  } else {
    var io = new IntersectionObserver(function(es){
      es.forEach(function(e){
        if(!e.isIntersecting) return;
        var t0 = performance.now();
        (function step(now){
          var k = Math.min(1, (now-t0)/1400);
          render(target * (1 - Math.pow(1-k, 4)));
          if(k < 1) requestAnimationFrame(step);
        })(t0);
        io.unobserve(e.target);
      });
    }, {threshold:.3});
    io.observe(el);
  }
});

/* ---------------------------------------------------- nav: dots + ground */
var nav = document.querySelector('.nav');
var dots = [].slice.call(document.querySelectorAll('.dots a'));
var chapters = [].slice.call(document.querySelectorAll('.ch[id]'));
function onScroll(){
  var y = window.scrollY || 0;
  if(nav) nav.dataset.solid = y > 40 ? '1' : '0';
  var mid = y + 42, best = -1, onNight = false;
  chapters.forEach(function(c, i){
    if(c.offsetTop <= mid) { best = i; }
  });
  if(best >= 0 && chapters[best].classList.contains('ch-night')) onNight = true;
  if(nav) nav.dataset.onNight = onNight ? '1' : '0';
  dots.forEach(function(a, i){
    if(i === best) a.setAttribute('aria-current','true'); else a.removeAttribute('aria-current');
  });
}
addEventListener('scroll', onScroll, {passive:true});
addEventListener('resize', onScroll, {passive:true});
onScroll();
dots.forEach(function(a){
  a.addEventListener('click', function(ev){
    var t = document.querySelector(a.getAttribute('href'));
    if(!t) return;
    ev.preventDefault();
    if(lenis) lenis.scrollTo(t, {offset:-40}); else t.scrollIntoView({behavior:RM?'auto':'smooth'});
  });
});

/* ------------------------------------------- horizontal APW rail (pinned) */
(function(){
  var outer = document.querySelector('.rail-outer');
  var track = document.querySelector('.rail-track');
  if(!outer || !track) return;
  if(!hasGSAP || RM || innerWidth < 760){ outer.style.height='auto'; return; }
  var distance = function(){ return Math.max(0, track.scrollWidth - innerWidth + 80); };
  G.to(track, {
    x: function(){ return -distance(); },
    ease:'none',
    scrollTrigger:{
      trigger: outer, start:'top top', end:function(){ return '+=' + distance(); },
      pin: outer.querySelector('.rail-pin'), scrub: 0.8, invalidateOnRefresh: true,
      anticipatePin: 1
    }
  });
  /* Each panel's spread bar draws as the panel arrives. */
  track.querySelectorAll('.rail-bar i').forEach(function(bar){
    G.fromTo(bar, {scaleX:0}, {scaleX:1, transformOrigin:'left', ease:'expo.out',
      duration:0.9, scrollTrigger:{ trigger:bar.closest('.rail-panel'),
        containerAnimation: ST.getAll().slice(-1)[0], start:'left 72%' } });
  });
})();

/* --------------------------------------------- forensic decomposition bars */
(function(){
  var rowsEl = document.querySelectorAll('.decomp .track i');
  if(!rowsEl.length) return;
  if(RM){ rowsEl.forEach(function(b){ b.style.transform='scaleX(1)'; }); return; }
  rowsEl.forEach(function(b){ b.style.transform='scaleX(0)'; });
  if(hasGSAP){
    G.to('.decomp .track i', { scaleX:1, duration:1.1, ease:'expo.out', stagger:0.08,
      scrollTrigger:{ trigger:'.decomp', start:'top 78%' } });
  } else {
    var io = new IntersectionObserver(function(es){
      es.forEach(function(e){ if(!e.isIntersecting) return;
        rowsEl.forEach(function(b,i){
          b.style.transition='transform .9s cubic-bezier(.16,1,.3,1) '+(i*0.08)+'s';
          b.style.transform='scaleX(1)'; });
        io.disconnect(); });
    }, {threshold:.25});
    io.observe(document.querySelector('.decomp'));
  }
})();

/* -------------------------------------------------------- APW chart hover */
if(D && D.apw){
  var byApw = {}; D.apw.forEach(function(p){ byApw[p.apw] = p; });
  document.querySelectorAll('.hit[data-apw]').forEach(function(h){
    function show(){
      var p = byApw[h.dataset.apw]; if(!p) return;
      var r = h.getBoundingClientRect();
      showTip('<div class="h">T+'+p.apw+' · '+p.day_of_week+' '+p.travel_date+'</div>' +
        rows([['geometric mean', inr(p.geomean)], ['observed min', inr(p.min)],
              ['observed max', inr(p.max)], ['spread', p.spread_pct+'%'],
              ['observations', p.n]]), r.left + r.width/2, r.top);
    }
    h.addEventListener('mouseenter', show); h.addEventListener('focus', show);
    h.addEventListener('mouseleave', hideTip); h.addEventListener('blur', hideTip);
  });
}
if(D && D.bands){
  var byBand = {}; D.bands.forEach(function(b){ byBand[b.band] = b; });
  document.querySelectorAll('.bar[data-band]').forEach(function(el){
    function show(){
      var b = byBand[el.dataset.band]; if(!b) return;
      var r = el.getBoundingClientRect();
      showTip('<div class="h">Band '+b.band+' · '+b.window+'</div>' +
        rows([['geometric mean', inr(b.geomean)], ['observations', b.n]]),
        r.left + r.width/2, r.top);
    }
    el.addEventListener('mouseenter', show); el.addEventListener('focus', show);
    el.addEventListener('mouseleave', hideTip); el.addEventListener('blur', hideTip);
  });
}

/* ----------------------------------------------------------- evidence wall */
if(D && D.obs){
  document.querySelectorAll('.wall button[data-i]').forEach(function(b){
    function show(){
      var o = D.obs[+b.dataset.i]; if(!o) return;
      var r = b.getBoundingClientRect();
      var grade = (o.ev==='PRIMARY_HASHED') ? 'primary · hashed' : 'secondary · chat image';
      showTip('<div class="h">'+grade+'</div>' +
        rows([['flight', o.flight], ['travel date', o.td], ['T+', o.apw],
              ['band', o.band], ['fare', inr(o.total)]]),
        r.left + r.width/2, r.top);
    }
    b.addEventListener('mouseenter', show); b.addEventListener('focus', show);
    b.addEventListener('mouseleave', hideTip); b.addEventListener('blur', hideTip);
  });
}

/* -------------------------------------------------------- boundary stages */
document.querySelectorAll('.stage').forEach(function(btn){
  btn.addEventListener('click', function(){
    var open = btn.getAttribute('aria-expanded') === 'true';
    var body = document.getElementById(btn.getAttribute('aria-controls'));
    btn.setAttribute('aria-expanded', open ? 'false' : 'true');
    if(body) body.dataset.open = open ? '0' : '1';
    if(hasGSAP) ST.refresh();
  });
});

/* ------------------------------------------------------------ data vault */
(function(){
  var table = document.getElementById('obs-table');
  if(!table) return;
  var trs = [].slice.call(table.querySelectorAll('tbody tr'));
  var out = document.getElementById('obs-count');
  var state = {apw:'all', band:'all', ev:'all'};
  function apply(){
    var shown = 0;
    trs.forEach(function(tr){
      var ok = (state.apw==='all' || tr.dataset.apw===state.apw) &&
               (state.band==='all' || tr.dataset.band===state.band) &&
               (state.ev==='all' || tr.dataset.ev===state.ev);
      tr.hidden = !ok; if(ok) shown++;
    });
    if(out) out.innerHTML = '<b>'+shown+'</b> of '+trs.length+' observations';
  }
  document.querySelectorAll('.fset button[data-f]').forEach(function(b){
    b.addEventListener('click', function(){
      state[b.dataset.f] = b.dataset.v;
      b.parentNode.querySelectorAll('button').forEach(function(o){
        o.setAttribute('aria-pressed', o===b ? 'true':'false'); });
      apply();
    });
  });
  apply();
})();

/* =========================================== WebGL observation field ======
   35 nodes, one per real observation. Every axis is a recorded field:
       x   advance-purchase bucket index      (lead time)
       y   payable fare, min-max normalised   (price)
       z   departure band                     (time of day)
   colour  evidence grade
   The lattice joins along both axes, so the mesh IS the 7 x 5 collection
   plan: a gap in it would be a slot the collector did not fill. Scroll drives
   a morph between a flat price cloud and that full spatial lattice, which is
   the same reorganisation the narrative describes in words.
   Nothing is encoded that is not in panel.json.                            */
(function(){
  var cv = document.getElementById('field');
  if(!cv || !D || !D.obs || RM){ if(cv) cv.remove(); return; }
  var gl = null;
  try {
    gl = cv.getContext('webgl', {alpha:true, antialias:true, premultipliedAlpha:false});
  } catch(e){}
  if(!gl){ cv.remove(); return; }

  var VS = 'attribute vec3 a;attribute vec3 b;attribute vec3 c;attribute float s;' +
    'uniform mat4 mvp;uniform float m;varying vec3 vc;' +
    'void main(){vec3 p=mix(a,b,m);vec4 q=mvp*vec4(p,1.0);gl_Position=q;' +
    'gl_PointSize=s*clamp(1.9/max(q.w,0.4),0.3,2.6);vc=c;}';
  var FS = 'precision mediump float;varying vec3 vc;' +
    'void main(){vec2 d=gl_PointCoord-vec2(0.5);float r=length(d);' +
    'if(r>0.5)discard;float k=smoothstep(0.5,0.08,r);' +
    'gl_FragColor=vec4(vc,k*0.95);}';
  function sh(t,src){ var o=gl.createShader(t); gl.shaderSource(o,src); gl.compileShader(o);
    return gl.getShaderParameter(o,gl.COMPILE_STATUS)?o:null; }
  var vs=sh(gl.VERTEX_SHADER,VS), fs=sh(gl.FRAGMENT_SHADER,FS);
  if(!vs||!fs){ cv.remove(); return; }
  var pr=gl.createProgram(); gl.attachShader(pr,vs); gl.attachShader(pr,fs); gl.linkProgram(pr);
  if(!gl.getProgramParameter(pr,gl.LINK_STATUS)){ cv.remove(); return; }
  gl.useProgram(pr);

  var obs=D.obs, apws=D.apwOrder;
  var fares=obs.map(function(o){return o.total;});
  var flo=Math.min.apply(null,fares), fhi=Math.max.apply(null,fares);
  var PRIM=[0.17,0.42,0.31], SEC=[0.72,0.45,0.07];   /* green / amber, on paper */
  function norm(v,a,b){ return (v-a)/Math.max(b-a,1); }
  /* phase A: a flat price cloud, ordered only by fare */
  function A(o,i){ return [ (i/(obs.length-1)-0.5)*3.6, (norm(o.total,flo,fhi)-0.5)*1.5, 0 ]; }
  /* phase B: the 7 x 5 collection lattice */
  function B(o){ return [ (apws.indexOf(o.apw)/Math.max(apws.length-1,1)-0.5)*3.4,
                          (norm(o.total,flo,fhi)-0.5)*1.5,
                          ((o.band-2)/4-0.5)*2.2 ]; }
  var PA=[],PB=[],C=[],S=[];
  obs.forEach(function(o,i){
    var a=A(o,i), b=B(o);
    PA.push(a[0],a[1],a[2]); PB.push(b[0],b[1],b[2]);
    var col = (o.ev==='PRIMARY_HASHED')?PRIM:SEC;
    C.push(col[0],col[1],col[2]);
    S.push(o.ev==='PRIMARY_HASHED'?15.0:21.0);
  });
  var LA=[],LB=[],LC=[];
  function edge(p,q,i,j){
    var a1=A(p,i),a2=A(q,j),b1=B(p),b2=B(q);
    LA.push(a1[0],a1[1],a1[2],a2[0],a2[1],a2[2]);
    LB.push(b1[0],b1[1],b1[2],b2[0],b2[1],b2[2]);
    LC.push(0.55,0.58,0.62,0.55,0.58,0.62);
  }
  var idx = {}; obs.forEach(function(o,i){ idx[o.observation_id||i] = i; });
  var bandsSeen=[];
  obs.forEach(function(o){ if(bandsSeen.indexOf(o.band)<0) bandsSeen.push(o.band); });
  bandsSeen.sort(function(m,n){return m-n;});
  apws.forEach(function(a){
    var g=[]; obs.forEach(function(o,i){ if(o.apw===a) g.push({o:o,i:i}); });
    g.sort(function(m,n){ return m.o.band-n.o.band; });
    for(var k=0;k<g.length-1;k++) edge(g[k].o,g[k+1].o,g[k].i,g[k+1].i);
  });
  bandsSeen.forEach(function(bd){
    var g=[]; obs.forEach(function(o,i){ if(o.band===bd) g.push({o:o,i:i}); });
    g.sort(function(m,n){ return apws.indexOf(m.o.apw)-apws.indexOf(n.o.apw); });
    for(var k=0;k<g.length-1;k++) edge(g[k].o,g[k+1].o,g[k].i,g[k+1].i);
  });

  function buf(d){ var b=gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER,b);
    gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(d),gl.STATIC_DRAW); return b; }
  var bPA=buf(PA),bPB=buf(PB),bC=buf(C),bS=buf(S),bLA=buf(LA),bLB=buf(LB),bLC=buf(LC);
  var aA=gl.getAttribLocation(pr,'a'),aB=gl.getAttribLocation(pr,'b'),
      aC=gl.getAttribLocation(pr,'c'),aS=gl.getAttribLocation(pr,'s'),
      uM=gl.getUniformLocation(pr,'mvp'),uMix=gl.getUniformLocation(pr,'m');
  function bind(b,loc,n){ gl.bindBuffer(gl.ARRAY_BUFFER,b); gl.enableVertexAttribArray(loc);
    gl.vertexAttribPointer(loc,n,gl.FLOAT,false,0,0); }
  function mul(x,y){ var o=new Float32Array(16);
    for(var i=0;i<4;i++)for(var j=0;j<4;j++){var s=0;
      for(var k=0;k<4;k++)s+=x[k*4+j]*y[i*4+k]; o[i*4+j]=s;} return o; }
  function persp(f,as,n,fa){ var t=1/Math.tan(f/2);
    return new Float32Array([t/as,0,0,0, 0,t,0,0, 0,0,(fa+n)/(n-fa),-1, 0,0,2*fa*n/(n-fa),0]); }
  function view(ang,dist,lift){
    var ex=Math.sin(ang)*dist, ey=lift, ez=Math.cos(ang)*dist;
    var L=Math.hypot(ex,ey,ez), zx=ex/L,zy=ey/L,zz=ez/L;
    var L2=Math.hypot(zz,0,-zx), xx=zz/L2,xy=0,xz=-zx/L2;
    var yx=zy*xz-zz*xy, yy=zz*xx-zx*xz, yz=zx*xy-zy*xx;
    return new Float32Array([xx,yx,zx,0, xy,yy,zy,0, xz,yz,zz,0,
      -(xx*ex+xy*ey+xz*ez), -(yx*ex+yy*ey+yz*ez), -(zx*ex+zy*ey+zz*ez), 1]);
  }

  var morph = 0, targetMorph = 0, running = true, raf = 0, t0 = performance.now();
  var host = cv.parentElement;
  if(hasGSAP && host){
    ST.create({ trigger: host, start:'top 80%', end:'bottom top', scrub:true,
      onUpdate:function(self){ targetMorph = Math.min(1, self.progress * 2.1); } });
  } else { targetMorph = 1; }

  function size(){
    var dpr = Math.min(devicePixelRatio||1, innerWidth<760?1.5:2);
    var w=cv.clientWidth, h=cv.clientHeight;
    if(cv.width!==(w*dpr|0)||cv.height!==(h*dpr|0)){ cv.width=w*dpr|0; cv.height=h*dpr|0; }
    gl.viewport(0,0,cv.width,cv.height);
  }
  function frame(now){
    if(!running) return;
    size();
    morph += (targetMorph - morph) * 0.06;
    var ang = (now-t0)*0.00006 + morph*0.55;
    var mvp = mul(persp(1.0, cv.width/Math.max(cv.height,1), 0.1, 60),
                  view(ang, 4.6, 0.85+morph*0.5));
    gl.clearColor(0,0,0,0); gl.clear(gl.COLOR_BUFFER_BIT);
    gl.enable(gl.BLEND); gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
    gl.uniformMatrix4fv(uM,false,mvp); gl.uniform1f(uMix, morph);
    if(LA.length){
      bind(bLA,aA,3); bind(bLB,aB,3); bind(bLC,aC,3);
      gl.disableVertexAttribArray(aS); gl.vertexAttrib1f(aS,1.0);
      gl.drawArrays(gl.LINES,0,LA.length/3);
    }
    bind(bPA,aA,3); bind(bPB,aB,3); bind(bC,aC,3); bind(bS,aS,1);
    gl.drawArrays(gl.POINTS,0,PA.length/3);
    raf = requestAnimationFrame(frame);
  }
  var io = new IntersectionObserver(function(es){
    es.forEach(function(e){
      if(e.isIntersecting && !running){ running=true; raf=requestAnimationFrame(frame); }
      else if(!e.isIntersecting && running){ running=false; cancelAnimationFrame(raf); }
    });
  }, {threshold:0.01});
  io.observe(cv);
  raf = requestAnimationFrame(frame);
  addEventListener('resize', size, {passive:true});
})();
})();
"""
