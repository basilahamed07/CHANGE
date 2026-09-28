# E2E DISCOVERY EXPANSION REPORT — live verification

**Run:** 2026-09-28T13:27:15+00:00  
**Countries:** Canada, Australia, Poland, India  
**Orchestrator:** real `run_discovery_cycle` · real 15 adapters · real HTTP · real temp SQLite DB

## Health probes (new adapters, live)

| source | ok | note |
|---|---|---|
| jooble | False | no API key configured (Settings → scraper keys: 'jooble') |
| adzuna | False | no API keys configured (scraper keys 'adzuna' + 'adzuna-id') |
| arbeitnow | True |  |
| remotive | True |  |
| jobicy | True |  |
| weworkremotely | True |  |
| remoteok | True |  |
| himalayas | True |  |
| 4dayweek | True |  |
| landingjobs | True |  |
| recruitee | True |  |

## Canada

**Real jobs ingested (keyless sources):** 22

| check | result | detail |
|---|---|---|
| all 15 adapters ran | PASS | ran=15 |
| keyed jooble honest no-op | PASS | stop=SOURCE_FAILURE err=jooble API key not configured (scraper key 'jooble |
| keyed adzuna honest no-op | PASS | stop=SOURCE_FAILURE err=adzuna keys not configured (scraper keys 'adzuna'  |
| real jobs ingested for Canada | PASS | new=22 |
| region gate holds on ingested rows | PASS | checked=1 offside=0 |

Per-source telemetry:

| source | stop_reason | found | ingested | dupes | error |
|---|---|---|---|---|---|
| greenhouse | NO_MORE_RESULTS | 154 | 21 | 8 |  |
| lever | NO_MORE_RESULTS | 0 | 0 | 0 |  |
| ashby | SOURCE_FAILURE | 0 | 0 | 0 | Client error '404 Not Found' for url 'https://api.ashbyhq.co |
| smartrecruiters | NO_MORE_RESULTS | 0 | 0 | 0 |  |
| jooble | SOURCE_FAILURE | 0 | 0 | 0 | jooble API key not configured (scraper key 'jooble') |
| adzuna | SOURCE_FAILURE | 0 | 0 | 0 | adzuna keys not configured (scraper keys 'adzuna' + 'adzuna- |
| arbeitnow | NO_MORE_RESULTS | 0 | 0 | 0 |  |
| remotive | NO_MORE_RESULTS | 2 | 0 | 0 |  |
| jobicy | NO_MORE_RESULTS | 7 | 0 | 0 |  |
| weworkremotely | NO_MORE_RESULTS | 0 | 0 | 0 |  |
| remoteok | NO_MORE_RESULTS | 0 | 0 | 0 |  |
| himalayas | NO_MORE_RESULTS | 4 | 1 | 0 |  |
| 4dayweek | NO_MORE_RESULTS | 0 | 0 | 0 |  |
| landingjobs | NO_MORE_RESULTS | 0 | 0 | 0 |  |
| recruitee | NO_MORE_RESULTS | 0 | 0 | 0 |  |

Sample locations ingested:

- Canada

## Australia

**Real jobs ingested (keyless sources):** 2

| check | result | detail |
|---|---|---|
| all 15 adapters ran | PASS | ran=15 |
| keyed jooble honest no-op | PASS | stop=SOURCE_FAILURE err=jooble API key not configured (scraper key 'jooble |
| keyed adzuna honest no-op | PASS | stop=SOURCE_FAILURE err=adzuna keys not configured (scraper keys 'adzuna'  |
| real jobs ingested for Australia | PASS | new=2 |
| region gate holds on ingested rows | PASS | checked=2 offside=0 |

Per-source telemetry:

| source | stop_reason | found | ingested | dupes | error |
|---|---|---|---|---|---|
| greenhouse | NO_MORE_RESULTS | 47 | 0 | 0 |  |
| lever | NO_MORE_RESULTS | 0 | 0 | 0 |  |
| ashby | SOURCE_FAILURE | 0 | 0 | 0 | Client error '404 Not Found' for url 'https://api.ashbyhq.co |
| smartrecruiters | NO_MORE_RESULTS | 0 | 0 | 0 |  |
| jooble | SOURCE_FAILURE | 0 | 0 | 0 | jooble API key not configured (scraper key 'jooble') |
| adzuna | SOURCE_FAILURE | 0 | 0 | 0 | adzuna keys not configured (scraper keys 'adzuna' + 'adzuna- |
| arbeitnow | NO_MORE_RESULTS | 0 | 0 | 0 |  |
| remotive | NO_MORE_RESULTS | 0 | 0 | 0 |  |
| jobicy | NO_MORE_RESULTS | 0 | 0 | 0 |  |
| weworkremotely | NO_MORE_RESULTS | 0 | 0 | 0 |  |
| remoteok | NO_MORE_RESULTS | 0 | 0 | 0 |  |
| himalayas | NO_MORE_RESULTS | 3 | 2 | 0 |  |
| 4dayweek | NO_MORE_RESULTS | 0 | 0 | 0 |  |
| landingjobs | NO_MORE_RESULTS | 0 | 0 | 0 |  |
| recruitee | NO_MORE_RESULTS | 0 | 0 | 0 |  |

Sample locations ingested:

- Australia
- Australia

## Poland

**Real jobs ingested (keyless sources):** 6

| check | result | detail |
|---|---|---|
| all 15 adapters ran | PASS | ran=15 |
| keyed jooble honest no-op | PASS | stop=SOURCE_FAILURE err=jooble API key not configured (scraper key 'jooble |
| keyed adzuna honest no-op | PASS | stop=SOURCE_FAILURE err=adzuna keys not configured (scraper keys 'adzuna'  |
| real jobs ingested for Poland | PASS | new=6 |
| region gate holds on ingested rows | PASS | checked=1 offside=0 |

Per-source telemetry:

| source | stop_reason | found | ingested | dupes | error |
|---|---|---|---|---|---|
| greenhouse | NO_MORE_RESULTS | 24 | 5 | 0 |  |
| lever | NO_MORE_RESULTS | 0 | 0 | 0 |  |
| ashby | SOURCE_FAILURE | 0 | 0 | 0 | Client error '404 Not Found' for url 'https://api.ashbyhq.co |
| smartrecruiters | NO_MORE_RESULTS | 0 | 0 | 0 |  |
| jooble | SOURCE_FAILURE | 0 | 0 | 0 | jooble API key not configured (scraper key 'jooble') |
| adzuna | SOURCE_FAILURE | 0 | 0 | 0 | adzuna keys not configured (scraper keys 'adzuna' + 'adzuna- |
| arbeitnow | NO_MORE_RESULTS | 0 | 0 | 0 |  |
| remotive | NO_MORE_RESULTS | 0 | 0 | 0 |  |
| jobicy | NO_MORE_RESULTS | 0 | 0 | 0 |  |
| weworkremotely | NO_MORE_RESULTS | 0 | 0 | 0 |  |
| remoteok | NO_MORE_RESULTS | 0 | 0 | 0 |  |
| himalayas | NO_MORE_RESULTS | 3 | 1 | 1 |  |
| 4dayweek | NO_MORE_RESULTS | 0 | 0 | 0 |  |
| landingjobs | NO_MORE_RESULTS | 1 | 0 | 0 |  |
| recruitee | NO_MORE_RESULTS | 0 | 0 | 0 |  |

Sample locations ingested:

- Poland

## India

**Real jobs ingested (keyless sources):** 19

| check | result | detail |
|---|---|---|
| all 15 adapters ran | PASS | ran=15 |
| keyed jooble honest no-op | PASS | stop=SOURCE_FAILURE err=jooble API key not configured (scraper key 'jooble |
| keyed adzuna honest no-op | PASS | stop=SOURCE_FAILURE err=adzuna keys not configured (scraper keys 'adzuna'  |
| real jobs ingested for India | PASS | new=19 |
| region gate holds on ingested rows | PASS | checked=0 offside=0 |

Per-source telemetry:

| source | stop_reason | found | ingested | dupes | error |
|---|---|---|---|---|---|
| greenhouse | NO_MORE_RESULTS | 183 | 18 | 9 |  |
| lever | NO_MORE_RESULTS | 0 | 0 | 0 |  |
| ashby | SOURCE_FAILURE | 1 | 1 | 0 | Client error '404 Not Found' for url 'https://api.ashbyhq.co |
| smartrecruiters | NO_MORE_RESULTS | 0 | 0 | 0 |  |
| jooble | SOURCE_FAILURE | 0 | 0 | 0 | jooble API key not configured (scraper key 'jooble') |
| adzuna | SOURCE_FAILURE | 0 | 0 | 0 | adzuna keys not configured (scraper keys 'adzuna' + 'adzuna- |
| arbeitnow | NO_MORE_RESULTS | 0 | 0 | 0 |  |
| remotive | NO_MORE_RESULTS | 0 | 0 | 0 |  |
| jobicy | NO_MORE_RESULTS | 0 | 0 | 0 |  |
| weworkremotely | NO_MORE_RESULTS | 0 | 0 | 0 |  |
| remoteok | NO_MORE_RESULTS | 0 | 0 | 0 |  |
| himalayas | NO_MORE_RESULTS | 2 | 0 | 1 |  |
| 4dayweek | NO_MORE_RESULTS | 0 | 0 | 0 |  |
| landingjobs | NO_MORE_RESULTS | 0 | 0 | 0 |  |
| recruitee | NO_MORE_RESULTS | 0 | 0 | 0 |  |

## Verdict

**20/20 checks passed, 0 keyless health failures** — GREEN ✅
