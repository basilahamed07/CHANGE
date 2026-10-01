# STAGE-2 CLASSIFY — Classification Rules

`app/classification.py` implements one deterministic priority chain followed by
a bounded AI fallback for the residue. **Strongest evidence wins; nothing is
fabricated.**

## Priority chain (task §3)

| # | source | fires when | confidence | example |
|---|---|---|---|---|
| 1 | `STRUCTURED_COUNTRY` | explicit ISO/`country_code` field on the job | HIGH | `country_code: "DE"` |
| 2 | `TEXT_LOCATION` | country name/alias in the location text | HIGH | `"United Kingdom (Remote)"` → GB |
| 3 | `CITY_MAP` | city-only location | HIGH | `"Berlin"` → DE |
| 4 | `DESCRIPTION` | deterministic description evidence | MEDIUM | `"Location: Dublin, Ireland"` → IE |
| 5 | `ATS_METADATA` | JobPosting `addressCountry`/`country` | HIGH | ATS payload country field |
| 6 | `SOURCE_HINT` | only the searched country remains | **LOW** | unconfigured place under the SG search → SG |
| 7 | `AI_FALLBACK` | deterministic chain returned UNKNOWN **and** an AI client is present | MEDIUM (≥0.5 only) | validated LLM country |
| 8 | `UNKNOWN` | no usable evidence | UNKNOWN | `"Nowhereville"`, no hint |

Ordering note: multi-location, remote-qualified and region-only cases are
resolved between tiers 3 and 4 (below), because the location text is the job's
own structured signal and description is secondary for them.

### Structured country vs ATS metadata
An explicit `country_code` is tier 1. An ATS structured field is checked in the
same block; if present it is reported as `ATS_METADATA` (HIGH) rather than
`STRUCTURED_COUNTRY`, so the audit reflects the actual evidence.

## Country normalization (`COUNTRY_ALIASES`)

`normalize_country_code(token) -> ISO-2 | None` accepts the configured countries'
aliases. Anything outside the 10 configured countries returns `None` — an
unconfigured place is **never** mapped to a configured country.

| code | name | representative aliases |
|---|---|---|
| DE | Germany | germany, deutschland, de |
| NL | Netherlands | netherlands, holland, the netherlands, nl |
| IE | Ireland | ireland, republic of ireland, eire, ie |
| GB | United Kingdom | uk, u.k., united kingdom, great britain, britain, gb, england, scotland, wales |
| SG | Singapore | singapore, sg |
| AE | United Arab Emirates | united arab emirates, uae, u.a.e., emirates, ae |
| IN | India | india, in |
| CA | Canada | canada, ca |
| AU | Australia | australia, au |
| PL | Poland | poland, pl |

The region string stored in `jobs.location_region` comes from the country
registry when available (`GB` → `"UK"`, `AE` → `"UAE"`), so it matches the
strings the pipeline and country strategy already use.

## City map (`CITY_TO_COUNTRY`)

Deterministic city → country. Covers the canonical cities of all 10 countries
(Berlin, Amsterdam, Dublin, London, Singapore, Dubai, Bengaluru, Toronto,
Sydney, Warsaw, …) plus common variants (`münchen`, `bengaluru`, `gurugram`,
`kraków`). Cities are matched on word boundaries, so `"uk"` never matches
inside `"ukraine"`.

## Remote handling

The location is checked for `REMOTE` / `HYBRID` / `ONSITE` first (independent of
the country answer), then:

| location | result |
|---|---|
| `Remote - India` | IN / India, HIGH, `TEXT_LOCATION` |
| `Remote (EMEA)` | region EMEA, MEDIUM, country NULL |
| `Remote Worldwide` / `Anywhere` | region GLOBAL, country NULL |
| bare `Remote` + `"must reside in Germany"` | DE / Germany, MEDIUM, `DESCRIPTION` |
| bare `Remote`, no evidence | country NULL, honest UNKNOWN/GLOBAL, LOW |

Remote region patterns are checked **before** description residency, so
`Remote (EU)` stays region-constrained even if the description mentions one
country — that disagreement is recorded as a **conflict**, not silently applied.

## Multi-location

`"Singapore / London / New York"` → primary `SG`, `supported_countries` lists
every configured country found (`["SG","GB"]`). Primary is the first configured
country in string order.

## Source country is a HINT only

The searched country (`search_country` / `source_country`) is tier 6, recorded at
**LOW** confidence, and is never allowed to override explicit text: a job found
under the SG search whose location says `Kuala Lumpur` does not become Singapore
by text — it falls through to the source hint at LOW (or stays UNKNOWN if the
place maps to no configured country with no hint). The golden rule is visible in
the data: text-classified rows carry `TEXT_LOCATION`/`CITY_MAP`, hint-only rows
carry `SOURCE_HINT` + LOW.

## Conflicts (task §15)

`detect_conflict(job, result)` returns a description when the location and the
description disagree. The location always wins; the disagreement is appended to
`classification_reason` and counted in metrics. Two forms:

1. description evidence names a **different configured country** → conflict;
2. description evidence names a place that maps to **no configured country**
   (e.g. `"Kuala Lumpur office"`) → conflict.

## AI fallback (task §7)

`classify_job_ai(job, ai_client)` runs **only** on rows the deterministic chain
left `UNKNOWN`, and only when an AI client is supplied. It:
- sends one short bounded prompt (location + ≤600 chars of description) for a
  single job,
- accepts the answer **only** if it is a configured country code,
- rejects low-confidence (`LOW` → treated as <0.5) answers,
- swallows every error and returns the honest UNKNOWN.

The scheduler (`run_location_classification`) enforces this: residue rows are
held out of the deterministic batch, sent one-by-one to the AI tier, and the
final decision (AI-resolved or UNKNOWN) is what gets persisted and counted.
Deterministically-resolved jobs never touch AI (unit-tested).

## Idempotency

Classification is a pure function of the job's inputs. A job is classified once
(`location_classified = 0` → `1`); repeat runs classify nothing and produce
identical output for identical inputs (unit-tested).
