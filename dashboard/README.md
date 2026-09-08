# dashboard/ — Next.js product surface

**Owner:** [@Basant-creator](https://github.com/Basant-creator)

## Not yet implemented

Checkpoint 5. Next.js + TypeScript + Tailwind + ECharts.

## The five screens

Each answers one question the primary user — a statistical analyst evaluating
whether the series is adoptable — would actually ask, in the order they would
ask it.

| Screen | Question it answers |
|---|---|
| National index | What is the number? |
| Methodology switchboard | How was it computed? |
| Method comparison | Is the movement real? |
| Route intelligence | What moved it? |
| Provenance and compliance | Can it be trusted? |

The secondary user is a monetary-policy economist who needs the series, its
revision status and its uncertainty.

## Presentation rules that are methodology, not design

- **Growth rates are compared, never levels.** The two estimators accumulate
  along different paths, so a level gap between them is an artifact of divergence
  since the base period, not a monthly composition effect.
- **"Effective N" is never displayed as a single number**, because it is not one
  number — Kish? cluster-adjusted? independent product count? The headline shows
  three counts that each mean exactly one thing: matched items contributing
  relatives, unique offers observed, and independent source groups after
  collapsing shared-inventory platforms.
- **Operational statistics sit one click deeper**, on the provenance screen, so
  the headline stays readable to a policy user.
- **`source_type` is rendered distinctly** and never blended silently.
- **Quality caveats are shown on the headline**, not in a footnote: the
  unit-value caveat when Tier-3 weight share exceeds 25%, and the coverage caveat
  when suppressed weight exceeds 15%.
- **A synthetic demonstration is labelled on the chart itself**, not in a
  footnote. A clearly declared controlled experiment is more credible than a
  real-data chart that could have been chosen for its shape.

## Anything marked illustrative is a placeholder

Every figure in the dossier's screen mockups is illustrative. None may reach an
external artifact without being replaced by a measured value.
