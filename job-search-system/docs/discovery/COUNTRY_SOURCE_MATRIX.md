# COUNTRY SOURCE MATRIX — Stage-1 discovery upgrade (2026-09-30)

Live smoke run: 10 countries × 20 sources = 200 passes, real HTTP, real
orchestrator (`analysis/discovery_upgrade_smoke.py` → results/*.json + results/countries/<CODE>.json).

Legend: PASS = returned jobs · NO_RESULTS = reachable, nothing relevant ·
CONF_REQ = implemented, key missing · N/A = single-country source, honest skip.
"Jobs" = unique jobs ingested for that country in the smoke cycle.

## Per-country totals

| Country | Sources | PASS | NO_RESULTS | CONF_REQ | N/A | FAILED | Raw | Unique | Coverage status |
|---|---|---|---|---|---|---|---|---|---|
| AE | 20 | 3 | 12 | 2 | 3 | 0 | 4 | 2 | FULL |
| AU | 20 | 5 | 10 | 2 | 3 | 0 | 57 | 4 | FULL |
| CA | 20 | 7 | 8 | 2 | 3 | 0 | 179 | 29 | FULL |
| DE | 20 | 6 | 10 | 2 | 2 | 0 | 86 | 9 | FULL |
| GB | 20 | 8 | 7 | 3 | 2 | 0 | 199 | 24 | FULL |
| IE | 20 | 5 | 10 | 2 | 3 | 0 | 72 | 2 | FULL |
| IN | 20 | 5 | 10 | 2 | 3 | 0 | 217 | 38 | FULL |
| NL | 20 | 3 | 12 | 2 | 3 | 0 | 58 | 2 | FULL |
| PL | 20 | 4 | 11 | 2 | 3 | 0 | 29 | 2 | FULL |
| SG | 20 | 7 | 9 | 2 | 2 | 0 | 157 | 82 | FULL |

GLOBAL by_status: PASS 53 · NO_RESULTS 99 · CONFIGURATION_REQUIRED 21 ·
NOT_APPLICABLE 27 · **FAILED 0 · RATE_LIMITED 0**.

## Source × country highlights (from results/countries/*.json)

| Country | Top contributing sources (unique jobs) | Notes |
|---|---|---|
| SG (82) | greenhouse, wellfound, builtin, himalayas | mycareersfuture N/A-guard only fires elsewhere; SG govt board PASS |
| IN (38) | builtin (20 — the JSON-LD fix live), wellfound, greenhouse | |
| CA (29) | greenhouse (25), wellfound, 4dayweek | builtin NO_RESULTS (remote-only listings carry no CA text) |
| GB (24) | greenhouse, wellfound, himalayas | reed = CONF_REQ (key pending) |
| DE (9) | greenhouse, wellfound, arbeitnow (DE-native PASS) | |
| AU (4) | greenhouse, wellfound, himalayas | remote-heavy market for these boards |
| AE (2) | wellfound (OpenAI Abu Dhabi, Accountable Dubai), greenhouse | |
| IE (2) | greenhouse, wellfound | small market on these boards — jooble key will lift |
| NL (2) | greenhouse, recruitee (bunq/Adyen… boards) | |
| PL (2) | greenhouse, landingjobs | same |

Every country's full source×status breakdown is machine-readable in
`results/countries/<CODE>.json` (with bounded job samples incl. provenance).
