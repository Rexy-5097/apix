"""The APIx design system — an editorial light palette, type scale and stylesheet.

Separated from the page builder because a design system that lives inside the
markup that uses it stops being a system. Everything here is a token or a rule
about tokens; nothing here knows a single statistical figure.

**Light-first, and typographic rather than chromatic.** The previous dark
instrument reached for glow to signal sophistication. This one reaches for
paper, space and one restrained signal colour, because that is closer to what a
document a statistical office might actually adopt looks like. Four grounds
carry the narrative — warm paper, a deeper neutral, pale sky, and near-black
for the engine chapter — so the chapter you are in is legible from the
background before a word is read.

**Contrast is measured, not eyeballed.** Every foreground token clears WCAG AA
on the *worst* ground it is used against, not the most flattering one::

    ink       16.18 paper · 14.07 sky
    ink-2      7.17 paper ·  6.24 sky
    ink-3      5.44 paper ·  4.73 sky
    amber-ink  5.86 paper ·  5.10 sky      small text
    amber      3.45 paper ·  3.00 sky      marks and large type only
    green / red / blue      >= 5.0 on every ground

Fonts load from Google Fonts behind a full system fallback stack, so a failed
network costs the page its personality and none of its content.
"""

from __future__ import annotations

#: One display family, one technical family. No third.
FONT_HREF = (
    "https://fonts.googleapis.com/css2"
    "?family=Plus+Jakarta+Sans:wght@400;500;600;700;800"
    "&family=IBM+Plex+Mono:wght@400;500&display=swap"
)

#: Semantic classes for the four execution-boundary states. EXERCISED is
#: deliberately not the success colour: "the code ran" is a weaker claim than
#: "the property is validated", and the palette must not blur that.
STATE_COLOURS = {
    "EXERCISED": "ex",
    "DEGENERATE": "dg",
    "PENDING": "pd",
    "BLOCKED": "bl",
}

