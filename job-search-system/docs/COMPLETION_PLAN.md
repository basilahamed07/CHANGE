# COMPLETION PLAN — finish jobagent

> **What this is:** the single plan that takes the repo from *~57% done* to done —
> an **autonomous daily run**, all remaining defects fixed, and the per-stage docs
> contract the roadmap promises.
>
> Decisions locked with Basil (2026-10-03):
> 1. **"Agentic" = the daily run runs the whole 10-stage pipeline unattended** (no more
>    `not_implemented`), not a new AI agent feature.
> 2. **P1 severity first** — the 9 P1 defects before P2/P3.
> 3. **Commit checkpoints as work finishes.**
>
> Siblings: `STAGE_ROADMAP.md` (status board) · `DEFECT_BACKLOG.md` (all 40 open defects)
> · `STAGE_TEST_RESULTS.md` (execution log) · `NEXT_5_PLAN.md` (separate N2–N5 queue).

---

## 0. Where we are

| | |
|---|---|
| Pipeline stages fully hardened | **4 / 10** (DISCOVER, CLASSIFY, ELIGIBILITY, SCORE) |
| Defects fixed | **4 / 42** — all four P0s |
| Defects open | **40** → 9 P1 · 5 P2 · 24 P3 · 2 already fixed (see below) |
| Readiness | **~57%** |
| E2E (real server) | `USER_JOURNEY_E2E_REPORT.md` — **23/26** (shortened budgets; 3 non-regressions) |
| Working tree | 3 sessions + stages 3–4 **uncommitted** |

### Why "autonomous" matters — the E2E exposed it
`POST /api/daily-run/run` returns 10 stages where **8 say `skipped / not_implemented`**.
The daily run builds **zero packages** and can never meet its target. That is the single
biggest gap between what the product claims and what it does.

**Root cause:** `DailyRun.run()` (app/daily_run.py:145) is a complete orchestrator —
order, per-stage crash markers, resumability, shortfall vocabulary, target counting — but
`app/routers/crm.py:176-196` only passes **two** stage implementations (`select`,
`packages`), and `_packages` just *counts pending rows* instead of building.

---

## Phase 0 — safety net before any feature work

Cheap, and it makes every later "green" claim trustworthy.

| # | Task | Why |
|---|---|---|
| 0.1 | **Commit checkpoint A** — stages 3 + 4 + the four P0 fixes | 3 sessions of work are uncommitted; a later regression would be unreviewable |
| 0.2 | **Restore / annotate `docs/USER_JOURNEY_E2E_REPORT.md`** | My run overwrote the definitive 26/26 run (`2026-09-24_125119`) with a shortened-budget 23/26 (+139/−170). The repo's main E2E doc now understates reality |
| 0.3 | **Fix `E2E_RUN_STATUS.md` contradiction** | Still says "latest run = `2026-09-24_125119`" |
| 0.4 | **Fix the 4 failing `tests/test_ats.py`** (`layout_hazard`) | Untracked WIP (`app/ats.py`). Until they pass, "full suite green" cannot be claimed |
| 0.5 | **Fix the E2E harness itself** — `UnicodeEncodeError: cp1252` on `✓` (`e2e_user_journey.py:110`) and the stale `applied→offered must be blocked` expectation | Otherwise every future E2E run dies early and reports a false failure |

**Gate:** `uv run pytest -q --timeout=300` → **0 failed**; harness starts cleanly on Windows.

---

## Phase 1 — the 9 P1 defects (severity order)

Ordered by **what the autonomous daily run needs**, not by number.

### 1.1 · S3 — selection never re-checks eligibility
`app/database.py:3750-3752` — `get_top_unpackaged_jobs` filters only `dismissed` /
`strategy_dismissed`. A score row survives an eligibility flip, so a job that went stale
after scoring is still selected and packaged.
**Fix:** add `AND j.eligibility_status = 'ELIGIBLE'`.
**Test:** job scores → eligibility flips to `INELIGIBLE` → never selected.

### 1.2 · D2 — evidence gate does not validate personal facts
`app/evidence_checker.py:181-185`. The one **proven-live** defect left: run
`2026-09-24_125119` shipped `Singapore → Amsterdam, Netherlands` and flipped
`visa sponsorship welcomed → required` right through the gate.
**Fix:** `_check_personal_facts()` covering **relocation target · visa sponsorship stance ·
willingness to relocate · years of experience**, matched against the candidate's stored
evidence — never the JD. Failure → regenerate once → **422** (same contract as the rest).
**Required before** the daily run may build packages unattended.

