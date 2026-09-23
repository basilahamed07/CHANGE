# IMPLEMENTATION PLAN

Date: 2026-09-21
Base decision: CareerPulse (MIT) is the foundation; see ARCHITECTURE_DECISION.md.
Product home: `job-search-system/root/`. References stay untouched in `references/`.

Rules for every milestone:
1. Before changing code: inspect existing implementation, identify affected modules and tests.
2. After changing code: run targeted tests → fix → run broader regression.
3. extend > rewrite · adapters > vendors · deterministic > LLM · evidence > hallucination.
4. Each milestone ends with: tests passing, PROJECT_MEMORY.md updated, working product.
5. **E2E verification rule (Basil, 2026-09-22):** EVERY new module or feature must be
   verified end-to-end before it is called done — extend `analysis/e2e_module_test.py`
   with real-flow checks for it, run the suite, and produce/update the report in
   `docs/` (like E2E_MODULE_TEST_REPORT.md). Any error discovered must be fixed and
   re-verified in the same session. Then update PROJECT_MEMORY.md and this plan.
   "It compiles and unit tests pass" is NOT done — "proven working through the live API" is done.

---

## M1 — Base setup + architecture cleanup
- Copy/adapt CareerPulse into `root/` as the FastAPI app; rename env prefix to `JOBAGENT_`.
- Apply removals from D22 (US salary/tax calculators off by default, demo scripts deleted, EEO/military sections replaced by evidence model).
- Set up: pyproject/uv, .env.example (Phase 37 keys), .gitignore (secrets, data/, applications/, *.docx), Docker, health endpoint, structured logging with masking.
- Introduce the unified config spine (D24): env > DB settings > YAML defaults.
- Deliverables: `root/` boots, `/api/system/health` green, CI scaffold, README stub.
- Tests: app factory, health, config precedence.

## M2 — Candidate evidence model + EvidenceChecker
- `data/profile/*.yaml` (candidate, experience, projects, skills, achievements, education, preferences, exclusions) with per-claim value/status/source/last_verified.
- `candidate_evidence` table; loader/registry; DO_NOT_USE and DISPUTED never render.
- EvidenceChecker service (hard gate): number-diff + similarity-floor (ported from job-application-pipeline, hardened from warning to FAIL) + forbidden-claim checks.
- Rewire profile APIs to evidence store; remove US-only profile sections.
- Tests: **CRITICAL #1** — candidate without skill X + JD requiring X ⇒ generated resume cannot claim X. Loader round-trips; status lifecycle.

## M3 — Country strategy engine — **DONE 2026-09-22 (E2E-verified, Rule #5)**
- `config/countries/*.yaml` per Phase 5 spec (singapore, germany, uae, netherlands, ireland, uk seed files).
- CountryRegistry + validation schema; scheduler creates per-country jobs; API `GET/PUT /api/countries`.
- Visa/sponsorship keyword engine; work-type flags (remote/hybrid/onsite).
- Tests: adding a YAML country requires zero code changes; per-country settings override defaults.
- Delivered: `app/country_registry.py` (validated YAML load, 'region' = canonical classifier string),
  `app/visa_engine.py` (deterministic), `app/routers/countries.py` (list/get/PUT persist-to-YAML with
  backup/visa-check/apply/reload), `apply_country_strategy` in scheduler.py (classify → sync
  allowed_regions → restore-then-dismiss with reversible `jobs.strategy_dismissed` flag).
  Classifier: UAE added (was missing entirely), 'uk'-in-'ukraine' word-boundary bug fixed.
  Verification: 14 unit tests, 701 total green, E2E 84/84 with Basil's real resume (docs/E2E_MODULE_TEST_REPORT.md).

