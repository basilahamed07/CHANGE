# STAGE TEST RESULTS — execution log

> **What this is:** the record of everything that was actually run on 2026-10-03, with real output.
> Before this run, **no test had ever been executed** for the stages 4–10 work — every stage doc was
> written from reading code. This file is the evidence that changed that.
>
> Companions: `STAGE_ROADMAP.md` (status) · `DEFECT_BACKLOG.md` (42 open defects) ·
> `docs/<stage>/TEST_RESULTS.md` and `docs/<stage>/LIVE_SAMPLE_RESULTS.md` (per stage).

---

## 1. Test suites

| # | Command | Result |
|---|---|---|
| 1 | `uv run pytest tests/test_scoring.py -q` | **23 passed** |
| 2 | `uv run pytest tests/test_matcher.py tests/test_matcher_extended.py tests/test_scoring.py -q` | **37 passed** |
| 3 | `uv run pytest` over the stage-relevant group¹ | **212 passed, 1 failed → fixed** |
| 4 | `uv run pytest -q --timeout=300` (full backend) | **1171 passed, 0 failed** (300 s) |

¹ `test_hybrid_matcher, test_daily_run, test_digest, test_outreach, test_application_builder,
test_contact_providers, test_evidence, test_eligibility, test_classification, test_dedup`

The full suite was run twice: the first pass surfaced the flaky heartbeat test described below;
after the fix, the second pass was **1171 passed, 0 failed**.

### Four tests were wrong, not the code

Every failure was a **test that encoded behaviour the hardening deliberately removed**, or a
platform assumption. No product defect was found by the suite.

| Test | Why it failed | Fix |
|---|---|---|
| `test_matcher_extended.py::test_parse_batch_response_missing_entry` | asserted the *old* D1 behaviour: a job with no batch entry gets a fabricated `score=0`. Hardening omits it instead. | rewritten to assert the omitted job is absent and nothing is invented |
| `test_eligibility.py::test_job_closed_gate` | used **local** `date.today()` while the engine compares against **UTC** `_today()`. When local date ≠ UTC date the computed "yesterday" is still today in UTC, so the job is correctly not closed. Wall-clock dependent. | derive past/future from the same UTC clock and pass `now=` explicitly |
| `test_api.py::test_build_ai_client_signature_accepts_settings_object` | built `Settings(...)` without blanking `deepseek_api_key`, so the key now in `.env` leaked in and produced a client where the test expected `None`. | `_env_file=None` + every provider key blanked — the test is about the function, not the machine |
| `test_scrape_robust.py::test_scrape_heartbeat_updates` | Windows `time.monotonic()` ticks ~15.6 ms; the fake cycle finished inside one tick so both reads tied and `>` failed. Flaky under load only. | wait for a real clock tick before running; assertion stays strict |

| `test_workspaces.py::test_first_migration_moves_db_together_with_its_wal` | held a live SQLite handle open across the migration; Windows refuses to rename/unlink an open file (`WinError 32`). | sidecars materialised as real files on disk; the move-one-unit contract is still asserted |

---

## 2. Live verification (copied DB, never the original)

| Stage | Script | Result |
|---|---|---|
| 2 CLASSIFY | `verify_classification_live.py` | **PASS** — curated battery 16/16; live rows 104/104 classified, 0 UNKNOWN, 0 AI fallback, 0 conflicts |
| 3 ELIGIBILITY | `verify_eligibility_live.py` | **PASS** — 1244 evaluated → **26 ELIGIBLE**, 1201 INELIGIBLE, 17 REVIEW_REQUIRED; gate chain behaves as designed |
| 4 SCORE | `verify_score_live.py` | **PASS** — pool 26, `stage3_leaked_scores=0`, `d1_fabricated_zero_total=0`; live scoring 3/3 accounted for, 0 fabricated |

### Stage-4 live scoring — the end-to-end proof

```
scoring 3 real jobs via deepseek/deepseek-flash ...
requested: 3   scored: 3   skipped: 0
scores: #259 → 35 (role_match=false)   #260 → 63 (true)   #295 → 72 (true)
```

`scored + skipped == requested` proves the new **"omit, never pad"** parser against a real model. A
genuine resilience path also fired live: DeepSeek's first reply returned
`finish=length, chars=0, reasoning_tokens=1536`; `app/ai_client.py` escalated the output budget,
retried, and succeeded.

---

## 3. Phase-0 — resume AI evaluation (`analysis/resume_ai_eval.py`)

**COMPLETE, 3/3 AI calls (hard cap honoured).**

