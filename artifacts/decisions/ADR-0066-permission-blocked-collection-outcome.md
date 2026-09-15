# ADR-0066 — `PERMISSION_BLOCKED` as a collection outcome

> **Status:** ACCEPTED · **Date:** 2026-09-15 · **Checkpoint:** PS-platform
> **Owner:** [@slazyverse](https://github.com/slazyverse) (ingestion) ·
> **Requires co-sign:** [@Rexy-5097](https://github.com/Rexy-5097) — `schemas/` is jointly owned and
> `enums.py` is declared LOCKED
> **Bears on:** spec H.1, spec I, AMB-8

## Why this ADR exists at all

`src/apix/schemas/enums.py` opens with a standing rule:

> *"Every enum here is LOCKED for `methodology_version 2.0`. Adding or removing a member is a
> methodology change requiring an ADR and a version bump — not a code change."*

This change adds a member to `CollectionOutcome`. The rule therefore applies, and this document
exists rather than the member being slipped in as a code change.

## Context

The scheduler added for PS 26056 iterates routes × advance-purchase windows × departure bands ×
sources and attempts collection from each. Almost every attempt currently ends the same way: the
compliance gate refuses the source, because **zero of thirty registered sources clear the live gate.**

Before this change a gate refusal raised `GateRefused` and the run aborted. **Nothing was recorded.**
That is the defect: spec H.1's whole design is that *"missingness cannot be measured from a table of
successes"*, and a refusal that raises leaves no attempt row at all. A scheduled run over an
uncleared register produced an exception, not a measurement.

## The decision

Add one member:

```python
PERMISSION_BLOCKED = "PERMISSION_BLOCKED"
```

classified as **`is_collector_failure`**, which places it **inside the spec I coverage denominator**
and attributes the absence to us.

## Why not reuse an existing member

Each alternative was considered and each is wrong in a specific way:

| Candidate | Why it is wrong |
|---|---|
| `NO_FLIGHT` | **The dangerous one.** It is the *only* outcome that leaves the coverage denominator. A register where nothing is cleared would report full coverage, as though no service existed on any route. Our lack of authorisation would read as an absence of flights |
| `SOURCE_UNAVAILABLE` | Means the source was reachable and failed, or is rate-limited. A refused source is neither — it was never contacted. Conflating them makes a permanent policy state look like a transient outage that will clear on its own |
| `TECHNICAL_FAILURE` | A market fact under `is_market_fact`, and cell-carried under spec E.4. Carrying a cell forward because we lack permission would propagate a stale price on the strength of a compliance gap |
| `CAPTCHA_OR_ANTIBOT_STOP` | Closest in spirit, and still wrong: a challenge means a request *was* made and was refused at the edge. Under `PERMISSION_BLOCKED` **no request is made at all**. Merging them would lose the distinction between "we asked and were stopped" and "we never asked" — and the second is the one that proves the gate works |
| A boolean flag on the attempt | Would sit outside the H.1 partition, so `test_every_outcome_is_classified_exactly_once` could not enforce it, and the coverage denominator would acquire a new meaning silently. That test exists precisely to prevent this |

## Consequences

**Intended.** A scheduled run over an uncleared register now produces a complete, auditable attempt
table in which every cell is accounted for and every absence is attributed. The run reports total
coverage loss **attributed to us**, which is the truthful picture and exactly what the source-health
view is built to display.

**On the partition.** `tests/test_collection_contract.py::test_collector_failures_are_named` pinned the
collector-failure set at three members and now pins four. That test's purpose — forcing every new
outcome to be classified — is honoured, not weakened: the set was extended deliberately, with the
reason recorded in the test's own docstring.

**On AMB-8.** This sharpens the open question rather than resolving it. `PERMISSION_BLOCKED` keeps its
cell in the denominator, so it makes the *numerator* smaller and the coverage shortfall visible. What
counts as an `expected_cell` is still undefined, and this change does not define it.

**Not affected.** No statistical rule changes. The APW vector, departure bands, admissibility,
matching, Jevons, aggregation, chaining and the publication guards are untouched. No published value
moves, because no index value is published.

## Version bump

`methodology_version` stays at **2.1**, deliberately.

The locked-enum rule exists to stop a change to a *statistical* vocabulary passing as a code change.
`CollectionOutcome` is an **operational** vocabulary: it records what happened during acquisition. The
test that decides whether a change is statistical is whether it can move a published number, and this
one cannot — it adds a way to record an event that previously raised an exception, and it reclassifies
no existing member.

**If @Rexy-5097 disagrees, the correct resolution is a `methodology_version` bump to 2.2 and a
re-freeze, not reverting the member** — because the alternative is a scheduler that cannot record why
it collected nothing.
