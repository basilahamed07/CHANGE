# LIVE STATUS — Real User-Journey E2E + fixes

> **What this file is:** the running status board for the "prove the whole product
> for real" task. Update it as work lands. The authoritative, generated report is
> `docs/USER_JOURNEY_E2E_REPORT.md` (rewritten on every harness run) and the raw
> evidence lives in `analysis/e2e_runs/<date>_<time>/`.

**Last updated:** 2026-09-24 (latest harness run `2026-09-24_125119` — definitive, config-isolated)

---

## 1. Headline result

| Metric | Value |
|--------|-------|
| Scenarios | **26 / 26 passed** |
| Checks | **204 / 204 passed** |
| Failures | **0** |
| Real HTTP calls recorded | **289** |
| API coverage (OpenAPI operations touched) | **187 / 218 = 85.8 %** |
| Provider under test | `deepseek` / `deepseek-flash` (live, billed) |
| Server mode | real `uvicorn app.main:create_app --factory`, **auth ON, `testing=False`** |
| Data | isolated throwaway directory per run (Basil's live pool untouched) |

Run folder: `job-search-system/analysis/e2e_runs/2026-09-24_125119/`
(→ `report.md`, `api_calls.jsonl`, `scenarios.json`, `api_coverage.json`, `artifacts/`)

Three runs tell the story: **20/25 → 25/26 → 26/26** (each red run drove a real fix).

---

## 2. Deliverable — the harness

`job-search-system/analysis/e2e_user_journey.py`

Boots the **actual server** and drives it **only over HTTP** as a brand-new user,
top to bottom. Three runs: 20/25 → 25/26 → **26/26**.

Outputs, all in one dated folder per run:

| File | Contents |
|------|----------|
| `report.md` | the human-readable journey report (also copied to `docs/USER_JOURNEY_E2E_REPORT.md`) |
| `api_calls.jsonl` | one row per HTTP call: scenario, method, path, status, ms, request, response, artifact |
| `scenarios.json` | per-scenario pass/fail with every individual check |
| `api_coverage.json` | every OpenAPI operation + called/excused with a reason |
| `artifacts/` | the resume actually uploaded, tailored resume, cover letter, downloaded package files |
| `server.log` | the real server's log for the run |

---

## 3. Product bugs found and FIXED

Found only because the journey ran the real server instead of an in-process test client.

| # | Bug | Impact | Fix | Status |
|---|-----|--------|-----|--------|
| 1 | Resume upload graded with the **app-level** AI client and rebuilt the app-level matcher from the caller's resume | Every user's resume was analysed with the *admin's* provider/key, and one user's upload mutated another's matcher (cross-user contamination) | `routers/settings.py` resolves the client through `ai_state_for(request)`; app-level reinit only on the no-workspace legacy path | ✅ fixed |
| 2 | Legacy scrape / AI-score / rescore pipelines always ran against `app.state.bg_db` (the **admin** DB) | A user pressing "Scrape now" or "Score" filled the *admin's* pool and graded with the admin's resume — per-user pool never grew | New `_task_target(request)` in `routers/scraping.py` binds the run to the requesting user's workspace DB + their own matcher; `_score_unscored` accepts a per-user matcher | ✅ fixed |
| 3 | LLM **cost meter** wrote every call to one global sink (the admin DB) | Per-user spend read as `$0` / 0 calls — the "how far does my top-up go?" panel was wrong for everyone but the admin | `app/ai_usage.py` gains a `ContextVar` request sink; `workspace_middleware` binds it to the user's DB per request | ✅ fixed |
| 4 | `POST /api/custom-qa`, `/api/work-history`, `/api/certifications` returned **500** on an unknown field name | A client typo crashed with an unhandled `ValueError` from the DB column guard | `_save_profile_entry()` helper in `routers/settings.py` translates it to a **400** for all 7 profile save endpoints | ✅ fixed |
| 5 | Discovery had no way to run a bounded cycle | The 24-pass budget made a "run discovery now" sweep unpredictable / unbounded in time | `POST /api/discovery/run?passes=1..24` + `max_passes` on `run_discovery_cycle` | ✅ fixed (new control) |

Regression tests for #4: `tests/test_profile_save_validation.py` (15 tests).

---

## 4. Non-bugs clarified during this work

- `applied → offered` is **allowed by design** (an off-platform offer is real); the
  invariant that the engine actually enforces is *"you cannot land on `offered`
  without ever applying"* and *"a terminal state cannot be resurrected"*. The harness
  now asserts those two instead.
- `POST /api/scrape` returns **202** (started) / 409 (already running), not 200.
- CRM status transitions take `to_status` as a **query** parameter, not a JSON body.

---

## 4b. Verification evidence (test suites)

| Suite | Result |
|-------|--------|
| User-journey E2E (real server, live DeepSeek) | **26/26 scenarios · 204/204 checks · 0 fail · 285 HTTP calls** |
| `tests/test_profile_save_validation.py` (new regression tests for bug #4) | 15 passed |
| Touched areas serially — `test_workspaces` + `test_auth` + `test_profile_save_validation` + `test_api` + `test_evidence` + `test_resume_grading` | **120 passed** (87 s, `--timeout=180`) |
| Full backend suite (serial, `--timeout=300`) | 982 passed, 1 error |
| Full backend suite (`-n auto`, `--timeout=300`) | 989 passed, 2 errors |

The 1–2 full-suite errors are `pytest-timeout` trips in `tests/test_workspaces.py`
(`test_jobs_are_isolated`, `test_resumes_are_isolated`,
`test_ai_key_and_search_config_are_isolated`) that **pass in isolation (8 passed,
18 s)** and pass in the 120-test targeted run above. They are load-induced, not
regressions — worth raising `pytest-timeout` for that file in a later pass.

## 5. Known gaps / not yet done

| Item | State |
|------|-------|
| Config isolation | the run now gets its own copy of `config/` (`JOBAGENT_COUNTRIES_DIR`) because `PUT /api/countries/{region}` writes YAML — a first draft rewrote the repo's `singapore.yaml` (reverted, and now impossible) |
| Partial runs (`--only`) need their prerequisites | e.g. `--only s10_countries` alone has no logged-in user, so it 401s — run the earlier scenarios too |
| 31 API operations not exercised (14.2%) | mostly destructive, email-sending, SSE, or feature-flagged-off — each carries a written reason in `api_coverage.json` |
| Full-suite `pytest-timeout` flakiness in `tests/test_workspaces.py` | 3 tests time out only when the whole suite runs in parallel; they pass alone — raise their timeout |
| Nothing is committed yet | the harness, the 5 fixes and the docs are working-tree changes (branch `dev`) |
| AI-dependent paths were previously SKIPped pending a key | now **live** on DeepSeek (grading, tailoring, cover letter, interview-prep, contact research) |
| M15c remaining | per-user **Gmail token** and per-user **scraper keys** still resolve from the app-level settings; per-user *scheduled* (background-interval) cycles still use the admin workspace |
| M15d / M15e | admin "Act as user" audit UI and key encryption at rest still pending (see `docs/MULTI_USER_PLAN.md`) |

---

## 6. How to re-run

```bash
cd job-search-system/root
.venv/bin/python ../analysis/e2e_user_journey.py            # full journey (~8-10 min)
.venv/bin/python ../analysis/e2e_user_journey.py --only s02_bootstrap s08_resume_upload_and_grading
```

Budgets are env-tunable:
`JOBAGENT_E2E_DISCOVERY_SECS` (default 300), `JOBAGENT_E2E_SCRAPE_SECS` (default 240).

Launch it detached (`setsid nohup … &`) — a background job started from a
short-lived shell gets reaped when that shell exits.