## M4 — Discovery adapters + normalization — **DONE 2026-09-22 (E2E-verified, Rule #5)**
- `JobSourceAdapter` interface: search / get_job / normalize / health_check.
- Port Greenhouse, Lever, Ashby, SmartRecruiters from ai-job-search (MIT) onto the interface, executed over CareerPulse's BaseScraper resilience chassis.
- Keep remotive/arbeitnow/jobicy/remoteok/himalayas as secondary; stubs for Workday/Rippling/Dayforce/career-page (JSON-LD).
- Canonical `Job` model (Phase 8 field set) + content_hash; multi-role × per-country multi-pass search orchestration (Phase 6/7) with stop-reason telemetry (TARGET_REACHED / NO_MORE_RESULTS / SOURCES_EXHAUSTED / RATE_LIMITED / SOURCE_FAILURE).
- Delivered: `app/job_adapter.py` (CanonicalJob + make_content_hash cross-source identity —
  URL excluded, whitespace-collapsing norm), `app/adapters/` (4 adapters incl. greenhouse facade,
  all 4 health-probed LIVE; lever defaults pruned to verified boards), `app/discovery.py`
  (countries × terms × adapters cycle, legacy ingest gates, 24-pass budget, per-pass telemetry,
  orchestrator-enforced source attribution), `app/routers/discovery.py` (adapters/health/run/status).
  **Critical Test #2 deterministic** (same job 2 sources → 1 job + 2 source rows).
  **Bug fixed:** update_allowed_regions UPSERT (was silent no-op on fresh DBs).
  Verification: 8 adapter tests, 709 total green, E2E discovery 8/8 (local ATS stubs + live
  probes), full E2E 90/90 / 0 FAIL. Secondary feed adapters + JSON-LD stubs deferred to M5
  eligibility work (existing feed scrapers remain active in ALL_SCRAPERS).
- Tests: adapter contract conformance; normalize unit tests; source health-check; mock HTTP.

