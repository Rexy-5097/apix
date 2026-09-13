# `collection-input/` — the audit trail from screenshot to observation

**This directory is provenance, not product.** It holds the working record of how
152 fare screenshots collected on 2026-09-12 became the **35 canonical
observations** in [`data/panel.json`](../data/panel.json) — and, just as
importantly, how the other 122 did not.

Nothing here is an APIx result. The canonical contract is `data/panel.json`; if
any file here ever disagrees with it, the contract wins.

> **Why keep the intermediates at all?** Because "we excluded 122 screenshots"
> is only checkable if the record of *what was read off each screenshot* still
> exists. Ten of the files below are referenced by no code. Deleting them would
> make the repository tidier and the evidence weaker, which is the wrong trade
> for a project whose entire claim is traceability.

---

## Load-bearing — code and tests read these

Changing any of these changes a published figure or fails the build.

| File | Contents | Read by |
|---|---|---|
| `extract/panel_raw.json` | **152 rows**, every field read off every screenshot | `tools/analysis/replay_exclusions.py` · `tests/test_execution_boundary.py` |
| `extract/exclusions.json` | **6 reason groups**, 122 screenshot ids | `replay_exclusions.py` · `build_panel_json.py` · `panel_report.py` · `tests/` |
| `loader/fares.csv` | **30 fare rows** staged for ingestion | `tools/collection/load_manual.py` |
| `loader/attempts.csv` | **6 collection attempts** with outcomes | `tools/collection/load_manual.py` |
| `extract/verified.csv` | **30 hand-verified primary rows** | `tests/test_observed_panel.py` |

`panel_raw.json` is the one that makes the exclusion replay possible:
`exclusions.json` stores only screenshot **ids**, so without the fields in
`panel_raw.json` the recorded verdicts could not be re-derived, and
[the replay claim](../docs/claim-evidence-matrix.md) could not be made.

## Retained provenance — nothing reads these, and they stay

Referenced by **no** code, test, or CI job. They are kept because they are the
derivation, and a derivation you have thrown away is an assertion.

| File | Contents | Why it is retained |
|---|---|---|
| `extract/ocr_parsed.json` | 152 raw OCR reads | What the machine saw before any human judgement |
| `extract/times.json` | 152 departure-time extractions | The §B.2 banding input, pre-verification |
| `extract/index.json` | 152 screenshot → travel-date map | How each shot was dated |
| `extract/selected.json` | 32 provisional selections | The earliest-in-band rule being applied |
| `extract/provisional_selection.json` | 7 APW groups | Selection before verification |
| `extract/rows.csv` | 26 intermediate rows | Working set during verification |
| `extract/t45_staged.csv` | 24 T+45 rows | The batch with **weaker provenance** — chat images, no hashable bytes |
| `extract/build_panel.py` | OCR + verified dates → `panel_raw.json` | The derivation itself. It already ran; its output is load-bearing |
| `extract/parse_ocr.py` | Screenshot text → `ocr_parsed.json` | First step of the same chain |
| `extract/to_loader.py` | Verified rows → `loader/*.csv` | Last step before the SQLite store |

`t45_staged.csv` is worth naming explicitly: it is the raw form of the five
`SECONDARY_CHAT_IMAGE` observations. That weaker provenance is
[disclosed on the dashboard](../data/dashboard.html) and in
[`docs/claim-evidence-matrix.md`](../docs/claim-evidence-matrix.md). It is not
hidden here either.

---

## What this directory is not

- **Not a second source of truth.** `extract/build_panel.py` produces
  `panel_raw.json`, the *candidate* record. The canonical panel is produced by
  `tools/analysis/build_panel_json.py` from the SQLite store. Two different
  jobs; only the second one feeds anything published.
- **Not re-run in CI.** These scripts ran once, during the 2026-09-12
  extraction. Re-running them is not part of any build.
- **Not a collection tool.** Collection is manual and governed by
  [`compliance/manual-collection-procedure.md`](../compliance/manual-collection-procedure.md).

## The chain, end to end

```
152 screenshots
  → parse_ocr.py      → ocr_parsed.json, times.json, index.json
  → build_panel.py    → panel_raw.json          152 rows, every field read
  → human triage      → exclusions.json         122 excluded, each with a reason
                        verified.csv             30 primary rows
                        t45_staged.csv           5 accepted, weaker provenance
  → to_loader.py      → loader/fares.csv, loader/attempts.csv
  → load_manual.py    → data/collection/collection.sqlite3   (gitignored)
  → build_panel_json.py → data/panel.json        35 observations  ← CANONICAL
```

The replay in `tools/analysis/replay_exclusions.py` closes the loop: it feeds
the recorded exclusions back through the frozen §A.3 and §B.2 code and asks
whether the engine independently reaches the same verdict.
