# KNOWN LIMITATIONS — Stage-1 DISCOVER (2026-09-30)

Honest gaps. Nothing here is hidden or dressed up (task §51).

## Credentials missing (adapters IMPLEMENTED, CONFIGURATION_REQUIRED)

| Source | What unlocks it | Impact today |
|---|---|---|
| Jooble | `JOBAGENT_JOOBLE_API_KEY` (free, one key) | localized discovery in ALL 10 countries — biggest single win |
| Adzuna | `JOBAGENT_ADZUNA_APP_KEY` + `JOBAGENT_ADZUNA_APP_ID` | per-country markets |
| Reed | `JOBAGENT_REED_API_KEY` (free, instant) | UK structured discovery |

## Blocked / fragile (pre-existing, unchanged)

* **Indeed** — IP-blocked from datacenter hosts. Not removed; documented.
* **LinkedIn** — guest scraping works but is brittle; kept as a tier-3
  source and treated as PARTIALLY_SUPPORTED.

## ATS providers detected but not queryable

Workday, Teamtailor, Workable, BambooHR, Jobvite, iCIMS, SAP SuccessFactors,
Comeet, Taleo, PageUp — `ats_detect` identifies their career URLs, but no
adapters exist (their APIs need per-tenant tokens or scraping is
auth-walled). Detection still routes AWAY from JSON-LD parsing and records
the provider in company cache. Building adapters = follow-up work, one
file each, registered like the existing five.

## Geo-signal weaknesses (measured, live)

* **builtin.com** — remote listings carry no country text; only listings
  with explicit locations (US/CA/IN observed) pass the country gates
  (1/10 PASS in the live run; IN: 20 jobs ingested).
* **weworkremotely** — RSS lacks structured geo; 0/10 PASS against strict
  country gates. Kept as long-tail; feeds remain useful for Remote.
* **smartrecruiters** — default company boards post few AI roles
  (0/10 PASS on jobs, endpoint healthy). Extending via
  `smartrecruiters_companies` key is a config change, not code.

## Search-engine job discovery

Evaluated (task §9) and deliberately NOT implemented: SERP scraping is
fragile and against the maintenance bar. Google Careers (Google's own jobs
site) is a different thing and is NOT what this section means. Revisit if an
official API or a stable JobPosting-search endpoint becomes available.

## Concurrency

Ingest is sequential per country (bounded, rate-limited per source via the
existing `rate_limiter`). Sources within a country run one at a time —
deliberate: polite crawling, no request storms. Parallelizing is possible
later (asyncio.gather with a semaphore) without touching adapters.

## Not done here (out of scope by design)

* N2–N5 (per-user scheduled cycles, run-state, build-ship, admin panel) — untouched.
* No UI changes (task §57) — `/api/discovery/registry` exposes data for a future card.
* No pagination additions to scrapers that already paginate (arbeitnow 3
  pages, jooble 2, adzuna 2); scrapers with single-shot APIs unchanged.
