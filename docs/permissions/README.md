# `docs/permissions/` — access requests, and their status

> ## ⚠ NOTHING IN THIS DIRECTORY IS A GRANT OF ACCESS
>
> Every document here is a **REQUEST THAT APIx INTENDS TO SEND, OR HAS SENT**. None of them is a
> permission, a licence, an agreement, or evidence of one.
>
> **No source has granted APIx automated access. No request in this directory has been answered.**

---

## Why this directory exists

The 2026-09-15 source discovery audit and acquisition sweep — `compliance/source-audit-2026-09-15.md`
and `compliance/acquisition-sweep-2026-09-15.md`, both on the `feat/slazy/source-register-audit`
branch and not yet merged — established a structural result: APIx's compliance gate requires
`automation_gate: AUTOMATION_ALLOWED`, which the
[source register](../../source_registry/registry.yaml) defines as *"the source's own published terms
permit it. Requires POSITIVE evidence, quoted."*

Consumer airline and OTA terms are either **prohibitive or silent**. None publishes an affirmative
permission to collect automatically, because there is no commercial reason to. So the gate can never
be satisfied by reading more terms — silence is not permission, and the register says so in as many
words.

**Two things can produce the positive evidence the gate needs: a written permission, or an official
programmatic channel under agreement.** Both have to be asked for. That is what these documents do.

## Status

| Request | Source | Sent | Response | Register effect |
|---|---|:---:|:---:|---|
| [Alliance Air](alliance-air-automated-access-request.md) | `alliance_air` | **NOT SENT** | — | **None.** Stays `AUTOMATION_UNKNOWN` |
| [IndiGo](indigo-automated-access-request.md) | `indigo`, `indigo_ndc` | **NOT SENT** | — | **None.** Stays `AUTOMATION_PROHIBITED` / `AUTOMATION_ALLOWED_WITH_PERMISSION` |

**Update this table when a request is actually sent, and again when one is answered.** A drafted
letter changes nothing.

## What a granted permission would and would not do

If a source replies in writing permitting rate-limited automated retrieval, the sequence is:

1. The reply text is recorded **verbatim** in `registry.yaml` as `tos_evidence` with its date and
   evidence grade, exactly as every other status in that file is.
2. `automation_gate` is changed to `AUTOMATION_ALLOWED` **by a reviewed pull request owned by
   [@slazyverse](https://github.com/slazyverse)** — never by a flag, an environment variable or an
   argument. The gate has no override and none is to be added.
3. `data_rights` is set from whatever the reply says about retention and republication. A permission
   to *retrieve* is not a permission to *retain*; the acquisition sweep found sources that grant the
   first and forbid the second.
4. `data_admissibility` remains a **separate** methodology question. A permitted fare is not
   automatically an admissible one.

**Even all four clearing does not make automated data index input.**
[`collection-windows.yaml`](../../source_registry/collection-windows.yaml) admits only `@primary`
runs, `@primary` is reserved to the manual Day-1 contract, and adopting any automated channel as
index input is an owner decision recorded in an ADR. The code that enforces it,
`src/apix/ingestion/collectors/index_boundary.py`, is on the `feat/slazy/indigo-ndc` branch and not
yet merged.

## What these requests deliberately do not ask for

They do not ask for anything APIx has already ruled out, and they say so on their face, because a
request that leaves it ambiguous invites the wrong grant:

- no CAPTCHA solving, and no third party doing it on our behalf
- no stealth browsers, driver patching or fingerprint spoofing
- no proxy or IP rotation, and specifically none triggered by a block, challenge or `429`
- no retry past an access challenge
- no undocumented or private endpoints
- no resale or redistribution of the underlying fare data

Each is a standing prohibition in [`CLAUDE.md`](../../CLAUDE.md) and the
[collection control contract](../../compliance/collection-control-contract.md), not a concession
offered in exchange for access.

## Drafting rules for anything added here

- State the statutory context (MoSPI PS 26056, CPI augmentation) and that the purpose is statistical,
  not commercial.
- Name the **exact fields** wanted. A vague request gets a vague answer, or none.
- Name a **concrete** rate ceiling, in requests per day, with the interval between them.
- Offer the alternative channel explicitly: permission for the website **or** an official
  API/NDC/B2B research channel. The second is better for both parties and should be presented that way.
- Never imply access has already been taken. APIx has collected **zero** fares automatically from any
  source, and the letters say so.
- Give a named technical contact for onboarding.
