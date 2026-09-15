# Request to IndiGo — NDC research access, or permission for rate-limited automated retrieval

> **STATUS: DRAFT. NOT SENT. NO PERMISSION HELD.**
> Owner: [@slazyverse](https://github.com/slazyverse) · Drafted 2026-09-15 · See [README](README.md)
>
> Register effect while unsent and unanswered: **none.** `indigo` (website) remains
> `automation_gate: AUTOMATION_PROHIBITED`; `indigo_ndc` remains
> `AUTOMATION_ALLOWED_WITH_PERMISSION`. Both block collection.

**Suggested recipients.** Chief Digital Officer / Chief Information Officer and Chief Commercial
Officer, InterGlobe Aviation Limited (IndiGo), with a copy to the NDC or distribution team if a named
contact can be identified. Confirm current officers before sending. Section 8 asks a question IndiGo's
own IT team will want the answer to, which may be the most reliable way in.

---

## Letter

**Subject: Request for NDC/API research access — airfare measurement for CPI augmentation (MoSPI Problem Statement 26056). Also: your developer portal is returning HTTP 502**

Dear Sir or Madam,

**1. Who we are**

We are the APIx project team, working on **Problem Statement 26056** issued by the **Data
Informatics & Innovation Division, Ministry of Statistics and Programme Implementation (MoSPI)**.
The problem statement calls for a real-time airfare price index for India to **augment the Consumer
Price Index**, which the Reserve Bank of India uses under the flexible inflation-targeting framework.

**2. Why we are writing to IndiGo specifically**

Our pilot measurement is **Delhi–Mumbai on IndiGo**. We hold 35 audited fare observations on that
sector, collected on 2026-09-12 across seven advance-purchase windows and five departure-time bands,
under a frozen protocol with a complete evidence trail. IndiGo is the incumbent source of the only
real data this project has.

Those observations were collected **manually — by a person, in an ordinary browser**, one search at a
time. That was a deliberate choice, and section 3 explains why.

**3. What we have not done, and why**

We have read IndiGo's published terms. The clause available to us prohibits "any automated use",
"robots", and "any spider, robot … scraper", while expressly exempting "internet browser usage" by a
person. We have taken that at its word and honoured it exactly:

> **APIx has never automatically collected a fare from `goindigo.in`, and our software will not do
> so.** Our automated collector refuses to issue a request to any source our compliance register has
> not cleared. IndiGo's website is recorded in that register as `AUTOMATION_PROHIBITED`, and the
> collector has never been cleared for it. There is no override — no flag, no environment variable,
> no configuration setting — and a test fails our build on the day any source becomes cleared, so
> this cannot change silently.

We are writing because the honest way to obtain automated access is to ask for it.

**4. What we are asking for**

> **(a) Access to IndiGo's NDC interface** for statistical research — UAT or production, under
> whatever agreement you consider appropriate; **or**
>
> **(b) Written permission** for rate-limited automated retrieval of the fare information already
> displayed publicly on `goindigo.in`, on the terms in section 6; **or**
>
> **(c) Any other machine-readable channel** you would prefer us to use — a B2B or agency interface,
> a research feed, or a periodic extract.

**We would much prefer (a).** Your developer portal describes an `IATA_AirShoppingRQ` served by a
Navitaire NDC Gateway, which is exactly the structured, decomposed fare data our methodology needs
and which a rendered results page frequently does not expose. It would also put no load at all on
your consumer booking engine.

We understand NDC programmes are ordinarily scoped to accredited sellers of travel. **We are not a
travel seller and will never issue a ticket** — we shop without booking, and we have no interest in
distribution. If that makes standard NDC onboarding inapplicable, we would welcome a pointer to
whatever research, academic or institutional arrangement would fit, or confirmation that none exists
so we can record the position and stop asking.

**5. Exactly what we would retrieve**

Only what a member of the public already sees on a results page. Per flight:

| | Fields |
|---|---|
| Itinerary | origin, destination, travel date, scheduled departure time, flight number, marketing and operating carrier, number of stops, journey duration |
| Fare | fare family as displayed (for example *Saver*), total payable fare, and where available: base fare, taxes, **user development fee**, and convenience or reservation charges, with currency |
| Entitlements | checked baggage allowance, and change and cancellation conditions as displayed |
| Provenance | the retrieval timestamp, and a cryptographic hash of the retrieved response for audit |

We request **no** personal, passenger, booking, payment, loyalty or account data, and nothing behind
a login. We search as a general member of the public, **signed out** — our frozen protocol mandates
it and our software raises an error on any other setting, partly because a signed-in fare may be a
member fare and therefore a different thing from the price an ordinary household pays.

The four-way fare split is a requirement of the problem statement, which asks that the index
"separates base fare from taxes, user-development fee and convenience charges".

**6. The limits we would operate under, and commit to in writing**

Enforced in our code today, not undertakings we would have to add:

| | Commitment |
|---|---|
| **Volume** | At most **seven search requests per route per day** — one per advance-purchase window. For Delhi–Mumbai that is seven requests daily. We will accept any lower ceiling you set |
| **Pacing** | **Sequential, never parallel**, minimum **30 seconds** apart. The floor is enforced in code and cannot be set below 10 seconds |
| **Window** | One declared hour per day, to be agreed, and away from peak booking hours if you prefer |
| **Identification** | A clearly identifying user agent naming the project with a contact address, so you can attribute and reach us at any time |
| **No circumvention** | **No CAPTCHA solving, no bot-detection bypass, no stealth browsers, no fingerprint spoofing, no IP rotation** — and no third-party service doing any of it on our behalf. Single declared stable egress. Our code has no path from a block, challenge or HTTP 429 to changing address or retrying |
| **Access challenge = stop** | Any control presented stops that source for the entire run, is recorded, and is never retried. A typed outcome in our software, not a policy note |
| **robots.txt** | Binding. A `Disallow` on a path we need ends the matter regardless of what any permission says |
| **No booking** | Look-only. We never complete, hold or cancel a booking, and never generate a segment. Our look-to-book ratio is, by construction, infinite — we would accept a hard cap on requests to make that harmless |
| **No resale** | Fare data will **not** be resold, redistributed, licensed or published as a dataset |
| **Retention & security** | Retained only as long as needed for statistical audit, access-controlled, with a cryptographic hash chain making alteration detectable. Any retention limit you specify will be honoured, and we will delete on request |
| **Attribution** | IndiGo named as a source in any publication, in whatever form you prefer, with no suggestion that you endorse our results |
| **Withdrawal** | Immediate and unconditional on request, by email, no explanation required |

**7. What would be published**

An **aggregate price index** and statistical analysis. No individual fare republished as a price
list, no fare presented as current or bookable, and nothing functioning as a fare comparison or
booking service. We would be glad to share the methodology and the index with you before publication.

**8. A practical note, offered in good faith**

**Your developer portal appears to be down.** On 2026-09-15 we requested each documented path —
`/`, `/ndcAPI`, `/authentication`, `/FAQs`, `/airshopping`, `/offerPrice` and `/serviceList` — and every
one returned **HTTP 502 Bad Gateway** from `Microsoft-Azure-Application-Gateway/v2`. The Akamai edge
in front of it is healthy and passing requests through, so the fault appears to be at the origin
rather than in delivery. We first saw this on 2026-09-10 and it has persisted since. We received no
401, 403 or 429 and no bot challenge at any point, so we do not believe we were being refused — the
service simply does not answer.

We mention it because registration is not currently possible through that portal, and your team may
not be aware.

**9. One question we would like answered either way**

The prohibiting clause we found is published in IndiGo's **loyalty programme** terms. We have not
been able to retrieve the general website Terms of Use — the host does not serve our client, and we
have not attempted to work around that.

**Could you confirm which document governs automated retrieval of publicly displayed fares?** If the
general Terms of Use prohibit it too, we will record that as settled and close the question. We would
rather have the correct answer than the convenient one.

**10. Next step**

A single line by email is sufficient, and we would be grateful for it either way. **A refusal is a
useful answer and will be recorded and respected; we will not re-approach through another route, or
through a third party.** If it helps, we will send our collection protocol and compliance controls for
your technical team to review first.

Yours faithfully,

**APIx project team — Problem Statement 26056, MoSPI Data Informatics & Innovation Division**

Technical onboarding and compliance contact: *[named engineer, role, email, telephone — complete
before sending]*
Project repository: `https://github.com/Rexy-5097/apix`
Methodology and compliance documentation available on request.

---

## Notes for whoever sends this

- **Complete the contact block** before sending.
- **Section 8 is the strongest opening.** A specific, reproducible, well-diagnosed outage report with
  timestamps is useful to IndiGo whatever they decide about us, and it routes naturally to an
  engineering team rather than a legal inbox.
- **Do not soften section 3.** That we have honoured the prohibition, in code, with a test enforcing
  it, is the whole basis of the request. It is also verifiable from the public repository.
- **Section 9 cuts both ways and should stay.** The answer may be that automated retrieval is
  prohibited outright, in which case the register records it as `NOT_PERMITTED` on quoted evidence
  and the website question is closed for good. That is a better outcome than a standing `UNKNOWN`.
- **Record the outcome in the register.** Any reply goes into `registry.yaml` verbatim as
  `tos_evidence`, with its date, and the gate changes only by a reviewed pull request.
- **A non-reply is not a permission.** `indigo` stays `AUTOMATION_PROHIBITED` and `indigo_ndc` stays
  `AUTOMATION_ALLOWED_WITH_PERMISSION`, and both stay blocked.