CSS = """
/* ============================================================== TOKENS === */
:root{
  color-scheme: light;

  /* Grounds. Paper, not white -- white is a screen, paper is a document. */
  --paper:#F6F4F0;
  --paper-2:#EFEBE4;
  --sky:#DCE6F0;
  --sky-2:#C9D9E9;
  --night:#101317;
  --night-2:#191E24;
  --card:#FFFFFF;

  /* Ink. A near-black with a trace of blue; #000 reads as a hole on paper. */
  --ink:#16181C;
  --ink-2:#4C525B;
  --ink-3:#5E646B;
  --line:#DFDAD2;
  --line-2:#CAC4BA;

  /* One signal colour, in two weights: a mark weight and a text-safe weight. */
  --amber:#B87413;
  --amber-ink:#8A5109;
  --amber-wash:#F3E7D4;

  /* Semantics, muted. */
  --green:#2C6B4F;  --green-wash:#E1EDE7;
  --red:#A63A2C;    --red-wash:#F6E4E1;
  --blue:#2E5C8A;   --blue-wash:#E2EAF3;

  /* Boundary states map onto the semantics, never onto decoration. */
  --ex:#2E5C8A;  --ex-wash:#E2EAF3;
  --dg:#8A5109;  --dg-wash:#F3E7D4;
  --pd:#5E646B;  --pd-wash:#EAE7E1;
  --bl:#A63A2C;  --bl-wash:#F6E4E1;

  --disp:"Plus Jakarta Sans",ui-sans-serif,-apple-system,"Segoe UI Variable Display",
         "Segoe UI",Inter,system-ui,sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,"SF Mono","Cascadia Code",Menlo,Consolas,monospace;

  /* Type scale. The hero is enormous; everything else is quiet. */
  /* Height-aware, not width-only: a 158px headline fits 1280 wide and blows
     through 720 tall. Both scales take the smaller of a width and a height
     measure, so the hero never outgrows the viewport it sits in. */
  --t-hero:clamp(48px,min(11vw,15.5vh),176px);
  --t-stmt:clamp(32px,min(6vw,9.4vh),88px);
  --t-chap:clamp(28px,3.9vw,58px);
  --t-sub:clamp(19px,1.7vw,25px);
  --t-body:clamp(15.5px,1.05vw,17.5px);
  --t-sm:14px; --t-xs:12px; --t-2xs:10.5px;

  --s1:4px; --s2:8px; --s3:14px; --s4:22px; --s5:34px;
  --s6:52px; --s7:78px; --s8:116px; --s9:168px;

  /* Rounding: generous on large surfaces, sharp on technical marks. */
  --r-xs:4px; --r-sm:10px; --r:18px; --r-lg:30px; --r-xl:52px;

  --maxw:1320px; --readw:60ch;

  --fast:200ms; --med:560ms; --slow:1100ms;
  --out:cubic-bezier(.16,1,.3,1);
  --inout:cubic-bezier(.65,.05,.36,1);
  --spring:cubic-bezier(.34,1.56,.64,1);
}

/* ================================================================ BASE === */
*,*::before,*::after{box-sizing:border-box}
/* `clip` rather than `hidden`: hidden on body alone does not reliably contain
   the viewport, and hidden on html would create a scroll container that breaks
   every position:sticky on the page. `clip` contains without doing either. */
html{-webkit-text-size-adjust:100%; overflow-x:clip}
body{
  margin:0; background:var(--paper); color:var(--ink);
  font-family:var(--disp); font-size:var(--t-body); font-weight:400;
  line-height:1.62; letter-spacing:-.008em;
  -webkit-font-smoothing:antialiased; text-rendering:optimizeLegibility;
  overflow-x:clip;
}
h1,h2,h3{margin:0; font-weight:600; letter-spacing:-.035em; line-height:1.02;
         text-wrap:balance}
h1{font-size:var(--t-hero); font-weight:700; letter-spacing:-.052em; line-height:.9}
h2{font-size:var(--t-chap)}
h3{font-size:var(--t-sub); letter-spacing:-.02em; line-height:1.24}
p{margin:0}
a{color:inherit; text-underline-offset:3px; text-decoration-color:var(--line-2)}
a:hover{text-decoration-color:var(--amber)}
:focus-visible{outline:2.5px solid var(--amber-ink); outline-offset:4px;
               border-radius:var(--r-xs)}
svg{display:block}
::selection{background:var(--amber); color:#fff}

.mono{font-family:var(--mono); font-variant-numeric:tabular-nums slashed-zero;
      letter-spacing:-.01em}
.meta{font-family:var(--mono); font-size:var(--t-xs); letter-spacing:.1em;
      text-transform:uppercase; color:var(--ink-3); font-weight:500}
.wrap{max-width:var(--maxw); margin-inline:auto; padding-inline:clamp(20px,5vw,64px)}
.read{max-width:var(--readw)}
.sr{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;
    clip:rect(0 0 0 0);white-space:nowrap;border:0}
.skip{position:fixed;top:-70px;left:16px;z-index:300;background:var(--ink);
      color:var(--paper);padding:12px 20px;border-radius:var(--r-sm);
      font-weight:600;transition:top var(--fast) var(--out)}
.skip:focus{top:16px}

/* =========================================================== MATERIALS === */
/* Three materials, each with one job, each used on a named short list of
   surfaces. Applied everywhere they would stop meaning anything. */

/* GLASS — for surfaces that float ABOVE the document and must not hide it:
   the nav, the tooltip, the index-status chip, the unlock card. */
.glass{
  background:color-mix(in srgb,var(--card) 58%,transparent);
  -webkit-backdrop-filter:blur(22px) saturate(1.8);
  backdrop-filter:blur(22px) saturate(1.8);
  border:1px solid color-mix(in srgb,#FFFFFF 66%,transparent);
  box-shadow:0 1px 0 color-mix(in srgb,#FFFFFF 78%,transparent) inset,
             0 20px 48px -26px rgba(22,24,28,.40);
}
.ch-night .glass,.glass-dark{
  background:color-mix(in srgb,#000000 34%,transparent);
  border-color:color-mix(in srgb,#FFFFFF 14%,transparent);
  box-shadow:0 1px 0 color-mix(in srgb,#FFFFFF 12%,transparent) inset,
             0 20px 48px -26px rgba(0,0,0,.7);
}
@supports not (backdrop-filter: blur(1px)){
  .glass{background:color-mix(in srgb,var(--card) 94%,transparent)}
}

/* CLAY — for things you press. Soft, inset-lit, obviously pushable. Never on
   the evidence itself: the data must not look like a toy. */
.clay{
  background:var(--paper-2);border:0;
  box-shadow:5px 6px 13px -8px rgba(22,24,28,.24),
             -4px -4px 10px -7px #FFFFFF inset,
             2px 2px 5px -3px rgba(22,24,28,.14) inset;
}

/* TACTILE — hover lifts, press compresses, release springs back. */
.tactile{transition:transform 240ms var(--spring),box-shadow var(--fast) var(--out),
         background var(--fast) var(--out),color var(--fast) var(--out)}
.tactile:hover{transform:translateY(-2px)}
.tactile:active{transform:translateY(0) scale(.965);transition-duration:90ms}

/* ============================================================== LADDER === */
/* The audit accounting as a sum you can follow, not three unrelated tiles. */
.ladder{list-style:none;margin:var(--s6) 0 0;padding:0;max-width:760px;
        counter-reset:none}
.ladder li{display:grid;grid-template-columns:42px minmax(0,auto) 1fr;
           gap:var(--s4);align-items:baseline;padding-block:var(--s3);
           border-bottom:1px solid var(--line)}
.ladder li::before{content:attr(data-op);font-family:var(--mono);font-size:26px;
                   color:var(--ink-3);text-align:center;line-height:1}
.ladder li:first-child::before{content:""}
.ladder b{font-size:clamp(38px,5vw,66px);font-weight:700;letter-spacing:-.04em;
          font-variant-numeric:tabular-nums;line-height:1}
.ladder span{font-size:var(--t-body);color:var(--ink-2);align-self:center}
.ladder li[data-total="1"]{border-bottom:0;border-top:2px solid var(--ink);
                           margin-top:var(--s2);padding-top:var(--s4)}
.ladder li[data-total="1"] b{color:var(--amber-ink)}
.ladder li[data-total="1"]::before{color:var(--ink)}

/* ======================================================== EXPLAINERS ===== */
/* Plain sentence first, mathematics on request. A judge should never need the
   equation to understand what the equation is for. */
.plain{margin-top:var(--s5);max-width:62ch}
.plain .q{font-family:var(--mono);font-size:var(--t-2xs);letter-spacing:.16em;
          text-transform:uppercase;color:var(--amber-ink);font-weight:500}
.plain .a{font-size:var(--t-sub);line-height:1.45;letter-spacing:-.016em;
          color:var(--ink);margin-top:var(--s2)}
.ch-night .plain .a{color:var(--paper)}
.ch-night .plain .q{color:#E0A046}
.tech{margin-top:var(--s4);border-top:1px solid var(--line)}
.ch-night .tech{border-top-color:#2B323A}
.tech summary{cursor:pointer;list-style:none;padding-top:var(--s3);
              font-family:var(--mono);font-size:var(--t-xs);letter-spacing:.12em;
              text-transform:uppercase;color:var(--ink-3);display:flex;gap:10px;
              align-items:center;transition:color var(--fast)}
.tech summary::-webkit-details-marker{display:none}
.tech summary::after{content:"+";font-size:15px;color:var(--amber-ink)}
.tech[open] summary::after{content:"2"}
.tech summary:hover{color:var(--ink)}
.ch-night .tech summary:hover{color:var(--paper)}
.tech .body{margin-top:var(--s3)}
.eq{font-family:var(--mono);font-size:var(--t-sm);background:var(--paper-2);
    padding:var(--s4);border-radius:var(--r-sm);margin-top:var(--s3);
    overflow-x:auto;line-height:1.9}
.ch-night .eq{background:var(--night-2)}

/* ============================================================= STEPS ===== */
/* A concept built up one line at a time instead of dropped as a formula. */
.steps{display:flex;flex-direction:column;gap:var(--s2);margin-top:var(--s5);
       max-width:520px}
.steps div{display:flex;align-items:center;gap:var(--s4);padding:var(--s3) var(--s4);
           border-radius:var(--r-sm);background:var(--card);
           font-size:var(--t-body)}
.ch-night .steps div{background:var(--night-2)}
.steps div b{font-family:var(--mono);font-size:var(--t-xs);color:var(--amber-ink);
             letter-spacing:.1em}
.ch-night .steps div b{color:#E0A046}
.steps i{display:block;height:18px;width:1px;background:var(--line-2);
         margin-left:calc(var(--s4) + 6px)}

/* ============================================================= CHAPTER === */
/* Each chapter owns a ground. The chapter you are in is legible from the
   background alone, before a single word is read. */
.ch{position:relative; padding-block:var(--s9)}
/* A chapter made of full-height scenes already owns its vertical rhythm; the
   chapter padding on top of it pushed 300px of empty paper above the first
   word on a 720px screen. */
.ch-scene{padding-block:var(--s5)}
.ch-paper{background:var(--paper)}
.ch-neutral{background:var(--paper-2)}
.ch-sky{background:var(--sky)}
.ch-night{background:var(--night); color:var(--paper)}
.ch-night h1,.ch-night h2,.ch-night h3{color:var(--paper)}
.ch-night .meta{color:#9AA3AE}
.ch-night .lede,.ch-night .body{color:#C3CAD3}
.ch-night .rule{background:#2B323A}

.eyebrow{font-family:var(--mono);font-size:var(--t-xs);letter-spacing:.18em;
         text-transform:uppercase;color:var(--amber-ink);font-weight:500;
         margin-bottom:var(--s4)}
.ch-night .eyebrow{color:#E0A046}
.lede{font-size:var(--t-sub);line-height:1.48;color:var(--ink-2);
      max-width:34ch;letter-spacing:-.018em;font-weight:400}
.body{font-size:var(--t-body);color:var(--ink-2);max-width:var(--readw)}
.body+.body{margin-top:var(--s3)}
.rule{height:1px;background:var(--line);border:0;margin:0}

/* =============================================================== NAV ===== */
/* The nav is fixed, so anything scrolled flush to the top of the viewport
   lands underneath it. scroll-padding-top moves the resting place of every
   scroll target -- anchor links, the skip link, scrollIntoView, keyboard
   focus -- clear of the bar, and scroll-margin-top covers the elements a
   browser scrolls to directly. One token so the two can never drift apart. */
:root{--nav-h:64px;--nav-clear:calc(var(--nav-h) + 22px)}
html{scroll-padding-top:var(--nav-clear)}
[id]{scroll-margin-top:var(--nav-clear)}
.nav{position:fixed;inset:0 0 auto 0;z-index:200;height:var(--nav-h);display:flex;
     align-items:center;gap:var(--s5);padding-inline:clamp(20px,5vw,64px);
     transition:background var(--med) var(--out),color var(--med) var(--out)}
.nav[data-solid="1"]{background:color-mix(in srgb,var(--card) 58%,transparent);
  -webkit-backdrop-filter:blur(22px) saturate(1.8);
  backdrop-filter:blur(22px) saturate(1.8);
  box-shadow:0 1px 0 color-mix(in srgb,#FFFFFF 70%,transparent) inset,
             0 14px 34px -26px rgba(22,24,28,.38)}
.nav[data-on-night="1"]{color:var(--paper)}
.nav[data-on-night="1"][data-solid="1"]{
  background:color-mix(in srgb,#000000 42%,transparent);
  box-shadow:0 1px 0 color-mix(in srgb,#FFFFFF 12%,transparent) inset,
             0 14px 34px -26px rgba(0,0,0,.8)}
.brand{font-weight:800;font-size:19px;letter-spacing:-.04em;display:flex;
       align-items:center;gap:9px;flex-shrink:0}
.brand i{width:10px;height:10px;border-radius:3px;background:var(--amber);
         display:block;font-style:normal}
.nav .sp{flex:1}
.chip{font-family:var(--mono);font-size:var(--t-2xs);letter-spacing:.12em;
      padding:7px 13px 7px 11px;border-radius:100px;white-space:nowrap;
      font-weight:500;background:color-mix(in srgb,var(--red-wash) 72%,transparent);
      color:var(--red);display:flex;align-items:center;gap:8px;
      -webkit-backdrop-filter:blur(16px) saturate(1.6);
      backdrop-filter:blur(16px) saturate(1.6);
      border:1px solid color-mix(in srgb,var(--red) 22%,transparent)}
.chip::before{content:"";width:6px;height:6px;border-radius:50%;
              background:currentColor;flex-shrink:0;
              animation:pulse 2.8s var(--inout) infinite}
@keyframes pulse{0%,100%{opacity:.35}50%{opacity:1}}
.nav[data-on-night="1"] .chip{background:#2A1A17;color:#E08878}
.dots{display:flex;gap:7px;align-items:center}
.dots a{display:flex;align-items:center;gap:7px;padding:0}
.dots a i{width:8px;height:8px;border-radius:50%;display:block;flex-shrink:0;
          background:var(--line-2);transition:all var(--fast) var(--out)}
.dots a[aria-current="true"] i{background:var(--amber);width:22px;border-radius:100px}
/* Collapsed by width, never by display: the name stays in the accessibility
   tree for every chapter even while only the waypoints show it on screen. */
.dots a span{font-family:var(--mono);font-size:var(--t-2xs);letter-spacing:.1em;
             text-transform:uppercase;white-space:nowrap;color:var(--ink-3);
             max-width:0;opacity:0;overflow:hidden;
             transition:max-width var(--med) var(--out),
                        opacity var(--fast) var(--out),color var(--fast) var(--out)}
.dots a[aria-current="true"] span{color:var(--ink)}
.dots:hover a span,.dots a:focus-visible span{max-width:14ch;opacity:1}
@media (min-width:1200px){ .dots a[data-key="1"] span{max-width:14ch;opacity:1} }
.nav[data-on-night="1"] .dots a i{background:#3A424B}
.nav[data-on-night="1"] .dots a[aria-current="true"] i{background:#E0A046}
.nav[data-on-night="1"] .dots a span{color:#939CA6}
.nav[data-on-night="1"] .dots a[aria-current="true"] span{color:var(--paper)}

/* ============================================================== HERO ===== */
.hero{min-height:100svh;display:grid;grid-template-rows:1fr auto;
      padding:120px 0 var(--s5);position:relative;overflow:hidden}
.hero .wrap{align-self:center;width:100%;position:relative;z-index:1}
.hero h1{max-width:11ch}
.hero .sub{margin-top:var(--s5);max-width:34ch;font-size:var(--t-sub);
           color:var(--ink-2);letter-spacing:-.018em;line-height:1.45}
.hero-foot{display:flex;justify-content:space-between;align-items:flex-end;
           gap:var(--s5);flex-wrap:wrap;position:relative;z-index:1}
.cue{display:flex;align-items:center;gap:11px;font-family:var(--mono);
     font-size:var(--t-2xs);letter-spacing:.16em;text-transform:uppercase;
     color:var(--ink-3)}
.cue i{width:28px;height:1px;background:var(--ink-3);display:block;
       transform-origin:left;animation:cue 2.6s var(--inout) infinite}
@keyframes cue{0%{transform:scaleX(0)}45%{transform:scaleX(1)}
               100%{transform:scaleX(0);transform-origin:right}}

/* ================================================= SCENE (full-screen) === */
/* A statement that owns the viewport. No card, no border, no chart. */
.scene{min-height:88svh;display:flex;align-items:center;position:relative}
.scene .stmt{font-size:var(--t-stmt);font-weight:600;letter-spacing:-.042em;
             line-height:1.04;max-width:17ch}
.scene .stmt em{font-style:normal;color:var(--amber-ink)}
.scene .after{margin-top:var(--s5);max-width:46ch;font-size:var(--t-sub);
              color:var(--ink-2);letter-spacing:-.016em;line-height:1.45}
.scene.right{justify-content:flex-end;text-align:right}
.scene.right .stmt,.scene.right .after{margin-left:auto}

/* A single enormous figure. Used three times in the whole document. */
.figure-xl{font-size:clamp(88px,19vw,290px);font-weight:700;letter-spacing:-.06em;
           line-height:.82;font-variant-numeric:tabular-nums}
.figure-xl.amber{color:var(--amber)}
.figure-xl.red{color:var(--red)}
/* Prose stays in the display family. Monospace is the instrumentation layer --
   dates, ids, fares, status labels -- and a paragraph set in it reads as code
   rather than as writing. */
.figure-note{margin-top:var(--s4);font-size:var(--t-body);line-height:1.56;
             color:var(--ink-2);max-width:46ch}

/* ================================================= SPLIT (sticky text) === */
.split{display:grid;grid-template-columns:minmax(0,.8fr) minmax(0,1.2fr);
       gap:var(--s7);align-items:start}
.split .stick{position:sticky;top:128px}

/* ========================================================== DATA FIELD === */
/* One visual data object, composed rather than overlaid. It occupies the
   lower-right quadrant and fades out toward the type, so the headline always
   has clean ground; at narrow widths it drops behind the fold entirely. */
#field{position:absolute;right:-4%;bottom:-6%;width:min(62%,760px);
       height:min(64%,620px);z-index:0;pointer-events:none;opacity:.55;
       -webkit-mask-image:radial-gradient(74% 74% at 68% 62%,#000 38%,transparent 76%);
       mask-image:radial-gradient(74% 74% at 68% 62%,#000 38%,transparent 76%)}
@media (min-width:1200px){
  #field{width:min(56%,820px);height:min(72%,700px);opacity:.66;right:-2%}
}
@media (max-width:860px){
  #field{width:86%;height:38%;right:-12%;bottom:2%;opacity:.4}
}

/* ======================================================== FIELD STORY ==== */
/* A pinned canvas with the narration scrolling over it. The canvas carries no
   text of its own, so the beats stay readable when WebGL is unavailable and
   the section degrades to an ordinary sequence of paragraphs. */
.field-story{position:relative;padding-block:0}
.field-pin{position:sticky;top:0;height:100svh;margin-bottom:-100svh;z-index:0;
           pointer-events:none}
#field3d{width:100%;height:100%;display:block}
.field-steps{position:relative;z-index:1}
.fbeat{min-height:92svh;display:flex;flex-direction:column;justify-content:center;
       max-width:34ch;opacity:.22;transition:opacity var(--med) var(--out)}
.fbeat[data-on="1"]{opacity:1}
.fbeat h3{font-size:var(--t-chap);font-weight:600;letter-spacing:-.035em;
          line-height:1.02;margin-block:var(--s3)}
.fbeat .body{max-width:34ch}
@media (min-width:1000px){
  .field-pin{margin-left:34%;width:66%}
}
@media (max-width:999px){
  /* A single column has no empty side for the canvas to occupy, so the phone
     layout uses the other half of the scrollytelling convention: the graphic
     is an opaque band held at the top and the narration scrolls beneath it.
     The canvas never sits behind body copy, which is what made the earlier
     translucent version hard to read. */
  .field-pin{height:34svh;margin-bottom:-34svh;z-index:2;background:var(--paper);
             -webkit-mask-image:linear-gradient(#000 74%,transparent);
             mask-image:linear-gradient(#000 74%,transparent)}
  .field-steps{padding-top:36svh}
  .fbeat{min-height:50svh;padding-block:var(--s5);max-width:none;opacity:1}
}

/* =============================================================== RAIL ==== */
/* The horizontal APW journey: the landscape moves, not a row of cards. */
.rail-outer{position:relative;height:560vh}
.rail-pin{position:sticky;top:0;height:100svh;display:flex;align-items:center;
          overflow:hidden}
.rail-track{display:flex;will-change:transform}
.rail-panel{flex:0 0 min(72vw,820px);padding-inline:clamp(20px,4vw,60px);
            display:flex;flex-direction:column;justify-content:center;
            min-height:60svh;border-left:1px solid var(--line)}
.rail-panel:first-child{border-left:0}
.rail-panel .apw{font-size:clamp(52px,7vw,112px);font-weight:700;
                 letter-spacing:-.05em;line-height:.9}
.rail-panel .when{margin-top:var(--s3);font-family:var(--mono);
                  font-size:var(--t-sm);color:var(--ink-3);letter-spacing:.04em}
.rail-figs{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));
           gap:var(--s4) var(--s5);margin-top:var(--s5);max-width:500px}
.rail-figs div{display:flex;flex-direction:column;gap:3px}
.rail-figs dt{font-family:var(--mono);font-size:var(--t-2xs);letter-spacing:.12em;
              text-transform:uppercase;color:var(--ink-3)}
.rail-figs dd{margin:0;font-family:var(--mono);font-size:21px;font-weight:500;
              font-variant-numeric:tabular-nums}
.rail-bar{height:3px;background:var(--line);margin-top:var(--s5);max-width:500px;
          border-radius:100px;overflow:hidden}
.rail-bar i{display:block;height:100%;background:var(--amber);border-radius:100px}

/* ========================================================== EVIDENCE ===== */
/* A wall of real artifacts: 30 hashed + 5 chat images, one tile each. */
.wall{display:grid;grid-template-columns:repeat(auto-fill,minmax(50px,1fr));
      gap:9px;max-width:700px;margin-top:var(--s5)}
.wall button{aspect-ratio:1;border:0;border-radius:var(--r-sm);cursor:pointer;
             background:var(--green-wash);position:relative;padding:0;
             transition:transform var(--fast) var(--out)}
.wall button[data-ev="SECONDARY_CHAT_IMAGE"]{background:var(--amber-wash)}
.wall button::after{content:"";position:absolute;inset:0;border-radius:inherit;
                    border:1.5px solid transparent;transition:border-color var(--fast)}
.wall button{transition:transform 260ms var(--spring)}
.wall button:hover,.wall button:focus-visible{transform:translateY(-4px) scale(1.1)}
.wall button:active{transform:translateY(-1px) scale(1.02);transition-duration:90ms}
.wall button:hover::after{border-color:var(--ink)}
.wall-key{display:flex;gap:var(--s5);flex-wrap:wrap;margin-top:var(--s4)}
.wall-key span{display:flex;align-items:center;gap:9px;font-family:var(--mono);
               font-size:var(--t-xs);color:var(--ink-2)}
.wall-key i{width:14px;height:14px;border-radius:4px;display:block}

/* =========================================================== FORENSIC ==== */
.decomp{display:flex;flex-direction:column;gap:3px;max-width:780px;
        margin-top:var(--s5)}
.decomp .row{display:grid;grid-template-columns:62px 1fr auto;gap:var(--s4);
             align-items:center}
.decomp .n{font-family:var(--mono);font-size:19px;font-weight:500;
           font-variant-numeric:tabular-nums;text-align:right}
.decomp .track{height:24px;border-radius:var(--r-xs);background:var(--line);
               overflow:hidden}
.decomp .track i{display:block;height:100%;background:var(--pd);
                 transform-origin:left}
.decomp .row[data-mech="1"] .track i{background:var(--ex)}
.decomp .lab{font-family:var(--mono);font-size:var(--t-xs);color:var(--ink-3);
             white-space:nowrap}

/* =========================================================== BOUNDARY ==== */
.stages{margin-top:var(--s6);max-width:940px}
.stage{display:grid;grid-template-columns:18px 1fr auto;gap:var(--s4);
       align-items:start;padding-block:var(--s4);width:100%;text-align:left;
       background:none;border:0;border-top:1px solid var(--line);font:inherit;
       color:inherit;cursor:pointer;transition:opacity var(--fast) var(--out)}
.ch-night .stage{border-top-color:#262C33}
.stage:hover{opacity:.66}
.stage .dot{width:9px;height:9px;border-radius:50%;margin-top:10px;
            background:var(--pd);display:block}
.stage[data-state="EXERCISED"] .dot{background:var(--ex)}
.stage[data-state="DEGENERATE"] .dot{background:var(--dg)}
.stage[data-state="BLOCKED"] .dot{background:var(--bl)}
.ch-night .stage[data-state="EXERCISED"] .dot{background:#7FB2FF}
.ch-night .stage[data-state="DEGENERATE"] .dot{background:#E0A046}
.ch-night .stage[data-state="BLOCKED"] .dot{background:#E08878}
.ch-night .stage[data-state="PENDING"] .dot{background:#4A525B}
.stage .nm{font-size:var(--t-sub);font-weight:500;letter-spacing:-.02em}
.stage .sp{display:block;font-family:var(--mono);font-size:var(--t-xs);
           color:var(--ink-3);margin-top:6px;word-break:break-word}
.ch-night .stage .sp{color:#8A939D}
.state{font-family:var(--mono);font-size:var(--t-2xs);letter-spacing:.12em;
       padding:6px 12px;border-radius:100px;white-space:nowrap;font-weight:500;
       background:var(--pd-wash);color:var(--pd)}
.state.ex{background:var(--ex-wash);color:var(--ex)}
.state.dg{background:var(--dg-wash);color:var(--dg)}
.state.bl{background:var(--bl-wash);color:var(--bl)}
.ch-night .state{background:#232930;color:#9AA3AE}
.ch-night .state.ex{background:#152238;color:#8FB8FF}
.ch-night .state.dg{background:#2A2013;color:#E5AC5C}
.ch-night .state.bl{background:#2A1A17;color:#E89486}
.stage-body{display:grid;grid-template-rows:0fr;
            transition:grid-template-rows var(--med) var(--out)}
.stage-body[data-open="1"]{grid-template-rows:1fr}
.stage-body>div{overflow:hidden;min-height:0}
.stage-body ul{margin:0 0 var(--s3);padding-left:20px;font-size:var(--t-sm);
               color:var(--ink-2);max-width:64ch}
.ch-night .stage-body ul{color:#B6BDC6}
.stage-body li{margin-bottom:5px}
.stage-body .note{font-size:var(--t-sm);color:var(--ink-3);max-width:64ch}
.ch-night .stage-body .note{color:#8A939D}
.stop-line{display:flex;align-items:center;gap:var(--s4);margin-block:var(--s5);
           font-family:var(--mono);font-size:var(--t-xs);letter-spacing:.14em;
           text-transform:uppercase;color:var(--bl);font-weight:500}
.stop-line::before,.stop-line::after{content:"";flex:1;height:1px;
                                     background:currentColor;opacity:.34}
.ch-night .stop-line{color:#E08878}

/* ========================================================== DERIVATION === */
/* The +38.6% arrives as an arithmetic you can follow, not as a headline. */
.derive{list-style:none;margin:0 0 var(--s6);padding:0;max-width:560px}
.derive li{display:grid;grid-template-columns:88px auto 1fr;gap:var(--s4);
           align-items:baseline;padding-block:var(--s3);
           border-bottom:1px solid var(--line)}
.derive .dk{font-family:var(--mono);font-size:var(--t-xs);letter-spacing:.12em;
            text-transform:uppercase;color:var(--ink-3)}
.derive .dv{font-size:30px;font-weight:500;letter-spacing:-.02em}
.derive .dn{font-size:var(--t-xs);color:var(--ink-3);align-self:center}
.derive li[data-op="ratio"]{border-bottom:0;border-top:2px solid var(--ink);
                            margin-top:var(--s2);padding-top:var(--s4)}
.derive li[data-op="ratio"] .dv{color:var(--amber-ink)}

/* The qualification travels with the number and never scrolls away from it. */
.qualify{margin-top:var(--s4);display:inline-flex;align-items:center;gap:10px;
         font-family:var(--mono);font-size:var(--t-xs);letter-spacing:.1em;
         text-transform:uppercase;color:var(--amber-ink);
         background:var(--amber-wash);padding:10px 16px;border-radius:100px}
.qualify strong{font-weight:600}

/* ====================================================== PIPELINE FREEZE == */
/* Stages the real data reaches light as they arrive. Stages past the evidence
   boundary never light: they stay inert, because nothing has run there. */
.js .stage[data-past="0"]{opacity:.38;transition:opacity var(--med) var(--out)}
.js .stage[data-past="0"][data-lit="1"]{opacity:1}
.stage[data-past="1"]{opacity:.52}
.stage[data-past="1"] .nm{color:var(--ink-3)}
.ch-night .stage[data-past="1"] .nm{color:#7F8893}
.stage[data-past="1"]{background:repeating-linear-gradient(-45deg,
  transparent 0 7px, color-mix(in srgb,var(--ink) 4%,transparent) 7px 8px)}
.ch-night .stage[data-past="1"]{background:repeating-linear-gradient(-45deg,
  transparent 0 7px, rgba(255,255,255,.035) 7px 8px)}

/* ============================================================= CHART ===== */
.chart{margin-top:var(--s5)}
.chart figcaption{margin-bottom:var(--s4)}
.chart figcaption h3{margin-bottom:6px}
.chart .src{margin-top:var(--s4);font-size:var(--t-sm);color:var(--ink-3);
            max-width:62ch}
.cwrap{max-width:100%}
.axis{stroke:var(--line-2);stroke-width:1}
.grid-l{stroke:var(--line);stroke-width:1}
.tick{fill:var(--ink-3);font-family:var(--mono);font-size:11px}
.tick.b{fill:var(--ink-2);font-weight:500}
.ser{fill:none;stroke:var(--amber);stroke-width:2.5;stroke-linejoin:round;
     stroke-linecap:round}
.dot{fill:var(--paper);stroke:var(--amber);stroke-width:2.5;
     transition:r var(--fast) var(--out)}
.hit{fill:transparent;cursor:pointer}
.hit:hover+.dot,.hit:focus-visible+.dot{r:8}
.bar{fill:var(--ex);transition:fill var(--fast) var(--out)}
.bar:hover{fill:var(--amber)}

#tip{position:fixed;z-index:400;pointer-events:none;opacity:0;
     background:color-mix(in srgb,var(--ink) 84%,transparent);
     -webkit-backdrop-filter:blur(20px) saturate(1.7);
     backdrop-filter:blur(20px) saturate(1.7);
     border:1px solid color-mix(in srgb,#FFFFFF 16%,transparent);
     color:var(--paper);padding:13px 16px;border-radius:var(--r);min-width:170px;
     max-width:290px;font-size:var(--t-sm);box-shadow:0 18px 44px -20px rgba(0,0,0,.55);
     transition:opacity var(--fast) var(--out);transform:translate(-50%,calc(-100% - 16px))}
#tip.on{opacity:1}
#tip .h{font-family:var(--mono);font-size:var(--t-2xs);letter-spacing:.1em;
        text-transform:uppercase;color:#E0A046;margin-bottom:7px}
#tip dl{margin:0;display:grid;grid-template-columns:auto 1fr;gap:3px 16px}
#tip dt{color:#9AA3AE;font-size:var(--t-xs)}
#tip dd{margin:0;font-family:var(--mono);font-size:var(--t-xs);text-align:right}

/* ============================================================== VAULT ==== */
.filters{display:flex;flex-wrap:wrap;gap:var(--s4);align-items:center;
         margin-bottom:var(--s5);max-width:100%}
.fset{display:flex;flex-wrap:wrap;gap:7px;align-items:center;min-width:0}
.fset>span{font-family:var(--mono);font-size:var(--t-2xs);letter-spacing:.14em;
           text-transform:uppercase;color:var(--ink-3);margin-right:5px}
.fset button{background:var(--paper-2);border:0;color:var(--ink-2);
             font-family:var(--mono);font-size:var(--t-xs);padding:8px 15px;
             border-radius:100px;cursor:pointer;
             box-shadow:4px 5px 11px -8px rgba(22,24,28,.26),
                        -3px -3px 8px -6px #FFFFFF inset,
                        2px 2px 4px -3px rgba(22,24,28,.12) inset;
             transition:transform 240ms var(--spring),
                        box-shadow var(--fast) var(--out),
                        background var(--fast) var(--out),color var(--fast) var(--out)}
.fset button:hover{color:var(--ink);transform:translateY(-2px)}
.fset button:active{transform:translateY(0) scale(.955);transition-duration:90ms}
.fset button[aria-pressed="true"]{background:var(--ink);border-color:var(--ink);
                                  color:var(--paper)}
.vcount{font-family:var(--mono);font-size:var(--t-xs);color:var(--ink-3);
        margin-left:auto}
.vcount b{color:var(--ink);font-weight:500}
.tscroll{overflow-x:auto;max-width:100%;-webkit-overflow-scrolling:touch}
table{border-collapse:collapse;width:100%;font-size:var(--t-sm)}
thead th{font-family:var(--mono);font-size:var(--t-2xs);letter-spacing:.12em;
         text-transform:uppercase;color:var(--ink-3);font-weight:500;
         text-align:left;padding:12px 16px 12px 0;
         border-bottom:1px solid var(--line-2);white-space:nowrap}
tbody td{padding:13px 16px 13px 0;border-bottom:1px solid var(--line);
         white-space:nowrap}
tbody tr{transition:background var(--fast) var(--out)}
tbody tr:hover{background:var(--card)}
tbody tr[hidden]{display:none}
td.r,th.r{text-align:right;padding-right:0}
td.m{font-family:var(--mono);font-size:var(--t-xs);font-variant-numeric:tabular-nums}
.pill{font-family:var(--mono);font-size:var(--t-2xs);letter-spacing:.08em;
      padding:4px 10px;border-radius:100px;white-space:nowrap}
.pill.p{background:var(--green-wash);color:var(--green)}
.pill.s{background:var(--amber-wash);color:var(--amber-ink)}

/* ============================================================ PENDING ==== */
.timeline{display:flex;align-items:center;gap:var(--s4);flex-wrap:wrap;
          margin-top:var(--s6);font-family:var(--mono);font-size:var(--t-xs)}
.timeline .node{display:flex;flex-direction:column;gap:9px;min-width:94px}
.timeline .node i{width:11px;height:11px;border-radius:50%;
                  background:var(--line-2);display:block}
.timeline .node[data-now="1"] i{background:var(--ink)}
.timeline .node[data-key="1"] i{background:var(--amber)}
.timeline .node b{font-weight:500;letter-spacing:.02em}
.timeline .node span{color:var(--ink-3);font-size:var(--t-2xs)}
.timeline .link{flex:1;height:1px;background:var(--line-2);min-width:24px}
.timeline .link.dash{background:repeating-linear-gradient(90deg,
                     var(--line-2) 0 5px,transparent 5px 11px)}

/* ============================================================= FAQ ======= */
.qa{border-top:1px solid var(--line);padding-block:var(--s4)}
.qa summary{cursor:pointer;font-size:var(--t-sub);font-weight:500;
            letter-spacing:-.018em;list-style:none;display:flex;gap:var(--s4);
            align-items:baseline;transition:color var(--fast)}
.qa summary::-webkit-details-marker{display:none}
.qa summary::before{content:"+";font-family:var(--mono);color:var(--amber-ink);
                    font-size:22px;line-height:1;transition:transform var(--med) var(--out)}
.qa[open] summary::before{transform:rotate(45deg)}
.qa summary:hover{color:var(--amber-ink)}
.qa .a{padding-top:var(--s3);padding-left:34px;font-size:var(--t-body);
       color:var(--ink-2);max-width:60ch}

/* ============================================================= FOOTER ==== */
footer{background:var(--night);color:#9AA3AE;padding-block:var(--s7);
       font-size:var(--t-sm)}
footer .cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));
             gap:var(--s5)}
footer b{color:var(--paper);font-weight:500}
footer .mono{color:#B6BDC6}

/* ============================================================ REVEALS ==== */
/* Progressive enhancement: visible by default, hidden only once script has
   confirmed itself with `html.js`. A blocked script costs the animation, not
   the evidence. */
.rv{opacity:1;transform:none}
.js .rv{opacity:0;transform:translateY(20px)}
/* The beats dim only once script is present to brighten the active one. */
html:not(.js) .fbeat{opacity:1}
/* The clip that makes the reveal also clips descenders. Pad the box and pull
   it back, so a 'y' keeps its tail and the line spacing is unchanged. */
.line-mask{display:block;overflow:hidden;padding-bottom:.16em;margin-bottom:-.16em}
.js .line-mask>span{display:block;transform:translateY(112%)}

/* The rail travels sideways under a script-driven transform. Nothing else can
   move it, so when the driver is absent — no script at all, or the animation
   library blocked — six of the seven panels sit outside a clipped pin and are
   unreachable, and the reader loses six advance-purchase buckets without any
   sign that they existed. Both cases fall back to the vertical stack the phone
   layout already uses: `html:not(.js)` covers no script, and the script adds
   `rail-flat` itself when it finds no library. */
html:not(.js) .rail-outer,html.rail-flat .rail-outer{height:auto}
html:not(.js) .rail-pin,html.rail-flat .rail-pin{position:static;height:auto;
                                                 display:block;overflow:visible}
html:not(.js) .rail-track,html.rail-flat .rail-track{flex-direction:column;
                                                     transform:none!important}
html:not(.js) .rail-panel,html.rail-flat .rail-panel{flex:auto;border-left:0;
            border-top:1px solid var(--line);padding-inline:0;
            padding-block:var(--s6);min-height:0}
html:not(.js) .rail-panel:first-child,
html.rail-flat .rail-panel:first-child{border-top:0}

/* ========================================================= RESPONSIVE ==== */
@media (max-width:1080px){
  :root{--s9:120px;--s8:88px}
  .rail-panel{flex:0 0 84vw}
  .split{grid-template-columns:1fr;gap:var(--s5)}
  .split .stick{position:static}
}
@media (max-width:760px){
  :root{--s9:88px;--s8:64px;--s7:56px}
  .derive li{grid-template-columns:72px 1fr;gap:var(--s3)}
  .derive .dn{grid-column:2}
  /* A phone has no room for thirteen dots and a label beside each, but it
     still needs a way through the argument. The six waypoints stay, unlabelled
     and on a tighter gap; the intermediate chapters are reached by scrolling,
     which on a phone is what a reader does anyway. */
  .nav{gap:14px}
  .nav .dots{display:flex;gap:9px}
  .dots a:not([data-key="1"]){display:none}
  .dots a span{display:none}
  .hero h1{max-width:none}
  .scene{min-height:auto;padding-block:var(--s7)}
  .scene .stmt{max-width:none}
  .scene.right{text-align:left;justify-content:flex-start}
  .scene.right .stmt,.scene.right .after{margin-left:0}
  .rail-outer{height:auto}
  .rail-pin{position:static;height:auto;display:block}
  .rail-track{flex-direction:column;transform:none!important}
  .rail-panel{flex:auto;border-left:0;border-top:1px solid var(--line);
              padding-inline:0;padding-block:var(--s6);min-height:0}
  .rail-panel:first-child{border-top:0}
  .cwrap{overflow-x:auto;margin-inline:calc(var(--s3) * -1);padding-inline:var(--s3)}
  .cwrap>svg{min-width:640px}
  .stage{grid-template-columns:14px 1fr;gap:var(--s3)}
  .stage .state{grid-column:2;justify-self:start;margin-top:var(--s2)}
}

/* ===================================================== REDUCED MOTION ==== */
@media (prefers-reduced-motion:reduce){
  *,*::before,*::after{animation-duration:.001ms!important;
                       animation-iteration-count:1!important;
                       transition-duration:.001ms!important}
  .js .rv{opacity:1;transform:none}
  .js .line-mask>span{transform:none}
  .cue i{animation:none}
  #field,#field3d{display:none}
  .field-pin{position:static;height:0;margin-bottom:0}
  .field-steps{padding-top:0}
  .fbeat{min-height:auto;opacity:1;padding-block:var(--s6);max-width:none}
  .rail-outer{height:auto}
  .rail-pin{position:static;height:auto;display:block}
  .rail-track{flex-direction:column;transform:none!important}
  .rail-panel{flex:auto;border-left:0;border-top:1px solid var(--line);min-height:0}
}

/* =============================================================== PRINT === */
@media print{
  .nav,.cue,#field,#field3d,#tip,.filters{display:none!important}
  .field-pin{position:static;height:0;margin-bottom:0}
  .field-steps{padding-top:0}
  .fbeat{min-height:auto;opacity:1;max-width:none}
  body{background:#fff}
  .ch{padding-block:28px;break-inside:avoid}
  .ch-night{background:#fff;color:#000}
  .js .rv{opacity:1;transform:none}
  .js .line-mask>span{transform:none}
  .rail-outer{height:auto} .rail-pin{position:static;height:auto}
  .rail-track{flex-direction:column;transform:none!important}
}
"""
