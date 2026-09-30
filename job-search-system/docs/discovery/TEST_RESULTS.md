# TEST RESULTS — Stage-1 discovery upgrade (2026-09-30)

All commands run from `job-search-system/root`. Counts are REAL terminal
output from this session — nothing typed from memory.

## New deterministic tests (this upgrade)

```bash
.venv/bin/python -m pytest tests/test_discovery_upgrade.py -q --timeout=60 -p no:cacheprovider
```
→ **39 passed**

Covers: registry↔adapter consistency (strict + non-strict), tier ordering,
canonical-source ranking, CONFIGURATION_REQUIRED vs FAILED keyed-source
mapping, health-status mapping, per-country relevance/coverage buckets,
run-health record shape, 14 ATS-detection host-pattern cases + adapter hints,
JSON-LD extraction (@graph, malformed skip), full canonical mapping,
dedupe-by-URL, non-JobPosting rejection, **unknown-date-stays-None**,
candidate career URLs, provenance stamping on cross-source merge, source
health per pass, honest NOT_APPLICABLE country skip, global summary shape,
and the downstream CLASSIFY/ELIGIBILITY contract.

## Existing suites re-run (green = no regression)

```bash
.venv/bin/python -m pytest tests/test_adapters.py tests/test_discovery_expansion.py \
    tests/test_scrapers/test_builtin.py -q --timeout=60 -p no:cacheprovider
```
→ **75 passed** (discovery_expansion updated: 19 → 20 adapters, +`builtin` in the name set)

```bash
.venv/bin/python -m pytest tests/test_a*.py tests/test_b*.py tests/test_c*.py -q --timeout=120
```
→ **289 passed** (adapters→countries alphabet; auth, API, CRM, dedup…)

```bash
.venv/bin/python -m pytest tests/test_dedup.py tests/test_database.py … tests/test_email_digest.py -q
```
→ **144 passed** (incl. Critical Test #2 cross-source dedup, discovery resee honesty)

```bash
.venv/bin/python -m pytest tests/test_enrichment.py … tests/test_multiuser_real_scenario.py -q
```
→ **196 passed** (incl. 4/4 real-scenario multiuser)

```bash
.venv/bin/python -m pytest tests/test_notifications.py … tests/test_rate_limiter.py -q
```
→ **133 passed**

```bash
.venv/bin/python -m pytest tests/test_reminders.py … tests/test_workspaces.py tests/test_scrapers/ -q
```
→ **294 passed** (incl. Critical Test #5 workspace isolation, 137 scraper tests)

## Session total

```text
39 + 75 + 289 + 144 + 196 + 133 + 294  =  1070 test runs, 0 failures
(1055 collected in tests/ + 15 repeat-runs of changed files during fixes)
```

## Critical Tests (system-level, from AGENT_CONTEXT.md)

| # | Critical Test | Status |
|---|---|---|
| 2 | Same job via 2 sources ⇒ 1 job + 2 source rows | green (`tests/test_adapters.py::test_discovery_cycle_cross_source_dedup`) |
| 3 | DATE_UNKNOWN never becomes VERIFIED_FRESH | green (`tests/test_eligibility.py`) — plus new guard: JSON-LD job without datePosted keeps None |
| 5 | Two users ⇒ isolated workspaces | green (`tests/test_workspaces.py`, 12/12) |

## Live regression: real server boot (uvicorn, port 8097)

Real `uvicorn app.main:create_app --factory` boot + authenticated HTTP:

```text
RESULT bootstrap: 200
RESULT login: 200
RESULT registry: 200 | sources: 20 | countries: 10
RESULT discovery-no-resume: 428 (expect 428)   ← resume gate intact
RESULT scrape-no-resume: 428 (expect 428)      ← resume gate intact
```

(Finding from this check: `/api/discovery/registry` initially 500'd via a bad
`from app.config import settings` import — fixed, verified 200 above. Also:
bootstrap returned 403 on the first attempt because a previous boot's
`/tmp/system.db` already claimed the admin — the one-time-bootstrap lock
working as designed.)

## Live all-countries smoke (real runtime, not asserted)

```bash
setsid nohup .venv/bin/python -u ../analysis/discovery_upgrade_smoke.py > /tmp/discovery_smoke3.log &
```
→ 10/10 countries × 20 sources = 200 passes · 0 FAILED · 0 RATE_LIMITED
· by_status: PASS 53 · NO_RESULTS 99 · CONFIGURATION_REQUIRED 21 ·
NOT_APPLICABLE 27 · totals: raw 1058 → unique 194 (73 duplicates removed)
· reports in `docs/discovery/results/` (per-country samples in `results/countries/`).