```
Resume: Basil Ahamed H - AI Engineer Resume.docx  (4282 chars)
Model : deepseek / deepseek-flash
[1/3] analyze_resume()  →  ATS score 90/100, 12 search terms, 5 issues
[2/3] critique()        →  8 weaknesses, 5 rewrites
[3/3] role_fit()        →  best role: Agentic AI Engineer
```

Raw output (private): `root/data/resume_ai_eval.json`. Written findings: `docs/RESUME_AI_EVAL.md`.

---

## 4. The deployment finding that shaped everything

**The live data is split across two databases, so no single DB can run the pipeline end-to-end.**

| DB | jobs | resumes | ai_settings |
|---|---|---|---|
| `root/data/jobagent.db` | **1245** | 0 | 0 |
| `root/data/users/1-basil/jobagent.db` | 0 | 2 | 1 (deepseek) |

The job rows are in the *legacy* location; the resume and AI settings are in the *workspace*. The
verifiers originally read only the workspace DB, so every "live" number came back zero — a silent
false-negative. All three verifiers now select the DB that actually holds jobs, and the Stage-4
verifier borrows the real resume + settings from the workspace (on the copy only).

**This also means the running app, if it opens the workspace DB, currently shows 0 jobs.** Worth
confirming which DB the server actually binds before the next live run.

---

## 5. What is proven vs. still open

**Proven by execution:**
- Stage-2 classification: green (unit + live).
- Stage-3 eligibility: green (unit + live), gate chain correct on 1244 real jobs.
- Stage-4 scoring: green (unit + live + real AI call), no fabrication, containment holds.
- Phase-0: complete.

**Fixed since this log was written — all four P0s:**
- **P0 #4 SSRF** — fixed and committed `c96e0f7` (`app/url_safety.py` + 30 tests).
- **P0 #1 ungated send** — fixed 2026-10-03 by deleting the endpoint, its helper, and the UI send
  button; `tests/test_email_digest.py` gains two route-level guards. `test_email_digest.py` → 15 passed.
- **P0 #3 hybrid destroys the AI score (Stage-5 H1)** — found already implemented in the working tree
  (score column-ownership split + backfilling migration); verified `tests/test_scoring_ownership.py`
  **8 passed**. Docs were stale; no code change needed.
- **P0 #2 reviewed-text overwrite (Stage-8 D1/D3/D4)** — `POST /build` default inverted to package the
  stored reviewed text at zero AI; `regenerate=true` is the only rewrite path; `metadata.json` records
  `generated_by`. `tests/test_application_builder.py` → **15 passed** (4 new regression tests).

**Still open:**
- Stages **5–10 hardening**: **38** of the 42 defects in `DEFECT_BACKLOG.md` remain (9 P1 · 5 P2 · 24 P3).
  Tests for those stages exist and pass, but they test *current* behaviour — the defects remain.
- **Stage-8 D2** — the evidence gate still does not validate personal facts (relocation target, visa
  sponsorship stance, willingness, years). This is the one proven-live defect left in PACKAGES.
- **Pre-existing, unrelated:** `tests/test_ats.py` has **4 failing tests** (untracked WIP `app/ats.py` +
  `tests/test_ats.py` from a prior session; `layout_hazard` assertions). Not touched by this work.
- Per-stage doc sets for stages 5–10 — only the `AUDIT` file of each exists.

> **Golden Rule #11:** unit tests passing is not done. Stages 2–4 now have unit + live evidence;
> they are the only stages that do.

---

## 6. Real end-to-end user journey (2026-10-03) — proves the P0-#2 fix

Full harness `analysis/e2e_user_journey.py` — the REAL server (`uvicorn app.main:create_app --factory`,
auth ON, `testing=False`), 250 HTTP calls, 26 scenarios, throwaway data dir, live DeepSeek. Long budgets
shortened via `JOBAGENT_E2E_SCRAPE_SECS=20` / `JOBAGENT_E2E_DISCOVERY_SECS=20`.

| Metric | Result |
|---|---|
| Scenarios | **23 / 26 passed** |
| Checks | **200 / 203** |
| HTTP calls | 250 |
| Run dir | `analysis/e2e_runs/2026-10-02_221045/` |

### The P0-#2 fix, proven through the running product

`s19_package` **passed 10/10** against the new code path:

```
POST /api/packages/jobs/1/build            -> 200   (packaged the STORED reviewed text)
POST /api/packages/jobs/1/build?refresh=true -> 200
files: cover_letter.docx, cover_letter.txt, resume.docx, resume.txt
```

Real `metadata.json` written by that run:

