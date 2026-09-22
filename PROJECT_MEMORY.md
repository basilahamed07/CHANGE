# PROJECT MEMORY — Basil's International AI Job Search System

> **PURPOSE:** This file is the persistent memory for building the Personal International
> AI Job Search + Recruiter Outreach System for **Basil Ahamed H**. Update this file
> whenever any phase, feature, or milestone is COMPLETED. Never delete completed entries —
> append status changes.

---

## 1. PROJECT IDENTITY

- **Candidate:** Basil Ahamed H
- **Target roles:** AI Engineer, Generative AI Engineer, AI Application Developer,
  Python AI Developer, LLM Engineer, RAG Engineer, Agentic AI Engineer, Backend/AI Engineer
- **Product:** One coherent system — discover → normalize → dedupe → verify → eligibility
  → match → rank → research → contacts → tailor resume → cover letter → outreach →
  Gmail DRAFT (never auto-send) → track → follow-up → monitor → feedback loop.
- **GitHub:** https://github.com/basilahamed07/CHANGE (public, branch `main`) —
  code + memory + docs all versioned here; .env / data/ / *.docx / references/ are
  deliberately NOT in the repo (see Session 15 notes for new-PC setup).

## 2. GOLDEN RULES (from master prompt — do not violate)

1. **One coherent product.** Never tape 5 repos together. Borrow ideas, port selectively.
2. **CareerPulse is the primary architectural base** unless inspection reveals a serious reason not to.
3. **extend > rewrite.** Never delete working CareerPulse functionality just because another repo does it differently.
4. **Deterministic code for deterministic problems.** Python handles dates/pagination/dedup/filters/math/state. LLMs only for semantics/phrasing/research interpretation.
5. **Evidence system is sacred.** LLMs may NEVER invent skills, dates, employers, metrics, certifications, education, visa status. UNVERIFIED must never become VERIFIED. EvidenceChecker gates every generated resume.
6. **Default = CREATE DRAFT, never send.** Sending requires explicit human approval.
7. **Daily target = qualifying application packages, not scraped URLs.** Never lower eligibility bar to hit target.
8. **Country is a first-class entity** (config/countries/*.yaml). Adding a country must not touch core business logic.
9. **Adapters over vendors.** JobSourceAdapter, ContactProvider, GmailProvider interfaces.
10. **MAX_JOB_AGE_DAYS default = 7.** DATE_UNKNOWN is NOT fresh. Freshness evidence stored.
11. **E2E verification rule (Basil, 2026-09-22):** Every new module/feature MUST be
    verified end-to-end through the live API (extend `analysis/e2e_module_test.py`),
    with a written report in `docs/`, before it counts as done. Fix + re-verify every
    error found in the same session, then update PROJECT_MEMORY.md and the plan.
    Unit tests passing ≠ done; proven through the running product = done.

## 3. CURRENT STATE

- **Phases completed:** 0–4, 5–11 (M3+M4+M5), 42, 43 (analysis-only gate satisfied)
- **Current phase:** M5 COMPLETE ✅ → next up **M6 (hybrid matching engine)**
- **Approved to implement:** YES — Basil approved M1 start after architecture review
- **Workspace:** `job-search-system/` with root/ (final product), references/ (5 clones), docs/, analysis/
- **Analysis artifacts DONE:** docs/REPOSITORY_ANALYSIS.md, docs/FEATURE_MATRIX.md,
  docs/ARCHITECTURE_DECISION.md, docs/IMPLEMENTATION_PLAN.md
- **Next action:** Begin milestone M6 (hybrid matching: deterministic components + TF-IDF ATS overlap + RAG semantic layer).
- **Note:** Project root is `~/Documents/PERSONAL PROJECT/job_get` which pre-contains
  CENTER-AGNET/, job_get/, testing/ — untouched, unrelated to this build.
- **Analysis-only gate:** SATISFIED — all 4 analysis docs exist. NO major implementation
  until Basil reviews/approves them.

## 4. PHASE CHECKLIST (from master prompt)

| Phase | Description | Status |
|-------|-------------|--------|
| 0 | Create workspace | DONE 2026-09-21 |
| 1 | Clone + study 5 repos | DONE 2026-09-21 (all cloned to references/, inspected: READMEs, structures, DB schema, adapters, guardrails, scorers) |
| 2 | REPOSITORY_ANALYSIS.md + FEATURE_MATRIX.md | DONE 2026-09-21 |
| 3 | ARCHITECTURE_DECISION.md | DONE 2026-09-21 (26 decisions D1–D26, CareerPulse confirmed as base) |
| 4 | Candidate evidence system | DONE 2026-09-21 (M2: store, checker, gate, API, DB, profiles) |
| 5 | Country strategy engine | DONE 2026-09-22 (M3) |
| 6 | Job discovery engine | DONE 2026-09-22 (M4) |
| 7 | Search self-correction | DONE 2026-09-22 (M4 — stop-reason telemetry + budget caps) |
| 8 | Job normalization (canonical model) | DONE 2026-09-22 (M4 — CanonicalJob) |
| 9 | Deduplication | DONE 2026-09-22 (M4/M5 — cross-source hash + job_duplicates graph) |
| 10 | Freshness verification | DONE 2026-09-22 (M5) |
| 11 | Eligibility engine | DONE 2026-09-22 (M5) |
| 12 | Hybrid matching engine | PENDING |
| 13 | RAG / semantic matching | PENDING |
| 14 | Deterministic vs LLM split | PENDING |
| 15 | Company research | PENDING |
| 16 | People/contact discovery | PENDING |
| 17 | Contact confidence | PENDING |
| 18 | Resume tailoring (DOCX primary) | PENDING |
| 19 | Application package layout | PENDING |
| 20 | Outreach engine | PENDING |
| 21 | Outreach sequences (config-driven) | PENDING |
| 22 | Gmail draft integration | PENDING |
| 23 | Application CRM + events | PENDING |
| 24 | Kanban dashboard | PENDING |
| 25 | Daily automation scheduler | PENDING |
| 26 | Daily target logic | PENDING |
| 27 | Response monitor | PENDING |
| 28 | Follow-up engine | PENDING |
| 29 | Feedback loop | PENDING |
| 30 | Analytics | PENDING |
| 31 | Database (SQLite first, migration-friendly) | PENDING |
| 32 | REST API + OpenAPI | PENDING |
| 33 | Dashboard pages | PENDING |
| 34 | Human approval gates | PENDING |
| 35 | Cost control | PENDING |
| 36 | Resilience | PENDING |
| 37 | Security (.env, no secrets committed) | PENDING |
| 38 | Testing (incl. 4 critical tests) | PENDING |
| 39 | Observability (run_id etc.) | PENDING |
| 40 | CLI (same service layer as UI) | PENDING |
| 41 | Documentation set | PENDING |
| 42 | IMPLEMENTATION_PLAN.md milestones M1–M14 | DONE 2026-09-21 |
| 43 | First execution = analysis ONLY, then STOP | DONE 2026-09-21 — STOPPED, awaiting approval |
| 44 | Development rules enforcement | ONGOING |

## 5. MILESTONE TRACKER (filled during implementation)

- M1 Base CareerPulse setup + architecture cleanup — **DONE 2026-09-21**. Details:
  - CareerPulse copied into `root/` (excl. .git/screenshots/demo scripts); renamed **jobagent** everywhere (0 CareerPulse/jobfinder refs left)
  - Unified config: `JOBAGENT_` prefix, OpenRouter default provider (env fallback order: OpenRouter → Anthropic), feature flags (US tools/career/predictor OFF; autofill ON; linkedin_guest OFF), `allow_send=false`
  - Endpoints: `/api/health` kept + new `/api/system/health` (adds product/version/features); app title jobagent; db `data/jobagent.db`
  - Feature-flag gating added to offers/career/predictor endpoints (404 when off)
  - Tests: backend **668 passed** (~105s), frontend **180 passed**, extension **469 passed**; live server boot + curl verified
  - Test infra: added pytest-timeout + pytest-xdist (dev); `tests/test_scrapers/conftest.py` neutralizes real rate-limit/backoff/anti-detection sleeps in mocked scraper tests (this was the "hang")
  - Known pre-existing issue for M14: job-board-overlay.test.js unhandled rejections (badge retry timer after teardown); tests still pass
- M2 Candidate evidence model + EvidenceChecker — **DONE 2026-09-21**. Details:
  - `data/profile/` — 8 YAML evidence templates (candidate, skills, experience, projects,
    achievements, education, preferences, exclusions). All claims UNVERIFIED by default
    (fail-closed); only 3 preferences claims pre-VERIFIED. Basil flips status + adds source.
  - `app/evidence_store.py` — EvidenceStore: loads all YAMLs, Claim model, statuses
    VERIFIED/UNVERIFIED/DISPUTED/DO_NOT_USE, verified corpus, skill_values_all_statuses(),
    normalize_skill; DB sync (candidate_evidence table) + get_evidence_summary().
  - `app/evidence_checker.py` — EvidenceChecker HARD gate (ported from job-application-pipeline
    guardrail, upgraded warn→fail): fabricated_number (years 1990-2035 exempt),
    unsupported_claim (Jaccard similarity floor 0.18), unsupported_skill (boundary-aware,
    verified-sentence exemption) = Critical Test #1. Machine-readable failures list.
  - Gate wired into `POST /api/jobs/{id}/prepare`: store/checker on app.state (503 fail-closed
    if missing), 1 regeneration attempt on failure, persistent failure → 422 + event logged,
    NOTHING saved. Evidence check result returned in response.
  - `app/routers/evidence.py` — GET /api/evidence (summary), POST /api/evidence/sync,
    POST /api/evidence/check (dev validation). Wired in main.py lifespan.
  - Database: `candidate_evidence` table (category, claim_id, value, status, source,
    last_verified, notes, synced_at, UNIQUE(category,claim_id)) + accessor.
  - **Fixed product bug found by tests:** db.get_score crashed with JSONDecodeError on
    empty match_reasons/concerns/suggested_keywords (any prepare on an unscored job → 500).
  - Tests: tests/test_evidence.py — 14 tests incl. Critical Test #1 end-to-end (fabricated
    skill → 422, nothing saved). NOTE: never patch Starlette State class (attrs live in _state;
    class patch shadows instance). test_api.py prepare test updated with minimal verified corpus.
  - Suite: **682 passed** (~80s). Live boot verified: /api/system/health green + /api/evidence serving.
- M3 Country strategy — **DONE 2026-09-22** (E2E-verified per Golden Rule #11). Details:
  - `config/countries/*.yaml` — 6 seeds (Germany, Netherlands, Ireland, UK, Singapore, UAE).
    Schema: code/name/region/enabled/aliases/cities/work_types/visa{requires_sponsorship,
    sponsorship_keywords}/salary{currency,min}/search.extra_terms. **Adding a country = drop a
    YAML, zero code changes** (unit-proven). Bad schema fails loud (CountryConfigError).
  - `app/country_registry.py` — CountryRegistry: load/validate, enabled vs known, per-country
    work types + salary floors, classification_terms() (aliases/cities for the classifier).
    'region' field = canonical classifier string (UK, UAE) — display name can differ.
  - `app/visa_engine.py` — DETERMINISTIC keyword scan (word-boundary regex, longest-first).
    No LLM (Golden Rule 4). Returns matched keywords + sponsors_international flag.
  - `app/routers/countries.py` — GET /api/countries, GET/PUT /api/countries/{region}
    (PUT persists to YAML with timestamped backup in config/countries/.backups/),
    POST /api/countries/{region}/visa-check, POST /api/countries/apply, POST /api/countries/reload.
  - `apply_country_strategy` (scheduler.py): classify unclassified (rule-based, no AI cost) →
    sync allowed_regions = enabled countries + Remote → **restore-then-dismiss**.
  - **Reversibility design:** jobs.strategy_dismissed column (migration added). Strategy
    auto-dismissals are flagged + reversible; user dismissals stay permanent. Wider strategy
    re-admits jobs (restore_strategy_dismissed_jobs) — switching countries never loses data.
    E2E-proven: disable UAE → Dubai job dismissed; re-enable → RESTORED.
  - **Fixed real gap:** UAE was completely missing from location_classifier (Dubai/Abu Dhabi
    jobs could never classify to a target). Added UAE entries. **Fixed latent bug:** 'uk'
    substring-matched inside 'ukraine' → word-boundary _match_country now; Remote - Ukraine
    classifies correctly. Registry aliases (e.g. deutschland→Germany) flow into classifier.
  - Tests: tests/test_countries.py 14 tests (zero-code addition, schema fail-loud, duplicates,
    disabled countries, UAE/Ukraine classifier regressions, visa determinism, API surface).
    **701 passed** full suite (was 686, +15). E2E: **84/84, 0 SKIP, 0 FAIL** with Basil's REAL
    resume uploaded as .docx + real AI scoring (AI job 85, designer 20) — report: docs/E2E_MODULE_TEST_REPORT.md.
- M4 Discovery adapters + normalization — **DONE 2026-09-22** (E2E-verified per Golden Rule #11). Details:
  - `app/job_adapter.py` — JobSourceAdapter interface (search/health_check, NEVER raises,
    returns AdapterResult with stop-reason telemetry), CanonicalJob (Phase-8 field set),
    make_content_hash = CROSS-SOURCE dedup key (normalized title|company|city; URL excluded).
    _norm collapses whitespace (smoke test caught missing collapse → false dedup misses).
  - `app/adapters/` — greenhouse (facade over existing scraper), lever, ashby, smartrecruiters
    (ported from ai-job-search MIT concepts onto BaseScraper chassis). All 4 health-probed
    LIVE: greenhouse/lever/ashby/smartrecruiters 200. Lever DEFAULT_COMPANIES pruned to
    verified-live boards (spotify, palantir — stripe/netflix/revolut/wise left Lever).
  - `app/discovery.py` — run_discovery_cycle: enabled countries × search_terms × adapters,
    SAME ingest gates as legacy (title gate, region gate), budget cap 24 passes/cycle,
    MAX 200 listings/pass, per-pass telemetry (stop_reason/found/ingested/duplicates).
    Orchestrator ENFORCES source attribution (job.source = adapter.source_name) — a
    mislabeled listing must not corrupt dedup (caught by test with deliberately-wrong stub).
  - **Critical Test #2 now passes deterministically:** same job via 2 sources → 1 job row +
    2 source rows (cross-source dupe merge in discovery cycle mirrors legacy ingest).
  - `app/routers/discovery.py` — GET /api/discovery/adapters, GET /api/discovery/health
    (parallel live probes), POST /api/discovery/run (background + progress),
    GET /api/discovery/status (telemetry of last cycle).
  - **Fixed real bug:** update_allowed_regions was a bare UPDATE — silently no-op on a
    fresh DB with no search_config row (strategy sync lost). Now an UPSERT.
  - Tests: tests/test_adapters.py — 8 tests (hash identity incl. Critical Test #2 property,
    posted-date normalization, Lever normalization/filter via respx, never-raise contract,
    country scoping, cross-source dedup end-to-end on real Database). **709 passed** full suite.
  - E2E: discovery section 8/8 with local ATS stub servers (real HTTP, real orchestrator,
    real DB) + live per-source health probes against the REAL 4 ATS APIs. Full E2E 90/90,
    0 FAIL (10 AI checks SKIP — free quota exhausted; scoring ran 20/592 jobs before
    quota died and circuit breaker stopped it gracefully — resilience verified live).
- M5 Dedup + freshness + eligibility — **DONE 2026-09-22** (E2E-verified, Golden Rule #11). Details:
  - `app/freshness.py` — 3 freshness states (VERIFIED_FRESH / STALE / DATE_UNKNOWN) with
    evidence dict stored on jobs.freshness_evidence (audit trail). DATE_UNKNOWN is terminal —
    never upgraded (Critical Test #3). MAX_JOB_AGE_DAYS=7 default per Golden Rule 10.
  - `app/eligibility.py` — deterministic gate chain (dismissed → freshness → evidence →
    repost-pending) with machine-readable reason codes; zero LLM on INELIGIBLE (Golden Rule 4).
  - `app/routers/eligibility.py` — POST /jobs/{id}/eligibility (re-evaluate),
    GET /eligibility/eligible-jobs (live pool), GET /jobs/{id}/freshness (evidence).
  - `job_duplicates` repost graph + record_duplicate/merge paths in database.py; freshness
    wired into discovery ingest + maintenance cycle.
  - **Fixed real bug:** auto_dismiss_stale used 30d, violating Golden Rule 10 (MAX_JOB_AGE_DAYS=7)
    → freshness-driven now.
  - Tests: 14 eligibility unit tests incl. full Critical #3 matrix; **723 passed** full suite (+14).
  - E2E: eligibility 8/8 incl. CRITICAL #3 via live API; full suite **98/98, 0 FAIL**
    (10 SKIP = AI-quota-only checks, environmental). Live-validated on Basil's real 778-job
    pool (3 eligible jobs found through the running API).
- M6 Hybrid matching — PENDING
- M7 Company/contact research — PENDING
- M8 Resume/application package generation — PENDING
- M9 Outreach + Gmail drafts — PENDING
- M10 CRM + follow-ups — PENDING
- M11 Scheduler — PENDING
- M12 Analytics + feedback — PENDING
- M13 UI refinement — PENDING
- M14 Tests + docs + hardening — PENDING

## 6. REFERENCE REPOSITORIES

| Repo | URL | License | Verified strengths to draw from |
|------|-----|---------|--------------------------------|
| CareerPulse | https://github.com/tcpsyn/CareerPulse | **MIT** | BASE. FastAPI+SQLite+SPA, 39 tables, BaseScraper (backoff/rate-limit/UA), 5-provider AI client, CRM+queue+approvals, scheduler, 1248 tests |
| job_search_agent | https://github.com/KartikeyaMohan/job_search_agent | **NONE — concepts only, ZERO code** | TF-IDF ATS scoring, RAG over candidate, feedback loop |
| job-application-pipeline | https://github.com/DavidAromose/job-application-pipeline | **MIT** | Anti-fabrication guardrail (number-diff+similarity floor), Gmail draft + dedup, Hunter/Apollo contacts, JSON-LD JD extraction |
| apply-pilot | https://github.com/shashikirandevadiga/apply-pilot | **MIT** | Creator→Verifier gates, audience-specific multi-track outreach, APPLICATIONS/ layout |
| ai-job-search | https://github.com/AgentWong/ai-job-search | **MIT** | 22 ATS platform adapters (port 4), FilterStats reject-reasons, disqualifier framework, deterministic/LLM split doctrine |

## 7. KEY DECISIONS LOG

| Date | Decision | Reason |
|------|----------|--------|
| 2026-09-21 | Start with analysis-only phase per Phase 43 gate | Master prompt forbids implementation before analysis artifacts |
| 2026-09-21 | CareerPulse = base (D1–D2); env prefix renamed JOBAGENT_ | Only complete web product, MIT, 1248 tests |
| 2026-09-21 | Port Greenhouse/Lever/Ashby/SmartRecruiters from ai-job-search behind NEW JobSourceAdapter interface | ATS-first discovery, adapter discipline |
| 2026-09-21 | EvidenceChecker = HARD gate (fail+regenerate), not warning (upgrade of pipeline's guardrail) | Master prompt Phase 4 requires fail, not warn |
| 2026-09-21 | job_search_agent: concepts ONLY, never copy code | No LICENSE file = all rights reserved |
| 2026-09-21 | Remove/flag-off US-only features (salary/tax calc, EEO, military sections) in root/ | International focus; D22 |
| 2026-09-21 | daily_target counts qualifying PACKAGES; eligibility never lowered | Phase 26 |
| 2026-09-21 | **BASIL'S DECISIONS:** AI provider default = OpenRouter (one key, many models, cost control); US-specific features DISABLED via feature flags (not deleted); countries = all 6 (Singapore, Germany, UAE, Netherlands, Ireland, UK) seeded in M3 | User answered review questions before M1 |

## 8. CRITICAL TESTS (must exist before we call the system done)

1. Candidate without skill X + JD requiring X → generated resume MUST NOT claim X.
2. Same job via Greenhouse + another source → must NOT create two applications.
3. DATE_UNKNOWN must never become VERIFIED_FRESH.
4. Creating outreach twice must not create duplicate Gmail drafts.

## 9. SESSION LOG

| Date (UTC) | Session summary |
|------------|-----------------|
| 2026-09-21 | Session 1 started. Memory created. Beginning Phase 0/1: workspace + clones. |
| 2026-09-21 | Session 1 COMPLETE: Phases 0–3 + 42 + 43 done. All 4 analysis artifacts written. Stopped at gate as required. Milestones M1–M14 NOT started. |
| 2026-09-21 | Session 2: M1 COMPLETE. root/ = renamed jobagent app, config spine + flags, OpenRouter default, /api/system/health, 668+180+469 tests green, live boot verified. Scraper-test sleep neutralization added. Ready for M2. |
| 2026-09-21 | Session 3: M2 COMPLETE. Evidence store + EvidenceChecker hard gate + /api/evidence + candidate_evidence table + 8 profile YAMLs (all UNVERIFIED by default). Critical Test #1 passes end-to-end. Fixed get_score empty-JSON bug. 682 tests green, live boot verified. |
| 2026-09-21 | Session 4: Live demo via analysis/demo_script.py (server+demo in one process — sandbox reaps background procs between commands; use setsid+nohup to keep app running for browser). Opened dashboard in Chromium (127.0.0.1:8085). **Fixed live bug found via server log:** settings.py:631 called old 2-positional form `_build_ai_client(ai_settings, env_key)` after M1 signature added `settings=` param → resume upload 500'd (`'str' object has no attribute 'openrouter_api_key'`). Fixed with kwargs; +2 regression tests (signature unit test + env-fallback endpoint test). NOTE: pkill -f self-match pitfall — use `[u]vicorn` bracket pattern and split kill/start into separate commands. |
| 2026-09-21 | Session 9: **Model benchmark — all 21 free OpenRouter models tested against Basil's real stored resume + the app's production analysis prompt. Report: docs/MODEL_BENCHMARK_REPORT.md; script: analysis/model_benchmark.py.** Result: 11/21 usable; 4 scored 5/5 (poolside/laguna-s-2.1:free 9.5s ← WINNER now set in ai_settings.model + verified live via /api/ai-settings/test {ok:true} and full analyze_resume: terms AI/ML/MCP/LangGraph Engineer, skills LangGraph/LangChain/RAG, senior, ATS 82). nex-n2.5-pro 11.9s and nex-n2.5-mini 13.2s are backups. Failures: 429 rate-limits (gemma×2, qwen, glm-5.2, laguna-xs), 403 agentic-only (thinkingmachines×2), KeyError choices (nemotron-3 omni/super — reasoning models emit non-standard payload), ReadTimeout (nemotron-3.5-lightning), 0/5 quality (content-safety/fin/sante = task-specialized models, lfm-2.6b too small, north-mini-code, dots-3, nemotron-ultra 120s timeout). Free-tier 429s are transient — retry works. Basil's paid credit ($0.13) now untouched; all AI runs on :free models. |
| 2026-09-21 | Session 8: **Dashboard showed 0 jobs — root cause: GET /api/jobs declared `min_score: int` but the frontend always sends `min_score=` (empty string) → 422 on EVERY default Jobs-page load; frontend swallowed the error → empty list.** Fixed: accept str, parse leniently (empty/invalid → None = no filter); + regression test replaying the exact frontend query. Verified live: exact frontend query now returns 25 jobs. test_api.py 29 green. NOTE for M3+: when adding numeric query params, decide explicitly how empty-string values behave.
| 2026-09-21 | Session 6: Diagnosis of 3,397-job flood (root: empty search_terms → DevOps-era fallbacks + US-only hardcode + unfiltered feed sources). Session 7: **relevance pipeline fixed end-to-end.** (a) Real OpenRouter key stored in .env (JOBAGENT_OPENROUTER_API_KEY, gitignored) + DB ai_settings; verified 'AI VERIFICATION: OK'. (b) AI analysis of Basil's resume succeeded: search_terms (AI Engineer, ML Engineer, MLOps, AI Application Developer…), key_skills (Azure OpenAI, LangChain, LangGraph, RAG, multi-agent…), senior, ATS 88 — persisted to search_config (restored from captured output after a 402 killed the persist run; profile-parse max_tokens lowered 4000→2000 to fit free credit tier). (c) Hard-coded DevOps fallbacks replaced in linkedin/indeed/dice/remotive/jobicy via NEW app/scrapers/defaults.py (SEARCH_TERMS/JOB_TITLES); linkedin location 'United States'→'' (worldwide; M3 passes countries); remotive categories software-dev+data; jobicy tags ai+ml+python+backend+engineer. (d) NEW app/title_filter.py deterministic title gate wired into scheduler ingest (skipped_off_topic counter) — blocks Graphic-Designer/Attorney/Intern noise with zero AI cost. (e) 686 tests green (scheduler fixtures renamed to AI Engineer; remotive default assertion updated). (f) Clean rescrape: 778 relevant jobs (vs 3,397 mixed); HN 77→8 all-AI; noise≈0. NOTE: Basil's OpenRouter free credits nearly exhausted (402) — scoring/enrichment will stall until he adds credits or a second key. |
| 2026-09-21 | Session 10: **End-to-end module test harness — `job-search-system/analysis/e2e_module_test.py`.** Booted an isolated instance of the real app (fresh DB, real AI settings on `poolside/laguna-s-2.1:free`, evidence profile seeded from Basil's actual resume) and exercised all 134 endpoints across 17 module sections through the actual HTTP API. **Result: 67/67 checks passed** (57 PASS + 10 SKIP for AI-dependent checks due to OpenRouter free-tier 50/day quota exhaustion; 0 FAIL). Report: `docs/E2E_MODULE_TEST_REPORT.md`. **Product bugs found + fixed:** (1) Feature flags NOT enforced on `/api/jobs/{id}/estimate-salary` and `/api/career/suggestions` — both returned 200 instead of 404 when flags were off; added `enable_salary_tools`/`enable_career_advisor` checks in `app/routers/jobs.py:174` and `app/routers/analytics.py:190`. (2) `generate-cover-letter` endpoint swallowed all AI errors (quota, network, parse) and returned 200 with an empty letter — added honest 502 in `app/routers/tailoring.py:222`. (3) EvidenceChecker: Jaccard similarity floor unfairly penalized short verified lines against long corpus entries — added containment-based alternative pass in `app/evidence_checker.py:107`. **Test infra issue found:** `/api/queue/events` is an SSE streaming endpoint (infinite loop) — calling `client.get().json()` on it hangs forever; fixed test to use `asyncio.wait_for` with 5s timeout. **Existing tests still green:** 43 passed (test_api.py + test_evidence.py). |
| 2026-09-22 | Session 12: **M3 Country strategy COMPLETE (E2E-verified per Golden Rule #11).** 6 country YAMLs + CountryRegistry + deterministic visa engine + /api/countries API + apply_country_strategy (restore-then-dismiss with jobs.strategy_dismissed reversibility column). **Basil's REAL resume used for E2E** (uploaded as .docx from live DB, evidence corpus seeded from it; safe_dump for YAML robustness). 84/84 E2E (16 new country checks incl. UAE disable→dismiss→re-enable→RESTORE round trip); 701 unit tests green (+15). Real gaps fixed: UAE missing from classifier entirely; 'uk'-in-'ukraine' substring bug (word-boundary matching now); registry-region vs classifier-string mismatch caught by unit test before E2E (added explicit 'region' field to schema). **Server-ops lessons:** (a) pkill SIGTERM never finishes while a browser holds the SSE /api/queue/events connection open — 'Waiting for connections to close' forever; use kill -9 on the uvicorn PIDs, then verify with `ss -tlnp | grep 8085` = exactly ONE python listener (pgrep counts uv run wrappers + bash wrappers — count the .venv/bin/uvicorn python process, not matches); (b) embedded test uvicorn MUST use lifespan="off" (Session 10 lesson, re-confirmed). |
| 2026-09-22 | Session 15: **Memory hygiene + first GitHub push.** (a) Milestone tracker + phase checklist + CURRENT STATE synced to actual state (M3/M4/M5 complete, next M6). (b) Workspace had NO git repo — initialized one at `~/Documents/PERSONAL PROJECT/job_get/` (branch main) with a workspace .gitignore that excludes references/ (5 clones keep their own history), .venv, caches. Pre-commit safety scan verified: NO .env (OpenRouter key), no data/ (778-job DB), no *.docx resumes, no venv in the commit — 262 files / 3.3 MB clean. Initial commit d764f83 pushed to **github.com/basilahamed07/CHANGE** (user-created repo, public, SSH auth verified as basilahamed07). (c) **Decisions that required asking Basil (recorded for future sessions):** repo URL/name (user created empty repo himself — gh CLI not installed, SSH cannot create repos), visibility = PUBLIC, push target confirmed interactively. (d) **New-PC setup notes:** clone → `cd job-search-system/root` → `uv sync` → copy .env.example to .env + paste OpenRouter key → upload resume .docx via dashboard. NOT in repo (manual copy or fresh start): root/.env (key), root/data/ (SQLite: jobs, resume text, ai_settings), Basil's *.docx, references/ clones (not needed for dev). |
| 2026-09-22 | Session 14: **M5 Dedup + freshness + eligibility COMPLETE (E2E-verified, Rule #11).** `app/freshness.py` — 3 states (VERIFIED_FRESH / STALE / DATE_UNKNOWN) with evidence dict stored on jobs.freshness_evidence (audit trail); DATE_UNKNOWN is terminal — never upgraded (Critical Test #3). `app/eligibility.py` — deterministic gate chain (dismissed → freshness → evidence → repost-pending) with reason codes, zero LLM on INELIGIBLE. API: POST /jobs/{id}/eligibility, GET /eligibility/eligible-jobs, GET /jobs/{id}/freshness. `job_duplicates` repost graph + merge path in discovery cross-source dedup. **Real bug fixed:** auto_dismiss_stale used 30d, violating Golden Rule 10 (MAX_JOB_AGE_DAYS=7) — freshness-driven now. E2E 98/98 / 0 FAIL (eligibility 8/8 incl. CRITICAL #3 via API); 723 unit tests green (+14). Router lesson: `_engine()()` double-call left a coroutine un-awaited — dependency injection must return the instance, not a factory. Server-ops: pkill+restart verified via `ss -tlnp` single-listener + /api/system/health + live-pool eligibility query (3 eligible jobs found on Basil's 778-job pool). |
| 2026-09-22 | Session 13: **M4 Discovery adapters + normalization COMPLETE (E2E-verified).** JobSourceAdapter interface + CanonicalJob + make_content_hash (cross-source identity, URL excluded). 4 ATS adapters (greenhouse facade, lever, ashby, smartrecruiters) on BaseScraper chassis — all 4 probed LIVE against real APIs (lever defaults pruned to verified-live boards spotify/palantir). run_discovery_cycle: countries × terms × adapters with legacy ingest gates + budget cap + per-pass stop-reason telemetry; orchestrator enforces source attribution. **Critical Test #2 deterministic:** same job 2 sources → 1 job + 2 source rows. **Real bug fixed:** update_allowed_regions bare UPDATE silently no-op'd on fresh DBs → UPSERT. E2E 90/90 (discovery 8/8 with local ATS stubs + live probes); 709 unit tests green. AI-quota SKIPs (10) environmental: scoring ran 20/592 then circuit breaker stopped gracefully. respx added as dev dep. |
| 2026-09-22 | Session 11: **E2E suite completed with REAL AI — 68/68 PASS, 0 SKIP, 0 FAIL** (report: docs/E2E_MODULE_TEST_REPORT.md @ 07:09 UTC). Quota had reset, so scoring/tailoring/cover-letter/interview-prep all ran against poolside/laguna-s-2.1:free — noise job (Graphic Designer) scored 0, AI job scored high, evidence-gated tailoring passed. **Harness hardening (analysis/e2e_module_test.py):** (1) SSE pub/sub check now runs against a REAL embedded uvicorn socket — ASGITransport buffers whole responses so an SSE event can NEVER arrive in-process; must pass `lifespan="off"` or the embedded server re-runs lifespan and closes state.db mid-suite (crashed a run with 'no active connection' + SchedulerNotRunningError); stuck probe is abandoned WITHOUT join (endpoint swallows CancelledError). (2) Seed now walks the REAL `run_location_classification` step — scoring is gated on `location_classified=1`, synthetic jobs otherwise invisible to scoring. (3) Job score is nested: `job.score.match_score`, not top-level. (4) Dismiss test moved AFTER scoring (dismissed jobs excluded from scoring by design). (5) Crash guard: any uncaught section error is recorded and the report still writes. **Live validation of earlier fixes:** free quota died mid-run during cover-letter generation → endpoint returned the honest 502 exactly as designed (fix #2 from Session 10 verified in production conditions). **No new product bugs found.** Unit suites green: 43 passed (test_api + test_evidence). Same day: **Basil added Golden Rule #11** — every new module/feature requires E2E verification + report in docs/ + fixes + memory/plan updates before it can be called done. Codified in IMPLEMENTATION_PLAN.md milestone rules (#5) and Golden Rules (#11). |
| 2026-09-21 | Session 5: Basil hit "✗ No resume yet" after uploading. **Two product bugs fixed:** (1) POST /api/resume/upload never created a resumes row (only search_config) → GET /api/resumes empty → onboarding checklist stuck; now creates row (first upload = default, re-upload same filename updates in place). (2) .docx uploads stored as raw ZIP bytes (text began 'PK\u0003\u0004…') — added python-docx extraction incl. table cells + empty-doc 400. Cleaned corrupted binary resume_text from search_config. +2 regression tests (upload→list flow, docx extraction); test_api.py now 28 green. Basil must RE-UPLOAD his .docx (old upload was unrecoverable binary). |
