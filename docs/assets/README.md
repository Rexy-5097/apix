# Media assets

Canonical location for every image, diagram and recording used to present APIx.
`docs/assets/` is the only such directory — there is no `docs/media/`.

Every asset here is listed below with its source, whether it depicts **real
market data** or a **controlled fixture**, and when it was made. An asset that
is not in this table should not be used in a presentation: it is either stale or
unverified.

```
docs/assets/
  architecture/   hand-authored SVG, drawn from the code
  social/         repository / social preview card
  screenshots/    NOT YET CAPTURED — see "Pending capture" below
  videos/         NOT YET CAPTURED — see "Pending capture" below
```

## Architecture diagrams

| Asset | Source of truth | Data | Made | Use |
|---|---|---|---|---|
| `architecture/apix-system-architecture.svg` | `src/apix/` package layout · `tests/test_architecture.py` | n/a — structural | 2026-09-14 | README, slides |
| `architecture/apix-execution-boundary.svg` | The 14 stages rendered by `tools/analysis/execution_boundary.py`, states read from the built dashboard | Real — describes the real-data boundary | 2026-09-14 | README, jury technical segment |
| `architecture/apix-current-vs-next-wave.svg` | `docs/collection-2026-09-19.md` · §C.1 | Real — one wave held, second wave dated | 2026-09-14 | Slides, "why pending" |

The boundary diagram's stage names, spec references and the four states
(EXERCISED / DEGENERATE / PENDING / BLOCKED) were extracted from the generated
`data/dashboard.html`, not retyped. If the boundary changes, regenerate the
dashboard and redraw rather than editing the SVG's labels by hand.

## Social preview

| Asset | Data | Made | Use |
|---|---|---|---|
| `social/apix-social-preview.svg` | Real — 35 / 7 of 7 / 122 / v2.1, all from `data/panel.json` | 2026-09-14 | GitHub social preview, slide title card |

GitHub's social-preview slot accepts PNG or JPG, not SVG, and it is set by
upload in repository **Settings → General → Social preview** — there is no REST
API for it. Export once at 1600×900 (open the SVG in a browser and save, or
`rsvg-convert -w 1600 -h 900`) and upload the PNG. The SVG is the source; keep
it, and re-export rather than editing a PNG.

Every claim on the card is checkable: 35 observations, 7 of 7 frozen APW
buckets, 122 audited exclusions, methodology v2.1, index pending, and the
explicit "not nationally representative · not production-ready" strip.

## Pending capture

**No screenshots or videos have been captured.** They are absent rather than
provisional, because capture in the environment available produced assets that
would fail this pass's own rules:

- **Resolution.** The capture surface was 800×505. The stated bar is 1440×900
  or 1600×1000 for desktop and 390×844 for mobile.
- **The 3D observation field renders blank.** With the browser pane hidden the
  page gets no `requestAnimationFrame` callbacks, so the WebGL field never
  draws. Reading the GL buffer back confirmed it: nothing painted.
- **Animated figures freeze mid-reveal.** The same missing frame callbacks
  leave masked statistics part-revealed, which is exactly the "partially
  animated intermediate value" a capture must never show.

A sub-resolution set missing its signature visual is worse than none: it would
have to be recaptured, and stale assets outlive the reason they were made.

### Capture protocol, when a real browser is available

Serve the repo (`python -m http.server 8753`) and open
`http://127.0.0.1:8753/data/dashboard.html` in a visible browser window.

1. Desktop 1440×900, mobile 390×844. One viewport per set; do not mix.
2. Wait for `document.fonts.ready`, then scroll the full page once and return —
   reveals are scroll-triggered and will not have fired otherwise.
3. **Before each capture, assert every figure shows its final value.** This is
   mechanical, so make it mechanical:

   ```js
   [...document.querySelectorAll('[data-count]')].every(el =>
     el.textContent.trim().replace(/^\+/,'').replace(/%$/,'').replace(/,/g,'')
       === el.dataset.count.replace(/,/g,''))
   ```

   If that is not `true`, the page is mid-animation. Do not capture.
4. Confirm the WebGL field has drawn before capturing the motion chapter —
   a blank canvas is the failure mode to watch for.
5. No devtools, no browser chrome, no cursor in frame, no hover states.

Chapters worth capturing, in page order: hero, the problem beats, the
observation chapter, the moving panel (3D), the seven-bucket rail, the T+1→T+60
difference, the confound, dispersion, evidence and provenance, the exclusion
replay, the execution boundary, index-pending, the 19 September unlock, and the
observation vault. Curate down to the five strongest for the README; the rest
belong in the gallery, not the landing page.

### Videos

None. Recording is not available in this environment at all — there is no
screen-capture path, so a video would have to be fabricated rather than
recorded. The demo script in the repository is the current substitute.
