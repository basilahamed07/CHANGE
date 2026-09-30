# DISCOVERY OVERVIEW — Stage-1 DISCOVER (after the 2026-09-30 upgrade)

```
DISCOVER (Stage 1) — one orchestrated cycle, app/discovery.py
│
├── SOURCE REGISTRY (app/source_registry.py)
│     every source: type · tier · countries · access · enabled
│     tier 1  direct careers · employer ATS · country majors (SG gov, DE, UK)
│     tier 2  global boards · keyed metasearch · startup · remote
│     tier 3  long-tail remote feeds
│
├── GLOBAL BOARDS          adzuna* · wellfound
├── COUNTRY-SPECIFIC       arbeitnow (DE) · reed* (UK) · mycareersfuture (SG gov)
├── TECH / STARTUP         wellfound · landingjobs · builtin
├── GOVERNMENT             mycareersfuture (SG) · usajobs (US, keyed)
├── ATS DISCOVERY          greenhouse · lever · ashby · smartrecruiters · recruitee
├── DIRECT COMPANY CAREERS JSON-LD JobPosting parser (opt-in, company_careers.py)
│     company → career page → ATS? route to ATS adapter : parse JSON-LD
├── SEARCH DISCOVERY       evaluated — NOT implemented (fragile; see limitations)
├── ATS DETECTION          app/ats_detect.py — 22 URL rules, 16 providers
├── REMOTE BOARDS          remotive · jobicy · himalayas · weworkremotely
│                         remoteok · workingnomads · 4dayweek
│
├── INGEST (unchanged gates — Stage 1 does NOT do later stages' work)
│     title gate → cross-source DEDUP (content hash; URL excluded)
│     → region gate → insert → source attribution → freshness evidence
│
├── PROVENANCE             canonical_source + source_types stamped on every job
│                          (career > ATS > gov > board > aggregator)
├── HEALTH                 per-pass SourceRunHealth: PASS · PARTIAL · NO_RESULTS
│                          CONFIGURATION_REQUIRED · RATE_LIMITED · FAILED ·
│                          BLOCKED · NOT_APPLICABLE
└── LOGS                   [DISCOVERY][CC][source] raw= parsed= unique= duration= PASS

    * keyed — implemented, waits on credentials (jooble, adzuna, reed)
```

## Flow into Stage 2 (unchanged contract)

DISCOVER emits rows in the same `jobs` table with the same gates. CLASSIFY
(Stage 2) does location classification; ELIGIBILITY (Stage 3) does freshness
policy. Discovery only stamps extra provenance metadata
(`canonical_source`, `source_types`) — verified by
`tests/test_discovery_upgrade.py::test_discovered_job_flows_to_classify_and_eligibility`.

## Where to look

| Doc | Content |
|---|---|
| DISCOVERY_AUDIT.md | before/after, bugs found, what remains |
| COUNTRY_SOURCE_MATRIX.md | per-country coverage buckets (generated) |
| GLOBAL_SOURCE_MATRIX.md | per-source global view |
| ATS_COVERAGE.md | ATS adapters vs detection vs tests |
| DIRECT_CAREER_DISCOVERY.md | the company-careers layer |
| SOURCE_HEALTH.md | live run health (generated) |
| TEST_RESULTS.md | test commands + real counts |
| KNOWN_LIMITATIONS.md | honest gaps |
| results/*.json | machine-readable evidence |
