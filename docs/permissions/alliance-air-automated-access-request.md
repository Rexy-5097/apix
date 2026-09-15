# Request to Alliance Air — automated access to publicly displayed airfare data

> **STATUS: DRAFT. NOT SENT. NO PERMISSION HELD.**
> Owner: [@slazyverse](https://github.com/slazyverse) · Drafted 2026-09-15 · See [README](README.md)
>
> Register effect while unsent and unanswered: **none.** `alliance_air` remains
> `automation_gate: AUTOMATION_UNKNOWN`, which blocks collection.

**Suggested recipients.** Chief Commercial Officer and Chief Information Officer, Alliance Air
Aviation Limited, with a copy to `support@allianceair.in` (the address published on
`allianceair.in`). Confirm current named officers from the *Our Management* and *Board of Directors*
pages before sending. If the project's MoSPI counterpart is willing to co-sign or forward, that is
materially stronger than a cold approach — see the note at the end.

---

## Letter

**Subject: Request for permission — rate-limited automated retrieval of published airfare data for CPI research (MoSPI Problem Statement 26056)**

Dear Sir or Madam,

**1. Who we are and why we are writing**

We are the APIx project team, working on **Problem Statement 26056** issued by the **Data
Informatics & Innovation Division, Ministry of Statistics and Programme Implementation (MoSPI)**.
The problem statement calls for the development of a real-time airfare price index for India to
**augment the Consumer Price Index**, which the Reserve Bank of India uses under the flexible
inflation-targeting framework.

Airfare is the weakest measurement point in the CPI transport basket. Every neighbouring item is
priced from an administrative source with a single authoritative provider; airfare is collected from
commercial, dynamically priced websites, and no administrative feed reports the transacted consumer
price. Our work is to measure it properly rather than approximately.

We are writing to ask permission for something we have deliberately **not** done without it.

**2. What we have done so far, stated plainly**

We have collected **35 airfare observations manually** — a person, in an ordinary browser — for a
single route on a single day, under a frozen collection protocol with a full evidence trail. We have
built the automated collection software, and it is **switched off**: it will not issue a request to
any source that our compliance register has not cleared, and it has never cleared one.

**To date APIx has automatically collected zero fares from Alliance Air or from any other airline or
travel website.** We would like to change that with your permission, and not otherwise.

**3. What we are asking for**

Either of the following would resolve our position, and we would be glad of whichever suits you:

> **(a) Written permission** for rate-limited automated retrieval of the airfare information already
> displayed publicly on `allianceair.in`, on the terms in section 5 below; **or**
>
> **(b) Access to an official machine-readable channel** — an API, an NDC interface, a B2B or agency
> interface, a research or statistical feed, or a periodic data extract — under whatever agreement
> you consider appropriate.

**We would prefer (b).** A structured channel is better for both parties: it puts no load on your
booking engine, it is unaffected by changes to your website, and it gives us the fare components
decomposed, which a rendered page usually does not. If a suitable channel exists but requires a
partner or research agreement, please tell us what the process is and we will follow it.

**4. Exactly what we would retrieve**

We ask only for what a member of the public already sees on a search results page. Per flight:

| | Fields |
|---|---|
| Itinerary | origin, destination, travel date, scheduled departure time, flight number, operating carrier, number of stops, journey duration |
| Fare | fare family or product name as displayed, total payable fare, and where displayed: base fare, taxes, **user development fee**, and convenience or reservation charges, with currency |
| Entitlements | checked baggage allowance, and change and cancellation conditions as displayed |
| Provenance | the retrieval timestamp, and a cryptographic hash of the retrieved page for audit |

We request **no** personal data, no passenger data, no booking, payment, loyalty or account
information, and nothing behind a login. We would search as a general member of the public, signed
out, for a single adult in economy class — our frozen protocol mandates signed-out collection, and
our software refuses to run otherwise.

The four-way fare split above is a requirement of the problem statement itself, which asks that a
price index "separates base fare from taxes, user-development fee and convenience charges". Your
published domestic tariff sheet sets out these components at the tariff level; what we lack is which
of them applies to a specific flight on a specific date, which only a search result shows.

**5. The limits we would operate under, and commit to in writing**

These are constraints our software already enforces, not undertakings we would have to add:

| | Commitment |
|---|---|
| **Volume** | At most **seven search requests per route per day** — one for each advance-purchase window we measure. For a single route that is seven requests daily, and we would agree any lower ceiling you set |
| **Pacing** | Requests issued **sequentially, never in parallel**, with a minimum of **30 seconds** between them. The floor is enforced in code and cannot be configured below 10 seconds |
| **Window** | Collection confined to one declared hour of the day, to be agreed with you, and not during peak booking periods if you would rather it were not |
| **Identification** | A clearly identifying user agent naming the project, with a contact address, so you can attribute and contact us at any time |
| **No circumvention** | **We will not solve or bypass CAPTCHAs, defeat bot detection, use stealth browsers, spoof fingerprints, or rotate IP addresses.** We operate from a single declared, stable egress. Our code has no path from a block, a challenge or an HTTP 429 to changing address or retrying |
| **Access challenge = stop** | If any control is presented, our collector **stops for that source for the whole run**, records the event, and does not retry. This is a typed outcome in our software, not a policy note |
| **robots.txt** | Honoured as binding. A `Disallow` on a path we need ends the matter, whatever your terms permit |
| **No booking** | We never complete, hold or cancel a booking. We are a look-only client, and will never generate a segment |
| **No resale** | The retrieved fare data will **not** be resold, redistributed, licensed or published as a dataset |
| **Retention & security** | Retained only as long as needed for statistical audit, on access-controlled storage, with a cryptographic hash chain so any alteration is detectable. We will honour any retention limit you specify, and delete on request |
| **Attribution** | Alliance Air named as a source in any publication, in whatever form you prefer. We will not suggest that you endorse our results |
| **Withdrawal** | Immediate and unconditional, on request, by email, with no explanation required |

**6. What would be published**

An **aggregate price index** and statistical analysis. No individual fare quote would be republished
as a price list, no fare of yours would be presented as current or bookable, and nothing we publish
would function as a fare comparison or booking service. The output is a statistical series of the
kind a national statistical office publishes.

We would be glad to share our methodology, and the index itself, with you before any publication.

**7. Why we are approaching Alliance Air**

Three reasons, and we would rather state them than leave them implicit. Alliance Air already
publishes its domestic tariff sheet and unbundled services and charges openly, which suggests a
disposition towards transparency that this request depends on. Its published terms and conditions —
which we have read in full — place no restriction on automated retrieval, so we are asking rather
than assuming. And as a wholly government-owned carrier, Alliance Air has a natural interest in the
integrity of an official statistic that measures its own sector.

We recognise that the Alliance Air network does not currently include the Delhi–Mumbai sector our
pilot has measured. That is not an obstacle: the measurement design is route-agnostic, and Delhi–Shimla,
Kolkata–Guwahati, Hyderabad–Tirupati or Bhubaneswar–Rourkela would each serve as well, and would extend
the index's coverage to regional sectors that are otherwise absent from it.

**8. What we are not asking for**

We are not asking for commercial terms, a partnership, preferential access, confidential data, fares
not shown to the public, or anything that would place us in a different position from any other
visitor to your website — except that we would be acting with your knowledge and consent rather than
without it.

**9. Next step**

A single line by email confirming or declining (a) or (b) is sufficient to settle our position, and
we would be grateful for it either way. **A refusal is a useful answer and will be recorded and
respected; we will not re-approach through another route.** If it would help, we are happy to take a
short call, or to send our collection protocol and compliance controls for your technical team to
review before you decide.

Yours faithfully,

**APIx project team — Problem Statement 26056, MoSPI Data Informatics & Innovation Division**

Technical onboarding and compliance contact: *[named engineer, role, email, telephone — complete
before sending]*
Project repository: `https://github.com/Rexy-5097/apix`
Methodology and compliance documentation available on request.

---

## Notes for whoever sends this

- **Complete the contact block.** An unsigned request with no named human is easy to ignore, and
  correctly so.
- **Confirm the recipients** from the live *Our Management* and *Board of Directors* pages. Do not
  send to an address inferred from a pattern.
- **The MoSPI channel is worth trying first.** Alliance Air is government-owned and the problem
  statement is MoSPI's. A request forwarded by, or copied to, the project's MoSPI counterpart is a
  different letter in substance, even with identical text — and it opens the possibility of a
  statutory route under the Collection of Statistics Act, 2008, which would be stronger than any
  commercial permission. See [`acquisition-strategy.md`](../engineering/acquisition-strategy.md).
- **Record the outcome in the register.** Any reply goes into `registry.yaml` verbatim as
  `tos_evidence`, with its date, and the gate changes only by a reviewed pull request.
- **A non-reply is not a permission.** If there is no answer, `alliance_air` stays
  `AUTOMATION_UNKNOWN` and stays blocked.
