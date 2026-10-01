# STAGE-3 ELIGIBILITY — Audit (before → after)

What existed before this stage, what was weak, and what changed. Only Stage-3
was touched; DISCOVER and CLASSIFY were not modified.

## What existed before

`app/eligibility.py#EligibilityEngine.check(job, freshness=None)` returned
`EligibilityResult(eligible, reasons, details)` from a single function that
checked, in order: dismissed → location_classified/region → work-type/salary →
freshness → description length.

`app/routers/eligibility.py` built the engine from live config and exposed
`POST /jobs/{id}/eligibility` + `GET /eligibility/eligible-jobs` +
`GET /jobs/{id}/freshness`.

`app/database.py#get_eligible_jobs` provided an SQL "eligible pool"
(dismissed=0, classified, in-region, posted within 7 days, description ≥ 80).

`app/freshness.py` was solid (three states, DATE_UNKNOWN terminal).

## Gaps found

| # | gap | impact | fix |
|---|---|---|---|
| 1 | **SCORE ignored eligibility.** `get_unscored_jobs` gated only on `dismissed=0 AND location_classified=1`. | Stale / out-of-region / unknown-date / already-applied jobs were AI-scored — ineligible jobs leaked into SCORE. | New `get_scoreable_jobs` (requires `eligibility_status='ELIGIBLE'`); both SCORE entry points use it. |
| 2 | **No persistence, no gate, no evidence.** Only a bool + reason list; nothing recorded on the job. | "Why was this rejected?" required reading code; no metrics; no review queue. | Persisted `eligibility_status/gate/reason/evidence/evaluated_at`; `reason` chooses the earliest gate. |
| 3 | **No already-applied protection.** | The pipeline could build a package for a job already submitted. | ALREADY_APPLIED gate over submitted application statuses. |
| 4 | **No closed-job handling.** | Nothing stopped an expired posting. | JOB_STATUS gate reading `job_status`/`closing_date` (positive evidence only). |
| 5 | **No data-sanity gate.** | Jobs with no title/company/URL could pass. | DATA_SANITY gate. |
| 6 | **Didn't consume Stage-2.** Only `location_region` was read. | Country code, confidence, source and `supported_countries` were ignored. | LOCATION gate reads all Stage-2 fields; remote/region/multi-location aware. |
| 7 | **Unknown location passed.** `region == "Unknown"` was explicitly allowed through. | Unclassified-country jobs were treated as eligible. | Unknown country → REVIEW_REQUIRED (never fabricated, never auto-accepted). |
| 8 | **No metrics.** | DIGEST had no structured rejection counts. | `eligibility_metrics` (status/gate/reason tallies) + `GET /eligibility/metrics`. |
| 9 | **Salary-floor reason mislabeled** as `WORK_TYPE_NOT_ALLOWED`. | A rejection for pay claimed a work type was evaluated — not explainable (task §20). | **Fixed** in the 2026-10-01 quality audit → `SALARY_BELOW_FLOOR`. |
| 10 | **DATE_UNKNOWN reported as INELIGIBLE.** | "We don't know the date" was presented as proof of a bad job. | **Fixed** → `REVIEW_REQUIRED` (still never fresh, still never scored). |

## What was deliberately NOT changed

- Freshness module (already correct, DATE_UNKNOWN terminal).
- `get_eligible_jobs` SQL pool (used by `GET /eligibility/eligible-jobs`).
- `auto_dismiss_stale` and the strategy dismissal/restore machinery.
- No relevance/scoring logic was added; no visa inference; no AI.

## Verification

- `tests/test_eligibility.py` — 33 tests (was 14; +15 new gates, +4 audit fixes).
- Regression: eligibility, stale_jobs, database, daily_run, scheduler,
  classification, pipeline, discovery_upgrade, workspaces, scoring_failures →
  **216 passed**; api, multiuser, matcher, crm, apply, evidence,
  hybrid_matcher, daily_run → **105 passed**.
- Live: 1,962 real workspace rows evaluated on a copied DB — see
  `LIVE_SAMPLE_RESULTS.md`.
- Quality audit (75 rows manually reviewed, 2 defects found + fixed,
  before/after numbers): see `QUALITY_AUDIT.md`.