### 1.3 · H2 — `/api/matching/score-all` scores against an empty profile
`app/routers/matching.py:68-71` + `app/matching_service.py:94-106` — the router passes a
stub state with only `.matcher`, so `evidence_store` / `country_registry` are absent ⇒ no
verified skills, no corpus, no visa keywords ⇒ every job gets `skills=50 / semantic=50`.
**Fix:** pass the real per-user state. **Required for the `hybrid_score` stage.**

### 1.4 · G1 + G4 — the digest is not a run report and has no eligibility filter
`app/digest.py:9-61` and `:17`. It counts new high-scoring **jobs**, never packages /
`target_met` / shortfall reasons (which `daily_run.py:44` already defines), and it joins
only on `job_scores` so a job whose eligibility flipped is still headlined.
**Fix:** lead with the outcome (packages vs target + `shortfall_reasons()`), add
`j.eligibility_status = 'ELIGIBLE'`. **Required for the `digest` stage.**

### 1.5 · O2 — Gmail draft dedup can adopt another job's draft
`app/outreach.py:183-199`, `:289-293` — `find_existing_draft` searches the whole mailbox by
subject substring and returns `drafts[0]`, so job B records job A's draft id and **no draft
is created for B**.
**Fix:** scope by subject **and recipient**, verify company/job before adopting.
**Required for the `outreach` stage.**

### 1.6 · R1 + R2 — research keys and the cached negative
- **R1** `contact_providers.py:182`, `:225` — `HunterProvider()` / `ApolloProvider()` read
  `os.getenv`, ignoring workspace `scraper_keys`. Multi-user ⇒ shared or absent key.
- **R2** `contact_providers.py:353-363` — `find()` swallows every exception into `[]`, so a
  timeout/429/bad key is cached as `not_found` for **7 days**. Six runs then "succeed" on a
  negative.
**Fix:** build the chain from workspace settings (env only as fallback); **do not persist a
fresh negative when any provider errored.** **Required for the `research` stage.**

### 1.7 · S6 + S4 — the daily run executes almost nothing (the agentic centrepiece)
`app/routers/crm.py:176-196`.
- Only `select` + `packages` are supplied; the other eight are `None` ⇒ `not_implemented`.
- `_packages` counts pending rows — it builds nothing.
- **S4** `:179-180` hardcodes `ALL_SCORED_BELOW_CUTOFF` whatever the real cause.

See **Phase 2** — implemented there.

**Gate:** all 9 have a regression test; full suite green.

---

## Phase 2 — the autonomous daily run (the "agentic" work)

### 2.1 Implement all ten stage adapters

`DailyRun.run(stage_impls)` already owns order, crash markers, resumability and the
shortfall vocabulary. It needs **adapters**, each delegating to an existing, already-tested
service — no new business logic.

| Stage | Adapter delegates to | Notes |
|---|---|---|
| `discover` | `run_discovery_cycle()` — `app/discovery.py:125` | **budget-capped** (full cycle is ~606s); per-user DB + their matcher; keep bounded concurrency = 5 |
| `classify` | `run_location_classification()` — `app/scheduler.py:251` | residue-only AI fallback |
| `eligibility` | `run_eligibility_pass()` — `app/scheduler.py` | deterministic, zero LLM |
| `score` | `_score_unscored(db, matcher)` — `app/main.py:458` | user's matcher, not admin's; circuit-breaker must degrade to a shortfall reason, never block |
| `hybrid_score` | `matching_service.score_all_unscored()` | free — runs **after** AI so leftovers get scored (needs 1.3) |
| `select` | existing `_select` + `select_candidates()` | needs 1.1 + **S5**: read `DailyRun.score_cutoff`, not literal `60` |
| `research` | company enrichment + `ContactProvider` chain | never raises (already true); needs 1.6 |
| `packages` | real evidence-gated build (`routers/packages.py` logic) | **needs 1.2**; born `ready_for_review` |
| `outreach` | `OutreachService.create` — `app/outreach.py:206` | **DRAFT-ONLY**, one per `(job, audience)`; needs 1.5 |
| `digest` | `generate_digest()` — `app/digest.py:9` | needs 1.4; `SMTP send stays optional` |

