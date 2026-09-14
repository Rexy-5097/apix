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
/* The three libraries are loaded with `defer`, so they execute after this
   script is parsed but before DOMContentLoaded. Reading window.gsap while the
   document was still parsing therefore always found nothing, and the entire
   animation layer silently took its no-library path on every load. Booting on
   DOMContentLoaded is what makes the libraries visible here. The fallbacks
   below still cover the case where they genuinely never arrive. */
function boot(){
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
    /* fromTo, not to: the resting offset is written in CSS as a percentage,
       and GSAP reads a computed transform back as pixels with yPercent 0 —
       so a tween *to* yPercent 0 moved nothing and every masked heading,
       including the hero, stayed hidden behind its own clip. Owning both
       ends of the tween is what makes the line actually ride up. */
    G.fromTo(el.querySelectorAll('span'), {yPercent:112, y:0}, {
      yPercent:0, y:0, duration:1.15, ease:'expo.out', stagger:0.07,
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
/* The element's own text is the TRUTH and is already correct in the markup.
   The counter animates 0 -> target and then restores that exact string, so a
   blocked script, a reduced-motion setting or the 1.6s before the animation
   runs all show the real figure rather than a zero. A page that renders "0
   screenshots audited" is worse than one that renders nothing. */
document.querySelectorAll('[data-count]').forEach(function(el){
  var target = parseFloat(el.dataset.count);
  if(!isFinite(target)) return;
  var truth = el.textContent;
  var dp = el.dataset.dp ? +el.dataset.dp : 0;
  var pre = el.dataset.pre || '', post = el.dataset.post || '';
  function render(v){ el.textContent = pre + v.toFixed(dp) + post; }
  function settle(){ el.textContent = truth; }
  if(RM) return;                       /* reduced motion: leave the truth alone */
  if(hasGSAP){
    var o = {v:0};
    G.to(o, { v:target, duration:1.5, ease:'expo.out',
      scrollTrigger:{ trigger:el, start:'top 88%' },
      onStart:function(){ render(0); },
      onUpdate:function(){ render(o.v); },
      onComplete:settle });
  } else if('IntersectionObserver' in window){
    var io = new IntersectionObserver(function(es){
      es.forEach(function(e){
        if(!e.isIntersecting) return;
        io.unobserve(e.target);
        var t0 = performance.now();
        render(0);
        (function step(now){
          var k = Math.min(1, (now-t0)/1300);
          if(k >= 1){ settle(); return; }
          render(target * (1 - Math.pow(1-k, 4)));
          requestAnimationFrame(step);
        })(t0);
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
  if(!hasGSAP || RM || innerWidth < 760){
    /* No driver for the sideways travel: stack the panels instead of leaving
       six of them clipped outside the pin. */
    document.documentElement.classList.add('rail-flat');
    outer.style.height='auto'; return;
  }
  var distance = function(){ return Math.max(0, track.scrollWidth - innerWidth + 80); };
  /* Hold the tween itself: containerAnimation below needs the animation that
     moves the track, and ST.getAll() hands back ScrollTrigger instances, not
     tweens. Passing one of those threw on the first bar, which aborted the
     rest of this script — the decomposition bars, the pipeline lighting and
     the whole seven-beat sequence never ran. */
  var railTween = G.to(track, {
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
    try {
      G.fromTo(bar, {scaleX:0}, {scaleX:1, transformOrigin:'left', ease:'expo.out',
        duration:0.9, scrollTrigger:{ trigger:bar.closest('.rail-panel'),
          containerAnimation: railTween, start:'left 72%' } });
    } catch(e){ bar.style.transform = 'scaleX(1)'; }
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

/* ------------------------------------------------- pipeline, stage by stage */
/* Only stages the real data actually reaches light up. The ones past the
   evidence boundary are left inert on purpose: an animation that ran through
   them would be animating work that has not happened. */
(function(){
  var reached = [].slice.call(document.querySelectorAll('.stage[data-past="0"]'));
  if(!reached.length) return;
  if(RM){ reached.forEach(function(el){ el.dataset.lit = '1'; }); return; }
  if(hasGSAP){
    reached.forEach(function(el, i){
      ST.create({ trigger: el, start:'top 82%',
        onEnter:function(){ el.dataset.lit = '1'; },
        onLeaveBack:function(){ el.dataset.lit = '0'; } });
    });
  } else if('IntersectionObserver' in window){
    var io = new IntersectionObserver(function(es){
      es.forEach(function(e){ if(e.isIntersecting) e.target.dataset.lit = '1'; });
    }, {rootMargin:'0px 0px -18% 0px'});
    reached.forEach(function(el){ io.observe(el); });
  } else {
    reached.forEach(function(el){ el.dataset.lit = '1'; });
  }
})();

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

/* ==================================== WebGL observation field, seven beats ==
   35 nodes, one per real observation. Every coordinate is a recorded field --
   advance-purchase bucket, payable fare, departure band, travel weekday -- and
   nothing else is encoded. Scroll drives a continuous `beat` value and the
   points interpolate between layouts, so the reorganisation the narrative
   describes in words is the same reorganisation you watch happen.

   Beat 1 (lead time) and beat 3 (travel date) resolve to IDENTICAL geometry.
   That is not a shortcut: in this panel each bucket has exactly one travel
   date, so the two axes are the same axis. Watching them land on top of each
   other is the confound, demonstrated structurally rather than asserted.    */
(function(){
  var cv = document.getElementById('field3d');
  var host = cv && cv.closest('.field-pin');
  if(!cv || !D || !D.obs || RM){ if(cv) cv.remove(); return; }
  var gl = null;
  try {
    gl = cv.getContext('webgl', {alpha:true, antialias:true, premultipliedAlpha:false});
  } catch(e){}
  if(!gl){ cv.remove(); return; }

  var VS = 'attribute vec3 p;attribute vec3 c;attribute float s;uniform mat4 mvp;' +
    'varying vec3 vc;void main(){vec4 q=mvp*vec4(p,1.0);gl_Position=q;' +
    'gl_PointSize=s*clamp(1.9/max(q.w,0.4),0.3,2.8);vc=c;}';
  var FS = 'precision mediump float;varying vec3 vc;void main(){' +
    'vec2 d=gl_PointCoord-vec2(0.5);float r=length(d);if(r>0.5)discard;' +
    'gl_FragColor=vec4(vc,smoothstep(0.5,0.07,r)*0.95);}';
  function sh(t,src){ var o=gl.createShader(t); gl.shaderSource(o,src); gl.compileShader(o);
    return gl.getShaderParameter(o,gl.COMPILE_STATUS)?o:null; }
  var vs=sh(gl.VERTEX_SHADER,VS), fs=sh(gl.FRAGMENT_SHADER,FS);
  if(!vs||!fs){ cv.remove(); return; }
  var pr=gl.createProgram(); gl.attachShader(pr,vs); gl.attachShader(pr,fs);
  gl.linkProgram(pr);
  if(!gl.getProgramParameter(pr,gl.LINK_STATUS)){ cv.remove(); return; }
  gl.useProgram(pr);

  var obs = D.obs, apws = D.apwOrder;
  var fares = obs.map(function(o){ return o.total; });
  var flo = Math.min.apply(null, fares), fhi = Math.max.apply(null, fares);
  var bands = []; obs.forEach(function(o){ if(bands.indexOf(o.band)<0) bands.push(o.band); });
  bands.sort(function(a,b){ return a-b; });
  var dows = []; apws.forEach(function(a){
    var d = D.dowByApw[a]; if(dows.indexOf(d)<0) dows.push(d);
  });
  var dowCount = {};
  apws.forEach(function(a){ var d=D.dowByApw[a]; dowCount[d]=(dowCount[d]||0)+1; });

  function fy(o){ return ((o.total - flo) / Math.max(fhi - flo, 1) - 0.5) * 1.6; }
  function ax(o){ return (apws.indexOf(o.apw) / Math.max(apws.length-1,1) - 0.5) * 3.4; }
  function bz(o){ return (bands.indexOf(o.band) / Math.max(bands.length-1,1) - 0.5) * 2.3; }
  function dz(o){ return (dows.indexOf(D.dowByApw[o.apw]) /
                          Math.max(dows.length-1,1) - 0.5) * 2.3; }

  /* Per-bucket geometric means, straight from the contract: the shape the
     descriptive profile chart draws, reached by collapsing the cloud. */
  var gm = {}; D.apw.forEach(function(a){ gm[a.apw] = a.geomean; });
  function gy(o){ return ((gm[o.apw] - flo) / Math.max(fhi - flo, 1) - 0.5) * 1.6; }

  var INK=[0.30,0.34,0.39], BLUE=[0.18,0.36,0.54], AMBER=[0.72,0.45,0.07];

  /* Seven layouts. Each returns [x, y, z, colour], all from recorded fields. */
  var LAYOUTS = [
    function(o,i){ return [ (i/(obs.length-1)-0.5)*3.4, fy(o), 0, INK ]; },
    function(o){   return [ ax(o), fy(o), 0, BLUE ]; },
    function(o){   return [ ax(o), fy(o), bz(o), BLUE ]; },
    function(o){   return [ ax(o), fy(o), bz(o), BLUE ]; },
    function(o){   return [ ax(o), fy(o), dz(o),
                            dowCount[D.dowByApw[o.apw]] > 1 ? AMBER : BLUE ]; },
    function(o){   return [ ax(o), fy(o), dz(o),
                            dowCount[D.dowByApw[o.apw]] > 1 ? AMBER : BLUE ]; },
    function(o){   return [ ax(o), gy(o), 0, AMBER ]; }
  ];
  var BEATS = LAYOUTS.length;

  var P = new Float32Array(obs.length*3), C = new Float32Array(obs.length*3);
  var S = new Float32Array(obs.length);
  obs.forEach(function(o,i){ S[i] = o.ev === 'PRIMARY_HASHED' ? 17.0 : 23.0; });

  /* Lattice edges, bucket-wise and band-wise, so the mesh is the 7 x 5 plan. */
  var EDGES = [];
  apws.forEach(function(a){
    var g=[]; obs.forEach(function(o,i){ if(o.apw===a) g.push(i); });
    g.sort(function(m,n){ return obs[m].band-obs[n].band; });
    for(var k=0;k<g.length-1;k++) EDGES.push([g[k],g[k+1]]);
  });
  bands.forEach(function(b){
    var g=[]; obs.forEach(function(o,i){ if(o.band===b) g.push(i); });
    g.sort(function(m,n){ return apws.indexOf(obs[m].apw)-apws.indexOf(obs[n].apw); });
    for(var k=0;k<g.length-1;k++) EDGES.push([g[k],g[k+1]]);
  });
  var LP = new Float32Array(EDGES.length*6), LC = new Float32Array(EDGES.length*6);

  var bP=gl.createBuffer(), bC=gl.createBuffer(), bS=gl.createBuffer(),
      bLP=gl.createBuffer(), bLC=gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER,bS); gl.bufferData(gl.ARRAY_BUFFER,S,gl.STATIC_DRAW);
  var aP=gl.getAttribLocation(pr,'p'), aC=gl.getAttribLocation(pr,'c'),
      aS=gl.getAttribLocation(pr,'s'), uM=gl.getUniformLocation(pr,'mvp');
  function bind(b,loc,n){ gl.bindBuffer(gl.ARRAY_BUFFER,b); gl.enableVertexAttribArray(loc);
    gl.vertexAttribPointer(loc,n,gl.FLOAT,false,0,0); }
  function mul(x,y){ var o=new Float32Array(16);
    for(var i=0;i<4;i++)for(var j=0;j<4;j++){var s=0;
      for(var k=0;k<4;k++)s+=x[k*4+j]*y[i*4+k]; o[i*4+j]=s;} return o; }
  function persp(f,as,n,fa){ var t=1/Math.tan(f/2);
    return new Float32Array([t/as,0,0,0, 0,t,0,0, 0,0,(fa+n)/(n-fa),-1,
                             0,0,2*fa*n/(n-fa),0]); }
  function view(ang,dist,lift){
    var ex=Math.sin(ang)*dist, ey=lift, ez=Math.cos(ang)*dist;
    var L=Math.hypot(ex,ey,ez), zx=ex/L,zy=ey/L,zz=ez/L;
    var L2=Math.hypot(zz,0,-zx), xx=zz/L2,xy=0,xz=-zx/L2;
    var yx=zy*xz-zz*xy, yy=zz*xx-zx*xz, yz=zx*xy-zy*xx;
    return new Float32Array([xx,yx,zx,0, xy,yy,zy,0, xz,yz,zz,0,
      -(xx*ex+xy*ey+xz*ez), -(yx*ex+yy*ey+yz*ez), -(zx*ex+zy*ey+zz*ez), 1]);
  }
  function ease(t){ return t<0.5 ? 4*t*t*t : 1-Math.pow(-2*t+2,3)/2; }

  var beat = 0, targetBeat = 0, running = true, raf = 0, t0 = performance.now();
  var caps = [].slice.call(document.querySelectorAll('.fbeat'));

  function layout(){
    var lo = Math.max(0, Math.min(BEATS-1, Math.floor(beat)));
    var hi = Math.min(BEATS-1, lo+1);
    var k = ease(Math.max(0, Math.min(1, beat - lo)));
    for(var i=0;i<obs.length;i++){
      var a = LAYOUTS[lo](obs[i], i), b = LAYOUTS[hi](obs[i], i);
      P[i*3]   = a[0] + (b[0]-a[0])*k;
      P[i*3+1] = a[1] + (b[1]-a[1])*k;
      P[i*3+2] = a[2] + (b[2]-a[2])*k;
      for(var c=0;c<3;c++) C[i*3+c] = a[3][c] + (b[3][c]-a[3][c])*k;
    }
    /* Edges fade while the cloud is unordered and again while it collapses to
       the seven means: drawing a lattice between points that are not yet a
       lattice would be drawing a structure that is not there. */
    var vis = Math.min(1, Math.max(0, Math.min(beat-0.4, 5.5-beat)));
    for(var e=0;e<EDGES.length;e++){
      var m=EDGES[e][0], n=EDGES[e][1];
      LP[e*6]=P[m*3]; LP[e*6+1]=P[m*3+1]; LP[e*6+2]=P[m*3+2];
      LP[e*6+3]=P[n*3]; LP[e*6+4]=P[n*3+1]; LP[e*6+5]=P[n*3+2];
      var g = 0.80 - 0.34*vis;
      for(var q=0;q<6;q++) LC[e*6+q] = g;
    }
    gl.bindBuffer(gl.ARRAY_BUFFER,bP); gl.bufferData(gl.ARRAY_BUFFER,P,gl.DYNAMIC_DRAW);
    gl.bindBuffer(gl.ARRAY_BUFFER,bC); gl.bufferData(gl.ARRAY_BUFFER,C,gl.DYNAMIC_DRAW);
    gl.bindBuffer(gl.ARRAY_BUFFER,bLP); gl.bufferData(gl.ARRAY_BUFFER,LP,gl.DYNAMIC_DRAW);
    gl.bindBuffer(gl.ARRAY_BUFFER,bLC); gl.bufferData(gl.ARRAY_BUFFER,LC,gl.DYNAMIC_DRAW);
  }

  function size(){
    var dpr = Math.min(devicePixelRatio||1, innerWidth<760?1.5:2);
    var w=cv.clientWidth, h=cv.clientHeight;
    if(cv.width!==(w*dpr|0)||cv.height!==(h*dpr|0)){ cv.width=w*dpr|0; cv.height=h*dpr|0; }
    gl.viewport(0,0,cv.width,cv.height);
  }
  function frame(now){
    if(!running) return;
    size();
    beat += (targetBeat - beat) * 0.085;
    layout();
    /* The camera lifts while depth carries meaning and settles flat again when
       the cloud collapses into the two-dimensional profile. */
    var depth = Math.min(1, Math.max(0, Math.min(beat-1.3, 5.7-beat)));
    var ang = 0.20 + Math.sin((now-t0)*0.00007)*0.09 + depth*0.44;
    var mvp = mul(persp(0.98, cv.width/Math.max(cv.height,1), 0.1, 60),
                  view(ang, 4.35, 0.28 + depth*0.88));
    gl.clearColor(0,0,0,0); gl.clear(gl.COLOR_BUFFER_BIT);
    gl.enable(gl.BLEND); gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
    gl.uniformMatrix4fv(uM,false,mvp);
    if(EDGES.length){
      bind(bLP,aP,3); bind(bLC,aC,3);
      gl.disableVertexAttribArray(aS); gl.vertexAttrib1f(aS,1.0);
      gl.drawArrays(gl.LINES,0,EDGES.length*2);
    }
    bind(bP,aP,3); bind(bC,aC,3); bind(bS,aS,1);
    gl.drawArrays(gl.POINTS,0,obs.length);
    raf = requestAnimationFrame(frame);
  }

  function setBeat(b){
    targetBeat = Math.max(0, Math.min(BEATS-1, b));
    var active = Math.round(targetBeat);
    caps.forEach(function(el,i){
      el.dataset.on = i === active ? '1' : '0';
    });
  }

  if(hasGSAP && host && host.parentElement){
    ST.create({
      trigger: host.parentElement, start:'top top', end:'bottom bottom',
      scrub: 0.7, onUpdate:function(self){ setBeat(self.progress * (BEATS-1)); }
    });
  } else if('IntersectionObserver' in window){
    /* No ScrollTrigger: step the beats from the captions' own visibility, so
       the choreography still happens, just without scrubbing. */
    var io2 = new IntersectionObserver(function(es){
      es.forEach(function(e){ if(e.isIntersecting) setBeat(caps.indexOf(e.target)); });
    }, {rootMargin:'-45% 0px -45% 0px'});
    caps.forEach(function(el){ io2.observe(el); });
  } else { setBeat(BEATS-1); }
  setBeat(0);

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
}
if(document.readyState === 'loading'){
  document.addEventListener('DOMContentLoaded', boot);
} else { boot(); }
})();
"""
