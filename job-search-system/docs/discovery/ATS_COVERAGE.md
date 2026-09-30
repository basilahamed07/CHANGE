# ATS COVERAGE — adapters vs auto-detection (2026-09-30)

"Do not claim support simply because a file named after the ATS exists."
Each row states what is VERIFIED (test or live run).

| ATS | Adapter | Auto-detect | Test fixture | Live test | Countries observed (live) | Status |
|---|---|---|---|---|---|---|
| Greenhouse | YES (`greenhouse`) | YES (boards. + job-boards.) | YES (respx) | YES 10/10 | all 10 | **FULL** |
| Lever | YES (`lever`) | YES (jobs.lever.co, jobs.eu.lever.co) | YES (respx) | YES | GB, DE | FULL (2 verified-live boards) |
| Ashby | YES (`ashby`) | YES (jobs.ashbyhq.com) | YES (respx) | YES 7/10 | IN, CA, SG, AE… | FULL |
| SmartRecruiters | YES (`smartrecruiters`) | YES (jobs.smartrecruiters.com) | YES (respx) | YES | 0 jobs on default boards | PARTIAL — extend via `smartrecruiters_companies` key |
| Recruitee | YES (`recruitee`) | YES (*.recruitee.com) | YES (respx) | YES | DE/NL boards | PARTIAL (EU default set) |
| Workday | no adapter | YES (*.myworkdayjobs.com, *.myworkdaysite.com) | YES (unit) | n/a | — | DETECT-ONLY → falls back to JSON-LD career parsing |
| Teamtailor | no adapter | YES (*.teamtailor.com) | YES (unit) | n/a | — | DETECT-ONLY |
| Workable | no adapter | YES (apply.workable.com) | YES (unit) | n/a | — | DETECT-ONLY |
| BambooHR | no adapter | YES (*.bamboohr.com) | YES (unit) | n/a | — | DETECT-ONLY |
| Jobvite | no adapter | YES (jobs.jobvite.com) | YES (unit) | n/a | — | DETECT-ONLY |
| iCIMS | no adapter | YES (*.icims.com) | YES (unit) | n/a | — | DETECT-ONLY |
| SAP SuccessFactors | no adapter | YES (*.successfactors.com) | YES (unit) | n/a | — | DETECT-ONLY |
| Comeet | no adapter | YES (jobs.comeet.com) | YES (unit) | n/a | — | DETECT-ONLY |
| Taleo | no adapter | YES (jobs.taleo.net) | YES (unit) | n/a | — | DETECT-ONLY |
| PageUp | no adapter | YES (careers.pageuppeople.com) | YES (unit) | n/a | — | DETECT-ONLY |

Design (task §12): detection and routing live in ONE place
(`app/ats_detect.py`) — `detect_ats(url)` returns the provider,
`adapter_for(url)` returns the existing adapter that can query it, or None.
No ATS parsing is duplicated anywhere; `company_careers.py` routes
ATS-hosted pages to their adapters instead of re-parsing them.
