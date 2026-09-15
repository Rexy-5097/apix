"""Motion and interaction layer for ``data/platform.html``.

The editorial dashboard's motion system (``dashboard_viz.JS``) is the reference
implementation and this is its sibling, not a replacement: the same libraries
(vendored GSAP, ScrollTrigger, Lenis), the same conventions — ``.rv`` reveals,
``.line-mask`` headings, the ``#tip`` tooltip, the ``.js`` rest-state gate, the
2.5-second failsafe — and the same two rules that survived review there:

1. **A figure is revealed, never tallied.** Counting 0 → 35 puts "20 real
   observations" on screen for half a second, and a jury can screenshot any
   frame. Every measured number is masked and uncovered, so no intermediate
   value ever exists. Sequence is expressed by *order of reveal*, not by
   interpolating through wrong values.
2. **Motion animates work that happened.** The live-acquisition lane carries no
   packet, because no request was ever made. The manual-evidence lane carries a
   real observation and stops at the index, because that is where the evidence
   stops. Nothing loops in a way that implies live collection.

Everything here is an enhancement. With JavaScript off, the libraries missing,
or ``prefers-reduced-motion`` set, the page is complete and every figure reads
its true value.
"""

from __future__ import annotations

import json
from typing import Any

#: Vendored, same files the dashboard loads. Relative to ``data/``.
LIBS = (
    "vendor/gsap.min.js",
    "vendor/ScrollTrigger.min.js",
    "vendor/lenis.min.js",
)


def libs_tags() -> str:
    return "".join(f'<script src="{u}" defer></script>' for u in LIBS)


def island(data: dict[str, Any]) -> str:
    """The data island. Only recorded values reach it; the JS invents nothing."""
    return json.dumps(data, separators=(",", ":"), sort_keys=True, default=str)