### 2.2 Hard constraints the autonomous run must not break
- **Never sends.** Packages are born `ready_for_review`; outreach creates **drafts only**.
  "Agentic" = unattended *generation*, not unattended *sending* (Golden Rule 6).
- **Resume-first gate:** no resume ⇒ `428`, never scrape.
- **Evidence gate fail-closed:** a package that fails the checker is `422`, nothing saved —
  the run records `EVIDENCE_GATE` and continues.
- **AI quota:** a depleted provider becomes `AI_QUOTA_EXHAUSTED`, the run finishes, the
  report is honest. Never fabricate a score to hit the target.
- **Per-user:** workspace DB + that user's matcher/evidence only. Never `app.state.bg_db`.
- **Budget:** each run gets a discovery/scrape budget so a run can't hog the process.

### 2.3 Honest shortfall + real target
- `_select` computes **real** reasons (delete the hardcoded `ALL_SCORED_BELOW_CUTOFF`).
- `_finish` already counts `packages_created` from `applications.package_dir` — the packages
  stage must actually create them.
- Target counts **qualifying packages**, never scraped URLs (Golden Rule 7).

### 2.4 Make it run unattended
- Wire the full `DailyRun` into the **scheduler** (currently `main.py` interval jobs only
  call scrape/score against `app.state.bg_db`).
- **Known adjacent gap:** all 8 scheduler jobs run against the **admin** workspace only —
  this is `NEXT_5_PLAN` **N2**. Ship single-user autonomy first (Phase 2.1–2.3); N2 is a
  listed follow-on, not part of this phase's gate.

### 2.5 Prove it (Golden Rule #11)
1. **Unit:** `tests/test_daily_run_full.py` — every stage invoked, order enforced, a stage
   failing doesn't kill the run, idempotent second run, real shortfall reasons.
2. **Real E2E:** re-run `analysis/e2e_user_journey.py` with **default budgets** (not 20s)
   and assert **scenario 22 reports `packages_created ≥ 1` with 8 stages `done`**.
3. **Live:** `analysis/verify_daily_run_live.py` against a **copy** of the real DB.

**Gate:** one `POST /api/daily-run/run` on a real workspace drives discover → digest with
zero `not_implemented`, and the report is honest about any shortfall.

---

## Phase 3 — remaining P2 (5) and P3 (24)

