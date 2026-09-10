# source_registry/ — what may be collected, and on what evidence

**Owner:** [@slazyverse](https://github.com/slazyverse) (per `.github/CODEOWNERS`)
**Status:** pre-acquisition audit, Checkpoint 2F · **no source is cleared for collection**

`registry.yaml` is the artifact [`context/tech_stack.md`](../context/tech_stack.md)
names and [`src/apix/ingestion/README.md`](../src/apix/ingestion/README.md)
describes: *"the source registry, recording what is committed for the prototype
and what is **deferred rather than silently dropped**."*

## Read it as an evidence log, not a permission list

Every entry records **what was seen and when**. Nothing in it authorises
collection.

`robots.txt` is a crawling directive, not a licence. A path it does not
disallow may still be governed by terms that prohibit automated collection —
and this project has committed to honouring the directive regardless of what any
terms say, so a disallowed path is a stop signal either way.

**`NOT_VERIFIED` is the default and it is not a soft yes.** It means the
document was not read. Nothing is collected from a source whose terms have not
been read.

## What this audit found

| | |
|---|---|
| Sources catalogued | **14** across four channels, plus 4 reference sources |
| Terms of service retrieved | **0** |
| `robots.txt` retrieved | 6 of 11 web sources |
| **`robots.txt` disallowing the exact path APIx needs** | **4** — Air India Express, EaseMyTrip, Cleartrip, ixigo |
| Sources cleared for collection | **0** |

Four sources publish a `Disallow` covering the fare-search or fare-availability
path itself:

```
airindiaexpress.com   Disallow: /flight-availability
easemytrip.com        Disallow: /flight-search/listing*
cleartrip.com         Disallow: /flights/search*    (after a blanket Allow: /)
ixigo.com             Disallow: /flights/search
```

Cleartrip is the instructive one: a general `Allow: /` followed by a specific
`Disallow: /flights/search*`. **The general permission does not survive the
specific prohibition**, and an implementation that reads only the first line
would get this exactly wrong.

Two sources — Akasa Air and SpiceJet — carry no `Disallow` over the search path.
That is the *absence of one objection*, not a permission. Their terms remain
unread.

## Method, and its limits

Published `robots.txt` files were retrieved. **No fare page was requested, no
search was executed against any source, and no access control was tested.**
`captcha_or_interstitial_observed` is `NOT_TESTED` everywhere for that reason:
finding out requires collecting, and this checkpoint does not collect.

Five sources — IndiGo, Air India, MakeMyTrip, Goibibo, Yatra — could not be
retrieved (timeout or TLS failure). A timeout is an audit outcome. It was not
retried with different transport and nothing was circumvented.

`data.gov.in` returned **HTTP 403** to the schedule-resource request. Recorded as
an access outcome. Not worked around.

> **Environment caveat, material to all of the above.** The audit host sits
> behind a TLS-intercepting proxy — a `git push` to github.com failed with
> `SEC_E_UNTRUSTED_ROOT`, and `goindigo.in` returned *"self signed certificate in
> certificate chain"*. Retrieved content was served through an intermediary. The
> recorded bodies are internally consistent and site-specific, but **every one
> should be re-retrieved from an un-intercepted network before it is relied on**,
> and the five failures may be artifacts of the proxy rather than properties of
> the sources.

## Source groups are external evidence, never inferred

Spec B.6: *"Two aggregators reselling one inventory feed are **one** observation,
not two."* Effective sample size is computed on groups, so group membership
decides what `n` means — and it is a fact about **corporate ownership and
inventory supply**, not about fares.

Two sites showing different prices in different interfaces is **not** evidence of
independence. Neither is showing the same price evidence of dependence.

One group is assigned: `mmt_group` = MakeMyTrip + Goibibo, on the dossier's
explicit statement (p.12) that they are *"Same corporate group and shared
inventory."* Every other group is `independence: UNKNOWN` and is provisional —
each aggregator has its own group id **only because there is no evidence to merge
them**, not because independence has been established.

**This blocks OQ-A2.** Cross-source spread is defined *"within and across
independent source groups"*, and it cannot be interpreted without knowing the
effective `n`.

## Updating an entry

Change a status only with quoted text and a date. Downgrading to `NOT_VERIFIED`
when evidence goes stale is a normal edit, not a regression — terms change, and
an entry that says `CLEARLY_PERMITTED` on eighteen-month-old evidence is worse
than one that admits it does not know.