# --------------------------------------------------------------------------- CSS
# Rest states are gated on ``html.js`` so a blocked script leaves content
# visible. The reduced-motion block in dashboard_theme.CSS already neutralises
# .rv and .line-mask; the additions here cover this page's own components.
MOTION_CSS = """
/* ---------------------------------------------------------- nav, progress */
.pf-nav{position:sticky;top:0;z-index:20;background:color-mix(in srgb,var(--paper) 92%,transparent);
        backdrop-filter:saturate(140%) blur(8px);transition:box-shadow var(--fast) var(--out)}
.pf-nav[data-solid="1"]{box-shadow:0 1px 0 var(--line),0 8px 24px -18px rgba(23,28,33,.5)}
.pf-nav a{position:relative;transition:color 180ms var(--out)}
.pf-nav a::after{content:"";position:absolute;left:0;right:100%;bottom:1px;height:1.5px;
                 background:var(--amber);transition:right 220ms var(--out)}
.pf-nav a:hover::after,.pf-nav a:focus-visible::after{right:0}
.pf-nav a[aria-current="true"]{color:var(--ink);font-weight:600}
.pf-nav a[aria-current="true"]::after{right:0}
.pf-prog{position:absolute;left:0;bottom:-1px;height:2px;width:100%;background:var(--amber);
         transform:scaleX(0);transform-origin:0 50%;z-index:21}
.pf-where{font-family:var(--mono);font-size:10.5px;letter-spacing:.1em;color:var(--ink-3);
          padding:3px 0 1px;grid-column:1/-1}
.pf-where b{color:var(--amber-ink);font-weight:600}

/* ------------------------------------------------------------- hero field */
.pf-fieldwrap{position:relative;margin:26px 0 0;border:1px solid var(--line);background:var(--card)}
#pf-field{display:block;width:100%;height:210px}
.pf-beats{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:var(--line);
          border-top:1px solid var(--line)}
.pf-beats div{background:var(--card);padding:9px 12px;font-family:var(--mono);font-size:10.5px;
              letter-spacing:.07em;color:var(--ink-3);transition:color 260ms var(--out),
              background 260ms var(--out)}
.pf-beats div[data-on="1"]{color:var(--amber-ink);background:var(--amber-wash)}
.pf-beats b{display:block;font-size:11.5px;color:inherit;letter-spacing:.04em}

/* --------------------------------------------------------- source cards */
.scards{display:grid;grid-template-columns:repeat(auto-fill,minmax(228px,1fr));gap:12px;margin:0 0 18px}
.scard{border:1px solid var(--line);background:var(--card);padding:12px 13px;
       transition:transform 200ms var(--out),box-shadow 200ms var(--out),border-color 200ms var(--out)}
.scard:hover{transform:translateY(-2px);border-color:var(--line-2);
             box-shadow:0 10px 26px -20px rgba(23,28,33,.7)}
.scard h4{margin:0 0 2px;font-size:14px;letter-spacing:-.01em;display:flex;align-items:center;gap:7px}
.scard .ch{font-family:var(--mono);font-size:10px;letter-spacing:.09em;color:var(--ink-3);
           text-transform:uppercase;margin:0 0 9px}
.scard dl{margin:0;display:grid;grid-template-columns:auto 1fr;gap:3px 10px;font-size:11.5px}
.scard dt{color:var(--ink-3)}
.scard dd{margin:0;font-family:var(--mono);font-size:11px;text-align:right;overflow-wrap:anywhere}
/* Permission state and operational state are different facts and never share a
   colour: a refusal is not an outage. */
.sdot{width:9px;height:9px;border-radius:50%;flex:none;background:var(--ink-3);position:relative}
.scard[data-perm="AUTHORIZED"] .sdot{background:var(--green)}
.scard[data-perm="PENDING"] .sdot{background:var(--amber)}
.scard[data-perm="PROHIBITED"] .sdot{background:var(--red);border-radius:1.5px}
.scard[data-perm="UNKNOWN"] .sdot{background:var(--ink-3);opacity:.55}
.js .scard[data-perm="AUTHORIZED"][data-anim="1"] .sdot{animation:pf-pulse 2.4s var(--out) infinite}
.js .scard[data-perm="PENDING"][data-anim="1"] .sdot{animation:pf-breathe 3.6s ease-in-out infinite}
@keyframes pf-pulse{0%{box-shadow:0 0 0 0 var(--green-wash)}
                    70%{box-shadow:0 0 0 8px transparent}100%{box-shadow:0 0 0 0 transparent}}
@keyframes pf-breathe{0%,100%{opacity:.42}50%{opacity:1}}
.scard .ops{margin-top:9px;padding-top:8px;border-top:1px solid var(--line-2);
            font-family:var(--mono);font-size:10px;letter-spacing:.08em;color:var(--ink-3)}

/* ------------------------------------------------- architecture flow graph */
svg.ag{width:100%;height:auto;display:block;background:var(--card);border:1px solid var(--line)}
.ag-node rect{fill:var(--paper-2);stroke:var(--line);transition:fill 320ms var(--out),
              stroke 320ms var(--out)}
.ag-node text{font-family:var(--mono);font-size:10.5px;fill:var(--ink-2)}
.ag-node[data-lit="1"] rect{fill:var(--amber-wash);stroke:var(--amber)}
.ag-node[data-lit="1"] text{fill:var(--amber-ink)}
.ag-node[data-blocked="1"] rect{fill:var(--red-wash);stroke:var(--red)}
.ag-node[data-blocked="1"] text{fill:var(--red)}
.ag-edge{fill:none;stroke:var(--line-2);stroke-width:1.6}
.ag-edge.dead{stroke-dasharray:4 4;stroke:var(--red);opacity:.55}
.ag-pkt{opacity:0}
.ag-pkt rect{fill:var(--amber);stroke:none}
.ag-pkt text{font-family:var(--mono);font-size:9.5px;fill:var(--paper);font-weight:600}
.ag-stop{opacity:0}
.ag-stop rect{fill:var(--red-wash);stroke:var(--red)}
.ag-stop text{font-family:var(--mono);font-size:9.5px;fill:var(--red)}
.ag-cap{font-family:var(--mono);font-size:10px;fill:var(--ink-3)}
.agwrap{margin:0 0 4px}
@media(max-width:860px){
  .agwrap{overflow-x:auto;border:1px solid var(--line)}
  svg.ag{min-width:820px;border:none}
}

/* ------------------------------------------------- index dependency chain */
.dep{display:grid;gap:9px;margin:0 0 18px;max-width:560px}
.dep .row{display:flex;align-items:center;gap:11px;border:1px solid var(--line);background:var(--card);
          padding:10px 13px;font-size:13px}
.dep .row i{width:18px;height:18px;border-radius:50%;flex:none;display:grid;place-items:center;
            font-family:var(--mono);font-size:11px;font-style:normal;color:var(--paper)}
.dep .row[data-ok="1"] i{background:var(--green)}
.dep .row[data-ok="0"] i{background:var(--red)}
.dep .row b{font-family:var(--mono);font-size:11.5px;letter-spacing:.06em}
.dep .row span{color:var(--ink-3);font-size:12px;margin-left:auto;text-align:right}
.dep .arrow{font-family:var(--mono);color:var(--ink-3);font-size:12px;padding-left:8px}

/* ------------------------------------------------------- run stage ladder */
.ladder{display:grid;grid-template-columns:repeat(auto-fit,minmax(132px,1fr));gap:1px;
        background:var(--line);border:1px solid var(--line);margin:0 0 18px}
.ladder div{background:var(--card);padding:12px 13px}
.ladder b{display:block;font-family:var(--mono);font-size:20px;letter-spacing:-.02em;
          font-variant-numeric:tabular-nums}
.ladder span{font-size:11px;color:var(--ink-3)}
.ladder .zero b{color:var(--red)}

/* ------------------------------------------------------------- bar tracks */
.track{height:9px;background:var(--paper-2);border:1px solid var(--line);position:relative;
       overflow:hidden}
.track i{display:block;height:100%;background:var(--amber);transform:scaleX(0);transform-origin:0 50%}
.track.dead{background:repeating-linear-gradient(90deg,var(--paper-2) 0 7px,transparent 7px 14px)}
.btrow{display:grid;grid-template-columns:112px 1fr auto;gap:12px;align-items:center;
       font-size:12.5px;margin:0 0 9px}
.btrow .lab{font-family:var(--mono);font-size:11px;letter-spacing:.08em;color:var(--ink-2)}
.btrow .val{font-family:var(--mono);font-size:11px;color:var(--ink-3);white-space:nowrap}

/* ------------------------------------------------------ provenance lineage */
.lin{display:grid;gap:0;margin:0 0 6px;border:1px solid var(--line);background:var(--card)}
.lin .step{display:grid;grid-template-columns:130px 1fr;gap:12px;padding:10px 14px;
           border-bottom:1px solid var(--line-2);font-size:12.5px;opacity:1}
.js .lin .step{opacity:.25;transition:opacity 320ms var(--out),transform 320ms var(--out)}
.js .lin .step[data-on="1"]{opacity:1}
.lin .step:last-child{border-bottom:none}
.lin .step .k{font-family:var(--mono);font-size:10.5px;letter-spacing:.08em;color:var(--ink-3);
              text-transform:uppercase;padding-top:2px}
.lin .step .v{font-family:var(--mono);font-size:12px;overflow-wrap:anywhere}
.lin .step .v em{font-style:normal;color:var(--ink-3)}
.picker{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 14px}
.picker button{font-family:var(--mono);font-size:10.5px;letter-spacing:.04em;padding:5px 9px;
               border:1px solid var(--line);background:var(--card);color:var(--ink-2);cursor:pointer;
               transition:transform 180ms var(--out),border-color 180ms var(--out),
               background 180ms var(--out)}
.picker button:hover{transform:translateY(-1px);border-color:var(--amber)}
.picker button[aria-pressed="true"]{background:var(--amber-wash);border-color:var(--amber);
                                    color:var(--amber-ink);font-weight:600}

/* -------------------------------------------------------- heatmap interaction */
.hm-cell{cursor:pointer}
.hm-cell rect{transition:opacity 200ms var(--out),stroke 200ms var(--out)}
.hm-cell:hover rect,.hm-cell:focus-visible rect{stroke:var(--amber-ink);stroke-width:2}
.js .hm-cell[data-anim="1"]{opacity:0}
.hm-detail{border-left:3px solid var(--line-2);background:var(--card);padding:11px 15px;
           margin:0 0 18px;font-size:13px;min-height:44px}
.hm-detail[data-has="1"]{border-left-color:var(--amber)}
.hm-detail dl{margin:6px 0 0;display:grid;grid-template-columns:auto 1fr;gap:3px 14px;
              font-size:12px;max-width:420px}
.hm-detail dd{margin:0;font-family:var(--mono);text-align:right}

/* ---------------------------------------------------------- table stagger */
.js tbody tr.rvr{opacity:0}

/* ----------------------------------------------------------- endpoint cards */
.eps{display:grid;grid-template-columns:repeat(auto-fill,minmax(268px,1fr));gap:12px;margin:0 0 18px}
.epc{border:1px solid var(--line);background:var(--card);padding:11px 13px;
     transition:transform 200ms var(--out),border-color 200ms var(--out)}
.epc:hover{transform:translateY(-2px);border-color:var(--amber)}
.epc code{font-family:var(--mono);font-size:11.5px;color:var(--amber-ink);display:block;
          margin-bottom:5px;overflow-wrap:anywhere}
.epc p{margin:0;font-size:12px;color:var(--ink-3)}

/* ------------------------------------------------------------ closing beat */
.pf-close{padding:64px 0 76px;text-align:center}
.pf-close blockquote{margin:0 auto 26px;max-width:22ch;font-family:var(--disp);
                     font-size:clamp(26px,4vw,44px);line-height:1.12;letter-spacing:-.025em}
.pf-close .k{font-family:var(--mono);font-size:11px;letter-spacing:.16em;color:var(--ink-3);
             text-transform:uppercase}

@media (prefers-reduced-motion:reduce){
  .pf-prog{transform:scaleX(0)!important}
  #pf-field{display:none}
  .pf-fieldwrap{border:none}
  .js .lin .step{opacity:1}
  .js .hm-cell[data-anim="1"]{opacity:1}
  .js tbody tr.rvr{opacity:1}
  .track i{transform:scaleX(1)}
  .ag-pkt,.ag-stop{opacity:1}
}
@media(max-width:700px){
  #pf-field{height:150px}
  .pf-beats{grid-template-columns:1fr}
  .btrow{grid-template-columns:1fr;gap:5px}
  .lin .step{grid-template-columns:1fr;gap:3px}
}
"""


