"""The APIx design system — tokens, type scale and the whole stylesheet.

Separated from the page builder because a design system that lives inside the
markup that uses it stops being a system. Everything here is a token or a rule
about tokens; nothing here knows a single statistical figure.

**Deliberately dependency-free.** No webfont, no CDN, no framework. The page is
a committed artifact that must render byte-identically offline — from a USB
stick, on a venue network that has failed, inside a CSP that blocks everything.
That constraint is also what keeps the file honest: there is no build step in
which a number could be injected from somewhere other than ``panel.json``.

The palette is dark-first because the page is an instrument, and instruments
are read in the dark. A light scheme is provided for print and for anyone whose
system asks for it.
"""

from __future__ import annotations

#: Motion. Three durations and two curves, used everywhere; nothing improvises.
MOTION = {
    "fast": "140ms",
    "base": "260ms",
    "slow": "620ms",
    "ease": "cubic-bezier(.22,.61,.36,1)",
    "spring": "cubic-bezier(.34,1.36,.64,1)",
}

#: Semantic colours for the four execution-boundary states. EXERCISED is
#: deliberately NOT the success colour: the whole point of the vocabulary is
#: that "the code ran" is a weaker claim than "the property is validated".
STATE_COLOURS = {
    "EXERCISED": "ex",
    "DEGENERATE": "dg",
    "PENDING": "pd",
    "BLOCKED": "bl",
}

