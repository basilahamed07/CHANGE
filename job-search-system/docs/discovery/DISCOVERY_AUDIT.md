# DISCOVERY AUDIT — Stage-1 DISCOVER upgrade (2026-09-30)

Task §44: what existed before, what was actually active, what was broken,
what was added, and what remains. Every number below comes from code
inspection or the live smoke run (results/*.json) — none are aspirational.

## BEFORE (audited 2026-09-30)

### Scrapers that existed (app/scrapers/, 22 files)

| Scraper | In discovery? | Notes from audit |
|---|---|---|
| adzuna | yes (adapter) | US-hardcoded legacy + country-scoped adapter (keyed) |
| arbeitnow | yes (adapter) | DE board, 3 pages, keyless |
| ashby | yes (adapter) | 4 boards, keyless |
| **builtin** | **NO — orphaned** | `BuiltInScraper` existed since M1 but was NEVER wrapped/registered; discovery never used it |
| dice | yes (scraper) | US-weighted feed |
| fourdayweek | yes (adapter, name `4dayweek`) | remote feed |
| greenhouse | yes (adapter) | facade over scraper, keyless |
| hackernews | yes (scraper) | HN "who's hiring" |
| himalayas | yes (adapter) | remote |
| indeed | yes (scraper) | IP-blocked for datacenter (known limit) |
| jobicy | yes (adapter) | remote |
| landingjobs | yes (adapter) | EU tech |
| linkedin | yes (scraper) | guest scraping, brittle |
| mycareersfuture | yes (adapter) | SG govt board |
| recruitee | yes (adapter) | EU ATS |
| remotive | yes (adapter) | remote |
| remoteok | yes (adapter) | remote |
| usajobs | yes (scraper) | US govt (keyed) |
| wellfound | yes (adapter) | startup board |
| weworkremotely | yes (adapter) | RSS, weak geo signal |
| workingnomads | yes (adapter) | remote |

### Adapters registered in ALL_ADAPTERS (before): 19

### Countries configured: 10 (DE NL IE GB SG AE IN CA AU PL) — all enabled

### Broken / weak before the upgrade

| Issue | Evidence |
|---|---|
| `builtin` scraper orphaned (never in discovery) | grep: no adapter referenced it |
| `walkaway` Ashby board 404s permanently | removed 2026-09-28 (prior session) |
| Source logic scattered: orchestrator knew nothing about source types/tiers/countries | `discovery.py` ran adapters in import order |
| No canonical-source preference recorded | `jobs` table had no `canonical_source` |
| Health = stop_reason only; no CONFIGURATION_REQUIRED distinction in reports | telemetry pass records |
| Single-country sources wasted an HTTP pass per wrong country (region_hint) | facade behavior |
| Jooble/Adzuna/Reed pending keys | `scraper_keys` table empty for those ids |

## AFTER (this upgrade)

| Change | Where |
|---|---|
| Central SOURCE REGISTRY: type/tier/countries/access/enabled per source | `app/source_registry.py` |
| Tier-ordered runs (ATS → local majors → global/remote → long-tail) | `app/discovery.py` |
| Honest NOT_APPLICABLE country skip BEFORE any HTTP (registry-driven) | `app/discovery.py` |
| Canonical-source stamping + provenance map (career > ATS > gov > board > aggregator) | `jobs.canonical_source`, `jobs.source_types`, `discovery._stamp_provenance` |
| ATS auto-detection from URL shapes (22 rules, 16 providers) | `app/ats_detect.py` |
| Direct company career discovery: JSON-LD JobPosting → CanonicalJob, opt-in | `app/company_careers.py` |
| Company career cache columns (careers_ats, careers_checked_at) | `companies` table migration |
| Source-health capture per pass + structured [DISCOVERY] logs | `source_registry.SourceRunHealth` |
| `/api/discovery/registry` read-only report endpoint | `app/routers/discovery.py` |
| **BuiltinAdapter** wired (fixed 2 live bugs in its scraper — see below) | `app/adapters/country_scoped.py` |
| Adapters: 19 → **20** | `app/adapters/__init__.py` |

### Live bugs found + fixed in builtin.py (this session)

1. `<script type="application/ld&#x2B;json">` — HTML-entity-encoded `+` made
   BeautifulSoup's type filter match NOTHING → 0 jobs on every pass against a
   fully live board. Fixed with `_normalize_ld_type()` (regex unescape).
2. JobPosting JSON-LD wrapped in `@graph` — `_parse_detail_jsonld` only read
   top-level `@type` → every detail parse failed → fallback stubs with empty
   company/location. Fixed: walk `@graph` nodes.
   Live result: 0 jobs → 25 real jobs (JPMorganChase/Optum/Wells Fargo, with
   city + datePosted).

## What remains unavailable (honest)

| Item | Status |
|---|---|
| Jooble key | CONFIGURATION_REQUIRED (adapter implemented, all 10 countries ready) |
| Adzuna keys | CONFIGURATION_REQUIRED (same) |
| Reed key (UK) | CONFIGURATION_REQUIRED (same) |
| Indeed | BLOCKED from datacenter IPs (pre-existing, documented) |
| LinkedIn | PARTIAL — guest scraping, brittle, kept tier-3 |
| Workday/Teamtailor/Workable/BambooHR/iCIMS/SAP SF | DETECTED (ats_detect rules) but no adapters — routing falls back to JSON-LD career parsing |
| Search-engine job discovery (Google Jobs) | NOT_WORTH_IMPLEMENTING now — fragile SERP scraping; revisit with an official API |
| builtin geo signal | Remote-only listings carry no country text → NO_RESULTS outside US/CA/IN (evidence in results/) |