# ---------------------------------------------------------------------------- JS
MOTION_JS = r"""
(function(){
"use strict";
/* Booting on DOMContentLoaded, not at parse time: the three libraries are
   loaded with `defer`, so window.gsap does not exist while this script is being
   parsed. Reading it too early is what silently disabled the whole animation
   layer in the dashboard's first build. */
function boot(){
var RM = matchMedia('(prefers-reduced-motion: reduce)').matches;
var D = null;
try { D = JSON.parse(document.getElementById('apix-data').textContent); } catch(e) { D = null; }
var G = window.gsap, ST = window.ScrollTrigger, LenisCtor = window.Lenis;
var hasGSAP = !!(G && ST);
if(hasGSAP){ try { G.registerPlugin(ST); } catch(e){ hasGSAP = false; } }
var TRIGGERS = [];
function keep(t){ if(t) TRIGGERS.push(t); return t; }

/* ------------------------------------------------------- smooth scrolling */
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

/* --------------------------------------------------------------- tooltips */
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
function bind(el, fn){
  el.addEventListener('mouseenter', fn); el.addEventListener('focus', fn);
  el.addEventListener('mouseleave', hideTip); el.addEventListener('blur', hideTip);
}

/* ---------------------------------------------------------------- reveals */
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
  document.querySelectorAll('.line-mask').forEach(function(el){
    /* fromTo, not to: the resting offset is a CSS percentage and GSAP reads a
       computed transform back as pixels, so a tween *to* yPercent 0 moves
       nothing and the heading stays hidden behind its own clip. */
    G.fromTo(el.querySelectorAll('span'), {yPercent:112, y:0}, {
      yPercent:0, y:0, duration:1.15, ease:'expo.out', stagger:0.07,
      scrollTrigger:{ trigger:el, start:'top 90%' }
    });
  });
  document.querySelectorAll('.rv').forEach(function(el){
    G.to(el, { opacity:1, y:0, duration:0.9, ease:'expo.out',
      delay:(el.dataset.d ? +el.dataset.d * 0.08 : 0),
      scrollTrigger:{ trigger:el, start:'top 92%' } });
  });
}

/* Failsafe. The reveal is an enhancement, so it must not be the only path to
   visible content. If nothing revealed after 2.5s the mechanism is dead and
   everything is shown outright. */
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
  [].slice.call(document.querySelectorAll('[data-count]')).forEach(function(el){
    el.style.clipPath=''; el.style.transform=''; el.style.transition='';
  });
  [].slice.call(document.querySelectorAll('tbody tr.rvr, .hm-cell')).forEach(function(el){
    el.style.opacity='1';
  });
}, 2500);

/* -------------------------------------------------------- number reveals */
/* The element's text is already the true value; this only uncovers it. A
   0 -> 35 tally would put a WRONG statistic on screen for about a second, and
   any frame can be screenshotted, so no intermediate value is ever rendered. */
document.querySelectorAll('[data-count]').forEach(function(el){
  if(RM) return;
  var HID = 'inset(-25% 0 100% 0)', SEEN = 'inset(-25% 0 -25% 0)';
  function show(){ el.style.clipPath=''; el.style.transition=''; el.style.willChange=''; }
  el.style.willChange = 'clip-path';
  el.style.clipPath = HID;
  if(hasGSAP){
    G.fromTo(el, {clipPath:HID},
      { clipPath:SEEN, duration:1.0, ease:'expo.out', immediateRender:true,
        delay:(el.dataset.s ? +el.dataset.s * 0.09 : 0),
        scrollTrigger:{ trigger:el.closest('section, header') || el, start:'top 82%' },
        onComplete:show });
  } else if('IntersectionObserver' in window){
    var io = new IntersectionObserver(function(es){
      es.forEach(function(e){
        if(!e.isIntersecting) return;
        io.unobserve(e.target);
        el.style.transition = 'clip-path .95s cubic-bezier(.16,1,.3,1) ' +
                              (el.dataset.s ? +el.dataset.s * 0.09 : 0) + 's';
        el.style.clipPath = SEEN;
        setTimeout(show, 1400);
      });
    }, {threshold:.25});
    io.observe(el);
  } else { show(); }
});

/* ------------------------------------------- nav: active, progress, context */
(function(){
  var nav = document.querySelector('.pf-nav');
  var prog = document.querySelector('.pf-prog');
  var where = document.querySelector('.pf-where b');
  var links = [].slice.call(document.querySelectorAll('.pf-nav a[href^="#"]'));
  var secs = links.map(function(a){ return document.querySelector(a.getAttribute('href')); });
  function onScroll(){
    var y = window.scrollY || 0;
    if(nav) nav.dataset.solid = y > 30 ? '1' : '0';
    var doc = document.documentElement.scrollHeight - innerHeight;
    if(prog) prog.style.transform = 'scaleX(' + (doc > 0 ? Math.min(1, y/doc) : 0) + ')';
    var mid = y + (nav ? nav.offsetHeight : 48) + 30, best = -1;
    secs.forEach(function(s, i){ if(s && s.offsetTop <= mid) best = i; });
    links.forEach(function(a, i){
      if(i === best) a.setAttribute('aria-current','true'); else a.removeAttribute('aria-current');
    });
    if(where) where.textContent = best >= 0 ? links[best].textContent : 'Overview';
  }
  addEventListener('scroll', onScroll, {passive:true});
  addEventListener('resize', onScroll, {passive:true});
  onScroll();
  links.forEach(function(a){
    a.addEventListener('click', function(ev){
      var t = document.querySelector(a.getAttribute('href'));
      if(!t) return;
      ev.preventDefault();
      /* CSS scroll-padding handles scrollIntoView; Lenis scrolls itself and has
         to be told the same clearance explicitly. */
      var clear = (nav ? nav.offsetHeight : 48) + 18;
      if(lenis) lenis.scrollTo(t, {offset:-clear});
      else t.scrollIntoView({behavior:RM?'auto':'smooth'});
    });
  });
})();

/* ================================================= hero observation field ==
   35 points, one per real observation. Both coordinates are recorded fields --
   advance-purchase bucket and payable fare -- and scroll drives a continuous
   `beat` between three layouts: the quotes as collected, the same quotes keyed
   into their seven buckets, and the seven bucket geometric means the profile
   chart draws. Nothing is randomised and no value is invented.              */
(function(){
  var cv = document.getElementById('pf-field');
  if(!cv || !D || !D.obs || !D.obs.length || RM){ if(cv && RM) cv.remove(); return; }
  var ctx = null;
  try { ctx = cv.getContext('2d'); } catch(e){}
  if(!ctx){ cv.remove(); return; }

  var obs = D.obs, apws = D.apwOrder || [], gm = D.geomeanByApw || {};
  var fares = obs.map(function(o){ return o.total; });
  var flo = Math.min.apply(null, fares), fhi = Math.max.apply(null, fares);
  var caps = [].slice.call(document.querySelectorAll('.pf-beats div'));

  function nx(i){ return (i + 0.5) / obs.length; }
  function ax(o){ var k = apws.indexOf(o.apw);
                  return (k < 0 ? 0.5 : (k + 0.5) / Math.max(apws.length,1)); }
  function fy(v){ return 1 - (v - flo) / Math.max(fhi - flo, 1); }
  var LAY = [
    function(o,i){ return [nx(i), fy(o.total)]; },
    function(o){   return [ax(o),  fy(o.total)]; },
    function(o){   return [ax(o),  fy(gm[o.apw] != null ? gm[o.apw] : o.total)]; }
  ];
  var BEATS = LAY.length;
  var beat = 0, target = 0, running = false, rafId = 0, dpr = 1;

  function size(){
    dpr = Math.min(devicePixelRatio || 1, innerWidth < 760 ? 1.5 : 2);
    var w = cv.clientWidth, h = cv.clientHeight;
    if(cv.width !== (w*dpr|0) || cv.height !== (h*dpr|0)){
      cv.width = w*dpr|0; cv.height = h*dpr|0;
    }
  }
  function ease(t){ return t<0.5 ? 4*t*t*t : 1-Math.pow(-2*t+2,3)/2; }
  function draw(){
    var w = cv.width, h = cv.height, PL = 46*dpr, PR = 16*dpr, PT = 18*dpr, PB = 26*dpr;
    var iw = w - PL - PR, ih = h - PT - PB;
    ctx.clearRect(0,0,w,h);
    var lo = Math.max(0, Math.min(BEATS-1, Math.floor(beat)));
    var hi = Math.min(BEATS-1, lo+1);
    var k = ease(Math.max(0, Math.min(1, beat - lo)));
    /* baseline + bucket guides, drawn only once the points are keyed */
    ctx.strokeStyle = 'rgba(23,28,33,.10)'; ctx.lineWidth = 1*dpr;
    ctx.beginPath(); ctx.moveTo(PL, PT+ih); ctx.lineTo(PL+iw, PT+ih); ctx.stroke();
    var guide = Math.max(0, Math.min(1, beat - 0.25));
    if(guide > 0 && apws.length){
      ctx.strokeStyle = 'rgba(23,28,33,'+(0.07*guide).toFixed(3)+')';
      apws.forEach(function(a, gi){
        var gx = PL + iw * ((gi + 0.5) / apws.length);
        ctx.beginPath(); ctx.moveTo(gx, PT); ctx.lineTo(gx, PT+ih); ctx.stroke();
      });
    }
    for(var i=0;i<obs.length;i++){
      var a = LAY[lo](obs[i], i), b = LAY[hi](obs[i], i);
      var px = PL + iw * (a[0] + (b[0]-a[0])*k);
      var py = PT + ih * (a[1] + (b[1]-a[1])*k);
      var primary = obs[i].ev === 'PRIMARY_HASHED';
      ctx.beginPath();
      ctx.arc(px, py, (primary ? 2.6 : 3.6)*dpr, 0, 6.2832);
      ctx.fillStyle = beat > 1.55 ? 'rgba(166,104,16,.92)'
                    : (primary ? 'rgba(40,80,120,.80)' : 'rgba(166,104,16,.85)');
      ctx.fill();
    }
    ctx.fillStyle = 'rgba(23,28,33,.42)';
    ctx.font = (10*dpr) + 'px ui-monospace, SFMono-Regular, Menlo, monospace';
    ctx.fillText(inr(fhi), 4*dpr, PT + 4*dpr);
    ctx.fillText(inr(flo), 4*dpr, PT + ih);
  }
  function frame(){
    if(!running) return;
    size();
    beat += (target - beat) * 0.085;
    draw();
    rafId = requestAnimationFrame(frame);
  }
  function setBeat(b){
    target = Math.max(0, Math.min(BEATS-1, b));
    var act = Math.round(target);
    caps.forEach(function(el,i){ el.dataset.on = i === act ? '1' : '0'; });
  }
  setBeat(0);
  if(hasGSAP){
    keep(ST.create({ trigger:'.pf-hero', start:'top top', end:'bottom 30%', scrub:0.6,
      onUpdate:function(self){ setBeat(self.progress * (BEATS-1)); } }));
  } else {
    addEventListener('scroll', function(){
      var hero = document.querySelector('.pf-hero');
      if(!hero) return;
      var p = Math.min(1, Math.max(0, (window.scrollY||0) / Math.max(hero.offsetHeight,1)));
      setBeat(p * (BEATS-1));
    }, {passive:true});
  }
  /* Offscreen costs nothing: the loop is stopped, not throttled. */
  var io = new IntersectionObserver(function(es){
    es.forEach(function(e){
      if(e.isIntersecting && !running){ running = true; rafId = requestAnimationFrame(frame); }
      else if(!e.isIntersecting && running){ running = false; cancelAnimationFrame(rafId); }
    });
  }, {threshold:0.01});
  io.observe(cv);
  running = true; rafId = requestAnimationFrame(frame);
  addEventListener('resize', function(){ size(); draw(); }, {passive:true});
})();

/* ============================================== architecture: two lanes ====
   The manual-evidence lane carries a real observation from the island and
   stops at the index, because that is exactly where the evidence stops. The
   live-acquisition lane carries NOTHING past the gate: zero requests were
   made, so animating a packet through it would animate work that never
   happened.                                                                */
(function(){
  var svg = document.getElementById('arch-graph');
  if(!svg) return;
  var flow = svg.querySelector('#ag-flow');
  var pkt = svg.querySelector('#ag-pkt');
  var label = svg.querySelector('#ag-pkt-label');
  var stop = svg.querySelector('#ag-stop');
  var nodes = [].slice.call(svg.querySelectorAll('.ag-node[data-at]'));
  if(!flow || !pkt) return;
  var len = 0;
  try { len = flow.getTotalLength(); } catch(e){ return; }
  if(!len) return;

  var samples = (D && D.packets) || [];
  if(!samples.length) return;
  var si = 0;
  function dress(i){
    var s = samples[i % samples.length];
    if(label) label.textContent = s.label;
    var w = Math.max(74, s.label.length * 5.4 + 14);
    var r = pkt.querySelector('rect');
    if(r) r.setAttribute('width', w.toFixed(0));
    var t = pkt.querySelector('text');
    if(t) t.setAttribute('x', (w/2).toFixed(0));
  }
  dress(0);

  function place(p){
    var pt = flow.getPointAtLength(len * p);
    pkt.setAttribute('transform', 'translate(' + (pt.x - 6).toFixed(1) + ',' +
                                                 (pt.y - 9).toFixed(1) + ')');
    nodes.forEach(function(n){
      var at = parseFloat(n.dataset.at);
      if(n.dataset.blocked === '1') return;
      n.dataset.lit = (p >= at - 0.005) ? '1' : '0';
    });
  }
  place(0);
  if(RM){
    pkt.style.opacity = '1'; if(stop) stop.style.opacity = '1';
    nodes.forEach(function(n){ if(n.dataset.blocked !== '1') n.dataset.lit = '1'; });
    place(1);
    return;
  }

  if(!hasGSAP){
    pkt.style.opacity = '1'; place(1);
    if(stop) stop.style.opacity = '1';
    nodes.forEach(function(n){ if(n.dataset.blocked !== '1') n.dataset.lit = '1'; });
    return;
  }
  /* ONE timeline and ONE trigger, repeating. The first version rebuilt both on
     every pass and never killed the old trigger, so within a couple of cycles
     several stale triggers were toggling the same timeline and pausing the run
     that had just begun -- the packet froze mid-path. */
  var proxy = {p:0};
  var tl = G.timeline({ paused:true, repeat:-1, repeatDelay:0.5,
    onRepeat:function(){
      /* Next observation, same journey: a replay of recorded rows, never a
         live feed. The caption on the figure says exactly that. */
      si++; dress(si);
    }});
  tl.set(pkt, {opacity:0})
    .set(stop, {opacity:0})
    .set(proxy, {p:0})
    .to(pkt, {opacity:1, duration:0.28, ease:'power2.out'})
    .to(proxy, {p:1, duration:3.4, ease:'none',
                onUpdate:function(){ place(proxy.p); }}, '<')
    .to(pkt, {opacity:0, duration:0.3, ease:'power2.in'}, '+=0.15')
    .to(stop, {opacity:1, duration:0.4, ease:'expo.out'}, '<')
    .to(stop, {opacity:0, duration:0.4}, '+=1.5');
  var trig = keep(ST.create({ trigger:svg, start:'top 85%', end:'bottom 15%',
    onToggle:function(self){ if(self.isActive) tl.play(); else tl.pause(); } }));
  /* onToggle only fires on a transition, so a graph already in view when the
     trigger is created would never start. */
  if(trig && trig.isActive) tl.play();
})();

/* ------------------------------------------- index dependency chain, drawn */
(function(){
  var dep = document.querySelector('.dep');
  if(!dep) return;
  var rows = [].slice.call(dep.children);
  if(RM || !hasGSAP){ return; }
  G.from(rows, { opacity:0, x:-14, duration:0.6, ease:'expo.out', stagger:0.11,
    scrollTrigger:{ trigger:dep, start:'top 86%' } });
})();

/* ------------------------------------------------------------ bar tracks */
(function(){
  var bars = [].slice.call(document.querySelectorAll('.track i[data-w]'));
  if(!bars.length) return;
  bars.forEach(function(b){
    var w = Math.max(0, Math.min(1, parseFloat(b.dataset.w) || 0));
    if(RM){ b.style.transform = 'scaleX(' + w + ')'; return; }
    if(hasGSAP){
      G.fromTo(b, {scaleX:0}, { scaleX:w, duration:1.1, ease:'expo.out',
        immediateRender:true,
        scrollTrigger:{ trigger:b.closest('section') || b, start:'top 80%' } });
    } else if('IntersectionObserver' in window){
      var io = new IntersectionObserver(function(es){
        es.forEach(function(e){ if(!e.isIntersecting) return;
          io.disconnect();
          b.style.transition = 'transform .9s cubic-bezier(.16,1,.3,1)';
          b.style.transform = 'scaleX(' + w + ')'; });
      }, {threshold:.2});
      io.observe(b);
    } else { b.style.transform = 'scaleX(' + w + ')'; }
  });
})();

/* ------------------------------------------- lead-time curve, drawn on entry */
(function(){
  var svgs = [].slice.call(document.querySelectorAll('#leadtime svg, #trends svg'));
  svgs.forEach(function(svg){
    var path = svg.querySelector('path.ser, path[stroke-width="2.2"]');
    var dots = [].slice.call(svg.querySelectorAll('circle.dot, circle[r="3.5"]'));
    if(!path) return;
    var L = 0;
    try { L = path.getTotalLength(); } catch(e){ return; }
    if(!L) return;
    if(RM || !hasGSAP){
      if(!hasGSAP && !RM && 'IntersectionObserver' in window){
        path.style.strokeDasharray = L + ' ' + L;
        path.style.strokeDashoffset = L;
        var io = new IntersectionObserver(function(es){
          es.forEach(function(e){ if(!e.isIntersecting) return;
            io.disconnect();
            path.style.transition = 'stroke-dashoffset 1.3s cubic-bezier(.16,1,.3,1)';
            path.style.strokeDashoffset = 0; });
        }, {threshold:.2});
        io.observe(svg);
      }
      return;
    }
    G.fromTo(path, {strokeDasharray:L + ' ' + L, strokeDashoffset:L},
      { strokeDashoffset:0, duration:1.5, ease:'power2.inOut', immediateRender:true,
        scrollTrigger:{ trigger:svg, start:'top 82%' },
        onComplete:function(){ path.style.strokeDasharray=''; path.style.strokeDashoffset=''; } });
    if(dots.length){
      G.fromTo(dots, {opacity:0, scale:0.2, transformOrigin:'50% 50%'},
        { opacity:1, scale:1, duration:0.5, ease:'back.out(2)', stagger:0.1, delay:0.35,
          immediateRender:true, scrollTrigger:{ trigger:svg, start:'top 82%' } });
    }
  });
})();

/* APW tooltips, reusing the dashboard's contract shape. */
if(D && D.apw){
  var byApw = {}; D.apw.forEach(function(p){ byApw[p.apw] = p; });
  document.querySelectorAll('.hit[data-apw]').forEach(function(h){
    bind(h, function(){
      var p = byApw[h.dataset.apw]; if(!p) return;
      var r = h.getBoundingClientRect();
      showTip('<div class="h">T+'+p.apw+' · '+p.day_of_week+' '+p.travel_date+'</div>' +
        rows([['geometric mean', inr(p.geomean)], ['observed min', inr(p.min)],
              ['observed max', inr(p.max)], ['spread', p.spread_pct+'%'],
              ['observations', p.n], ['set', p.in_ps_26056_set ? 'PS 26056' : 'APIx research']]),
        r.left + r.width/2, r.top);
    });
  });
}

/* --------------------------------------------------------- route heatmap */
(function(){
  var cells = [].slice.call(document.querySelectorAll('.hm-cell'));
  if(!cells.length) return;
  var detail = document.querySelector('.hm-detail');
  var body = detail && detail.querySelector('.hm-body');
  if(!RM){
    if(hasGSAP){
      G.to(cells, { opacity:1, duration:0.5, ease:'power2.out', stagger:0.045,
        scrollTrigger:{ trigger:'#heatmap', start:'top 80%' } });
    } else if('IntersectionObserver' in window){
      var io = new IntersectionObserver(function(es){
        es.forEach(function(e){ if(!e.isIntersecting) return;
          io.disconnect();
          cells.forEach(function(c,i){
            c.style.transition = 'opacity .5s ease ' + (i*0.045) + 's';
            c.style.opacity = '1'; });
        });
      }, {threshold:.2});
      io.observe(document.getElementById('heatmap'));
    } else { cells.forEach(function(c){ c.style.opacity='1'; }); }
  }
  function metaOf(c){
    return { pair:c.dataset.pair, n:+c.dataset.n || 0, weight:c.dataset.weight,
             src:c.dataset.src, carrier:c.dataset.carrier || '—' };
  }
  cells.forEach(function(c){
    bind(c, function(){
      var m = metaOf(c), r = c.getBoundingClientRect();
      showTip('<div class="h">'+m.pair+'</div>' +
        rows([['observations held', m.n], ['basket weight', m.weight],
              ['weight source', m.src],
              ['status', m.n ? 'real observations' : 'no data — never collected']]),
        r.left + r.width/2, r.top);
    });
    function open(){
      if(!detail || !body) return;
      var m = metaOf(c);
      detail.dataset.has = '1';
      body.innerHTML = '<b>' + m.pair + '</b> — ' +
        (m.n ? m.n + ' real observations, carrier ' + m.carrier
             : 'no observations. This sector has never been collected: the live gate refuses every source and the manual protocol covered one route.') +
        rows([['basket weight', m.weight], ['weight source', m.src],
              ['observations', m.n], ['index contribution', m.n ? 'none — no matched pair' : 'none']]);
      cells.forEach(function(o){ o.setAttribute('aria-pressed', o===c ? 'true':'false'); });
      if(hasGSAP) G.fromTo(body, {opacity:0, y:6}, {opacity:1, y:0, duration:0.4, ease:'expo.out'});
    }
    c.addEventListener('click', open);
    c.addEventListener('keydown', function(ev){
      if(ev.key === 'Enter' || ev.key === ' '){ ev.preventDefault(); open(); }
    });
  });
})();

/* --------------------------------------------------- table row staggering */
(function(){
  var tables = [].slice.call(document.querySelectorAll('table.pf'));
  tables.forEach(function(t){
    var trs = [].slice.call(t.querySelectorAll('tbody tr')).slice(0, 14);
    if(!trs.length) return;
    trs.forEach(function(tr){ tr.classList.add('rvr'); });
    if(RM){ trs.forEach(function(tr){ tr.style.opacity='1'; }); return; }
    if(hasGSAP){
      G.to(trs, { opacity:1, duration:0.4, ease:'power1.out', stagger:0.035,
        scrollTrigger:{ trigger:t, start:'top 88%' } });
    } else if('IntersectionObserver' in window){
      var io = new IntersectionObserver(function(es){
        es.forEach(function(e){ if(!e.isIntersecting) return;
          io.disconnect();
          trs.forEach(function(tr,i){
            tr.style.transition='opacity .4s ease '+(i*0.035)+'s'; tr.style.opacity='1'; });
        });
      }, {threshold:.1});
      io.observe(t);
    } else { trs.forEach(function(tr){ tr.style.opacity='1'; }); }
  });
})();

/* ------------------------------------------------------ provenance lineage */
(function(){
  var picker = document.querySelector('.picker[data-for="lineage"]');
  var lin = document.querySelector('.lin');
  if(!picker || !lin || !D || !D.lineage) return;
  var steps = [].slice.call(lin.querySelectorAll('.step'));
  function paint(rec){
    steps.forEach(function(s){
      var k = s.dataset.k;
      var v = s.querySelector('.v');
      if(v && rec[k] != null) v.innerHTML = rec[k];
      s.dataset.on = '0';
    });
    if(RM || !hasGSAP){
      steps.forEach(function(s){ s.dataset.on = '1'; });
      return;
    }
    /* Lineage reveals in pipeline order, so the chain reads as a traversal
       rather than a table that happened to appear. */
    steps.forEach(function(s, i){
      setTimeout(function(){ s.dataset.on = '1'; }, 90 + i*110);
    });
  }
  picker.querySelectorAll('button[data-i]').forEach(function(b){
    b.addEventListener('click', function(){
      picker.querySelectorAll('button').forEach(function(o){
        o.setAttribute('aria-pressed', o===b ? 'true':'false'); });
      var rec = D.lineage[+b.dataset.i];
      if(rec) paint(rec);
    });
  });
  var first = picker.querySelector('button[data-i]');
  if(first){
    first.setAttribute('aria-pressed','true');
    if(RM || !hasGSAP){ paint(D.lineage[0]); }
    else {
      keep(ST.create({ trigger:lin, start:'top 84%', once:true,
        onEnter:function(){ paint(D.lineage[0]); } }));
      steps.forEach(function(s){ s.dataset.on = '0'; });
    }
  }
})();

/* ----------------------------------------------------------- source cards */
(function(){
  var cards = [].slice.call(document.querySelectorAll('.scard'));
  if(!cards.length) return;
  /* The status indicators animate only while the section is on screen: thirty
     breathing dots on a page nobody is looking at is wasted battery. */
  function setAnim(on){
    cards.forEach(function(c){ c.dataset.anim = on && !RM ? '1' : '0'; });
  }
  setAnim(false);
  if(hasGSAP){
    G.from(cards, { opacity:0, y:12, duration:0.55, ease:'expo.out', stagger:0.03,
      scrollTrigger:{ trigger:'#sources', start:'top 82%' } });
    keep(ST.create({ trigger:'#sources', start:'top bottom', end:'bottom top',
      onToggle:function(self){ setAnim(self.isActive); } }));
  } else if('IntersectionObserver' in window){
    var io = new IntersectionObserver(function(es){
      es.forEach(function(e){ setAnim(e.isIntersecting); });
    }, {threshold:0.01});
    io.observe(document.getElementById('sources'));
  } else { setAnim(true); }
})();

/* ScrollTrigger measures at load; late fonts and the sticky nav change the
   geometry underneath it. */
if(hasGSAP){
  addEventListener('load', function(){ ST.refresh(); });
  if(document.fonts && document.fonts.ready){
    document.fonts.ready.then(function(){ ST.refresh(); });
  }
}
}
if(document.readyState === 'loading'){
  document.addEventListener('DOMContentLoaded', boot);
} else { boot(); }
})();
"""
