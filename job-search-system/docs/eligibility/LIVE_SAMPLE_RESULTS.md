# STAGE-3 ELIGIBILITY — Live Sample Results

Validation of the **shipped** Stage-3 pass over a **copy** of Basil's real
workspace DB (1,996 jobs) — never his original. The script copies the DB, runs
the real `run_location_classification` (Stage-2) then `run_eligibility_pass`
(Stage-3), and aggregates the persisted decisions.

**Run:** 2026-10-01
```bash
cd job-search-system/root
.venv/bin/python -u ../analysis/verify_eligibility_live.py
```
Machine-readable output: `docs/eligibility/results/eligibility_summary.json`.

> **Superseded for reason/status labels by `QUALITY_AUDIT.md` (2026-10-01).**
> This file records the *first* live run, before two audit fixes: the
> salary-floor reason is now `SALARY_BELOW_FLOOR` (was
> `WORK_TYPE_NOT_ALLOWED`) and `POSTED_DATE_UNKNOWN` is now `REVIEW_REQUIRED`
> (77 rows) instead of INELIGIBLE. Gate counts and the 67 ELIGIBLE are
> unchanged. Use `QUALITY_AUDIT.md` for authoritative numbers.

Target regions: Australia, Canada, Germany, India, Ireland, Netherlands,
Poland, Singapore, UAE, UK, Remote.

## Overall (1,962 classified jobs)

| status | count |
|---|---:|
| ELIGIBLE | 67 |
| INELIGIBLE | 1,895 |
| REVIEW_REQUIRED | 0 |
| UNKNOWN | 0 |

**By gate:** DISMISSED 1,357 · FRESHNESS 515 · LOCATION 20 · EVIDENCE 1 ·
ALREADY_APPLIED 2 · FINAL_ELIGIBILITY 67.

**Top reasons:** `DISMISSED_BY_COUNTRY_STRATEGY` 941 · `STALE_POSTED_DATE` 436
· `DISMISSED` 416 · `POSTED_DATE_UNKNOWN` 79 · `OK` 67 ·
`WORK_TYPE_NOT_ALLOWED` 20 (salary floor) · `ALREADY_APPLIED` 2 ·
`MISSING_DESCRIPTION` 1.

## Per region

| region | evaluated | eligible | ineligible | review | top reasons |
|---|---:|---:|---:|---:|---|
| US | 1205 | 0 | 1205 | 0 | strategy-dismissed 938, dismissed 266 |
| Singapore | 262 | 12 | 250 | 0 | stale 176, dismissed 54, salary floor 20 |
| Remote | 251 | 27 | 224 | 0 | stale 149, dismissed 45, date-unknown 29 |
| UK | 103 | 9 | 94 | 0 | stale 45, dismissed 33, date-unknown 15 |
| Germany | 36 | 5 | 31 | 0 | date-unknown 16, dismissed 8, stale 7 |
| India | 28 | 5 | 23 | 0 | stale 13, date-unknown 10, OK 5 |
| Unknown | 25 | 0 | 25 | 0 | stale 24, date-unknown 1 |
| Canada | 19 | 2 | 17 | 0 | stale 15, OK 2 |
| Ireland | 15 | 4 | 11 | 0 | dismissed 8, OK 4 |
| Netherlands | 8 | 3 | 5 | 0 | date-unknown 3, OK 3 |
| UAE / Australia / Poland / buckets | ≤3 each | 0 | all | 0 | stale / date-unknown / dismissed |

## Manual review sample (task §34)

| kind | job | location | region | posted | decision |
|---|---|---|---|---|---|
| eligible | #1145 Senior AI Engineer | Remote | Remote | 2026-09-24 | ELIGIBLE / FINAL_ELIGIBILITY / OK |
| eligible | #1163 Senior AI Engineer (Node.js) | Remote | Remote | 2026-09-24 | ELIGIBLE / FINAL_ELIGIBILITY / OK |
| stale | #10 Senior AI Engineer | "Northern America, LATAM, Europe…" | Unknown | 2026-09-18 | INELIGIBLE / FRESHNESS / STALE_POSTED_DATE |
| unknown date | #1 Member of Technical Staff | Full-time | Unknown | — | INELIGIBLE / FRESHNESS / POSTED_DATE_UNKNOWN |
| dismissed | #3 Machine Learning Engineer | Irvine, CA | US | — | INELIGIBLE / DISMISSED / DISMISSED_BY_COUNTRY_STRATEGY |
| already applied | #149 AI Engineer | Los Angeles, CA | US | 2026-09-23 | INELIGIBLE / ALREADY_APPLIED / ALREADY_APPLIED |
| already applied | #1167 Senior AI Engineer | Remote | Remote | 2026-09-24 | INELIGIBLE / ALREADY_APPLIED / ALREADY_APPLIED |

These make sense: remote country-agnostic roles with fresh dates and full
descriptions pass; anything stale, undated, strategy-dismissed or already
submitted stops. Note the rule ordering is visible and correct — e.g. #149 has
a US region AND an application; the earliest gate (ALREADY_APPLIED) is reported
even though the region is also untargeted.

## What this proves

- The gate chain runs over real, messy rows with no crashes and fully
  deterministic decisions.
- The SCORE contract holds on real data: only the 67 ELIGIBLE rows are returned
  by `get_scoreable_jobs`, so 1,895 ineligible/review rows cannot enter SCORE.
- **REVIEW_REQUIRED is 0 here because every unknown-region row in this pool is
  *also* stale or undated** and FRESHNESS precedes LOCATION — an honest
  consequence of the gate order, not a missing rule. Unknown-country review is
  proven by unit tests (`test_unknown_country_is_review_not_fabricated`,
  `test_low_confidence_location_is_review`, `test_remote_region_buckets`).