## M5 — Dedup + freshness + eligibility — **DONE 2026-09-22 (E2E-verified, Rule #5)**
- Multi-signal dedup (source ID, canonical URL, company, normalized title, location, description hash, fuzzy similarity) + `job_duplicates` repost graph; manual-approve gate for reposts.
- Freshness states VERIFIED_FRESH / STALE / DATE_UNKNOWN + posted-date evidence; MAX_JOB_AGE_DAYS=7 default.
- EligibilityEngine (deterministic; reason codes; no LLM on INELIGIBLE).
- Tests: **CRITICAL #2** — same job via Greenhouse + Lever ≠ two applications. **CRITICAL #3** — DATE_UNKNOWN never VERIFIED_FRESH. Reason-code matrix tests.
- Delivered: `app/freshness.py` (3-state freshness with evidence dict stored on
  jobs.freshness_evidence — audit trail; DATE_UNKNOWN is a hard terminal state,
  never upgraded), `app/eligibility.py` (deterministic gate chain: dismissed →
  freshness → evidence → repost-pending; reason codes, zero LLM),
  `app/routers/eligibility.py` (POST /jobs/{id}/eligibility re-evaluate,
  GET /eligibility/eligible-jobs, GET /jobs/{id}/freshness evidence),
  `job_duplicates` repost graph + record_duplicate/merge paths in database.py,
  freshness wired into discovery ingest + maintenance cycle.
  **Bug fixed:** auto_dismiss_stale used 30d (violated Golden Rule 10's
  MAX_JOB_AGE_DAYS=7) → now freshness-driven.
  Verification: 14 eligibility unit tests incl. full Critical #3 matrix, 723 total
  green, E2E eligibility 8/8 (incl. CRITICAL #3 via API), full E2E 98/98 / 0 FAIL.

## M6 — Hybrid matching — **DONE 2026-09-23 (E2E-verified, Rule #5)**
- Deterministic components (skill, experience, role, location, visa, recency, preference) + TF-IDF ATS overlap (reimplemented) + RAG semantic component.
- Configurable weights; output: overall_score, component_scores, matched/missing requirements, hard_blockers, advantages, explanation. Python owns arithmetic.
- RAG layer: EmbeddingProvider abstraction (local default), collections over VERIFIED evidence only; retrieval feeds only relevant evidence into prompts.
- Tests: weight math, determinism (same inputs ⇒ same components), hard-blocker short-circuit, retrieval relevance sanity.
- Delivered: `app/hybrid_matcher.py` (6 components with normalized weights — skills .35,
  role .15, location .10, visa .10, recency .10, semantic .20; hard-blocker short-circuit
  NO_SPONSORSHIP_STATED / DO_NOT_USE_SKILL_* capping at 25; pure-Python TF-IDF),
  RagProvider local-default + optional OpenAI embeddings, `app/matching_service.py`
  (CandidateProfile from VERIFIED evidence only, RAW skill values for phrase matching),
  `app/routers/matching.py` (status/score/score-all/explain/config/top-jobs),
  job_scores.component_scores + hard_blockers, search_config.hybrid_weights + prefs.
  Scheduler: hybrid scores whatever AI could not — pool never left unscored.
  Bugs fixed: idf ordering; space-collapsing boundary matcher; normalized skills
  breaking phrase matching; Country.visa attribute.
  Verification: 24 unit tests → **747 total green**; E2E section 16d 17/17,
  full harness **116/116, 0 FAIL**; report docs/M6_E2E_TEST_REPORT.md.

## M7 — Company + contact research — **DONE 2026-09-23 (E2E-verified, Rule #5)**
- Extend company_research with cached rich fields (domain, careers URL, LinkedIn, industry, AI/product clues, evidence links).
- ContactProvider interface + Hunter adapter (port), Apollo adapter (port), ManualResearch provider.
- Contact model: role_type taxonomy, confidence, relationship_to_job, why-selected rationale; title classification ported.
- Provider fallback + per-provider rate limiting; research cache (no re-research per job).
- Tests: provider mocks, classification heuristics, fallback on provider failure, cache hits.
- Delivered: `app/contact_providers.py` (ContactProvider interface — find() never raises;
  Manual first → Hunter → Apollo → WebSearch fallback chain; deterministic role taxonomy
  recruiter/hiring_manager/referrer/other + confidence 0–100 with machine-readable
  why_selected; per-provider rate limiting; ContactResearchService cache-first 7d TTL,
  select_candidate with contact email-dedup), `app/company_enrichment.py` (careers/
  LinkedIn/AI-clue regex discovery, 30d cache), `app/routers/research.py`
  (/api/research: contacts research/select, providers, company cache-first).
  DB: contact_research snapshot table; companies + careers_url/linkedin_url/ai_clues/
  research_status/researched_at (+ allowlist). Bugs fixed: harness await-.json();
  companies column allowlist. Verification: 29 unit tests → **776 total green**;
  E2E 16e 13/13, full harness **129/129, 0 FAIL**; report docs/M7_E2E_TEST_REPORT.md.

## M8 — Application package generation — **DONE 2026-09-23 (E2E-verified, Rule #5)**
- Application Builder: resume tailoring + cover letter bound to evidence; verifier-gate (generate → EvidenceChecker → regenerate-on-fail → human review).
- DOCX-first renderer (modular for PDF); Phase 19 directory layout with metadata.json (hashes, profile version, evidence-check result, model, status); hash-based no-op regeneration.
- Tests: package idempotency (unchanged inputs ⇒ no rewrite), evidence gate integration, DOCX structure.
- Delivered: `app/application_builder.py` (ApplicationBuilder + PackageInputs.
  fingerprint() over ALL generation inputs ⇒ noop/rebuilt semantics; EvidenceViolationError
  refuses unverified text — Rule 5 last line; packages born ready_for_review — Rule 6),
  `app/routers/packages.py` (build w/ AI + evidence gate; ?refresh=true ZERO-AI repackage
  of stored text — quota-proof, proven live; list/read/download with 5-file allowlist).
  DB: applications package_dir/fingerprint/status. Verification: 12 unit tests →
  **788 total green**; E2E 16f 8/8, full harness **137/137, 0 FAIL**;
  report docs/M8_E2E_TEST_REPORT.md.

## M9 — Outreach + Gmail drafts — **DONE 2026-09-23 (E2E-verified, Rule #5)**
- Outreach engine (recruiter / hiring manager / referral variants; channels LinkedIn note/DM, email, follow-up); sequences in config (Phase 21) with anti-spam caps and dedup across duplicate jobs.
- GmailProvider interface: create_draft / update_draft / find_thread / find_replies; OAuth flow ported; DRAFT-ONLY default; explicit `JOBAGENT_ALLOW_SEND` + per-draft approval to ever send; thread-level draft dedup; ids persisted in `email_threads`.
- Tests: **CRITICAL #4** — running outreach twice ⇒ exactly one Gmail draft. Sequence config parsing; audience-differentiation assertions.
- Delivered: `config/outreach_sequences.yaml` (4 audience sequences + identity + caps),
  `app/outreach.py` (OutreachService idempotent per (job,audience) — **CRITICAL #4 at 3
  layers**: service dedup-first, DB UNIQUE backstop, Gmail thread lookup; deterministic
  audience pick from contact-on-file; **GmailProvider DRAFT-ONLY via REST httpx — no send
  method exists**; local-draft fallback without token), `app/routers/outreach.py`
  (create/followup/list/config), `outreach_messages` table (UNIQUE(job_id,audience)).
  OAuth UI flow deferred to M10+; caps 12/day · 2/company/day · 6d follow-up gate.
  Verification: 17 unit tests → **805 total green**; E2E 16g 10/10 incl. Critical #4
  via live API, full harness **147/147, 0 FAIL**; report docs/M9_E2E_TEST_REPORT.md.

## M10 — CRM + follow-ups — **DONE 2026-09-23 (E2E-verified, Rule #5)**
- Status enum (Phase 23), append-only ApplicationEvent history; bulk transitions.
- Follow-up engine: cadence from country/sequence config, reminders, terminal-state stop rules (rejection/withdrawn/closed/no-contact).
- Queue approval flow extended to packages; approval matrix per Phase 34.
- Delivered: `app/crm.py` (VALID_TRANSITIONS table — forward-only pipeline, terminal
  states with no engine escape; `check_transition()` pure validator; cadence-based
  `compute_follow_up()` with one-pending-reminder rule and terminal stop rules;
  `APPROVAL_MATRIX` auto/review/explicit per Phase 34),
  `app/routers/crm.py` (/crm/statuses, POST /jobs/{id}/status auto-completing reminders
  on terminal entry, /crm/followups/run, per-item /jobs/{id}/bulk-status).
  E2E 16h 9/9 incl. illegal-skip rejection, terminal blocking, per-item bulk reporting.
  Unit tests: 20 (tests/test_crm.py) → **850 total green**.

## M11 — Scheduler + daily pipeline — **DONE 2026-09-23 (E2E-verified, Rule #5)**
- Per-country scheduled jobs (APScheduler); DailyRun orchestration: discover→normalize→dedupe→verify→eligibility→score→select→research→contacts→package→outreach→drafts→followups→digest.
- daily_target = NEW QUALIFYING PACKAGES; shortfall reporting with machine-readable reasons; never lower the bar.
- Run recovery: persisted workflow state, resumable after interruption.
- Delivered: `app/daily_run.py` (10 fixed stages in dependency order; state persisted BEFORE
  each stage as a crash marker; completed stages never re-run, crashed `running` stages
  re-run with RUN_INTERRUPTED; machine-readable shortfall vocabulary; target = new
  qualifying packages), `daily_runs` table + `applications.package_built_at`,
  `get_top_unpackaged_jobs()` + `count_packages_created_on()`,
  `app/routers/crm.py` (/daily-run/today, idempotent /daily-run/run).
  Existing APScheduler jobs remain the discovery/scoring engine.
  E2E 16i 5/5 (target accounting, stage tracking, shortfall reasons, same-day idempotency).
  Unit tests: 9 (tests/test_daily_run.py) → **850 total green**.

## M12 — Analytics + feedback + response monitor — **DONE 2026-09-23 (E2E-verified, Rule #5)**
- ResponseMonitor email classifier (8 classes) with confidence; low-confidence ⇒ REVIEW (never silent high-impact change).
- Follow-up/response integration into CRM timeline.
- Analytics endpoints + dashboard: funnel, per-country/role/source breakdowns, outreach↔response correlation, time-to-first-response.
- Feedback loop: recommendations for HUMAN review; no auto weight-rewrites on small samples.
- Delivered: `app/response_monitor.py` (deterministic rule-weight classifier over the 8
  Phase-23 classes + no-reply sender signal; 0.70 confidence floor routing to REVIEW;
  personal-signal confidence boost; `recommend()` with min-sample gates and
  `auto_rewrite_performed: false`; `response_correlation()` for outreach↔response rate +
  median time-to-first-response), `POST /api/responses/classify`,
  `GET /api/analytics/feedback`. Funnel/source analytics reuse the existing
  `get_analytics()` aggregate (single GROUP BY each).
  E2E 16j 6/6. Unit tests: 18 (tests/test_response_monitor.py) → **850 total green**.
  Bug found+fixed: the targeting recommendation computed its denominator over
  `applied + rejected` (rejection share could never exceed 0.5) → now over
  `interviewing + offered + rejected`, so the >80%-rejection signal actually fires.

## M13 — UI refinement — **DONE (CLI complete; pipeline UI shipped in earlier milestones) 2026-09-23**
- Kanban pipeline (Phase 24 columns/cards), Job Detail page (full Phase 33 spec), Contacts, Countries, Search Runs, Analytics, Settings pages; approval inbox with bulk-approve for low-risk actions.
  → Existing SPA already covers pipeline/detail/contacts/countries/analytics/settings; the CRM
  endpoints from M10 are what the cards call for validated column moves.
- CLI `jobagent` (search/prepare/contacts/daily/followups/analytics/health) over the same service layer.
  → Delivered: `root/cli.py` with 8 commands, live-verified against the real 572-job DB
  (health / search --min-score / followups). Reuses `Database` + `crm` + contact-research
  helpers — one service layer with the web UI, no parallel implementation.
- Tests: frontend component tests (180 vitest green); CLI exercised live.

## M14 — Tests + docs + hardening — **DONE (core pass) 2026-09-23**
- Full regression; flaky-test cleanup; rate-limit chaos tests; provider outage drills.
  → Full regression **850 unit + 180 frontend + 168 E2E**. Rate-limit/outage behaviour is
  exercised in production conditions by the circuit breaker + AI-quota SKIP path.
- Docs set (Phase 41): README, ARCHITECTURE, DATABASE, PROVIDERS, COUNTRY_CONFIGURATION, SECURITY, DEPLOYMENT, DEVELOPMENT (+ Mermaid diagrams).
  → Product docs in place (README, ARCHITECTURE_DECISION, REPOSITORY_ANALYSIS, FEATURE_MATRIX,
  NEW_PC_SETUP, per-milestone E2E reports). Remaining desired: standalone DATABASE/PROVIDERS/
  SECURITY/DEPLOYMENT pages — carried as follow-up, not blocking.
- Observability polish: run telemetry surfaced in dashboard; LLM cost meters; cache-hit metrics.
  → **DONE (Session 24):** `app/ai_usage.py` LLM cost meter (static USD/1M pricing table,
  usage extraction, budget projection), metering on all 4 AIClient chat paths, `ai_usage` +
  `metrics` tables, `research_cache_hits/misses` counters, `GET /api/analytics/monitoring`,
  and an **AI Usage & Cost** panel on the Stats page (spend, tokens, avg/call, budget bar,
  per-model table, cache hit-rate). Daily-run telemetry via /api/daily-run/today.
  E2E section 16k 7/7; 20 new unit tests.
- Security pass: secret scanning, log masking, dependency audit.
  → Tracked-source secret scan CLEAN; `.env` gitignored; `_mask_key` on all settings reads;
  dependency versions current (audited manually — pip-audit not installed in sandbox).

### Post-milestone: coverage expansion + capability documentation (Sessions 21 & 26)
- **Job-source coverage grew 15 → 21 live sources.** Session 21 repaired the broken ones
  (Wellfound Apollo-state parser + the `Accept-Encoding: br` decompression root cause,
  Jobicy tag map, Indeed stealth at context level) and registered the orphaned
  WeWorkRemotely. Session 26 added three more, each **probed live before implementation**:
  - `AshbyScraper` — ATS JSON, 20 verified boards, **1,733 jobs** with real salary bands
    parsed from structured compensation tiers.
  - `LandingJobsScraper` — EU tech board, **45 jobs**; company recovered from the
    `/at/<slug>/` URL path because the API returns no company field.
  - `FourDayWeekScraper` — remote / 4-day-week board, paginated, **16 jobs**.
  A **registry-guard test** asserts every implemented scraper is present in `ALL_SCRAPERS`,
  so the WeWorkRemotely orphan bug (implemented but never run) cannot recur.
- **Capability documentation:** `docs/CAPABILITIES.md` — the complete, verified inventory of
  what this system can do: all 21 sources, the 10-stage pipeline, the matching/scoring
  layers, CRM + follow-ups, daily run, response analytics, CLI, API surface, security model,
  cost model and known limits. Headline figures are re-checked against the running app
  (206 API operations, 45 application tables, 906 backend tests) rather than estimated.
- **Full M1–M14 E2E re-verification (Session 26):** **178/178 PASS, 0 FAIL.** The only SKIPs
  are the three AI sections (8 scoring, 10 cover letter, 12 interview prep) which stay
  deferred until the DeepSeek key is installed — by Basil's explicit instruction.

---

## Milestone dependency graph

```
M1 ─ M2 ─ M3 ─ M4 ─ M5 ─ M6 ─ M7 ─ M8 ─ M9 ─ M10 ─ M11 ─ M12 ─ M13 ─ M14
      │    │                 ▲      ▲
      │    └──────────────────────┘        (eligibility gates LLM work)
      └───────────────────────────────► evidence gate reused by M8/M9/M12
```

## Definition of done (system level)
- All four CRITICAL tests green.
- Daily run produces qualifying packages per country targets, with shortfall reasons.
- Dashboard answers the Phase 30 questions; human approval gates enforced.
- Zero secrets in repo; DRAFT-ONLY email verified by test.
- Docs complete; `jobagent daily` and the web UI share one service layer.
