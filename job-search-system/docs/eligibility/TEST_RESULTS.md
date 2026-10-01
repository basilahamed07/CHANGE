# STAGE-3 ELIGIBILITY — Test Results

**Run:** 2026-10-01 · `cd job-search-system/root`
Command: `.venv/bin/python -m pytest <files> -q --timeout=60 -p no:cacheprovider`

## Unit suite — `tests/test_eligibility.py`

```
33 passed in ~5s
```

Coverage map (task §31):

| area | tests |
|---|---|
| eligible happy path + status/gate/reason | `test_eligible_job_passes`, `test_status_gate_reason_on_happy_path` |
| dismissed (+ gate) | `test_reason_dismissed_variants`, `test_dismissed_reports_gate` |
| already-applied (+ non-blocking saved) | `test_already_applied_hard_gate` |
| closed job / closing date | `test_job_closed_gate` |
| freshness fresh/stale/unknown | `test_fresh_within_7_days`, `test_stale_beyond_7_days`, `test_critical_3_*` |
| target / non-target country | `test_reason_region`, `test_target_country_via_stage2_code` |
| unknown country → review | `test_unknown_country_is_review_not_fabricated` |
| low-confidence location → review | `test_low_confidence_location_is_review` |
| remote buckets / worldwide | `test_remote_region_buckets` |
| multi-location supported | `test_multi_location_supported_country_matches` |
| data sanity (title/company/url) | `test_data_sanity_missing_identity_and_bad_url` |
| no work-auth fabrication | `test_no_work_authorization_fabrication` |
| idempotency | `test_eligibility_is_idempotent`, `test_eligibility_pass_is_idempotent` |
| Stage-4 SCORE contract | `test_stage4_score_contract_blocks_ineligible` |
| metrics | `test_stage4_score_contract_blocks_ineligible` (asserts metrics blob) |
| multi-user isolation | `test_multiuser_eligibility_isolation` |
| **audit fix A: salary reason** | `test_salary_floor_uses_dedicated_reason` |
| **audit fix B: DATE_UNKNOWN status** | `test_date_unknown_is_review_not_rejection`, `test_date_unknown_with_hard_reason_stays_ineligible`, `test_date_unknown_never_enters_scoreable` |

**Critical assertions proven:**
- **Critical Test #3** — DATE_UNKNOWN is never fresh, never eligible (freshness
  unit tests + gate test + DB pool test).
- **Critical Test #4** — User A's dismissal/application never affect User B
  (`test_multiuser_eligibility_isolation`).
- **Critical Test #5/#6** — an INELIGIBLE/REVIEW job is absent from
  `get_scoreable_jobs`; an ELIGIBLE job is present.

## Regression suites

```
test_stale_jobs, test_database, test_daily_run, test_pipeline,
test_classification, test_discovery_upgrade, test_workspaces,
test_scheduler, test_scoring_failures, test_eligibility
→ 216 passed in ~66s
```

```
test_api, test_multiuser_real_scenario, test_matcher, test_crm, test_apply,
test_evidence, test_hybrid_matcher, test_daily_run
→ 105 passed in ~41s
```

The SCORE entry points (`app/main.py`, `app/matching_service.py`) and the DB
suite pass unchanged after switching to `get_scoreable_jobs`, confirming the
contract change did not break existing scoring behavior for eligible jobs.

## Bugs caught and fixed during this stage

1. **Infinite loop in `run_eligibility_pass`** — the batch UPDATE tuple was in
   `(job_id, status, …)` order while the SQL expects `(status, …, job_id)`, so
   statuses were never set and the pass looped forever. Caught by the new
   idempotency test (it hung) → fixed to SQL parameter order.
2. **Reason/gate divergence** — `reason` was taken as the first *appended*
   reason rather than the *earliest gate*. Now resolved by `GATE_ORDER`.
3. **Salary-floor reason mislabeled** (found by the 2026-10-01 quality audit) —
   reported `WORK_TYPE_NOT_ALLOWED`; now `SALARY_BELOW_FLOOR`.
4. **DATE_UNKNOWN reported as a proven rejection** (same audit) — now
   `REVIEW_REQUIRED`, preserving Critical Test #3.
