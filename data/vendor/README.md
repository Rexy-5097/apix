# Vendored runtime assets

`data/dashboard.html` loads nothing from the network. Everything it needs is in
this directory, at a path relative to the artifact, so the page renders the same
on conference wifi, on a locked-down machine, and from a `file://` URL on a
laptop with the cable pulled.

These files are **third-party and unmodified**. They are not APIx code, they
contribute nothing to any statistical value, and deleting them degrades the
page to its no-library fallback rather than breaking it.

## Libraries

| File | Version | Source | Licence |
|---|---|---|---|
| `gsap.min.js` | 3.12.5 | `cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/gsap.min.js` | GreenSock Standard ("No Charge") — see header in file |
| `ScrollTrigger.min.js` | 3.12.5 | `cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/ScrollTrigger.min.js` | GreenSock Standard ("No Charge") |
| `lenis.min.js` | 1.1.13 | `cdn.jsdelivr.net/npm/lenis@1.1.13/dist/lenis.min.js` | MIT |

GSAP's licence header is retained verbatim in both files. The GreenSock Standard
licence covers use in a project that does not charge for access, which is what
APIx is; APIx is not a Club GreenSock product and uses no bonus plugins.

## Fonts

Cut from one Google Fonts request and self-hosted:

```
https://fonts.googleapis.com/css2
  ?family=Plus+Jakarta+Sans:wght@400;500;600;700;800
  &family=IBM+Plex+Mono:wght@400;500&display=swap
```

| File | Family | Weights | Subset |
|---|---|---|---|
| `fonts/PlusJakartaSans-variable-latin.woff2` | Plus Jakarta Sans | 400–800 (variable) | latin |
| `fonts/PlusJakartaSans-variable-latin-ext.woff2` | Plus Jakarta Sans | 400–800 (variable) | latin-ext |
| `fonts/IBMPlexMono-400-latin.woff2` | IBM Plex Mono | 400 | latin |
| `fonts/IBMPlexMono-400-latin-ext.woff2` | IBM Plex Mono | 400 | latin-ext |
| `fonts/IBMPlexMono-500-latin.woff2` | IBM Plex Mono | 500 | latin |
| `fonts/IBMPlexMono-500-latin-ext.woff2` | IBM Plex Mono | 500 | latin-ext |

Plus Jakarta Sans is a variable font, so Google serves one file per subset for
the whole weight axis. IBM Plex Mono is static, so each weight is its own file —
naming both the same way silently let Mono 500 overwrite Mono 400, which is why
the filenames say which is which.

**`latin-ext` is load-bearing, not an optimisation.** The rupee sign is U+20B9,
which sits in the `latin-ext` unicode-range and not in `latin`. Drop that subset
and every fare on the page loses its currency mark.

Both families are licensed under the SIL Open Font License 1.1, which permits
self-hosting and redistribution.

## Regenerating

`fonts.css` is the Google stylesheet with its `src:` URLs rewritten to the local
files and the non-latin subsets removed. If a family or weight changes in
`tools/analysis/dashboard_theme.py`, re-cut it from the same request rather than
editing `fonts.css` by hand.
