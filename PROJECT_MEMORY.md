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

- **Phases completed:** 0–4, 5–11 (M3+M4+M5), 12–13 (M6), 15–17 (M7), 18–19 (M8), 20–22 (M9), 23–28+31–41 (M10–M14), 42, 43; **M15a auth + M15b workspaces COMPLETE**; **REAL USER-JOURNEY E2E GREEN 2026-09-24 (26/26 scenarios, 204/204 checks, 285 live HTTP calls, 85.8% API coverage)**; **Discovery expansion 2026-09-28: 10 countries (India/Canada/Australia/Poland added) + 15 adapters, sponsor-country E2E 20/20 GREEN, 49 real jobs live-ingested** (docs/JOB_PORTALS_BY_COUNTRY.md + docs/E2E_DISCOVERY_EXPANSION_REPORT.md). Pending: Basil's Jooble (+optional Adzuna) keys to activate the keyed adapters.
- **Multi-user plan:** docs/MULTI_USER_PLAN.md (Basil decisions: 2–10 users, per-user discovery, admin full access via audited impersonation; Option C = per-user SQLite workspace, zero schema changes). M15a + M15b done; M15c partially done (per-user *interactive* discovery/scrape/score + per-user AI cost meter landed 2026-09-24); M15c remainder + M15d + M15e pending.
- **UI coverage (Basil's audit request):** ALL milestone features now reachable in the UI — Dashboard: Daily Run panel (run/stages/shortfall) + Targeting Feedback (M12); Settings: Countries & Discovery tab (M3+M4); Job detail: Pipeline Actions panel (M5–M9: eligibility, hybrid score, contacts, package build/repackage/download, outreach draft); Network: Outreach drafts list + Draft-due-follow-ups button (M9/M10). Guide: docs/USER_GUIDE.md.
- **Current phase:** M10–M14 + M15a + M15b COMPLETE; real end-to-end user journey verified GREEN 2026-09-24. **M15c: N1 per-user Gmail token DONE 2026-09-27**. Also landed 2026-09-27: **resume-first onboarding gate** (no resume → scrape/discovery 428; AI keyword extraction + confirm/edit screen; live E2E 26/26, docs/RESUME_ONBOARDING_E2E_REPORT.md). **NEXT-5 INTERRUPTION — STAGE-1 DISCOVERY UPGRADE DONE 2026-09-30 (branch `user_change_before_new_feature`, commits 959ed1e/18575d6/af31874):** central source registry (app/source_registry.py, 20 sources tiered/type/countries/access) drives the orchestrator — tier-ordered runs, honest NOT_APPLICABLE country skips, per-pass SourceRunHealth (10 statuses incl. CONFIGURATION_REQUIRED for keyed sources), [DISCOVERY] structured logs, canonical-source provenance (jobs.canonical_source + jobs.source_types; career>ATS>gov>board>aggregator); NEW app/ats_detect.py (22 URL rules, 16 ATS providers) + app/company_careers.py (opt-in JSON-LD JobPosting direct-career adapter) + BuiltinAdapter (fixed 2 live builtin.com JSON-LD bugs: entity-encoded ld+json type, @graph-wrapped JobPosting → 0→25 jobs); /api/discovery/registry endpoint; 39 deterministic tests (tests/test_discovery_upgrade.py); live 10-country smoke 200 passes 0 FAILED (docs/discovery/** 9 MD + results/*.json + per-country samples). **BOUNDED CONCURRENCY DONE 2026-09-30 (af31874):** asyncio.gather+Semaphore in discovery.py (default 5, arg `max_concurrent_sources=` or env JOBAGENT_DISCOVERY_CONCURRENCY; 1=serial), ingest stays serial, tier submission order preserves canonical preference, DONE duration logs + max_active telemetry; live benchmark 1390s→606s = **2.30× faster**, 0 FAILED/0 RATE_LIMITED both runs, unique 194→193 (web jitter); 4 new concurrency tests (semaphore cap, crash isolation, same-results-as-serial, env config); report docs/discovery/PERFORMANCE_CONCURRENCY.md. **STAGE-2 CLASSIFY DONE 2026-10-01 (same branch):** NEW `app/classification.py` — deterministic priority chain STRUCTURED_COUNTRY→TEXT_LOCATION→CITY_MAP→DESCRIPTION→ATS_METADATA→SOURCE_HINT(LOW)→AI_FALLBACK→UNKNOWN with a `Classification` dataclass (country_code/name, region, city, remote_type, confidence, source, reason, supported_countries), canonical `COUNTRY_ALIASES` for all 10 countries, `CITY_TO_COUNTRY`, region buckets (APAC/EMEA/EUROPE/LATAM/MENA/NORTH_AMERICA/GLOBAL), `normalize_country_code`, `detect_conflict`. Source country is HINT ONLY — never overrides text (golden rule kept in the data: text rows carry TEXT_LOCATION/CITY_MAP at HIGH, hint rows SOURCE_HINT at LOW). Bounded validated AI fallback (`classify_job_ai`) runs ONLY on deterministic residue, rejects unconfigured/low-confidence answers, swallows errors. New jobs columns `country_code/classification_confidence/classification_source/classification_reason/supported_countries` + `search_config.classification_metrics` (UPSERTs fixed: `updated_at` NOT NULL supplied; bare UPDATE no-op bug closed) + `get_unclassified_jobs` dead `source` column reference fixed. `run_location_classification` rewritten (residue-only AI, metrics, conflict counting, unknown-preserving dismissal). 70 tests (tests/test_classification.py, +6 AI) + 218 related-suite regression green; live validation over the real discovery sample pool 104/104 rows classified (77 same-country, 27 cross-country all legitimate text-wins, 0 unknown) + 16/16 curated priority-chain battery; docs/classify/** 6 MD + results/classification_summary.json; harness analysis/verify_classification_live.py. **STAGE-3 ELIGIBILITY DONE 2026-10-01 (same branch, NOT committed):** explicit ordered gate chain DATA_SANITY→DISMISSED→ALREADY_APPLIED→JOB_STATUS→FRESHNESS→LOCATION→EVIDENCE→FINAL_ELIGIBILITY with statuses ELIGIBLE/INELIGIBLE/REVIEW_REQUIRED/UNKNOWN + gate/reason/evidence (`app/eligibility.py`). **SCORE contract fixed:** new `db.get_scoreable_jobs()` requires `eligibility_status='ELIGIBLE'`; both SCORE entry points (`app/main.py` AI scoring, `app/matching_service.score_all_unscored`) evaluate eligibility first and read only scoreable jobs, so stale/out-of-region/unknown-date/already-applied jobs can no longer leak into SCORE (Critical #5/#6). New persisted jobs columns eligibility_status/gate/reason/evidence/evaluated_at + job_status/closing_date (JOB_STATUS gate, positive-evidence only) + search_config.eligibility_metrics; new scheduler pass `run_eligibility_pass`; router endpoints /eligibility/review-jobs + /eligibility/metrics. Consumes Stage-2 (country_code/confidence/source/supported_countries), handles remote region buckets (APAC/EMEA→review when targeted), worldwide remote, multi-location, unknown country→review (never fabricated). 29 tests (tests/test_eligibility.py, +15) + 307 related regression green; live validation on a COPY of Basil's real DB (analysis/verify_eligibility_live.py): 1962 evaluated → 67 ELIGIBLE / 1895 INELIGIBLE / 0 review (every unknown region row is also stale — honest gate-order effect), gates DISMISSED 1357 / FRESHNESS 515 / LOCATION 20; docs/eligibility/** 6 MD + results/eligibility_summary.json. Bug found+fixed: eligibility batch UPDATE param order caused an infinite loop (caught by idempotency test). **NEXT (Basil's queue): back to N2 per-user scheduled cycles → N3 run state → N4 ship-reviewed-text → N5 admin panel.** Server ops: docs server on 8090 (`docs_server.py`), NOT the app.
- **Status board:** docs/E2E_RUN_STATUS.md (live) · **generated report:** docs/USER_JOURNEY_E2E_REPORT.md · raw evidence: analysis/e2e_runs/<date>_<time>/ (gitignored — contains personal resume text)
- **User guide:** GUIDE.md (practical start-here: start server, log in, setup, daily use, multi-user, troubleshooting)
- **Agent boot file:** docs/AGENT_CONTEXT.md (2026-09-28) — the ONE self-contained context doc for any AI agent: capability map (21 rows, code-anchored), full input→pipeline→output flow diagram, the 10 hard invariants + 5 Critical Tests, current state + N2–N5 queue, verification commands. Read this FIRST when resuming work; when it and the code disagree, the code wins.
- **Branch (2026-09-24):** work pushed on **`dev_users_based`** (commit 2b008e6) — push WORKS now (`~/.ssh/id_ed25519` is present; the Session-25 "PUSH BLOCKED" note is obsolete)
- **Approved to implement:** YES — Basil approved M1 start after architecture review
- **Workspace:** `job-search-system/` with root/ (final product), references/ (5 clones), docs/, analysis/
- **Analysis artifacts DONE:** docs/REPOSITORY_ANALYSIS.md, docs/FEATURE_MATRIX.md,
  docs/ARCHITECTURE_DECISION.md, docs/IMPLEMENTATION_PLAN.md
- **Next action:** Begin milestone M10 (Application CRM status enum + append-only events, follow-up engine with country-cadence + terminal-state stop rules, queue approval flow extended to packages/outreach).
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
| 12 | Hybrid matching engine | DONE 2026-09-23 (M6 — deterministic, E2E-verified) |
| 13 | RAG / semantic matching | DONE 2026-09-23 (M6 — RagProvider over VERIFIED evidence) |
| 14 | Deterministic vs LLM split | DONE (enforced across M5/M6/M9/M10/M12; visa, eligibility, matching, CRM transitions are all zero-LLM) |
| 15 | Company research | DONE 2026-09-23 (M7 — cached rich fields) |
| 16 | People/contact discovery | DONE 2026-09-23 (M7 — ContactProvider chain) |
| 17 | Contact confidence | DONE 2026-09-23 (M7 — deterministic scoring) |
| 18 | Resume tailoring (DOCX primary) | DONE 2026-09-23 (M8 — package builder, DOCX-first) |
| 19 | Application package layout | DONE 2026-09-23 (M8 — Phase-19 layout + metadata.json) |
| 20 | Outreach engine | DONE 2026-09-23 (M9 — audience variants + caps) |
| 21 | Outreach sequences (config-driven) | DONE 2026-09-23 (M9 — YAML sequences) |
| 22 | Gmail draft integration | DONE 2026-09-23 (M9 — DRAFT-ONLY, local fallback) |
| 23 | Application CRM + events | DONE 2026-09-23 (M10) |
| 24 | Kanban dashboard | DONE 2026-09-23 (M10 + UI wiring fixed) |
| 25 | Daily automation scheduler | DONE 2026-09-23 (M11) |
| 26 | Daily target logic | DONE 2026-09-23 (M11 — qualifying PACKAGES) |
| 27 | Response monitor | DONE 2026-09-23 (M12) |
| 28 | Follow-up engine | DONE 2026-09-23 (M10/M11) |
| 29 | Feedback loop | DONE 2026-09-23 (M12) |
| 30 | Analytics | DONE 2026-09-23 (M12/M14) |
| 31 | Database (SQLite first, migration-friendly) | DONE (careerpulse schema + M15b per-user workspaces) |
| 32 | REST API + OpenAPI | DONE (218 operations; E2E covers 85.8% of them) |
| 33 | Dashboard pages | DONE 2026-09-23 (UI coverage audit) |
| 34 | Human approval gates | DONE 2026-09-23 (M10 approval matrix) |
| 35 | Cost control | DONE 2026-09-23 (M14 cost meter; per-user since 2026-09-24) |
| 36 | Resilience | DONE + hardened 2026-09-24 (profile-save 400-not-500) |
| 37 | Security (.env, no secrets committed) | DONE 2026-09-23 (tracked-source secret scan) |
| 38 | Testing (incl. 4 critical tests) | DONE + 2026-09-24 user-journey E2E harness (26 scenarios, Critical #5 = s24) |
| 39 | Observability (run_id etc.) | DONE 2026-09-23 (M14) |
| 40 | CLI (same service layer as UI) | DONE 2026-09-23 (M13) |
| 41 | Documentation set | DONE (CAPABILITIES.md, USER_GUIDE.md, per-milestone E2E reports, USER_JOURNEY_E2E_REPORT.md, E2E_RUN_STATUS.md) |
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
- M6 Hybrid matching — **DONE 2026-09-23** (E2E-verified, Golden Rule #11). Details:
  - `app/hybrid_matcher.py` — 6 deterministic components (skills .35 / role .15 /
    location .10 / visa .10 / recency .10 / semantic .20, validated+normalized weights),
    hard-blocker short-circuit (NO_SPONSORSHIP_STATED, DO_NOT_USE_SKILL_* → cap 25),
    pure-Python TF-IDF cosine (no new deps), machine-readable HybridScore
    (overall, component_scores, matched/missing requirements, hard_blockers,
    advantages, explanation). Zero LLM (Golden Rule 4).
  - RAG layer: RagProvider (local TF-IDF default, zero cost) + OpenAIRagProvider
    (optional embeddings, never fails scoring). Retrieval feeds ONLY relevant
    VERIFIED evidence (Golden Rule 5); DO_NOT_USE skills block, never credit;
    UNVERIFIED never enters the corpus.
  - `app/matching_service.py` — CandidateProfile built from evidence store
    (RAW skill values for phrase matching; normalized only as dedup key),
    search_config targets/prefs, M3 registry visa keywords; score_all_unscored()
    = free baseline over the whole pool.
  - `app/routers/matching.py` — GET status, POST jobs/{id}/score (persist),
    POST score-all, GET jobs/{id}/explain, GET/PUT config (weights normalized),
    GET top-jobs (ranked + breakdowns).
  - DB: job_scores.component_scores/hard_blockers (audit trail per score);
    search_config.hybrid_weights/prefers_remote/requires_sponsorship (UPSERT — M4 lesson).
  - Scheduler: after the AI scoring attempt, hybrid scores whatever AI could not
    (quota/provider down) — pool is never left unscored.
  - **Bugs found + fixed:** TfidfIndex idf-ordering; boundary matcher that
    collapsed spaces ("with python"→"withpython"); normalized skills breaking
    phrase matching ("azureopenai" never matches — profile now keeps raw values);
    Country.visa attribute (real attr: sponsorship_keywords).
  - Tests: tests/test_hybrid_matcher.py 24 tests; **747 passed** full suite (+24).
    E2E: section 16d — **17/17 checks, full harness 116/116, 0 FAIL** (AI-quota
    SKIPs unchanged, environmental). Report: docs/M6_E2E_TEST_REPORT.md.
- M7 Company/contact research — **DONE 2026-09-23** (E2E-verified, Golden Rule #11). Details:
  - `app/contact_providers.py` — ContactProvider interface (find() NEVER raises,
    M4 discipline) + role_type taxonomy (recruiter/hiring_manager/referrer/other,
    deterministic regex) + confidence 0–100 (provider base + title overlap + role
    weight + personal-mailbox bonus − generic-inbox/no-email penalties). Adapters:
    ManualResearch (Basil's saved contacts — FIRST in chain), Hunter (domain-search,
    JOBAGENT_HUNTER_API_KEY), Apollo (people search, JOBAGENT_APOLLO_API_KEY),
    WebSearch (legacy DDG heuristic wrapped). Fallback chain manual→hunter→apollo→web,
    per-provider AsyncRateLimiter. ContactResearchService: cache-first (7d TTL),
    rank_candidates, select_candidate (writes job.hiring_manager_* + email-dedup
    into contacts table).
  - `app/company_enrichment.py` — deterministic careers/LinkedIn URL discovery +
    AI-clue extraction (regex, no LLM), 30-day companies-table cache TTL.
  - `app/routers/research.py` — /api/research: contacts/job/{id} POST+GET+select,
    providers status, company/{name} POST+GET (cache-first).
  - DB: contact_research table (per-job snapshot, UPSERT); companies + careers_url/
    linkedin_url/ai_clues/research_status/researched_at (+ column allowlist updated).
  - **Bugs found + fixed:** harness `await client.get().json()` (json() is sync);
    _COLUMN_ALLOWLISTS['companies'] missing new columns → save_company rejected
    research_status (lesson: update allowlist whenever a table gains columns).
  - Tests: tests/test_contact_providers.py 29 tests (taxonomy table, confidence
    components, provider failure→[], respx Hunter parse, manual scoping, cache
    calls==1, force bypass, double-select dedup, TTL math, DB round-trips);
    **776 passed** full suite (+29). E2E: section 16e — 13/13, full harness
    **129/129, 0 FAIL**. Report: docs/M7_E2E_TEST_REPORT.md.
- M8 Resume/application package generation — **DONE 2026-09-23** (E2E-verified, Rule #11). Details:
  - `app/application_builder.py` — ApplicationBuilder: Phase-19 package layout per job
    (data/applications/{id}-{company-slug}/: resume.docx DOCX-FIRST + cover_letter.docx
    + .txt plain texts + metadata.json schema jobagent-package/1). PackageInputs.
    fingerprint() = sha256 over ALL generation inputs (job, JD hash, resume version,
    profile version, output hashes, model) ⇒ IDEMPOTENT: same fingerprint ⇒ noop
    zero file writes; changed ⇒ rebuilt. EvidenceViolationError refuses to package
    any text failing EvidenceChecker (Rule 5 last line — unverified claims never
    become .docx). Every package born `ready_for_review` (Rule 6).
  - `app/routers/packages.py` — /api/packages: POST jobs/{id}/build (full AI path w/
    evidence gate + one regen; ?refresh=true repackages STORED text with ZERO AI —
    quota-proof), GET jobs/{id}, GET list, GET jobs/{id}/download/{file} (5-file
    allowlist, path-traversal safe).
  - DB: applications + package_dir/package_fingerprint/package_status (migrations +
    allowlist).
  - Bugs fixed: corrupt-metadata reported `built` vs `rebuilt`; test-harness FK +
    fail-closed 503 (test now seeds real store+checker).
  - Tests: tests/test_application_builder.py 12 (fingerprint sensitivity, byte-level
    idempotency, refusal leaves no files, OOXML magic bytes, metadata audit trail);
    **788 passed** full suite (+12). E2E: 16f — 8/8, full harness **137/137, 0 FAIL**.
    Report: docs/M8_E2E_TEST_REPORT.md.
- M9 Outreach + Gmail drafts — **DONE 2026-09-23** (E2E-verified, Rule #11). Details:
  - `config/outreach_sequences.yaml` — 4 audience sequences (recruiter/hiring_manager/
    referral/followup) + identity + anti-spam limits (12/day, 2/company/day,
    6d follow-up wait). Phase-21 config-over-code.
  - `app/outreach.py` — OutreachService: create_outreach IDEMPOTENT per (job, audience)
    — **CRITICAL TEST #4 passes at 3 layers**: service dedup-first, DB UNIQUE(job_id,
    audience) backstop, Gmail thread-level find_existing_draft before create.
    Deterministic _pick_audience from contact-on-file (classify_role reuse);
    render_message with placeholder fill + blank-line collapse. **GmailProvider is
    DRAFT-ONLY (create_draft/find_existing_draft — no send method exists)** via
    httpx REST (zero new deps); local-draft fallback (provider='local') when no
    JOBAGENT_GMAIL_TOKEN so the pipeline completes without Gmail. Caps: daily,
    per-company; followup gated by wait window.
  - `app/routers/outreach.py` — POST jobs/{id}/create (already_exists on repeat),
    POST jobs/{id}/followup (too_soon gate), GET jobs/{id}, GET messages, GET config
    (gmail_connected honest false).
  - DB: outreach_messages (UNIQUE(job_id,audience), FK jobs, provider/draft_id/
    thread_id/status).
  - **Near-miss caught:** inserting outreach_messages CREATE inside
    contact_interactions statement — broken SQL caught by reading back the edit
    immediately; repaired with FK improvement.
  - Tests: tests/test_outreach.py 17 (Critical #4 x3 layers, no-send-method
    assertion, local fallback, gmail draft mock, thread dedup never-create,
    caps matrix, followup time-travel, API double-create); **805 passed** full
    suite (+17). E2E: 16g — 10/10 incl. Critical #4 via live API; full harness
    **147/147, 0 FAIL**. Report: docs/M9_E2E_TEST_REPORT.md.
- M10 CRM + follow-ups — **DONE 2026-09-23** (Session 23; E2E-verified)
- M11 Daily pipeline — **DONE 2026-09-23** (Session 23)
- M12 Response monitor + feedback — **DONE 2026-09-23** (Session 23)
- M13 CLI — **DONE 2026-09-23** (Session 23)
- M14 Hardening + observability — **DONE 2026-09-23** (Sessions 23–24)
- M15a Auth foundation — **DONE 2026-09-23** (E2E-verified). Details:
  - `app/auth.py` — SystemStore (system.db: users/sessions/admin_actions), scrypt
    hashing (stdlib, zero deps), SHA-256-stored session tokens (7-day), LoginThrottler
    (5 fails → 15-min lock), AuthGuardMiddleware (ASGI; enforces session on ALL paths
    except /, /static/*, /api/auth/*, /api/system/health, /docs; HTML 303→/ else 401).
    testing=True bypass keeps the 900+ pre-auth unit tests untouched; test_auth.py
    (25 tests) exercises the REAL guard via testing=False.
  - `app/routers/auth.py` — /api/auth/status|bootstrap|login|logout|me|change-password;
    one-time admin bootstrap (403 after first user); uniform login errors;
    change-password revokes all sessions; lazy ensure() init for lifespan-less clients.
  - Frontend: `static/js/auth.js` (bootstrap/login screens, authGate in handleRoute,
    nav user-chip + logout), api.js updateApplication note. First visit → Create Admin;
    then Sign In.
  - **UI coverage fix (Basil's request):** Dashboard = Daily Run panel + Targeting
    Feedback; Settings = Countries & Discovery tab (toggle countries, apply strategy,
    reload YAML, run discovery, adapter health); Job detail = Pipeline Actions panel
    (eligibility re-check, hybrid score+components, contact research, build/repackage
    package + download, create outreach draft); Network = outreach drafts + follow-up
    drafting button.
  - Verification: 25 new auth unit tests; **931 backend + 180 frontend green**;
    E2E harness: new section 0 auth (8 checks incl. anonymous-401 + login over live
    SSE-probe socket) → **190/190 PASS, 0 FAIL**. Live server verified: health 200,
    anon /api/jobs 401, bootstrap pending. Server run command updated to
    `uvicorn app.main:create_app --factory`.
  - Bugs found+fixed: aiosqlite.connect() unawaited-connection bug in get_user
    fallback; SSE probe needed login (fresh client had no cookie);
    test_upload_resume_env_fallback_path_no_crash now logs in (production path =
    guard active).
- M15b Per-user workspaces — **DONE 2026-09-23** (E2E-verified + Critical Test #5). Details:
  - `app/workspace.py` — WorkspaceManager/Workspace: `data/users/{id}-{username}/` with
    own `jobagent.db` (same 46-table schema, ZERO table changes), `profile/`,
    `applications/`, `gmail_drafts/`. New users get 8 pristine evidence templates
    from NEW `config/profile_templates/` (21 claims, all UNVERIFIED — fail-closed).
  - `app/workspace_middleware.py` — binds each authenticated request to the user's
    workspace DB (`request.state.db` + `request.state.workspace`).
  - `main.py#_db(request)` bridges ALL 157 router call sites that previously read
    `request.app.state.db` → the requesting user's DB (mechanical, zero behavior drift
    when no workspace is bound). `app.state.ai_state_for(request)` builds per-user
    matcher/tailor/evidence-store/checker from THEIR ai_settings + resume + profile dir,
    cached with a stamp and invalidated on settings/resume change.
  - Migration: pre-multi-user data (main DB + WAL/SHM, `profile/`, `applications/`)
    moves into the admin workspace (renamed to canonical `jobagent.db`); app.state.db
    and bg_db reopen on the admin workspace so the scheduler keeps working. Idempotent.
  - Per-user now: jobs pool, applications/packages, contacts, resumes, search config,
    AI provider+key, scraper keys, evidence, countries state, CRM, outreach drafts,
    analytics, daily-run (API path), discovery run.
  - Verification: **E2E 187/187 PASS, 0 FAIL** (harness pre-creates admin so the
    workspace migration runs at lifespan); **Critical Test #5 = tests/test_workspaces.py
    8/8** (jobs/contacts/keys/search-config/resumes/profile/CRM/evidence + distinct
    workspaces proven with 3 real logged-in clients); 939 backend tests green before
    the workspace swap + targeted suites re-run green after.
  - Known limit (M15c): the legacy standalone scheduler/scrape background cycles still
    run against the ADMIN workspace only; per-user discovery/Run-Discovery-Now is
    per-user already. Live server runs with migration applied
    (`data/users/1-basil/` = Basil's real pool).
- M15c Per-user pipeline features — **PARTIAL 2026-09-24** (E2E-verified, Rule #11). Landed:
  - Per-user **interactive** scrape/score: `routers/scraping.py#_task_target()` binds `POST /api/scrape`,
    `/api/score`, `/api/rescore-failed`, `/api/rescore-all` and `/api/jobs/enrich` to the requesting user's
    workspace DB + THEIR matcher (`_score_unscored(db, matcher=None)` in main.py). Before this, any user
    pressing "Scrape now" filled the ADMIN's pool and graded with the ADMIN's resume.
  - Per-user **LLM cost meter**: `ai_usage` gained a `ContextVar` request sink (`set_request_sink`) that
    `workspace_middleware` binds to the user's DB per request — previously every user's spend landed in the
    admin workspace, so `/api/analytics/monitoring` reported 0 calls/$0 for everyone else.
  - Per-user **resume grading**: `routers/settings.py#upload_resume` resolves the AI client via
    `ai_state_for(request)` and only mutates app-level state on the no-workspace legacy path (was: graded with
    the admin's provider AND overwrote the app-level matcher with the caller's resume).
  - **Bounded discovery**: `POST /api/discovery/run?passes=1..24` + `max_passes` on `run_discovery_cycle`.
  - **N1 per-user Gmail token — DONE 2026-09-27** (NEXT_5_PLAN item): token lives in the user's own workspace `email_settings` row; `routers/outreach.py#_gmail_credential()` resolves workspace-first, `JOBAGENT_GMAIL_TOKEN` env only as legacy fallback; `/api/settings/email` GET masks the token (`****`), POST round-trips the mask without blanking the stored credential, `clear_gmail_token` is the only eraser; `/api/outreach/config` reports `gmail_connected` + `gmail_source` (workspace|env|"") and never the raw token. Real-scenario tests: tests/test_multiuser_real_scenario.py 4/4 (two live users, distinct tokens, env-fallback, clear-isolation, no-token local-draft path). Re-verified 2026-09-28 with test_workspaces 12/12 + outreach/evidence/eligibility/digest 58/58 + api/profile/resume-grading 65/65, then committed.
  - Scraper keys were already per-user (corrected 2026-09-24 inspection). Still PENDING in M15c: per-user *scheduled* (interval) cycles (N2).
- M15d Admin panel — PENDING (user create/disable/reset already pulled forward into `routers/auth.py`)
- M15e Hardening + migration (Critical Test #5) — PENDING (key encryption at rest pending; isolation now
  continuously proven by E2E scenario s24_cross_user_isolation)

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
| 2026-09-23 | Session 20: **M9 Outreach + Gmail drafts COMPLETE (E2E-verified, Rule #11). CRITICAL TEST #4 PASSES at three layers** (service dedup-first → DB UNIQUE backstop → Gmail thread lookup): outreach twice ⇒ exactly one draft. DRAFT-ONLY by construction (no send method exists; local-draft fallback without token; honest gmail_connected=false). Config-driven sequences (4 audiences) + caps (12/day, 2/company, 6d followup gate). Near-miss fixed: outreach CREATE inserted inside contact_interactions SQL — caught by immediate read-back. 17 unit tests → 805 green; E2E 16g 10/10, full harness **147/147, 0 FAIL**; report docs/M9_E2E_TEST_REPORT.md. Committed+pushed M6–M8 (73fbd00) with NEW_PC_SETUP.md; data/profile/ evidence templates now versioned (fresh-clone fail-closed gap closed). Live server runs on 127.0.0.1:8085 for Basil; hybrid score-all covered 572/572 jobs free (avg 44.7, 17 sponsorship-blockers caught incl. all Cloudflare + NSA). |
| 2026-09-23 | Session 25: **M10–M14 committed; two-branch workflow established (main + dev).** Branch policy from Basil: **`main` = stable/release, `dev` = integration — day-to-day work lands on `dev`, then fast-forwards into `main`.** This milestone set was committed on `dev` (35a45fe) and fast-forwarded into `main`, so both branches are identical and ready. Also fixed a real leak risk before committing: `job-search-system/data/` (E2E-generated application packages containing Basil's resume text) and `freebuff-chat-*.md` transcripts were NOT ignored at the workspace level — added to the root `.gitignore` (root/data/* and .env were already covered by root/.gitignore). Staged diff secret-scanned clean; 34 files, 2915 insertions. **PUSH BLOCKED — no credentials in this sandbox:** no credential helper, no ~/.git-credentials, no GH_TOKEN, no gh CLI, and no SSH key (`~/.ssh` holds only `authorized_keys`; `ssh -T git@github.com` → Permission denied (publickey)). Basil must either run `git push -u origin main && git push -u origin dev` himself, supply a PAT, or add an SSH key. NOTE: the new commit's author defaulted to `Ubuntu <ubuntu@ip-172-31-7-58...>` because git identity is unset in this sandbox — previous commits are authored `Basil Ahamed <basilahamed46@gmail.com>`; set user.name/user.email locally and `git commit --amend --reset-author` if that matters. |
| 2026-09-23 | Session 24: **M14 observability finished (LLM cost meter + cache metrics) + server restarted live.** New `app/ai_usage.py`: static USD/1M-token pricing table (DeepSeek Flash 0.15/0.60 verified against the docs), family-keyword matching for dated model ids (claude-sonnet-4-20250514, us.anthropic.claude-opus-4-6-v1), `:free` models billed $0, OpenAI + Anthropic usage extraction, in-process buffer + DB sink, `summarize()`, `budget_projection()`. Metering is wired into `AIClient._meter()` on all 4 chat paths and **swallows its own errors** so a broken sink can never break an AI call (unit-tested with a raising sink). New `ai_usage` + `metrics` tables; `research_cache_hits/misses` counters in the M7 research service (best-effort); `GET /api/analytics/monitoring` (usage all-time + today, budget, cache hit-rate, daily-run state, `?days=` window). New **AI Usage & Cost** panel on the Stats page (spend/calls/tokens/avg-per-call, budget bar, per-model table, cache hit-rate, packages today). 20 new unit tests → **872 backend + 180 frontend green**; E2E **178/178 PASS, 0 FAIL** (new section 16k 7/7 incl. the "$2 ⇒ 380 applications" cost check). Server restarted and verified live: /api/system/health, /api/crm/statuses, /api/daily-run/today, /api/analytics/monitoring, /api/analytics/feedback all 200, clean boot log. Remaining M14 nicety (not blocking): standalone DATABASE/PROVIDERS/SECURITY/DEPLOYMENT doc pages. |
| 2026-09-23 | Session 23: **M10+M11+M12 COMPLETE + M13 CLI + M14 hardening pass (E2E-verified, Rule #11). The remaining milestone queue is now empty.** (1) **M10 CRM** — `app/crm.py`: VALID_TRANSITIONS table (forward-only pipeline; terminal states have no engine escape), pure `check_transition()`, cadence `compute_follow_up()` (one-pending-reminder rule; stop rules for rejected/withdrawn/closed/ghosted/offered/accepted), Phase-34 `APPROVAL_MATRIX`; `app/routers/crm.py` (/crm/statuses, POST /jobs/{id}/status auto-completing reminders on terminal entry, /crm/followups/run, per-item /jobs/{id}/bulk-status). (2) **M11 Daily pipeline** — `app/daily_run.py`: 10 ordered stages, state persisted BEFORE each stage as a crash marker, completed stages never re-run, crashed `running` stage re-runs with RUN_INTERRUPTED, machine-readable shortfall vocabulary, daily_target = NEW QUALIFYING PACKAGES (Golden Rule 4, keyed on applications.package_dir + new `package_built_at`); `daily_runs` table; /daily-run/today + idempotent /daily-run/run. (3) **M12 Response monitor** — `app/response_monitor.py`: deterministic 8-class classifier + no-reply sender signal + 0.70 confidence floor → REVIEW (never silent); `recommend()` min-sample gated with `auto_rewrite_performed:false`; `response_correlation()` (response rate + median days-to-response); /responses/classify + /analytics/feedback. **Bug found+fixed:** targeting recommendation divided by applied+rejected (rejection share could never exceed 0.5) → now over interviewing+offered+rejected. (4) **M13** — `root/cli.py` `jobagent` (health/search/prepare/contacts/daily/followups/analytics/status) over the SAME service layer, live-verified on the real 572-job DB. (5) **M14** — tracked-source secret scan clean, .env gitignored, `_mask_key` verified, deps current. **Verification (single E2E run per Basil's rule):** E2E sections 16h 9/9, 16i 5/5, 16j 6/6 → **168/168, 0 FAIL** (10 pre-existing AI-quota SKIPs); 41 new unit tests → **850 backend + 180 frontend green**; report docs/M10-M14_E2E_TEST_REPORT.md; plan updated. **IMPORTANT late find (caught by checking the UI, not by tests):** the Kanban drag-drop and the detail page's "Mark applied" button both called `api.updateApplication()` → the OLD **unvalidated** `POST /jobs/{id}/application`, so M10's engine governed only its own new endpoint while the UI could still create impossible states (e.g. `rejected → offered`) and terminal states never stopped follow-ups. Also, the first transition table forbade `interested → applied` — which the app's OWN "Mark applied" button performs, i.e. the strict table would have broken a core action. **Both fixed:** `api.js#updateApplication` now routes through validated `POST /jobs/{id}/status?to_status=…`; forward skips within the pipeline are allowed (off-platform applications are real), while `→ offered` shortcuts and terminal resurrection stay blocked. Lesson: **verify a new module against the UI's call sites, not just its own endpoints.** Re-verified: E2E **171/171 PASS, 0 FAIL** (16h now 13 checks incl. the UI Mark-applied path); **852 backend + 180 frontend green**; live uvicorn boot check 200 on /api/system/health, /api/crm/statuses, /api/daily-run/today, /api/analytics/feedback. Harness bugs fixed: approval-matrix dict compared to string; bulk-status target invalid for BOTH jobs; CRM walk assumed a fresh job but section 11 had already advanced ai_job to 'applied' (now walks an untracked job + asserts the clean-start precondition). Ops lesson: **the E2E harness MUST run from `root/`** (`cd root && .venv/bin/python ../analysis/e2e_module_test.py`) or relative config paths yield 0 countries and 11 false FAILs. |
| 2026-09-23 | Session 22: **DeepSeek provider added (7th AI provider) — Basil approved $2 top-up after 429-quota pain on OpenRouter free tier.** Read api-docs.deepseek.com live: API is OpenAI-compatible (base_url https://api.deepseek.com, Bearer key, model `deepseek-flash` = DeepSeek-V4.1-Flash; legacy `deepseek-v4-flash` names accepted but retired). Wired into the existing OPENAI_COMPAT_PROVIDERS spine in ai_client.py (retry/circuit-breaker/health-check all inherited free) + ALL_PROVIDERS; key-shape validation (sk- prefix) in settings.py; JOBAGENT_DEEPSEEK_API_KEY in config.py/.env.example; env fallback order in _build_ai_client is OpenRouter→DeepSeek→Anthropic (free tier stays default until DeepSeek key saved via UI). Frontend: settings.js dropdown + PROVIDER_MODELS (deepseek-flash/v4-pro/reasoner), onboarding.js. Cost math driving the decision: $2 ≈ 380 full tailoring packages @ ~$0.00525 each (15K in @ $0.15/M + 5K out @ $0.60/M, off-peak; resume text is cache-eligible @ $0.003/M making real cost lower). Unit tests +3 (config env, provider routing defaults, model override) → **809 backend + 180 frontend green, single full-suite run per Basil's one-E2E-only rule.** Basil to paste his DeepSeek key in Settings → AI after topping up; no E2E needed (routing = same OpenAI-compat path as OpenRouter).
| 2026-09-23 | Session 21: **Scraper reliability fixes from live server-log analysis (`/tmp/jobagent.log`).** (1) **Wellfound 0→188 jobs (two stacked bugs):** (a) page format changed — jobs now live as `JobListingSearchResult:<id>` Apollo entities under `__NEXT_DATA__ → pageProps.apolloState.data` (old `JobListing`/`pageProps.jobs` lookups found nothing); new `_extract_jobs_from_apollo_state` walks the cache map, resolves company names from sibling `StartupResult.highlightedJobListings` __refs, parses `compensation` strings ("$150k – $280k") via new `_parse_compensation`, builds `/jobs/<id>-<slug>` URLs; (b) **root cause of silent-empty even on 200:** `BROWSER_HEADERS` set `Accept-Encoding: gzip, deflate, br` manually → Cloudflare served Brotli, httpx does NOT auto-decompress when the caller declares encodings → parser got binary garbage. Removed the header (also `Connection`, forbidden in httpx). Also `_parse_next_data` regex fallback for the `crossorigin="anonymous"` script tag that BeautifulSoup's `.string` missed. (2) **Jobicy `tag=ai` → HTTP 400** (API rejects it, verified live): TAG_MAP now `ai→artificial-intelligence`, `engineer→engineering`, added genai/generative ai/rag/llm mappings; DEFAULT_TAGS updated; live-verified 100 jobs. (3) **Indeed 403:** playwright + playwright-stealth installed (`uv sync --extra playwright`, chromium downloaded) — Indeed still serves Cloudflare "Just a moment" to this datacenter IP even stealthed (needs residential proxy or paid API, honest warning now distinguishes IP-block vs playwright-missing); **real bug found:** playwright-stealth 2.0 removed `stealth_async` → stealth was silently never applied; `browser_pool.py` now normalizes v1/v2 behind `apply_stealth()` applied at CONTEXT level; navigation `networkidle→domcontentloaded` (30s timeouts were exceeding). (4) **stats.js career-advisor 404 noise:** frontend now checks `/api/system/health` features.career_advisor first and renders a disabled-state hint instead of calling the flagged endpoint. Tests: +3 wellfound (JobListingSearchResult parse, _parse_compensation), indeed stealth test updated to context-level contract; **807 backend + 180 frontend green**; live-verified Wellfound 188 jobs w/ companies+salaries+URLs, Jobicy 100. |
| 2026-09-23 | Session 19: **M8 Application package generation COMPLETE (E2E-verified, Rule #11).** ApplicationBuilder with Phase-19 layout (DOCX-first resume + cover letter + .txt + metadata.json audit), fingerprint-based idempotency (same inputs ⇒ noop, byte-identical), EvidenceViolationError as the last-line gate (unverified claims never materialize), packages born ready_for_review. /api/packages build/refresh/list/download (5-file allowlist). refresh=true works with ZERO AI on stored text — verified live in a quota-dead run. 12 unit tests → 788 green; E2E 16f 8/8, full harness **137/137, 0 FAIL**; report docs/M8_E2E_TEST_REPORT.md. |
| 2026-09-23 | Session 18: **M7 Company + contact research COMPLETE (E2E-verified, Rule #11).** ContactProvider interface + 4 adapters (Manual first, Hunter, Apollo, WebSearch) with never-raise contract + rate limiting; deterministic role taxonomy + confidence scoring; cache-first research service (7d TTL) with select_candidate + contact email-dedup; company enrichment (careers/LinkedIn/AI-clues, 30d cache) via regex — zero LLM. /api/research surface + contact_research table + companies rich columns. 2 bugs found+fixed (harness await-.json(); companies column allowlist). 29 unit tests → 776 green; E2E 16e 13/13, full harness **129/129, 0 FAIL**; report docs/M7_E2E_TEST_REPORT.md. System fully functional with NO paid contact-provider keys (manual+web fallback). |
| 2026-09-23 | Session 17: **M6 Hybrid matching COMPLETE (E2E-verified, Rule #11).** Deterministic 6-component engine (skills/role/location/visa/recency/semantic) + pure-Python TF-IDF + RagProvider over VERIFIED evidence; hard-blocker short-circuit; free baseline scoring of the whole pool (zero AI quota) wired into the scheduler as the layer under AI scoring; /api/matching surface (status/score/score-all/explain/config/top-jobs); component_scores + hard_blockers persisted per score. 4 bugs found+fixed (idf ordering, space-collapsing boundary matcher, normalized-skill phrase-match kill, Country.visa attr). 24 unit tests → 747 green; E2E 16d 17/17, full harness **116/116, 0 FAIL**; report docs/M6_E2E_TEST_REPORT.md. Also Session 16 same day: Basil-requested M1–M5 re-verification with real resume (98/98; harness resume-selection pinned to default resume; detached `uv run` dies silently — launch E2E via .venv/bin/python). |
| 2026-09-22 | Session 16: **Basil-requested re-verification of M1–M5 E2E with his REAL resume — 98/98 passed (88 PASS · 10 SKIP · 0 FAIL).** Report: docs/E2E_MODULE_TEST_REPORT.md. Harness fix: resume selection now pinned to the DEFAULT resume (ORDER BY is_default DESC, id ASC) — the live DB had 2 rows and row 2 is a career-market-analysis PDF, not a resume. Server-ops lesson: detached `uv run` processes die silently with no output in this sandbox — launch the E2E suite via `.venv/bin/python` directly (plain background processes DO survive; verified with a `sleep 120` control). All 10 SKIPs are OpenRouter free-quota 429s (X-RateLimit-Remaining: 0, resets 00:00 UTC; OpenRouter now offers 1000 req/day for $10 credits). Everything non-AI verified green with Basil's real 4109-char resume: docx upload/extraction, evidence gate (fabricated_number + unsupported_skill blocked), all 6 countries + strategy round-trip, 4-adapter discovery cycle + live health probes, Critical #3 eligibility matrix + reason codes, feature-flag 404s. |
| 2026-09-21 | Session 5: Basil hit "✗ No resume yet" after uploading. **Two product bugs fixed:** (1) POST /api/resume/upload never created a resumes row (only search_config) → GET /api/resumes empty → onboarding checklist stuck; now creates row (first upload = default, re-upload same filename updates in place). (2) .docx uploads stored as raw ZIP bytes (text began 'PK\u0003\u0004…') — added python-docx extraction incl. table cells + empty-doc 400. Cleaned corrupted binary resume_text from search_config. +2 regression tests (upload→list flow, docx extraction); test_api.py now 28 green. Basil must RE-UPLOAD his .docx (old upload was unrecoverable binary). |
| 2026-09-23 | Session 26: **M1–M14 full E2E re-verification + job-source coverage expansion (batch 2) + detailed CAPABILITIES.md.** (1) **E2E re-verified: 178/178 PASS, 0 FAIL** (harness run from `root/`; the only SKIPs are the three AI sections — 8 scoring, 10 cover letter, 12 interview prep — deferred by Basil pending the DeepSeek key). The harness exercises stub adapters, not the scraper registry, so adding sources does not invalidate this run. (2) **Scraping coverage expanded again — 3 new live-verified sources, registry now 21:** `AshbyScraper` (ATS JSON, 20 verified boards, live 1,733 jobs with real salary bands parsed from structured compensation tiers), `LandingJobsScraper` (EU tech board, live 45 jobs; company recovered from the `/at/<slug>/` URL path because the API has no company field), `FourDayWeekScraper` (remote/4-day-week board, paginated, live 16). (3) **Bug found and fixed in my own new code before it shipped:** 4dayweek salaries are in cents but the hourly/monthly/weekly branches DIVIDED by periods-per-year instead of MULTIPLYING — $50/hr became 0 and $8k/mo became $666. Now `(cents/100) × periods_per_year`, with a parametrized test covering year/hour/month/week/zero/missing. (4) **New detailed capability document `docs/CAPABILITIES.md`** (~310 lines): every capability, all 21 sources, the 10-stage pipeline, matching/scoring layers, CRM, daily run, analytics, CLI, API surface, security model and honest limits (Indeed IP-blocked; AI paths unverified pending key). Headline numbers re-verified against the live app and corrected (206 API operations, 45 application tables + 10 sqlite-vec shadow, 906 backend tests). (5) **Tests: 137 scraper tests (+20 for Ashby/Landing.jobs/4dayweek incl. a registry guard asserting every new source is in ALL_SCRAPERS so the WeWorkRemotely orphan bug cannot recur), 906 backend (+20), 180 frontend green.** Server restarted live (pid 17360) with all 21 sources registered; /api/system/health 200. |
| 2026-09-28 | Session 28: **Discovery expansion: sponsor-heavy countries (Canada/Australia/Poland/India) + 11 new adapters — E2E GREEN 20/20, 49 real jobs ingested live.** Basil asked for: all countries that actually sponsor visas + all possible discovery sources implemented + tested + the API-key list. (1) **Countries 6→10:** india.yaml (earlier step), then canada.yaml (LMIA/Global Talent Stream keywords), australia.yaml (482/186 employer-sponsored), poland.yaml (relocation-package/EU) — all zero-code YAML drops per Golden Rule 8; classifier static map already covered their cities, YAMLs add the long-tail cities as registry terms. (2) **Adapters 4→15:** NEW keyed **JoobleAdapter** (POST api.jooble.org/api/{key} — ONE key unlocks localized discovery in ALL 10 countries; honest no-op without key) + **AdzunaAdapter** (per-country API markets de/nl/ie/gb/in/ca/au/pl/ae/sg via Country.code) + **9 country-scoped ports of existing keyless scrapers** through a new shared `app/adapters/country_facade.py#CountryScopedAdapter` (arbeitnow, remotive, jobicy, weworkremotely, remoteok, himalayas, 4dayweek, landingjobs, recruitee) — the legacy scrapers had NO country scoping; the facade filters listings to the target Country and never raises. (3) **base.py:** `rate_limited_get` gained optional `method="POST"` (backward-compatible; Jooble needs POST) + jooble in DOMAIN_LIMITS. (4) **E2E (`analysis/e2e_discovery_expansion.py`, report docs/E2E_DISCOVERY_EXPANSION_REPORT.md):** real orchestrator + real 15 adapters + real HTTP + temp DB, one focused-registry cycle per country — Canada 22, India 19, Poland 6, Australia 2 real jobs ingested; all 9 keyless health probes OK live; keyed adapters honest no-ops; region gate holds on every ingested row (audit check scoped by max-job-id snapshot after a first-run false-FAIL taught me the audit was counting earlier countries' rows). (5) **Bugs found+fixed:** jooble/adzuna pagination overlap double-counted on repeated mocks → URL-dedup in both adapters; facade-level URL dedup added (recruitee/arbeitnow scrapers paginate without deduping); E2E audit check scoped per-cycle. (6) **Keys plumbing:** scraper_keys override param on run_discovery_cycle; `JOBAGENT_JOOBLE_API_KEY`/`JOBAGENT_ADZUNA_APP_KEY`/`JOBAGENT_ADZUNA_APP_ID` env fallbacks in the discovery router (DB keys win); Jooble field in Settings → Scraper API Keys UI; .env.example updated. **Basil's action: get a free Jooble key (jooble.org/api) + optional Adzuna keys (developer.adzuna.com).** Tests: +14 (tests/test_discovery_expansion.py, respx) → 874 non-scraper + 137 scraper + 184 frontend green. | 
| 2026-09-24 | Session 27: **REAL user-journey E2E — the running product driven top-to-bottom over HTTP; 5 real bugs found + fixed. 26/26 scenarios, 204/204 checks, 285 live HTTP calls, 85.8% API coverage.** Basil asked for proof through the REAL server (not in-process tests) as a brand-new user: create username/password → upload resume → AI analysis → scrapers → scoring → tailoring → cover letter, ≥15 scenarios, all outputs saved. Built `analysis/e2e_user_journey.py`: boots `uvicorn app.main:create_app --factory` with **auth ON and `testing=False`** against a throwaway data dir, creates an admin then a second user, and drives 26 scenarios over real HTTP (basil's REAL 4109-char resume rebuilt as a genuine .docx; **live DeepSeek `deepseek-flash`** read from the workspace DB). Every call recorded to `analysis/e2e_runs/<date>_<time>/` (api_calls.jsonl, scenarios.json, api_coverage.json, artifacts/, server.log, report.md) + `docs/USER_JOURNEY_E2E_REPORT.md`; status board `docs/E2E_RUN_STATUS.md`. **Bugs found only because it ran the real server: (1) resume upload graded with the APP-LEVEL AI client and overwrote the app-level matcher with the caller's resume — cross-user contamination (`routers/settings.py` now resolves via `ai_state_for`); (2) legacy scrape/AI-score/rescore always ran against `app.state.bg_db`=admin DB, so another user's "Scrape now" filled the ADMIN's pool and graded with the ADMIN's resume (new `_task_target()` binds scrape/score to the requesting user's workspace DB + their matcher; `_score_unscored(db, matcher=None)`); (3) the LLM cost meter had ONE global sink → every non-admin user's `/api/analytics/monitoring` read 0 calls/$0 (`ai_usage` gained a ContextVar request sink bound per request by workspace_middleware); (4) `POST /api/custom-qa`, `/api/work-history`, `/api/certifications` returned **500** on an unknown field name — an unhandled ValueError from the DB column guard (new `_save_profile_entry()` returns **400** for all 7 profile saves; 15 regression tests in `tests/test_profile_save_validation.py`); (5) discovery had no bounded mode (added `POST /api/discovery/run?passes=1..24` + `max_passes`). Also corrected two wrong expectations of MINE, not the product: `applied→offered` is allowed BY DESIGN (the real invariants are "cannot reach offered without applying" and "no terminal resurrection"), and `POST /api/scrape` returns 202/409. Harness covers Critical Test #4 (dedup outreach) and **Critical Test #5 (cross-user isolation, s24)** on the live server. Ops lesson: background jobs launched from a SYNC tool call are reaped when that call returns — use `setsid nohup … </dev/null &`. Full suite: **982 passed**; the only error was a pytest-timeout trip under serial load on `test_workspaces.py::test_jobs_are_isolated`, which passes alone (18s). |
| 2026-09-27 | Session 29: **Resume-first onboarding gate + N1 per-user Gmail tokens — both E2E-verified.** (Not logged at the time; reconstructed from the reports during Session 31's memory audit.) (1) **Onboarding gate** — new `app/search_gate.py` `require_resume_for_search()`: scrape + discovery return **428** with "Upload a resume first…" until the user has one; onboarding reordered Resume (required) → AI → Keywords (confirm/edit) → Done; new `POST /api/search-config/keywords` + `db.update_search_keywords()`/`has_usable_resume()`; live E2E **26/26** (`analysis/verify_resume_onboarding_live.py`, docs/RESUME_ONBOARDING_E2E_REPORT.md; throwaway user created + deleted, DeepSeek live). (2) **N1 per-user Gmail token** (NEXT_5_PLAN N1): token lives in the user's workspace `email_settings`; `routers/outreach.py#_gmail_credential()` resolves workspace-first with `JOBAGENT_GMAIL_TOKEN` env as legacy fallback; `/api/settings/email` GET masks the token, POST round-trips the mask without blanking the credential, `clear_gmail_token` is the only eraser; `/api/outreach/config` reports `gmail_connected` + `gmail_source` (workspace|env|"") and never the raw token. Real-scenario tests: `tests/test_multiuser_real_scenario.py` **4/4** (two logged-in users over live HTTP, distinct tokens, env-fallback, clear-isolation, no-token local-draft path). (3) **Full-suite proof:** 999 backend + 184 frontend + 469 extension green (docs/FULL_SUITE_TEST_REPORT.md); real bug found: date-rot time bomb in `test_eligibility.py` hardcoded 2026-09 dates → now `date.today()`-relative. Work left UNCOMMITTED in the tree (picked up by Session 31). |
| 2026-09-28 | Session 32: **DISCOVERY PHASE verified LIVE as Basil — 22/22 GREEN + 3 real bugs found & fixed (source-row stacking, re-see telemetry dishonesty, dead Ashby board).** Harness `analysis/verify_discovery_basil.py` drives the real server on :8085 as user `1-basil` (session via `SystemStore.create_session` — the login primitive; password untouched, session deleted after, Z1 check proves cleanup). Proved: auth 401/200, 19 adapters registered, 16 keyless sources LIVE (B3), keyed honest no-keys, resume gate lifted, 10 countries + apply(), full 50-pass cycle over Basil's real resume terms, ingest gates (attribution/region/freshness/dedup), eligible pool 100, direct-DB audit. **Bugs found by running the product (Rule #11):** (1) `insert_source` stacked rows — Basil's pool had 3 identical wellfound rows on job 1906, 1,505 exact-duplicate sources rows total (legacy scheduler re-see path was the main accumulator) → DB-layer idempotent INSERT…WHERE NOT EXISTS; (2) discovery re-see counted already-pooled jobs as `new_jobs` (run-2 said new=2) → high-water-mark `pre_cycle_max_id` + was_new gate; re-sweep now honestly reports new=0 dupes=32 (proven live, fixed vs unfixed in same session); (3) ashby DEFAULT_COMPANIES contained dead board `walkaway` (permanent 404 → every ashby pass SOURCE_FAILURE) → removed, health now clean. Tests: +3 regression (insert_source idempotency, re-see honesty, cross-source re-see stays merged incl. normalized-company lesson 'DupCo Inc'→'dupco') → 47/47 ingest-related suite green; server restarted on the fixed code; 1,505 legacy dupe rows cleaned (dedupe on (job_id, source_name, source_url), MIN(id) kept). Report: docs/DISCOVERY_PHASE_LIVE_VERIFICATION.md (flow diagram §1, health §3, telemetry §5, coverage matrix §6, DB audit §7, checks §8). | 
| 2026-09-28 | Session 31: **Memory audit + N1 closed out.** Reconstructed state from PROJECT_MEMORY + docs — NEXT_5_PLAN still said N1 "not started" while the working tree already contained the code, the 4 real-scenario tests and both reports. Re-ran the touched suites to re-verify the uncommitted tree: test_multiuser_real_scenario 4/4 + test_workspaces 12/12 (32s), outreach/evidence/eligibility/digest 58/58, api/profile-save/resume-grading 65/65 — all green. Docs synced: NEXT_5_PLAN backlog table + N1 section + progress board (N1 = DONE 2026-09-27), E2E_RUN_STATUS last-updated header + M15c gap table, CURRENT STATE + M15c tracker + this log. Committed the 2026-09-27 working tree (onboarding gate + N1 + docs) on `dev_users_based`. **Next: N2 per-user scheduled cycles.** |
| 2026-10-01 | Session 33: **STAGE-2 CLASSIFY audit/harden/test/document — COMPLETE (branch `user_change_before_new_feature`).** New `app/classification.py`: deterministic priority chain (STRUCTURED_COUNTRY→TEXT_LOCATION→CITY_MAP→DESCRIPTION→ATS_METADATA→SOURCE_HINT(LOW)→AI_FALLBACK→UNKNOWN), `Classification` dataclass, `COUNTRY_ALIASES` (all 10), `CITY_TO_COUNTRY`, region buckets, `normalize_country_code`, `detect_conflict`. **Source country is HINT ONLY** — text/structured always wins (live-proven on the real pool). Bounded/validated AI fallback runs ONLY on deterministic residue, rejects unconfigured/low-confidence answers, swallows errors. New jobs columns (country_code/classification_confidence/classification_source/classification_reason/supported_countries) + `search_config.classification_metrics`; **bugs fixed:** `set_classification_metrics` UPSERT (bare UPDATE no-op'd on fresh DB; first fix missed NOT NULL `updated_at`) and a dead `source` column reference in `get_unclassified_jobs`; bare `Remote` now falls through to description evidence. `run_location_classification` rewritten (residue-only AI, conflict counting, unknown-preserving dismissal, cleaned duplicated block). **Tests: 70 in tests/test_classification.py (incl. +6 AI-fallback) + 218 related-suite regression green.** Live validation (`analysis/verify_classification_live.py`) over the real discovery sample pool: 16/16 curated priority-chain battery + 104/104 live rows classified (77 same-country, 27 cross-country — all legitimate text-wins, 0 fabricated, 0 unknown). Docs: docs/classify/{CLASSIFY_OVERVIEW,CLASSIFY_AUDIT,CLASSIFICATION_RULES,TEST_RESULTS,LIVE_SAMPLE_RESULTS,KNOWN_LIMITATIONS}.md + results/classification_summary.json. **Next: N2 per-user scheduled cycles.** |
| 2026-10-01 | Session 34: **STAGE-3 ELIGIBILITY audit/harden/test/live-validate — COMPLETE (branch `user_change_before_new_feature`, NOT committed).** Rewrote `app/eligibility.py` into an explicit ordered gate chain (DATA_SANITY→DISMISSED→ALREADY_APPLIED→JOB_STATUS→FRESHNESS→LOCATION→EVIDENCE→FINAL_ELIGIBILITY) returning status/gate/reason/evidence, consuming Stage-2 (country_code/confidence/source/supported_countries) without re-classifying, handling remote region buckets (review when targeted), worldwide remote, multi-location and unknown-country→review. **Closed the SCORE leak:** `db.get_scoreable_jobs()` requires `eligibility_status='ELIGIBLE'`; `app/main.py#_score_unscored` and `app/matching_service.score_all_unscored` now run `run_eligibility_pass` then read only scoreable jobs (Critical #5/#6). New: scheduler `run_eligibility_pass`; jobs columns eligibility_status/gate/reason/evidence/evaluated_at + job_status/closing_date; search_config.eligibility_metrics; endpoints /eligibility/review-jobs + /eligibility/metrics; jobs evaluated in the scheduled scoring path after classification. **Tests:** 29 in tests/test_eligibility.py (+15: already-applied, closed, review, remote buckets, multi-location, data-sanity, idempotency, SCORE contract, multi-user isolation) → all green; 307 related regression green (207 + 100). **Live:** analysis/verify_eligibility_live.py on a COPY of Basil's real DB — 1962 evaluated → 67 ELIGIBLE / 1895 INELIGIBLE / 0 REVIEW (unknown-region rows are all stale, so FRESHNESS precedes LOCATION — honest); gates DISMISSED 1357 / FRESHNESS 515 / LOCATION 20 / EVIDENCE 1 / ALREADY_APPLIED 2. Bug found+fixed: batch UPDATE parameter order in run_eligibility_pass caused an infinite loop (caught by the idempotency test). Docs: docs/eligibility/{ELIGIBILITY_OVERVIEW,ELIGIBILITY_AUDIT,GATE_RULES,TEST_RESULTS,LIVE_SAMPLE_RESULTS,KNOWN_LIMITATIONS}.md + results/eligibility_summary.json. Not committed (per task §39). |
| 2026-10-01 | Session 35: **Stage-3 ELIGIBILITY quality audit — READY_FOR_SCORE (2 defects found + fixed, re-audited).** Script `analysis/eligibility_quality_audit.py` over a COPY of Basil's DB. **Exact counts (1,962 evaluated):** ELIGIBLE 67 (3.4%) · INELIGIBLE 1,895 → 1,818 · REVIEW 0 → 77 · UNKNOWN 0; gates DISMISSED 1,357 (69.2%) / FRESHNESS 515 / FINAL 67 / LOCATION 20 / ALREADY_APPLIED 2 / EVIDENCE 1; reasons strategy-dismissed 941, stale 436, dismissed 416, date-unknown 79, OK 67, salary 20, applied 2, desc 1. **Why 67:** 69% were already dismissed pre-stage (mostly region=US) → the real rate is 67/605 live = 11.1%, and 67/93 = 72% among live+fresh. **75 individual rows manually reviewed** → **0 decision-level false rejections** (all dismissals pre-existing, all stale dates genuinely >7d, unknown dates genuinely undated). **2 defects fixed:** (A) salary-floor rejections were labelled `WORK_TYPE_NOT_ALLOWED` (factually wrong) → new `SALARY_BELOW_FLOOR`; (B) `DATE_UNKNOWN` was reported as INELIGIBLE (uncertainty shown as proof) → now `REVIEW_REQUIRED`, still never VERIFIED_FRESH/eligible/scored. +4 regression tests → tests/test_eligibility.py 33 green; 216 + 105 regression green. Contract re-verified: 0 ineligible/review leaked into get_scoreable_jobs, 0 DATE_UNKNOWN fresh. **Key finding (not fixed):** `country_code` is NULL on ALL 1,962 legacy rows (Stage-2 only reclassifies `location_classified=0`), so LOCATION-gate country/confidence logic never engaged live — coverage gap, recommend a Stage-2 reclassification pass. Recommendations recorded in QUALITY_AUDIT.md §9 (salary-floor as hard gate, 7d-vs-30d freshness tension, review-queue UI). Docs: docs/eligibility/QUALITY_AUDIT.md + updated GATE_RULES/KNOWN_LIMITATIONS/AUDIT/TEST_RESULTS/LIVE_SAMPLE_RESULTS. Not committed. |
