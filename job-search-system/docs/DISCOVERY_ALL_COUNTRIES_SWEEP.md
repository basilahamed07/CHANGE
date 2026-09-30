# DISCOVERY — ALL 10 COUNTRIES LIVE SWEEP (Basil's workspace)

**Run:** 2026-09-28T20:33:10+00:00  
**Orchestrator:** real `run_discovery_cycle` (the code the server runs) · real 19 adapters · real HTTP · Basil's real DB + real resume terms  
**Term per country:** Basil's first search term · **budget:** 19 passes/country · **total:** 190 live passes in 996s

> The router wrapper (428 gate, auth, background task, telemetry state) was already proven 22/22 in `DISCOVERY_PHASE_LIVE_VERIFICATION.md`; this sweep answers the per-country question with the same ingest path.

## 1. Summary

| country | new | dupes | ingested rows | duration | verdict |
|---|---|---|---|---|---|
| Germany (DE) | 5 | 9 | 5 | 79.1s | GREEN |
| Netherlands (NL) | 1 | 4 | 1 | 91.9s | GREEN |
| Ireland (IE) | 1 | 12 | 1 | 83.0s | GREEN |
| UK (GB) | 2 | 45 | 2 | 85.5s | GREEN |
| Singapore (SG) | 6 | 97 | 7 | 90.9s | GREEN |
| UAE (AE) | 0 | 2 | 0 | 165.8s | GREEN |
| India (IN) | 24 | 11 | 29 | 85.1s | GREEN |
| Canada (CA) | 19 | 18 | 24 | 91.8s | GREEN |
| Australia (AU) | 0 | 3 | 0 | 101.3s | GREEN |
| Poland (PL) | 2 | 6 | 2 | 121.0s | GREEN |

**Totals: 60 new jobs, 50/50 checks passed — GREEN ✅**

## 2. Jobs ingested per source × country

| source | DE | NL | IE | GB | SG | AE | IN | CA | AU | PL |
|---|---|---|---|---|---|---|---|---|---|---|
| greenhouse | 0 | 0 | 0 | 0 | 0 | 0 | 18 | 17 | 0 | 2 |
| lever | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| ashby | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| smartrecruiters | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| jooble | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| adzuna | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| reed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| arbeitnow | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| remotive | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| jobicy | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| weworkremotely | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| remoteok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| himalayas | 3 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 4dayweek | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| landingjobs | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| recruitee | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| mycareersfuture | 0 | 0 | 0 | 0 | 6 | 0 | 0 | 0 | 0 | 0 |
| wellfound | 0 | 0 | 0 | 0 | 0 | 0 | 6 | 2 | 0 | 0 |
| workingnomads | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

(0 = ran but found nothing in-country, or keyed-but-unset — honest, not missing coverage)

## 3. Per-country checks

### Germany (DE)

