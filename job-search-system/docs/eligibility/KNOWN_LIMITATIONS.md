# STAGE-3 ELIGIBILITY — Known Limitations

Honest gaps. None block the stage; each is recorded so a later session does not
mistake it for coverage.

1. **Location-driven REVIEW is untested on live data.** In Basil's real pool
   every unknown-region job is also stale/undated, so FRESHNESS precedes
   LOCATION and location-review never surfaces. (The 77-row REVIEW queue that
   now exists comes from DATE_UNKNOWN.) Unknown-country / remote-bucket / low-
   confidence review paths are proven by unit tests only. `QUALITY_AUDIT.md` §6
   explains why: legacy rows have no Stage-2 `country_code`.

2. **`WORK_TYPE_NOT_ALLOWED` on the salary-floor gate — FIXED 2026-10-01.**
   The audit found salary-floor rejections labelled as a work-type failure;
   they now report `SALARY_BELOW_FLOOR`. `R_WORK_TYPE` is retained but
   currently unreachable (no real work-type rule is configured). See
   `QUALITY_AUDIT.md`.

3. **Work-type restrictions from country YAML are effectively inert.** The
   original code looked for a `{work_types: …}` dict inside
   `min_salary_by_region`, which the router never populates (it puts integers).
   This stage preserves the salary floor but does not resurrect the work-type
   rule; doing so needs a real config shape.

4. **`job_status` / `closing_date` are new, currently unpopulated columns.**
   No adapter writes them yet, so the JOB_STATUS gate is inert in production
   until discovery populates closure signals. It is implemented and tested so
   it activates the moment those fields are set — and it can never fire from a
   scrape miss.

5. **Re-evaluation is NULL-status-driven.** `run_eligibility_pass` evaluates
   jobs whose `eligibility_status IS NULL` (plus a `force` option). It does not
   automatically re-evaluate a job whose *inputs* change later (e.g. a
   previously ineligible job gets a description enriched, or the user's target
   regions change). `force=True` and `apply_country_strategy` cover the
   strategy-change case; per-input cache invalidation is deliberately avoided
   (task §23 — no unnecessary cache complexity).

6. **Multi-location primary is string order.** The LOCATION gate accepts a job
   if *any* `supported_countries` entry is targeted, but the primary region
   (used for display/metrics) is whatever Stage-2 chose first.

7. **No HTTP-API E2E for the new endpoints.** Verification is at the module +
   scheduler + DB levels (the exact code the pipeline runs). The router surface
   (`/eligibility/review-jobs`, `/eligibility/metrics`) was not driven over a
   live server in this stage.

8. **Work authorization / experience are intentionally out of scope.** No visa
   verdict is inferred (task §17) and experience mismatches stay in SCORE
   (task §18); this is correct by design, not a gap, but is listed so the
   boundary is explicit.
