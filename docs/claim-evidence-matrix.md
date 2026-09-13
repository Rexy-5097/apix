# Claim → evidence matrix

> **Every material public claim APIx makes, and what backs it.**
> Companion to [`capability-matrix.md`](capability-matrix.md), which answers
> *"what works?"*. This one answers *"why should anyone believe the numbers on
> the dashboard?"* — claim by claim, including the ones whose honest status is
> **not established**.

If a claim is not in this table, it is not a claim APIx makes. If a row's
evidence and its status disagree, believe the status.

## How to read the status column

| Status | Means |
|---|---|
| **ESTABLISHED** | Evidence exists, a calculation derives it, and a test fails the build if it drifts |
| **EXERCISED** | The frozen code path ran against real observations. **Not a validation claim** |
| **DEGENERATE** | The code executes on real data, but the panel supplies too little variation for the property to be established |
| **DISCLOSED LIMITATION** | A true statement about what APIx cannot currently do |
| **NOT ESTABLISHED** | Openly unresolved. No number is published in its place |
| **PENDING EVIDENCE** | Implemented and fixture-tested; the real evidence does not exist yet |

---

## 1. The observed panel

| Claim | Evidence source | Calculation / implementation | Test | Status | Limitation |
|---|---|---|---|---|---|
| **35 real market observations**, DEL–BOM / IndiGo / Saver, collected 2026-09-12 | SQLite store `data/collection/`, 30 SHA-256 screenshots + 5 chat images | `tools/analysis/build_panel_json.py` → `data/panel.json` | `test_panel_is_exactly_the_expected_size`, `test_a_worked_example_matches_the_screenshot_by_hand` | **ESTABLISHED** | One route, one carrier, one channel, one day. Not a sample of anything wider |
| **7 of 7 frozen APW buckets** present (T+1, 3, 7, 15, 30, 45, 60) | The 35 observations' travel dates | `APWBucket.from_lead_time`, exact match, no rounding (§A.3) | `test_the_seven_frozen_apw_buckets_are_all_present`, `test_each_apw_maps_to_its_hand_calculated_travel_date` | **ESTABLISHED** | Each bucket sits on a different travel date, so the seven are cross-sections, not a time series |
| **35/35 collection-plan slots filled** (7 buckets × 5 bands) | `panel.json` → `quality.plan_completion_pct` | `plan_slots = len(PRODUCTION_APW) × len(CONTRACT_BANDS)` | `test_reported_plan_completion_agrees_with_the_rows`, `test_exactly_one_flight_per_apw_band_cell` | **ESTABLISHED** | **Plan completion, not statistical coverage.** The two are different quantities and the renderers are tested never to call this "coverage" |
| **Every fare reconciles**: base + tax = total, 35/35, exact decimal | Fare breakdown read off each screenshot | `Decimal` comparison in `build_panel_json.py` | `test_base_plus_tax_equals_total_for_every_observation` | **ESTABLISHED** | Reconciliation checks internal arithmetic. It does not verify the fare was the cheapest available |
| **Provenance is not uniform**: 30 `PRIMARY_HASHED`, 5 `SECONDARY_CHAT_IMAGE` | Content-addressed artifacts bound to runs | Derived — an observation is `PRIMARY_HASHED` only if its run has an artifact | `test_the_weaker_t45_provenance_is_visible_not_hidden`, `test_evidence_counts_match_the_rows` | **ESTABLISHED** | The T+45 batch has **no hashed bytes** and its capture times are placeholders, not measurements |
| **9 observations fall outside their run's declared 21:00–22:00 window** | `panel.json` → `quality.window_flags` | `CollectionWindow.contains` via `filter_admissible` | `tests/test_execution_boundary.py` (admissibility stage) | **DISCLOSED LIMITATION** | §A.5 keeps them in the store and out of the index. The methodology window's *value* is **OQ-1 OPEN**, so no admissible count is normative yet |
| **The runs' `frame_id` names `T7-T15-T21-T30`, which is not the bucket set collected** | `panel.json` → `runs[].frame_id` | recorded verbatim at load time; not recomputed | — | **DISCLOSED LIMITATION** | The panel holds T+1/3/7/15/30/45/60 and no T+21. `frame_id` and `protocol_version` are **protected fields and were not edited**; the next wave must declare the frame it actually collects |

## 2. The exclusion audit and its replay