| check | result | detail |
|---|---|---|
| all 19 adapters ran once | PASS | passes=19 unique=19 |
| every pass has an honest stop_reason | PASS | ['NO_MORE_RESULTS', 'SOURCE_FAILURE'] |
| keyed sources honest without keys | PASS | jooble: jooble API key not configured (scraper k; adzuna: adzuna keys not configured (scraper keys; reed: reed covers UK only |
| region gate holds on ingested rows | PASS | rows=5 offside=[] |
| fresh rows carry freshness evidence | PASS | evidence=5/5 |

### Netherlands (NL)

| check | result | detail |
|---|---|---|
| all 19 adapters ran once | PASS | passes=19 unique=19 |
| every pass has an honest stop_reason | PASS | ['NO_MORE_RESULTS', 'SOURCE_FAILURE'] |
| keyed sources honest without keys | PASS | jooble: jooble API key not configured (scraper k; adzuna: adzuna keys not configured (scraper keys; reed: reed covers UK only |
| region gate holds on ingested rows | PASS | rows=1 offside=[] |
| fresh rows carry freshness evidence | PASS | evidence=1/1 |

### Ireland (IE)

| check | result | detail |
|---|---|---|
| all 19 adapters ran once | PASS | passes=19 unique=19 |
| every pass has an honest stop_reason | PASS | ['NO_MORE_RESULTS', 'SOURCE_FAILURE'] |
| keyed sources honest without keys | PASS | jooble: jooble API key not configured (scraper k; adzuna: adzuna keys not configured (scraper keys; reed: reed covers UK only |
| region gate holds on ingested rows | PASS | rows=1 offside=[] |
| fresh rows carry freshness evidence | PASS | evidence=1/1 |

### UK (GB)

| check | result | detail |
|---|---|---|
| all 19 adapters ran once | PASS | passes=19 unique=19 |
| every pass has an honest stop_reason | PASS | ['NO_MORE_RESULTS', 'SOURCE_FAILURE'] |
| keyed sources honest without keys | PASS | jooble: jooble API key not configured (scraper k; adzuna: adzuna keys not configured (scraper keys; reed: reed API key not configured (scrap |
| region gate holds on ingested rows | PASS | rows=2 offside=[] |
| fresh rows carry freshness evidence | PASS | evidence=2/2 |

### Singapore (SG)

| check | result | detail |
|---|---|---|
| all 19 adapters ran once | PASS | passes=19 unique=19 |
| every pass has an honest stop_reason | PASS | ['NO_MORE_RESULTS', 'SOURCE_FAILURE'] |
| keyed sources honest without keys | PASS | jooble: jooble API key not configured (scraper k; adzuna: adzuna keys not configured (scraper keys; reed: reed covers UK only |
| region gate holds on ingested rows | PASS | rows=7 offside=[] |
| fresh rows carry freshness evidence | PASS | evidence=6/6 |

### UAE (AE)

| check | result | detail |
|---|---|---|
| all 19 adapters ran once | PASS | passes=19 unique=19 |
| every pass has an honest stop_reason | PASS | ['NO_MORE_RESULTS', 'SOURCE_FAILURE'] |
| keyed sources honest without keys | PASS | jooble: jooble API key not configured (scraper k; adzuna: adzuna keys not configured (scraper keys; reed: reed covers UK only |
| region gate holds on ingested rows | PASS | rows=0 offside=[] |
| fresh rows carry freshness evidence | PASS | evidence=0/0 |

### India (IN)

| check | result | detail |
|---|---|---|
| all 19 adapters ran once | PASS | passes=19 unique=19 |
| every pass has an honest stop_reason | PASS | ['NO_MORE_RESULTS', 'SOURCE_FAILURE'] |
| keyed sources honest without keys | PASS | jooble: jooble API key not configured (scraper k; adzuna: adzuna keys not configured (scraper keys; reed: reed covers UK only |
| region gate holds on ingested rows | PASS | rows=29 offside=[] |
| fresh rows carry freshness evidence | PASS | evidence=24/24 |

### Canada (CA)

| check | result | detail |
|---|---|---|
| all 19 adapters ran once | PASS | passes=19 unique=19 |
| every pass has an honest stop_reason | PASS | ['NO_MORE_RESULTS', 'SOURCE_FAILURE'] |
| keyed sources honest without keys | PASS | jooble: jooble API key not configured (scraper k; adzuna: adzuna keys not configured (scraper keys; reed: reed covers UK only |
| region gate holds on ingested rows | PASS | rows=24 offside=[] |
| fresh rows carry freshness evidence | PASS | evidence=19/19 |

### Australia (AU)

| check | result | detail |
|---|---|---|
| all 19 adapters ran once | PASS | passes=19 unique=19 |
| every pass has an honest stop_reason | PASS | ['NO_MORE_RESULTS', 'SOURCE_FAILURE'] |
| keyed sources honest without keys | PASS | jooble: jooble API key not configured (scraper k; adzuna: adzuna keys not configured (scraper keys; reed: reed covers UK only |
| region gate holds on ingested rows | PASS | rows=0 offside=[] |
| fresh rows carry freshness evidence | PASS | evidence=0/0 |

### Poland (PL)

| check | result | detail |
|---|---|---|
| all 19 adapters ran once | PASS | passes=19 unique=19 |
| every pass has an honest stop_reason | PASS | ['NO_MORE_RESULTS', 'SOURCE_FAILURE'] |
| keyed sources honest without keys | PASS | jooble: jooble API key not configured (scraper k; adzuna: adzuna keys not configured (scraper keys; reed: reed covers UK only |
| region gate holds on ingested rows | PASS | rows=2 offside=[] |
| fresh rows carry freshness evidence | PASS | evidence=2/2 |

## 4. Sample of what landed per country

**Germany:** #1923 Berlin; #1924 Munich; #1925 Germany; #1926 Germany; #1927 Germany

**Netherlands:** #1932 Netherlands

**Ireland:** #1943 Ireland

**UK:** #1977 London, United Kingdom; #1984 United Kingdom (Hybrid)

**Singapore:** #2002 Singapore; #2015 Singapore; #2045 Singapore; #2048 Singapore; #2048 Singapore

**India:** #2079 Remote, Bangalore; #2080 Bangalore, India; #2080 Bangalore, India; #2081 Bangalore, India; #2081 Bangalore, India

**Canada:** #2111 Remote, Canada; #2113 Remote, Canada; Remote, United States; #2115 Remote, Canada; Remote, United States; #2115 Remote, Canada; Remote, United States; #2117 Remote, Canada; Remote, United States

**Poland:** #2148 Remote, Poland; #2152 Remote, Poland

## 5. Re-run

```bash
cd job-search-system/root
setsid nohup .venv/bin/python -u ../analysis/verify_discovery_all_countries.py \
    > /tmp/discovery_all_countries.log 2>&1 < /dev/null &
```