| P2 | Defect |
|---|---|
| 14 | **S4** hardcoded shortfall reason *(folded into 2.3)* |
| 15 | **D3** `refresh=true` silently spends an AI call *(already fixed by P0 #2 — verify + close)* |
| 16 | **G5** empty digest reported as a config failure |
| 17 | **G3** "new in the last 24h" uses discovery time, not freshness |
| 18 | **O5** Stage-9 `OutreachService` never wired (`outreach: None`) *(folded into 2.1)* |

P3 (24): determinism and hygiene — dead `select_candidates`, missing tie-breaks, duplicated
cutoff, dead RAG provider, weight renormalisation, reason-list set ordering, classifying
names/emails as roles, f-string RFC2822 message, follow-up measured from first outreach only,
no length guard, rolling-24h "per day" cap, digest schedule/tie-break/`match_reasons`.
Work these **per stage** alongside its hardening so one pass covers both.

---

## Phase 4 — the per-stage contract for 5 → 10

Each of the 6 stages gets the full treatment `docs/score/` received:

1. **Audit** ✅ *(done — exists)*
2. **Harden** — explicit entry point, persisted decision + reason + evidence, metrics
3. **Tests** — `tests/test_<stage>.py`, ~20–35, one regression per defect
4. **Live verify** — `analysis/verify_<stage>_live.py` on a **copy** of the real DB
5. **Docs** — the 6-file folder + `results/<stage>_summary.json`
6. **Memory + commit**

Deliverables: 6 test files, 6 verifier scripts, ~36 doc files (folders `hybrid/`, `select/`,
`research/`, `packages/`, `outreach/`, `digest/` currently hold **only** `_AUDIT.md`).

Also close the **Stage-4 deferrals**: `job_scores` provenance (model / prompt version / path
taken) and `search_config.score_metrics`.

---

## Phase 5 — finish the N2–N5 queue

Separate roadmap (`NEXT_5_PLAN.md`), tracked here so nothing is forgotten:

| | Item | State |
|---|---|---|
| N2 | Per-user scheduled cycles | ❌ gap — 8 interval jobs hit `app.state.bg_db` |
| N3 | Per-user background run state | ❌ gap — **`app/run_state.py` (74 lines) is untracked WIP**; finish + test |
| N4 | Ship reviewed text + personal-facts gate | 🔶 **partly done** — build default fixed (P0 #2); **D2 guard still open** |
| N5 | Admin panel (audited impersonation) | ❌ not started |

---

## Phase 6 — cross-cutting cleanups

1. **`country_code` NULL on ~1,962 legacy rows** — Stage-2 only reclassifies
   `location_classified=0`. Run the recommended **Stage-2 reclassification pass**; it changes
   what stages 3–6 see (it is why E2E scenario 14 scored 0/1).
2. **The split-brain database** — `root/data/jobagent.db` holds 1,245 jobs, the workspace
   `data/users/1-basil/jobagent.db` holds the resumes + AI settings. **No single DB can run
   the pipeline end-to-end.** Decide and migrate; until then verify which DB the server binds.
3. **Doc drift** — `docs/AGENT_CONTEXT.md` §2 says "21 scrapers + 15 ATS adapters"; the
   registry has **20**. Code wins.
4. **Deferred Stage-4 items** — score provenance + `score_metrics`.
5. **Frontend tests** — `app/static/node_modules` is absent; `npx vitest run` has **never
   been run in this effort**. Install and run before declaring done.
6. **The 9.7-hour AI call** — `POST /api/jobs/1/interview-prep` took
   `ms: 34851571`. A missing deadline on that endpoint; add a timeout.

---

## Sequencing

```
Phase 0  safety net ──────────────── commit A
   ↓
Phase 1  P1 defects 1.1 → 1.6 ────── commit B   (dependencies first)
   ↓
Phase 2  autonomous daily run ────── commit C   ← the centrepiece (1.7 / S6+S4)
   ↓
Phase 3  P2 + fold P3 into Phase 4 ─ commit D
   ↓
Phase 4  stage hardening 5 → 10 ──── commit per stage (E…J)
   ↓
Phase 5  N2–N5 queue ─────────────── commit K
   ↓
Phase 6  cross-cutting ───────────── commit L
   ↓
FINAL    full suite + default-budget E2E + memory
```

## Definition of done

- [ ] `uv run pytest -q --timeout=300` → **0 failed** (includes `test_ats.py`)
- [ ] `cd app/static && npx vitest run` → **0 failed**
- [ ] Real E2E with **default budgets** → **26/26** and scenario 22 reports real packages
- [ ] Zero defects left in `DEFECT_BACKLOG.md`, or each explicitly deferred with a reason
- [ ] All six stage folders hold the full 6-file set
- [ ] `docs/STAGE_ROADMAP.md` status board = **10/10**, every stage **DONE** + committed
- [ ] `PROJECT_MEMORY.md` session log current; nothing uncommitted

## Verification (every phase, in this order)

```powershell
cd D:\personal_project\CHANGE\CHANGE\job-search-system\root

uv run pytest tests/test_<stage>.py -q                 # 1. the touched tests
uv run pytest -q --timeout=300                         # 2. full backend
uv run python ../analysis/verify_<stage>_live.py       # 3. live, on a DB COPY
uv run python ../analysis/e2e_user_journey.py          # 4. real server, default budgets
cd app/static && npx vitest run                        # 5. frontend
```

## Honest open risks

| Risk | Impact |
|---|---|
| Full suite already exceeds 10 min on this machine | Phase gates need batching or a longer budget |
| Discovery is ~606s/cycle | The `discover` stage **must** be budget-capped or every run hangs |
| Live data is split across two DBs | Autonomy cannot be proven end-to-end until Phase 6.2 |
| `test_ats.py` (4 failing) + frontend tests never run | Blocks "full suite green" today |
| DeepSeek key is exposed in an old transcript | Rotate it; live E2E and daily-run scoring both spend from it |
| 3 sessions of work uncommitted | Any mistake before **commit A** is hard to unwind |