| Claim | Evidence source | Calculation / implementation | Test | Status | Limitation |
|---|---|---|---|---|---|
| **122 screenshots were audited, not discarded**, each with a reason and an id | `collection-input/extract/exclusions.json` | surfaced into `panel.json` → `exclusions` | `test_the_contract_carries_the_boundary_and_the_replay` | **ESTABLISHED** | The reasons were assigned by human triage. The replay below is what makes part of that mechanical |
| **45 of 46 mechanically decidable exclusions independently reproduce the recorded §A.3/§B.2 verdict; 1 record lacks a readable departure time and is not mechanically testable** | `collection-input/extract/panel_raw.json` (152 rows with fields) | `tools/analysis/replay_exclusions.py` — re-runs `APWBucket.from_lead_time`, `hour_band`, `filter_admissible` | `test_all_24_t68_records_reproduce_the_recorded_a3_verdict`, `test_15_of_16_band_7_records_reproduce_the_recorded_b2_verdict`, `test_all_6_band_1_records_reproduce_the_recorded_b2_verdict` | **ESTABLISHED** | Coverage differs per check: 46 A.3-testable, 38 B.2-testable, **9** reconstructable as full canonical observations |
| **0 replay disagreements** | as above | mismatch list is empty in every group | `test_the_replay_produces_zero_disagreements` | **ESTABLISHED** | Zero disagreements on 46 records is not zero disagreements on 122 |
| **All 35 accepted observations pass the same relevant rule checks with 0 false rejections** | `data/panel.json` → `observations` | control arm of the same replay | `test_no_accepted_observation_is_falsely_rejected` | **ESTABLISHED** | A rejection rule that also rejected the accepted panel would be worthless; this is the check that rules that out |
| **76 further exclusions are deliberately not replayed** (67 selection, 8 unreadable, 1 insufficient) | `exclusions.json` | skipped by name with a recorded reason | `test_selection_and_unreadable_reasons_are_skipped_not_silently_passed` | **DISCLOSED LIMITATION** | `NOT_EARLIEST_IN_BAND` is a collection-contract selection rule — the engine has no verdict on it. The other 9 record a field that was never readable, and **nothing is invented to stand in for it** |

## 3. What the frozen statistics code has actually seen

| Claim | Evidence source | Calculation / implementation | Test | Status | Limitation |
|---|---|---|---|---|---|
| **"Real market observations pass through APIx's admissibility, banding, key construction, deduplication and source-precedence stages. The pipeline stops at the longitudinal Jevons step because the required t−7 observation does not yet exist."** | `panel.json` → `execution_boundary` | `tools/analysis/execution_boundary.py` runs the frozen functions read-only | `test_the_boundary_claim_is_the_agreed_wording`, `test_the_boundary_stops_exactly_where_the_evidence_stops` | **EXERCISED** | **EXERCISED ≠ VALIDATED.** The observations are reconstructed from `panel.json` by a harness; the production loader still imports nothing from `apix.statistics` |
| Admissibility §A.6 runs on real observations | 35 reconstructed canonical observations | `filter_admissible` | `tests/test_execution_boundary.py` | **EXERCISED** | Run twice — `window=None` (35 admissible) and with the declared window (26 admissible, 9 excluded). Neither is normative while OQ-1 is open |
| Band derivation §B.2.2 runs on real observations | as above | `hour_band`, 35/35 agree with the recorded band | `test_the_dashboard_renders_every_stage_with_its_derived_state` | **EXERCISED** | — |
| Cell / parent / item keys are constructed from real observations | as above | `cell_key_for`, `parent_key_for`, `item_key_for` | `tests/test_execution_boundary.py` | **EXERCISED** | 7 cell keys, 7 parent keys, 7 Tier-1 and 5 Tier-2 item keys. Constructing a key is not matching it to anything |
| Deduplication §D.4 runs on real observations | as above | `duplicate_key`, `deduplicate` — 35 distinct keys, 0 duplicates | `test_deduplication_is_exercised_and_says_zero_duplicates_were_observed`, `test_no_duplicate_on_the_spec_d4_tuple` | **EXERCISED** | **0 duplicates observed; key construction exercised.** No collision occurred, so the timestamp tie-break rule is *not* exercised |
| Band price / within-band dispersion §B.2.3 | as above | `band_price`, `log_dispersion` | `test_the_single_wave_degeneracies_are_marked_degenerate_not_exercised` | **DEGENERATE** | Every (cell, band) group holds **n = 1**. The geometric mean returns the fare unchanged and dispersion returns `0.0` by the function's own rule for n < 2 |
| Source precedence §D.8.1 | as above | `SourcePrecedence.rank` | as above | **DEGENERATE** | **1 source.** `select()` is not reached at all — it returns the best source present in *both* t and t−7, and there is no t−7 |
| **T+3 shows the widest within-bucket spread, 24.9%** | `panel.json` → `dispersion`, tracing to two named observation ids | max/min ratio within the bucket | `test_dispersion_traces_to_real_observation_ids`, `test_within_band_dispersion_is_never_confused_with_the_t3_cross_band_spread` | **ESTABLISHED** | This is a **cross-band spread across 5 flights on one travel date**. It is *not* within-band dispersion, which is degenerate at n=1. The panel establishes the spread and **does not establish its cause** |