CSS = """
/* ============================================================ TOKENS ==== */
:root{
  color-scheme: dark;

  /* Ground. Near-black with a blue cast: black is a colour, not an absence. */
  --bg:#07090C; --bg-2:#0A0E13;
  --surface:#0E141B; --surface-2:#141C25; --sunk:#0A1016;
  --line:#1B242E; --line-2:#2A3742; --line-3:#3D4C5A;

  /* ink-3 sits on --surface more often than on --bg, and carries 11-12.5px
     metadata. #6C7E8E measured 4.42:1 there; this clears AA on all three
     grounds (surface 4.85, bg 5.23, sunk 5.01). */
  --ink:#EEF3F8; --ink-2:#A8B8C6; --ink-3:#728595; --ink-4:#47576544;

  /* APIx signature. One accent, used sparingly enough that it still means
     something when it appears. */
  --accent:#F0A93C; --accent-2:#FFC978; --accent-soft:#2A2113;

  /* Evidence-state palette. Each has a soft ground for fills. */
  --ex:#7FB2FF;  --ex-soft:#121B2B;      /* exercised  - ran, not validated  */
  --dg:#F0A93C;  --dg-soft:#241B0E;      /* degenerate - ran, established none*/
  --pd:#7C8B99;  --pd-soft:#131A21;      /* pending    - evidence absent     */
  --bl:#F0887C;  --bl-soft:#2A1614;      /* blocked    - refused by design   */
  --real:#5FD3A0; --real-soft:#0D2219;   /* real market data                 */

  --shadow-1:0 1px 2px rgba(0,0,0,.55);
  --shadow-2:0 2px 6px rgba(0,0,0,.4), 0 12px 32px -18px rgba(0,0,0,.9);
  --shadow-3:0 4px 12px rgba(0,0,0,.45), 0 28px 64px -28px rgba(0,0,0,1);
  --glow:0 0 0 1px var(--line-2), 0 0 24px -6px rgba(240,169,60,.22);

  /* System stacks. Chosen, not defaulted: SF Pro / Segoe UI Variable are the
     best display faces already on a jury's machine, and neither needs a
     network round trip to arrive. */
  --sans:ui-sans-serif,-apple-system,"Segoe UI Variable Text","Segoe UI",Inter,
         Roboto,system-ui,sans-serif;
  --disp:ui-sans-serif,-apple-system,"Segoe UI Variable Display","Segoe UI",
         Inter,system-ui,sans-serif;
  --mono:ui-monospace,"SF Mono","Cascadia Code","Segoe UI Mono",Menlo,Consolas,
         "Liberation Mono",monospace;

  /* Type scale, 1.25 minor third off 15px, clamped for fluid display sizes. */
  --t-xs:11px; --t-sm:12.5px; --t-md:14px; --t-lg:16px;
  --t-xl:clamp(20px,2.2vw,26px);
  --t-2xl:clamp(28px,3.4vw,42px);
  --t-3xl:clamp(38px,6vw,78px);
  --t-4xl:clamp(44px,6.6vw,96px);

  /* Space scale, 4px base. */
  --s1:4px; --s2:8px; --s3:12px; --s4:16px; --s5:24px;
  --s6:32px; --s7:48px; --s8:72px; --s9:112px; --s10:160px;

  --r:2px; --r-2:4px;          /* radii stay near-zero: this is an instrument */
  --maxw:1240px; --readw:66ch;

  --fast:140ms; --base:260ms; --slow:620ms;
  --ease:cubic-bezier(.22,.61,.36,1);
  --spring:cubic-bezier(.34,1.36,.64,1);
}

@media (prefers-color-scheme: light){
  :root:not([data-theme="dark"]){
    color-scheme: light;
    --bg:#F4F6F8; --bg-2:#EDF1F4;
    --surface:#FFFFFF; --surface-2:#F7F9FB; --sunk:#E7ECF1;
    --line:#DDE4EA; --line-2:#C3CED8; --line-3:#A3B1BE;
    /* ink-3 carries 11-12.5px metadata, so it is held to AA for small text:
       #6B7B8A measured 4.02:1 on this ground and was darkened to clear 4.5. */
    --ink:#0B1117; --ink-2:#41505D; --ink-3:#5F6E7A; --ink-4:#9AA9B644;
    --accent:#9C6410; --accent-2:#7A4E08; --accent-soft:#FBF0DC;
    --ex:#2C5AA8; --ex-soft:#E6EDF9;
    --dg:#9C6410; --dg-soft:#FBF0DC;
    --pd:#5F6E7C; --pd-soft:#EBEFF3;
    --bl:#A6342A; --bl-soft:#FAE6E3;
    --real:#14684A; --real-soft:#E2F2EB;
    --shadow-1:0 1px 2px rgba(13,19,26,.06);
    --shadow-2:0 1px 3px rgba(13,19,26,.07), 0 10px 24px -16px rgba(13,19,26,.3);
    --shadow-3:0 2px 6px rgba(13,19,26,.08), 0 24px 56px -28px rgba(13,19,26,.4);
    --glow:0 0 0 1px var(--line-2);
  }
}

/* ============================================================== BASE ==== */
*,*::before,*::after{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{
  margin:0; background:var(--bg); color:var(--ink);
  font-family:var(--sans); font-size:var(--t-md); line-height:1.6;
  -webkit-font-smoothing:antialiased; text-rendering:optimizeLegibility;
  overflow-x:hidden;
}
h1,h2,h3,h4{font-family:var(--disp); margin:0; text-wrap:balance; letter-spacing:-.022em}
h1{font-size:var(--t-4xl); font-weight:680; line-height:.94; letter-spacing:-.04em;
   max-width:15ch; text-wrap:balance}
h2{font-size:var(--t-2xl); font-weight:640; line-height:1.06}
h3{font-size:var(--t-xl);  font-weight:620; line-height:1.15}
p{margin:0}
a{color:inherit; text-underline-offset:3px; text-decoration-color:var(--line-3)}
a:hover{text-decoration-color:var(--accent)}
:focus-visible{outline:2px solid var(--accent); outline-offset:3px; border-radius:var(--r)}
.mono{font-family:var(--mono); font-variant-numeric:tabular-nums slashed-zero}
.tnum{font-variant-numeric:tabular-nums}
table{border-collapse:collapse; width:100%; font-size:var(--t-sm)}
svg{display:block}
::selection{background:var(--accent); color:#07090C}

.wrap{max-width:var(--maxw); margin-inline:auto; padding-inline:clamp(16px,4vw,40px)}
.read{max-width:var(--readw)}
.sr{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;
    clip:rect(0 0 0 0);white-space:nowrap;border:0}
.skip{position:fixed;top:-60px;left:12px;z-index:200;background:var(--accent);
      color:#07090C;padding:10px 16px;font-weight:640;transition:top var(--fast)}
.skip:focus{top:12px}

/* ============================================================== NAV ===== */
.nav{
  position:fixed; inset:0 0 auto 0; z-index:90; height:56px;
  display:flex; align-items:center; gap:var(--s5);
  padding-inline:clamp(16px,4vw,40px);
  background:color-mix(in srgb, var(--bg) 78%, transparent);
  backdrop-filter:saturate(1.6) blur(14px);
  border-bottom:1px solid transparent;
  transition:border-color var(--base) var(--ease), background var(--base) var(--ease);
}
.nav[data-stuck="1"]{border-bottom-color:var(--line);
  background:color-mix(in srgb, var(--bg) 92%, transparent)}
.nav .brand{font-family:var(--disp);font-weight:700;letter-spacing:-.03em;font-size:17px;
            display:flex;align-items:center;gap:9px;flex-shrink:0}
.nav .brand i{width:9px;height:9px;background:var(--accent);display:block;
              box-shadow:0 0 14px var(--accent); font-style:normal}
.nav ol{display:flex;gap:2px;list-style:none;margin:0;padding:0;overflow-x:auto;
        scrollbar-width:none}
.nav ol::-webkit-scrollbar{display:none}
.nav a{font-family:var(--mono);font-size:var(--t-xs);letter-spacing:.06em;
       text-transform:uppercase;color:var(--ink-3);padding:7px 10px;
       text-decoration:none;white-space:nowrap;position:relative;
       transition:color var(--fast) var(--ease)}
.nav a:hover{color:var(--ink)}
.nav a[aria-current="true"]{color:var(--accent)}
.nav a[aria-current="true"]::after{
  content:"";position:absolute;left:10px;right:10px;bottom:2px;height:1px;
  background:var(--accent)}
.nav .spacer{flex:1}
.nav .idx{font-family:var(--mono);font-size:var(--t-xs);letter-spacing:.08em;
          color:var(--bl);border:1px solid var(--bl);background:var(--bl-soft);
          padding:4px 9px;white-space:nowrap;flex-shrink:0}
.prog{position:fixed;top:56px;left:0;height:2px;background:var(--accent);z-index:91;
      width:0;box-shadow:0 0 12px var(--accent);transition:width 90ms linear}

/* ============================================================= HERO ===== */
.hero{position:relative;min-height:100svh;display:flex;flex-direction:column;
      justify-content:center;padding:84px 0 var(--s6);overflow:hidden}
#field{position:absolute;inset:0;width:100%;height:100%;z-index:0;opacity:.62;
       -webkit-mask-image:radial-gradient(115% 90% at 78% 52%,#000 42%,transparent 78%);
       mask-image:radial-gradient(115% 90% at 78% 52%,#000 42%,transparent 78%)}
@media (min-width:1000px){
  /* Right half only: the headline gets clean ground, the lattice gets room. */
  #field{left:38%;width:62%;opacity:.85;
         -webkit-mask-image:linear-gradient(90deg,transparent,#000 26%,#000 88%,transparent);
         mask-image:linear-gradient(90deg,transparent,#000 26%,#000 88%,transparent)}
}
.hero>.wrap{position:relative;z-index:1}
.hero .eyebrow{font-family:var(--mono);font-size:var(--t-xs);letter-spacing:.22em;
               text-transform:uppercase;color:var(--accent);margin-bottom:var(--s4)}
.hero h1{margin-bottom:var(--s4)}
.hero h1 em{font-style:normal;color:var(--accent);
            -webkit-text-stroke:0}
.hero .lede{font-size:var(--t-xl);color:var(--ink-2);max-width:30ch;line-height:1.35;
            font-weight:380;letter-spacing:-.015em}
.hero .route{display:flex;align-items:center;gap:var(--s3);margin-top:var(--s6);
             font-family:var(--mono);font-size:var(--t-sm);color:var(--ink-2);
             flex-wrap:wrap}
.hero .route b{color:var(--ink);font-weight:620;font-size:var(--t-lg)}
.hero .route .arr{color:var(--accent)}
.scroll-cue{position:absolute;bottom:26px;left:50%;translate:-50% 0;z-index:1;
            font-family:var(--mono);font-size:var(--t-xs);letter-spacing:.18em;
            text-transform:uppercase;color:var(--ink-3);display:flex;
            flex-direction:column;align-items:center;gap:8px}
.scroll-cue span{width:1px;height:26px;background:linear-gradient(var(--ink-3),transparent);
                 animation:cue 2.4s var(--ease) infinite}
@keyframes cue{0%{opacity:0;transform:scaleY(.3);transform-origin:top}
               40%{opacity:1}100%{opacity:0;transform:scaleY(1);transform-origin:top}}

/* ============================================================ METRICS === */
.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(168px,1fr));
         gap:1px;background:var(--line);border:1px solid var(--line);
         margin-top:var(--s6)}
.metric{background:var(--surface);padding:var(--s4) var(--s4) var(--s5);
        display:flex;flex-direction:column;gap:5px;position:relative;
        transition:background var(--base) var(--ease)}
.metric:hover{background:var(--surface-2)}
.metric .k{font-family:var(--mono);font-size:var(--t-xs);letter-spacing:.12em;
           text-transform:uppercase;color:var(--ink-3)}
.metric .v{font-family:var(--disp);font-size:30px;font-weight:660;line-height:1;
           letter-spacing:-.03em;font-variant-numeric:tabular-nums}
.metric .s{font-size:var(--t-sm);color:var(--ink-3);line-height:1.4}
.metric.is-real .v{color:var(--real)} .metric.is-real .k{color:var(--real)}
.metric.is-hold .v{color:var(--bl)}   .metric.is-hold .k{color:var(--bl)}
.metric.is-warn .v{color:var(--accent)} .metric.is-warn .k{color:var(--accent)}

/* =========================================================== SECTIONS === */
section{position:relative;padding-block:var(--s9)}
section+section{border-top:1px solid var(--line)}
.shead{display:flex;align-items:baseline;gap:var(--s4);margin-bottom:var(--s5)}
.shead .n{font-family:var(--mono);font-size:var(--t-xs);font-weight:600;
          color:var(--accent);letter-spacing:.14em;flex-shrink:0;padding-top:6px}
.lede{font-size:var(--t-lg);color:var(--ink-2);max-width:var(--readw);line-height:1.62}
.lede+.lede{margin-top:var(--s3)}
.sub{font-family:var(--mono);font-size:var(--t-xs);letter-spacing:.14em;
     text-transform:uppercase;color:var(--ink-3);margin-bottom:var(--s3)}

/* Reveal-on-scroll, as progressive enhancement.
   Content is visible by DEFAULT. The hidden initial state applies only under
   `html.js`, a class a tiny inline script sets during head parse. If script is
   disabled, blocked by a Content-Security-Policy, or throws before that line,
   the class never lands and every figure renders.
   `<noscript>` alone does NOT cover this: it applies when scripting is
   disabled, not when a script is present but prevented from running. */
.rv{opacity:1;transform:none}
.js .rv{opacity:0;transform:translateY(14px);
        transition:opacity var(--slow) var(--ease), transform var(--slow) var(--ease)}
.js .rv.in{opacity:1;transform:none}
.rv[data-d="1"]{transition-delay:70ms} .rv[data-d="2"]{transition-delay:140ms}
.rv[data-d="3"]{transition-delay:210ms} .rv[data-d="4"]{transition-delay:280ms}

/* ============================================================= BANNER === */
.banner{border-left:3px solid var(--accent);background:var(--accent-soft);
        padding:var(--s4) var(--s5);margin-block:var(--s5);
        display:flex;flex-direction:column;gap:var(--s2)}
.banner .t{font-family:var(--mono);font-size:var(--t-xs);letter-spacing:.16em;
           text-transform:uppercase;color:var(--accent);font-weight:640}
.banner p{font-size:var(--t-sm);color:var(--ink-2);max-width:var(--readw)}
.banner.stop{border-left-color:var(--bl);background:var(--bl-soft)}
.banner.stop .t{color:var(--bl)}
.banner.real{border-left-color:var(--real);background:var(--real-soft)}
.banner.real .t{color:var(--real)}

.note{font-size:var(--t-sm);color:var(--ink-2);position:relative;padding-left:18px;
      margin-top:var(--s3);max-width:var(--readw)}
.note::before{content:"\\2192";position:absolute;left:0;top:0;color:var(--accent);
              font-family:var(--mono)}

/* ============================================================== CARD ==== */
.grid{display:grid;gap:1px;background:var(--line);border:1px solid var(--line)}
.g2{grid-template-columns:repeat(auto-fit,minmax(300px,1fr))}
.g3{grid-template-columns:repeat(auto-fit,minmax(196px,1fr))}
.card{background:var(--surface);padding:var(--s5);display:flex;flex-direction:column;
      gap:var(--s2)}
.card h3{font-size:var(--t-lg);font-weight:640}
.card .k{font-family:var(--mono);font-size:var(--t-xs);letter-spacing:.12em;
         text-transform:uppercase;color:var(--ink-3)}
.card p{font-size:var(--t-sm);color:var(--ink-2)}

.pill{font-family:var(--mono);font-size:var(--t-xs);letter-spacing:.1em;
      padding:3px 9px;border:1px solid var(--line-2);color:var(--ink-2);
      white-space:nowrap;display:inline-block}
.pill.ex{border-color:var(--ex);background:var(--ex-soft);color:var(--ex);font-weight:640}
.pill.dg{border-color:var(--dg);background:var(--dg-soft);color:var(--dg);font-weight:640}
.pill.pd{border-color:var(--line-2);background:var(--pd-soft);color:var(--pd)}
.pill.bl{border-color:var(--bl);background:var(--bl-soft);color:var(--bl);font-weight:640}
.pill.real{border-color:var(--real);background:var(--real-soft);color:var(--real);font-weight:640}

/* ============================================================= CHART ==== */
.chart{background:var(--surface);border:1px solid var(--line);padding:var(--s5);
       position:relative}
.chart figcaption{display:flex;flex-wrap:wrap;gap:var(--s2) var(--s4);
                  align-items:baseline;margin-bottom:var(--s4)}
.chart figcaption h3{font-size:var(--t-lg)}
.chart .meta{font-family:var(--mono);font-size:var(--t-xs);color:var(--ink-3);
             letter-spacing:.04em}
.chart .src{font-family:var(--mono);font-size:var(--t-xs);color:var(--ink-3);
            margin-top:var(--s4);padding-top:var(--s3);border-top:1px solid var(--line)}
.cwrap{max-width:100%}
@media (max-width:820px){
  .cwrap{overflow-x:auto;-webkit-overflow-scrolling:touch;
         margin-inline:calc(var(--s3) * -1);padding-inline:var(--s3)}
  .cwrap>svg{min-width:660px}
}
.axis{stroke:var(--line-2);stroke-width:1}
.grid-l{stroke:var(--line);stroke-width:1;stroke-dasharray:2 5}
.tick{fill:var(--ink-3);font-family:var(--mono);font-size:10.5px}
.tick.b{fill:var(--ink-2)}
.ser{fill:none;stroke:var(--accent);stroke-width:2;stroke-linejoin:round;
     stroke-linecap:round}
.dot{fill:var(--surface);stroke:var(--accent);stroke-width:2;
     transition:r var(--fast) var(--spring)}
.hit{fill:transparent;cursor:pointer}
.hit:hover+.dot,.hit:focus-visible+.dot{r:7.5}
.bar{fill:var(--ex);transition:fill var(--fast) var(--ease),opacity var(--fast)}
.bar:hover{fill:var(--accent)}

/* Tooltip. One element, moved and refilled; never N tooltips in the DOM. */
#tip{position:fixed;z-index:120;pointer-events:none;opacity:0;
     background:var(--surface-2);border:1px solid var(--line-2);
     box-shadow:var(--shadow-3);padding:10px 13px;min-width:150px;max-width:280px;
     font-size:var(--t-sm);transition:opacity var(--fast) var(--ease);
     transform:translate(-50%,calc(-100% - 14px))}
#tip.on{opacity:1}
#tip .h{font-family:var(--mono);font-size:var(--t-xs);letter-spacing:.1em;
        text-transform:uppercase;color:var(--accent);margin-bottom:5px}
#tip dl{margin:0;display:grid;grid-template-columns:auto 1fr;gap:2px 12px}
#tip dt{color:var(--ink-3);font-size:var(--t-xs)}
#tip dd{margin:0;font-family:var(--mono);font-size:var(--t-xs);text-align:right;
        color:var(--ink)}

/* ========================================================== BOUNDARY ==== */
.bnd{display:flex;flex-direction:column;gap:1px;background:var(--line);
     border:1px solid var(--line)}
.bs{background:var(--surface);display:grid;
    grid-template-columns:28px minmax(0,1fr) auto;gap:var(--s2) var(--s4);
    align-items:start;padding:var(--s4) var(--s5);text-align:left;width:100%;
    border:0;border-left:2px solid transparent;font:inherit;color:inherit;
    cursor:pointer;transition:background var(--base) var(--ease),
    border-color var(--base) var(--ease)}
.bs:hover{background:var(--surface-2)}
.bs[aria-expanded="true"]{background:var(--surface-2);border-left-color:var(--accent)}
.bs .rail{grid-row:1/span 3;position:relative;height:100%;min-height:26px}
.bs .rail::before{content:"";position:absolute;left:50%;top:14px;bottom:-24px;
                  width:1px;background:var(--line-2);translate:-50% 0}
.bs:last-of-type .rail::before{display:none}
.bs .rail i{position:absolute;left:50%;top:6px;translate:-50% 0;width:9px;height:9px;
            border:1.5px solid var(--pd);background:var(--bg);border-radius:50%;
            font-style:normal;display:block}
.bs[data-state="EXERCISED"] .rail i{border-color:var(--ex);background:var(--ex);
                                    box-shadow:0 0 10px -1px var(--ex)}
.bs[data-state="DEGENERATE"] .rail i{border-color:var(--dg);background:var(--dg)}
.bs[data-state="BLOCKED"] .rail i{border-color:var(--bl);background:var(--bl)}
.bs .nm{font-weight:620;font-size:var(--t-md)}
.bs .sp{grid-column:2;font-family:var(--mono);font-size:var(--t-xs);
        color:var(--ink-3);word-break:break-word}
.bs .stt{grid-column:3;grid-row:1}
.bd{background:var(--sunk);padding:0 var(--s5) 0 calc(var(--s5) + 28px + var(--s4));
    display:grid;grid-template-rows:0fr;
    transition:grid-template-rows var(--base) var(--ease)}
.bd[data-open="1"]{grid-template-rows:1fr;padding-block:var(--s4)}
.bd>div{overflow:hidden;min-height:0}
.bd ul{margin:0 0 var(--s3);padding-left:17px;font-size:var(--t-sm);color:var(--ink-2)}
.bd li{margin-bottom:3px}
.bd .n{font-size:var(--t-sm);color:var(--ink-3);max-width:var(--readw)}
.stop-rule{display:flex;align-items:center;gap:var(--s3);padding:var(--s3) var(--s5);
           background:var(--bl-soft);border-block:1px solid var(--bl);
           font-family:var(--mono);font-size:var(--t-xs);letter-spacing:.12em;
           text-transform:uppercase;color:var(--bl);font-weight:640}
.stop-rule::before,.stop-rule::after{content:"";flex:1;height:1px;background:var(--bl);opacity:.4}

/* =========================================================== EXPLORER === */
.filters{display:flex;flex-wrap:wrap;gap:var(--s2);margin-bottom:var(--s4);
         align-items:center;max-width:100%;min-width:0}
.fgrp{display:flex;flex-wrap:wrap;gap:1px;background:var(--line);
      border:1px solid var(--line);max-width:100%}
.fgrp button{background:var(--surface);border:0;color:var(--ink-3);font:inherit;
             font-family:var(--mono);font-size:var(--t-xs);letter-spacing:.08em;
             padding:6px 11px;cursor:pointer;
             transition:background var(--fast) var(--ease),color var(--fast) var(--ease)}
.fgrp button:hover{color:var(--ink);background:var(--surface-2)}
.fgrp button[aria-pressed="true"]{background:var(--accent);color:#07090C;font-weight:640}
.flabel{font-family:var(--mono);font-size:var(--t-xs);letter-spacing:.12em;
        text-transform:uppercase;color:var(--ink-3);margin-right:2px}
.count{font-family:var(--mono);font-size:var(--t-xs);color:var(--ink-3);margin-left:auto}
.count b{color:var(--accent);font-weight:640}

.tscroll{overflow-x:auto;max-width:100%;border:1px solid var(--line);
         background:var(--surface);-webkit-overflow-scrolling:touch}
thead th{position:sticky;top:0;background:var(--surface-2);z-index:1;
         font-family:var(--mono);font-size:var(--t-xs);letter-spacing:.1em;
         text-transform:uppercase;color:var(--ink-3);font-weight:500;
         text-align:left;padding:10px 12px;border-bottom:1px solid var(--line-2);
         white-space:nowrap}
tbody td{padding:9px 12px;border-bottom:1px solid var(--line);white-space:nowrap}
tbody tr{transition:background var(--fast) var(--ease)}
tbody tr:hover{background:var(--surface-2)}
tbody tr[hidden]{display:none}
td.r,th.r{text-align:right}
td.m{font-family:var(--mono);font-size:var(--t-xs);font-variant-numeric:tabular-nums}
.tag{font-family:var(--mono);font-size:10px;letter-spacing:.08em;padding:2px 6px;
     border:1px solid var(--line-2);color:var(--ink-3)}
.tag.p{border-color:var(--real);color:var(--real);background:var(--real-soft)}
.tag.s{border-color:var(--dg);color:var(--dg);background:var(--dg-soft)}

/* =========================================================== PIPELINE === */
.flow{display:flex;flex-wrap:wrap;gap:7px;align-items:center;
      font-family:var(--mono);font-size:var(--t-xs)}
.flow .step{padding:7px 12px;border:1px solid var(--line-2);background:var(--surface);
            color:var(--ink-2);position:relative;overflow:hidden}
.flow .step.now{border-color:var(--ex);background:var(--ex-soft);color:var(--ex);font-weight:640}
.flow .step.next{border-color:var(--dg);background:var(--dg-soft);color:var(--dg);font-weight:640}
.flow .step.stop{border-color:var(--bl);background:var(--bl-soft);color:var(--bl);font-weight:640}
.flow .arr{color:var(--ink-3)}
#pipe{width:100%;height:150px;display:block}

/* ============================================================== FAQ ===== */
.faq{display:flex;flex-direction:column;gap:1px;background:var(--line);
     border:1px solid var(--line)}
.qa{background:var(--surface)}
.qa summary{padding:var(--s4) var(--s5);cursor:pointer;font-weight:600;
            font-size:var(--t-md);list-style:none;display:flex;gap:var(--s3);
            align-items:baseline;transition:background var(--fast) var(--ease)}
.qa summary::-webkit-details-marker{display:none}
.qa summary::before{content:"+";font-family:var(--mono);color:var(--accent);
                    font-size:var(--t-lg);line-height:1;transition:rotate var(--base) var(--ease)}
.qa[open] summary::before{rotate:45deg}
.qa summary:hover{background:var(--surface-2)}
.qa .a{padding:0 var(--s5) var(--s5) calc(var(--s5) + 20px);font-size:var(--t-sm);
       color:var(--ink-2);max-width:var(--readw)}

/* ============================================================ FOOTER ==== */
footer{border-top:1px solid var(--line);padding-block:var(--s7);
       font-size:var(--t-sm);color:var(--ink-3)}
footer .row{display:flex;flex-wrap:wrap;gap:var(--s5);justify-content:space-between}
footer b{color:var(--ink-2);font-weight:600}

/* ========================================================= RESPONSIVE === */
@media (max-width:1000px){
  /* 3+1 leaves an empty cell that reads as a broken card; 2x2 never does. */
  .metrics{grid-template-columns:1fr 1fr}
}
@media (max-width:900px){
  :root{--s9:72px;--s8:56px}
  .nav{gap:var(--s3)}
  .nav ol{-webkit-mask-image:linear-gradient(90deg,#000 85%,transparent)}
  .bs{grid-template-columns:20px minmax(0,1fr);gap:var(--s2)}
  .bs .stt{grid-column:2;grid-row:auto;justify-self:start}
  .bd{padding-left:calc(var(--s5) + 20px + var(--s2))}
  .hero .lede{max-width:100%}
}
/* The metrics row now sits near the bottom of the hero by design, so the
   absolutely-positioned cue collides with it on any normal laptop. It is
   decoration; it yields to the evidence. */
@media (max-height:1040px),(max-width:620px){
  .scroll-cue{display:none}
}
@media (max-width:620px){
  :root{--t-4xl:clamp(40px,13vw,64px)}
  .nav ol{display:none}
  h1{max-width:none}
  .metrics{grid-template-columns:1fr 1fr}
  .metric .v{font-size:24px}
  #field{opacity:.55}
  .chart{padding:var(--s4) var(--s3)}
}

/* ===================================================== REDUCED MOTION === */
@media (prefers-reduced-motion:reduce){
  *,*::before,*::after{animation-duration:.001ms!important;animation-iteration-count:1!important;
                       transition-duration:.001ms!important;scroll-behavior:auto!important}
  .js .rv{opacity:1;transform:none}
  .scroll-cue span{animation:none}
  #field,#pipe{display:none}
}

/* =============================================================== PRINT == */
@media print{
  .nav,.prog,.scroll-cue,#field,#pipe,#tip,.filters{display:none!important}
  body{background:#fff;color:#000}
  section{padding-block:24px;break-inside:avoid}
  .rv{opacity:1;transform:none}
}
"""
