# Contribution ownership policy

APIx has exactly three contributor identities. Every task has exactly one
primary owner, and the Git identity used for a commit must be the identity of
the contributor who owns that task.

This is not bookkeeping. Ownership is how a reviewer knows whether the person
who wrote a change was the person who understands its consequences.

## The three contributors

| Identity | GitHub | Role |
|---|---|---|
| **REXY-5097** | [@Rexy-5097](https://github.com/Rexy-5097) | Principal engineering owner |
| **SLAZYVERSE** | [@slazyverse](https://github.com/slazyverse) | Data engineering owner |
| **BASANT-CREATOR** | [@Basant-creator](https://github.com/Basant-creator) | Product engineering owner |

## Ownership matrix

### Rexy-5097 — principal engineering owner

Owns the most statistically sensitive work. If a change alters what a published
number means, it is Rexy's.

- Overall architecture, repository architecture, statistical architecture
- The deterministic statistics boundary and its CI enforcement
- Statistical contracts
- Matched-item design; Tier 1 / Tier 2 / Tier 3 matching
- Jevons elementary relatives; cell-level chaining
- Young / Modified Laspeyres aggregation; route aggregation
- National APIx-L
- APIx-TPD: specification, estimator, splice, validation
- Bootstrap and uncertainty
- The six controlled experiments
- Statistical validation and benchmark methodology
- Publication and vintage statistical logic
- Methodology documentation
- Architecture CI, cross-domain contracts, complex integration
- Final technical architecture review

### slazyverse — data engineering owner

Owns everything between a website and a canonical observation.

- Ingestion architecture; collectors; source adapters
- Airline and OTA collection
- The compliance gate, robots.txt handling, rate limiting
- Source registry
- Raw snapshots; Bronze/Silver ingestion
- Normalisation implementation; deduplication
- Source quality; parser fixtures
- Data quality; collection reliability; ingestion testing

### Basant-creator — product engineering owner

Owns everything a user sees.

- FastAPI; API implementation; SDMX serialisation; backend serving
- Next.js; dashboard; ECharts
- Methodology switchboard UI; estimator comparison UI
- Route intelligence; provenance UI; publication/vintage UI
- Frontend testing; product presentation layer

## Automatic task-to-identity routing

Ownership is derived from the task, not asked about. For every task:

1. Determine the assigned owner from the matrix above.
2. Verify the local Git identity matches that owner.
3. Verify GitHub authentication is that owner.
4. Ensure the branch prefix matches that owner.
5. Commit as that owner.
6. Push as that owner.
7. Open the PR as that owner.

Worked examples:

| Task | Owner |
|---|---|
| Implement the Jevons elementary relative | Rexy-5097 |
| Add an IndiGo collector | slazyverse |
| Build the provenance screen | Basant-creator |
| Freeze `apix_formula_spec_v1.md` | Rexy-5097 |
| Add a rate limiter to the compliance gate | slazyverse |
| Add the SDMX-JSON serialiser | Basant-creator |

## Cross-domain tasks

When a task genuinely spans domains:

- Select **one** primary owner — the domain that carries the risk, not the one
  with the most changed lines.
- Use that owner's identity for the branch, commits and PR.
- Request review from every affected domain owner.

A schema change touching `schemas/` is the common case: `CODEOWNERS` requires
both Rexy-5097 and slazyverse, because a canonical contract change breaks either
collection or computation.

## Rules that do not bend

- **Never default to Rexy-5097** merely because Rexy-5097 owns the repository.
- **Never fake authorship.** Commit author fields are not verified by Git, which
  is exactly why setting another contributor's name without their credentials is
  falsification rather than convenience.
- **Never rewrite history to balance contribution statistics.**
- **Never open meaningless PRs to inflate a contribution count.**
- **If the required GitHub identity is unavailable, STOP before commit and push.**
  Do not substitute another contributor. Report the blocker and wait.

## Verifying identity before committing

```bash
git config user.name
git config user.email
gh auth status
```

Per-repository identity, so a machine can hold more than one contributor:

```bash
git config user.name  "<contributor>"
git config user.email "<contributor's GitHub email>"
```

Switching the authenticated GitHub account:

```bash
gh auth switch --user <contributor>
```

See [development-setup.md](development-setup.md) for multi-account setup.