```json
"generated_by": "stored",
"evidence_check": { "ok": true },
"status": "ready_for_review"
```

Scenario 17 had persisted the reviewed text via `/prepare`; scenario 19 packaged it **unchanged** — no AI
regeneration, provenance recorded, evidence gate green.

### The 3 failures — none caused by this work

| # | Scenario | Failure | Cause |
|---|---|---|---|
| 12 | `s12_discovery` | `telemetry_keys=[] pool_growth=0` — "discovery still running when the poll budget expired" | **Budget artifact.** I cut discovery to 20s (default 300s). |
| 14 | `s14_scoring` | `score-all` → `{"scored": 0, "total": 0}` | **Documented gap, not a regression.** The seeded job was `location_classified=0`, so eligibility returned `INELIGIBLE / LOCATION_NOT_CLASSIFIED` and `eligible-jobs` = 0 → nothing to score. This is exactly the `country_code` / `location_classified` carry-in already recorded in `STAGE_ROADMAP.md`; classification never ran because discovery was cut short. Not touched by this work. |
| 21 | `s21_crm` | `unearned 'offered' is blocked` — API returned 200 `applied → offered` | **Stale harness expectation.** `applied → offered` is *allowed by design* (forward skips within the pipeline are real; the invariants are "cannot reach offered without applying" and "no terminal resurrection"). Recorded as a harness-expectation error in Session 27; this check was not updated. |

### Two anomalies worth following up

1. **`POST /api/jobs/1/interview-prep` took `ms: 34851571` ≈ 9.7 hours** (`api_calls.jsonl` #219). A single
   AI call with no effective timeout held the run open overnight. Needs investigation — either a hung
   upstream request or a missing deadline on that endpoint.
2. **The harness crashes on Windows** with `UnicodeEncodeError: cp1252` when printing `✓`
   (`analysis/e2e_user_journey.py:110`). Worked around with `PYTHONIOENCODING=utf-8`; the per-stage
   verifiers already carry `sys.stdout.reconfigure(encoding="utf-8")`, this harness does not. Minor fix,
   worth applying.

Also confirmed: **no orphaned server process** — the harness's ports closed cleanly; port 8085 (PID 500)
is Basil's pre-existing app server and was left untouched.

---

## 7. P1 closeout + daily-run route proof (2026-10-03)

### Fixed after the prior log

- **Stage-9 O2:** Gmail draft dedup now scopes by subject + recipient and verifies draft metadata headers
  before adopting. Unverifiable metadata fails closed.
- **Stage-7 R1:** research provider keys now resolve from the active workspace `scraper_keys` via
  `workspace_provider_chain(db)`; env remains fallback only.
- **Stage-7 R2:** provider exceptions are returned as `status="error"` with `provider_errors` and are
  not cached as seven-day `not_found` rows.
- **Stage-6 S6:** `POST /api/daily-run/run` now wires all ten stages: discover, classify, eligibility,
  score, hybrid_score, select, research, packages, outreach, digest.

### Tests run

| Command | Result |
|---|---|
| `uv run pytest tests/test_daily_run.py tests/test_contact_providers.py tests/test_outreach.py tests/test_multiuser_real_scenario.py tests/test_application_builder.py tests/test_digest.py -q --timeout=240` | **95 passed** |
| `uv run pytest -q --timeout=300` | **1280 passed, 1 warning** |

The warning was a Windows asyncio unclosed-transport warning during
`tests/test_workspaces.py::test_workspace_dirs_and_dbs_are_distinct`; it did not fail the run.

### Focused real-server E2E

```powershell
$env:PYTHONIOENCODING='utf-8'
$env:JOBAGENT_DAILY_DISCOVERY_PASSES='1'
$env:JOBAGENT_E2E_DISCOVERY_SECS='20'
$env:JOBAGENT_E2E_SCRAPE_SECS='20'
uv run python ../analysis/e2e_user_journey.py --only s01_boot s02_bootstrap s04_login s05_admin_creates_user s06_user_workspace_born_empty s07_user_sets_own_ai_key s08_resume_upload_and_grading s10_countries s22_daily_run
```

Result: **9/9 scenarios, 67/67 checks, 38 HTTP calls**.

Run directory: `analysis/e2e_runs/2026-10-03_112115/`.

Daily-run route response:

- `POST /api/daily-run/run` -> 200 in 46.6s.
- All ten stages returned `status="done"`.
- Shortfall was honest: `RATE_LIMITED` from the intentionally tiny discovery budget and
  `NO_ELIGIBLE_JOBS` because no selected job remained above the cutoff.
