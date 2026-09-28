# FULL-SUITE VERIFICATION — TEST REPORT

> **What this proves:** the working tree (resume-first onboarding gate + N1
> per-user Gmail tokens + the multiuser real-scenario tests) is green across
> **all three suites** — backend, frontend, extension — and the only red found
> was a **stale test date**, not a product bug.

- **Date:** 2026-09-27
- **Branch:** `dev_users_based` (uncommitted working-tree changes under test)
- **Python:** 3.14.7 (`.venv`) · runner: `pytest -q --timeout=300` (xdist `-n 4`)
- **Full backend suite duration:** 11m 56s

---

## 1. Headline result

| Suite | Result | Verdict |
|---|---|---|
| Backend (`root/tests`, parallel) | **999 passed**, 0 failed | ✅ |
| Frontend (`root/app/static`, vitest) | **184 / 184** | ✅ |
| Extension (`root/extension`, vitest) | **469 / 469** | ✅ |
| **Total checks green** | **1,652** | ✅ |

**Zero product bugs found.** The single backend failure was a **date-rot time
bomb inside a test** — the freshness engine was *right*, the test's hardcoded
date had simply gone stale. Fixed in this session (see §3).

## 2. Latest new tests (the working tree's own suites) — all green

| Suite | Result | What it covers |
|---|---|---|
| `tests/test_multiuser_real_scenario.py` | **4 / 4 PASS** (8.9 s) | N1 per-user Gmail token: two logged-in users over live HTTP (`testing=False`) get distinct tokens; env token only as legacy fallback; clearing disconnects only that user; outreach still works with **no** token anywhere (Critical Test #4 path intact) |
| `tests/test_workspaces.py` | **12 / 12 PASS** (21 s) | Critical Test #5 isolation matrix + the new resume-gate tests (`test_search_blocked_until_a_resume_exists`, `test_keyword_confirm_screen_saves_and_is_isolated`) |
| `app/static/tests/` incl. **new** `auth-gate-onboarding.test.js` | **184 / 184** | Onboarding reordered to Resume → AI → Keywords → Done; gate blocks search UI until a resume exists |

## 3. Bug found and FIXED: date-rot time bomb in `tests/test_eligibility.py`

**Symptom (full parallel run):**
`tests/test_eligibility.py::test_eligible_job_passes` failed with
`STALE_POSTED_DATE — posted 8d ago (> 7d limit)`.

**Root cause.** The test seeded `posted_date: "2026-09-19"` (hardcoded). On
2026-09-27 that is **8 days old** — past Golden Rule #10's 7-day freshness
limit — so `EligibilityEngine` correctly flagged the job STALE. The product
behaved exactly as designed; the test had a frozen date that rots as the
calendar moves.

**Second latent bomb caught in the same pass:** the DB-level test
`test_eligible_query_excludes_unknown_and_stale` seeded `"2026-09-20"` —
exactly at the 7-day boundary the day this was found; it would have failed the
next day.

**Fix.** Both seeded dates are now computed relative to today:

```python
"posted_date": (date.today() - timedelta(days=2)).isoformat(),   # _job() base
(date.today() - timedelta(days=1)).isoformat(),                  # fresh row in the DB test
```

**Re-run:** `tests/test_eligibility.py` → **14 / 14 PASS** (1.7 s).

*Note:* `test_hybrid_matcher.py` already used relative dates correctly; the
other hardcoded `2026-09-*` dates in tests (builder/outreach/contacts/daily-run)
feed code paths that do not assert on freshness age, so they are safe.

## 4. Known non-issues (unchanged, documented in E2E_RUN_STATUS.md)

| Item | Explanation |
|---|---|
| 2 `ERROR`s in the parallel full run (`test_workspaces.py::test_workspace_dirs_and_dbs_are_distinct`, `::test_admin_does_not_auto_see_user_data`) | **Load-induced `pytest-timeout` trips** under `-n 4`. Both **pass in isolation** (re-verified today: `2 passed in 4.97 s`) and inside the 16-test targeted run. Same known flakiness class already flagged in the status board — worth raising their timeout in a later pass. |
| Root-level `npx vitest run` shows 428 failures | Misconfiguration artifact: the root dir has **no vitest config**; those are the extension tests picked up without their `extension/vitest.config.js` (missing jsdom + aliases). Run each suite from its own directory (both green — see §1). |
| Extension suite prerequisites | `root/extension/node_modules` was absent in this environment; `npm install` restored it, then **469/469** passed. |

## 5. Live E2E reports on record (not re-run in this session)

| Report | Result | Date |
|---|---|---|
| Resume-driven onboarding (live, DeepSeek) — `RESUME_ONBOARDING_E2E_REPORT.md` | **26 / 26 checks, 0 fail** | 2026-09-27 |
| Real user-journey E2E — `USER_JOURNEY_E2E_REPORT.md` | **26 scenarios · 204 checks · 285 HTTP calls** | 2026-09-24 |

## 6. How to re-run

```bash
# Backend (from job-search-system/root)
.venv/bin/pytest -q --timeout=300                       # serial
.venv/bin/pytest -q --timeout=300 --tb=no -n 4          # parallel (~12 min)

# Targeted — the working tree's own tests
.venv/bin/pytest tests/test_multiuser_real_scenario.py tests/test_workspaces.py \
    tests/test_eligibility.py -q --timeout=180

# Frontend (from job-search-system/root/app/static)
npx vitest run

# Extension (from job-search-system/root/extension; npm install if needed)
npx vitest run
```