## 4. The index itself

| Claim | Evidence source | Calculation / implementation | Test | Status | Limitation |
|---|---|---|---|---|---|
| **No APIx market index value is published anywhere** | `panel.json` → `index_status`, both renderers | nothing computes one | `test_dashboard_never_claims_an_index_value`, `test_every_renderer_says_the_index_is_pending` | **ESTABLISHED** | Deliberate. The guards refuse rather than inventing a level |
| **APIx-L is PENDING, not broken** | `index_status.apix_l_computable = false` | derived from the collection dates, never asserted | `test_the_panel_holds_exactly_one_collection_wave`, `test_no_t_minus_7_counterpart_exists` | **PENDING EVIDENCE** | Implemented and fixture-tested end to end; the evidence the formula requires does not exist |
| **§C.1 is LOCKED: `I(c,t) = I(c,t−7) · J(c,t)`** — one wave gives zero matched pairs | `docs/methodology/apix_formula_spec_v2_1.md` | `src/apix/statistics/index/chaining.py` | `tests/test_pipeline_14_day.py` | **ESTABLISHED** | First date that can supply a matched pair: **2026-09-19** — see [`collection-2026-09-19.md`](collection-2026-09-19.md) |
| **Statistical coverage is NOT ESTABLISHED** | `quality.statistical_coverage` | no denominator is computed | `test_statistical_coverage_is_never_claimed`, `test_no_renderer_calls_plan_completion_coverage` | **NOT ESTABLISHED** | **AMB-8 open.** §I gates routes at "60% of expected cells" and nothing defines an expected cell. No denominator has been invented to close it |
| **Within-route carrier weighting is BLOCKED** | `within_route_weights` raises `WeightError` | guard only | `test_amb_8_and_amb_9_stay_visible` | **NOT ESTABLISHED** | **AMB-9 open** — §G.3/§G.5 carry no carrier term. Degenerate at one carrier, genuinely blocked beyond it |
| **The engine computes, chains and refuses correctly** | `tests/test_pipeline_14_day.py` 14-day fixture | `tools/analysis/engine_demo.py` → `data/engine-validation.html` | the full suite | **ESTABLISHED (synthetic)** | **Every value on that page is synthetic test data.** Nothing on it is an airfare observation or an APIx index value, and a test asserts it never merges with the real dashboard |

## 5. What APIx does not have

| Claim | Evidence source | Calculation / implementation | Test | Status | Limitation |
|---|---|---|---|---|---|
| **APIx-TPD (§M) is specified and not implemented** | `src/apix/statistics/tpd/` is an empty package | none | `test_tpd_and_uncertainty_packages_are_genuinely_empty`, `test_dashboard_states_tpd_is_specified_but_not_implemented` | **NOT ESTABLISHED** | Also 35 quotes against a `min_quotes_window` of **1,500**. Both facts are stated; neither threshold is lowered |
| **Uncertainty / bootstrap is specified and not implemented** | `src/apix/statistics/uncertainty/` is an empty package | none | `test_no_confidence_interval_is_reported_anywhere` | **NOT ESTABLISHED** | No confidence interval appears anywhere. The collection design does not yet record the admissible-flight universe per band, which such an interval would need |
| **The MoSPI CPI airfare series is REFERENCE_ONLY** | `data/mospi_cpi_airfare.json` → `role`, `is_apix_input: false` | growth computed **within a single base year only** | `tests/test_observed_panel.py` benchmark tests | **DISCLOSED LIMITATION** | It is **not** an APIx input, it does **not** validate the panel, and **MoSPI has not endorsed APIx**. A national CPI series cannot validate one route and one carrier |
| **National representativeness is NOT ESTABLISHED** | 1 route of the DGCA city-pair frame; 1 carrier | route/carrier weighting implemented, never exercised | `tests/test_observed_panel.py` limitations tests | **NOT ESTABLISHED** | DGCA route weights are *specified*, the source is **not secured**, and with one route no route weighting runs at all |
| **APIx is not production-ready** | this matrix | — | — | **DISCLOSED LIMITATION** | One wave, one route, one carrier, one source, no published index, two open ambiguities and an open OQ |

---

## Rules this table is held to

1. **A status may never be stronger than its test.** A row with no test cannot
   be **ESTABLISHED**.
2. **"Exercised" is never upgraded to "validated" in prose.**
   `test_no_rendered_surface_upgrades_exercised_into_validated` fails the build
   on the specific phrases that would do it.
3. **Four things stay distinguishable**: admissibility under §A, collection-
   contract scope under §B.2, statistical validation, and publication
   eligibility. They are not collapsed anywhere in this repository.
4. **An open question is reported as open.** AMB-8, AMB-9 and OQ-1 have no
   invented answers, and no number is published in place of one.
