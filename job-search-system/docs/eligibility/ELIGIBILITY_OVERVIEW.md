# STAGE-3 ELIGIBILITY — Overview

**Status:** audit + harden + test + live-validate COMPLETE (2026-10-01).
Deterministic gate chain, evidence-backed decisions, SCORE contract enforced.

Stage-3 ELIGIBILITY answers exactly one question:

> **Should this job be allowed to proceed to SCORE?**

It evaluates factual/gating conditions only. It never judges relevance —
skill match, experience match, title relevance and résumé similarity belong to
Stage-4 SCORE / the hybrid matcher. A job can be perfectly eligible and still
score near zero.

## Where it sits

```
RESUME → DISCOVER → CLASSIFY → [ELIGIBILITY] → SCORE → HYBRID → SELECT → …
```

- Entry: `app/eligibility.py#EligibilityEngine.check` (pure, deterministic).
- Stage pass: `app/scheduler.py#run_eligibility_pass` — evaluates un-evaluated
  jobs and **persists** status/gate/reason/evidence.
- SCORE contract: `app/database.py#get_scoreable_jobs` returns only jobs with
  `eligibility_status = 'ELIGIBLE'`. Both SCORE entry points (`app/main.py`
  AI scoring, `app/matching_service.score_all_unscored`) use it, so INELIGIBLE
  and REVIEW_REQUIRED jobs cannot leak into scoring.
- API: `POST /api/jobs/{id}/eligibility`, `GET /api/eligibility/eligible-jobs`,
  `GET /api/eligibility/review-jobs`, `GET /api/eligibility/metrics`.

## What changed (before → after)

| | Before | After |
|---|---|---|
| Gates | ad-hoc checks in one function | explicit ordered chain DATA_SANITY → DISMISSED → ALREADY_APPLIED → JOB_STATUS → FRESHNESS → LOCATION → EVIDENCE → FINAL |
| Output | `eligible` bool + reason list | + `status`, `gate`, `reason`, `evidence` |
| Consumes Stage-2 | only `location_region` | country_code, confidence, source, supported_countries, remote/region |
| SCORE gate | `dismissed=0 AND location_classified=1` | **+ `eligibility_status='ELIGIBLE'`** (ineligible/review never scored) |
| Persistence | none | `eligibility_status/gate/reason/evidence/evaluated_at` per job |
| Metrics | none | `search_config.eligibility_metrics` + live tallies |
| Already-applied | not checked | ALREADY_APPLIED gate (submitted applications only) |
| Closed jobs | not checked | JOB_STATUS gate (positive evidence only) |

## Gate chain (summary)

1. **DATA_SANITY** — title/company present (hard), actionable URL (review).
2. **DISMISSED** — user or country-strategy dismissal (hard).
3. **ALREADY_APPLIED** — a submitted application exists (hard); saved
   `interested`/built-but-unsent `prepared` do NOT block.
4. **JOB_STATUS** — `job_status ∈ closed…` or a passed `closing_date` (hard);
   never inferred from a scraper returning no results.
5. **FRESHNESS** — VERIFIED_FRESH passes; STALE / DATE_UNKNOWN are hard
   (Critical Test #3: DATE_UNKNOWN never fresh).
6. **LOCATION** — Stage-2 country/region vs configured targets, remote/region
   and multi-location aware. Unknown → REVIEW, not targeted → INELIGIBLE.
7. **EVIDENCE** — required description present.
8. **FINAL_ELIGIBILITY** — nothing stopped it → ELIGIBLE.

Full detail, reason codes and statuses: `GATE_RULES.md`.

## Docs map

- `ELIGIBILITY_AUDIT.md` — what existed before and the gaps closed.
- `GATE_RULES.md` — gates, statuses, reason codes, country/remote/confidence rules.
- `TEST_RESULTS.md` — unit + regression counts.
- `LIVE_SAMPLE_RESULTS.md` — real workspace rows (copied DB), per-country.
- `KNOWN_LIMITATIONS.md` — honest gaps.
- `results/eligibility_summary.json` — machine-readable live run.
