# GLOBAL SOURCE MATRIX — all discovery sources (registry view + live evidence)

Generated from `app/source_registry.py` + `results/source_health.json`
(2026-09-30 live run, 10 countries × 20 sources = 200 passes).

Tier 1 = direct/most-authoritative · Tier 3 = long-tail.

| Source | Type | Tier | Countries | Access | PASS (of 10) | Implementation | Test status | Notes |
|---|---|---|---|---|---|---|---|---|
| greenhouse | ATS | 1 | * | PUBLIC | 10 | adapter | respx + live | 10/10 countries — strongest source |
| ashby | ATS | 1 | * | PUBLIC | 7 | adapter | respx + live | linear/ramp/deel/openai boards |
| himalayas | REMOTE_BOARD | 2 | * | PUBLIC | 8 | adapter | respx + live | country-requirement field |
| wellfound | STARTUP_BOARD | 2 | * | PUBLIC | 8 | adapter | respx + live | incl. UAE/IN boards |
| workingnomads | REMOTE_BOARD | 2 | * | PUBLIC | 5 | adapter | respx + live | |
| builtin | TECH_BOARD | 2 | * | PUBLIC | 1 | adapter (NEW) | unit + live | fixed 2 JSON-LD bugs; geo-limited (US/CA/IN) |
| 4dayweek | REMOTE_BOARD | 3 | * | PUBLIC | 3 | adapter | respx + live | |
| jobicy | REMOTE_BOARD | 2 | * | PUBLIC | 2 | adapter | respx + live | jobGeo strings |
| landingjobs | TECH_BOARD | 2 | * | PUBLIC | 2 | adapter | respx + live | EU-weighted |
| remoteok | REMOTE_BOARD | 3 | * | PUBLIC | 2 | adapter | respx + live | |
| arbeitnow | LOCAL_BOARD | 1 | DE | PUBLIC | 1 (DE) | adapter | respx + live | DE PASS; honest N/A elsewhere |
| mycareersfuture | GOVERNMENT | 1 | SG | PUBLIC | 1 (SG) | adapter | respx + live | SG PASS; N/A elsewhere |
| recruitee | ATS | 1 | * | PUBLIC | 1 | adapter | respx + live | default EU boards |
| remotive | REMOTE_BOARD | 2 | * | PUBLIC | 1 | adapter | respx + live | |
| lever | ATS | 1 | * | PUBLIC | 1 | adapter | respx + live | 2 verified-live boards |
| jooble | AGGREGATOR | 2 | * | API_KEY | 0 | adapter | respx + live | CONFIGURATION_REQUIRED — key pending |
| adzuna | GLOBAL_BOARD | 2 | * | API_KEY | 0 | adapter | respx + live | CONFIGURATION_REQUIRED — keys pending |
| reed | LOCAL_BOARD | 1 | GB | API_KEY | 0 | adapter | respx + live | CONFIGURATION_REQUIRED — key pending (GB N/A ×9) |
| smartrecruiters | ATS | 1 | * | PUBLIC | 0 | adapter | respx + live | NO_RESULTS — default boards post few AI roles; key `smartrecruiters_companies` extends |
| weworkremotely | REMOTE_BOARD | 3 | * | PUBLIC | 0 | adapter | respx + live | RSS geo-signal too weak for most country gates |
| company_careers | COMPANY_CAREER | 1 | * | PUBLIC | opt-in | adapter (NEW) | unit (fixture JSON-LD) | runs only for configured `career_companies` |

Global status classification used (task §8): PUBLIC = SUPPORTED ·
API_KEY = API_REQUIRED → CONFIGURATION_REQUIRED until keys ·
Indeed = BLOCKED (datacenter) · LinkedIn = PARTIALLY_SUPPORTED ·
Google-Jobs-style SERP discovery = NOT_WORTH_IMPLEMENTING (fragile) ·
Handshake/ZipRecruiter/Glassdoor = NOT_APPLICABLE (auth-walled or no
permitted automated access — documented, not fake-implemented).
