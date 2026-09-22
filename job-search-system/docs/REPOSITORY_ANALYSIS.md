# REPOSITORY ANALYSIS

Analysis date: 2026-09-21
Candidate: Basil Ahamed H — AI/GenAI/LLM/RAG/Agentic engineering roles
Purpose: evaluate 5 reference repos before building ONE coherent system in `root/`.

Method: READMEs read fully; directory structures, database schemas, adapter
interfaces, guardrails, scoring code, and Gmail/contact implementations inspected
directly (grep + targeted file reads). No code modified.

---

## 1. tcpsyn/CareerPulse — PRIMARY ARCHITECTURAL BASE

| | |
|---|---|
| Purpose | Self-hosted job-search automation platform: scrape 14+ boards → AI score vs resume → tailored resume/cover letter → ATS autofill Chrome extension → application CRM → analytics |
| License | **MIT** (Luke MacNeil / MacNeil Media Group) ✅ |
| Activity | Alive — last commit Apr 2026, CI badge, 3 parallel test suites |
| Stack | Python 3.12, FastAPI (async), aiosqlite (SQLite, WAL), httpx, APScheduler, feedparser, BeautifulSoup4, PyMuPDF, python-docx; vanilla-JS SPA (no build step); Chrome MV3 extension |

**Architecture (verified in code):**
```
app/main.py               create_app factory + lifespan; dual DB conns (request + background)
app/database.py           39 tables, auto-migrating schema, FK enforcement, WAL
app/scrapers/             17 sources incl. greenhouse.py; base.py = JobListing dataclass +
                          BaseScraper (exponential backoff on 429/5xx, Retry-After respect,
                          per-domain rate limiting, randomized UA rotation)
app/ai_client.py          One AIClient, 5 providers: Anthropic | OpenAI | Gemini | OpenRouter | Ollama
app/matcher.py            JobMatcher: LLM scoring w/ batch + parse + fallback-individual paths
app/tailoring.py, cover_letter.py, docx_generator.py, pdf_generator.py
app/company_research.py, contact_finder.py, apply_link_finder.py, salary_estimator.py
app/follow_up.py, digest.py, embeddings.py, circuit_breaker.py, rate_limiter.py
app/scheduler.py          8 scheduled jobs (scrape, enrichment, scoring, maintenance,
                          reminders, digest, alerts, embeddings)
app/routers/              12 APIRouter modules; OpenAPI via /docs
tests/                    60 test files (~655 backend tests) + 140 frontend + 453 extension
```

**Database (verified):** `jobs, sources, job_scores, applications, app_events, search_config,
ai_settings, user_profile, work_history, education, certifications, skills, languages,
user_references, military_service, eeo_responses, custom_qa, autofill_history, scraper_keys,
companies, scraper_schedule, notifications, email_settings, saved_views, resumes, job_alerts,
application_queue, follow_up_templates, contacts, contact_interactions, job_contacts,
career_suggestions, offers, context_items, embedding_settings, reminders, interview_prep,
interview_rounds, ical_tokens`

**Best features:**
1. Production-grade scraper base class (retry/backoff/rate-limit/UA) — exactly the resilience model we need.
2. Complete application CRM: applications + app_events timeline, queue w/ approval workflow, contacts CRM, interview rounds, follow-up templates, reminders.
3. Provider-agnostic AI layer (5 providers incl. local Ollama) — cost-control friendly.
4. Freshness via `last_seen_at` (re-verified each scrape cycle) + 30-day auto-dismiss.
5. Human-in-the-loop queue: prepare-all → review → approve (never auto-submit).
6. Operational maturity: health endpoint, digest, CSV export, saved views, structured background jobs, circuit breaker.
7. Deduplication: SHA-256 of normalized title+company+URL; similar-listing flagging.
8. Strong test culture (1,248 tests).

**Weak features (for OUR requirements):**
1. Scoring is a single LLM call producing one score — no deterministic multi-component weighted score, no component breakdown.
2. No candidate **evidence** model with verification status (claims are profile rows, no VERIFIED/UNVERIFIED lifecycle).
3. No country-as-configuration concept; region filters are coarse (US/Europe/APAC...) — no visa/sponsorship engine.
4. No multi-pass self-correcting search; no search-stop-reason telemetry.
5. Greenhouse only among ATS APIs — no Lever/Ashby/SmartRecruiters; scrapers are aggregator-heavy.
6. No structured contact-confidence model (contact_finder is web-search based), no ContactProvider interface.
7. No Gmail integration (uses SMTP `emailer.py`); no outreach sequences.
8. No response-email classification; response tracking is manual entry.

**Reusable concepts:** scraper base, DB schema shape (jobs/applications/app_events/contacts/companies), queue-with-approval, scheduler job set, AI provider abstraction, digest, health/progress endpoints, DOCX generation, testing philosophy.
**Potentially reusable code (MIT):** `scrapers/base.py` (+ greenhouse/remotive/arbeitnow/jobicy adapters as porting references), `rate_limiter.py`, `circuit_breaker.py`, `database.py` patterns, `docx_generator.py`, scheduler/digest patterns. Port with renaming; do NOT vendor wholesale (schema prefixes/naming differ).

---

## 2. KartikeyaMohan/job_search_agent — MATCHING + FEEDBACK IDEATION

| | |
|---|---|
| Purpose | Multi-agent CLI pipeline: discover (LinkedIn/Wellfound/JSearch) → ATS score (pure Python) + RAG match → tailor resume → draft outreach; feedback loop |
| License | **NONE FOUND** ⚠️ — all-rights-reserved by default. **Do not copy code.** Borrow concepts only. |
| Stack | CrewAI, Claude, ChromaDB + sentence-transformers (all-MiniLM-L6-v2), Playwright, SQLAlchemy/SQLite, Typer+Rich |

**Verified implementation highlights:**
- `tools/ats_scorer.py`: `ATSResult`, `_tokenize`, `_extract_tech_keywords`, `_tfidf_cosine`, `score_resume_against_jd`, `top_missing_keywords` — **deterministic TF-IDF ATS scoring, zero API cost**.
- `tools/rag/`: document_processor (PDF/DOCX parse) + vector_store (ChromaDB local embeddings).
- `tools/retry.py`: exponential backoff wrapper.
- Feedback loop: `feedback <job> --response yes --days 5` records outcomes to improve matching.

**Best features:** deterministic ATS scoring; local/no-cost embeddings; explicit feedback loop; clean agent separation; relevance threshold gating.
**Weak features:** no license; scraper legality issues (LinkedIn ToS); CrewAI adds heavy dependency for little value; no web UI/API; single-user CLI; no dedup sophistication; no country/visa logic.

**Reusable concepts (NOT code):** TF-IDF-based deterministic ATS pre-score (reimplement — the algorithm is generic, ~100 lines); RAG-over-candidate-evidence with retrieval-into-prompt; relevance threshold; outcome feedback table feeding analytics.

---

## 3. DavidAromose/job-application-pipeline — GMAIL DRAFTS + CONTACTS + ANTI-FABRICATION

| | |
|---|---|
| Purpose | One URL → scrape JD → conservatively tailor CV (reorder/rephrase only) → DOCX→PDF → Hunter/Apollo contacts → **Gmail DRAFT (never sent)** → Google Sheet row |
| License | **MIT** (David Aromose) ✅ |
| Stack | Python, Anthropic API, Playwright, python-docx, LibreOffice headless (PDF), Google OAuth (Gmail+Sheets), Hunter/Apollo |

**Verified implementation highlights:**
- `pipeline/resume.py`: master resume parsed into typed `Block`s (corpus); `_numbers()` extracts every number in output; `_fabrication_check()` flags any number not present in master + any bullet whose best similarity ratio vs master corpus is below a floor → warnings. Plus `RESUME_CONSTRAINTS/REPLACEMENTS/DROP_PATTERNS` truthful-correction hooks.
- `pipeline/gmail_draft.py`: `create_draft(...)` + `_find_existing_draft(service, subject)` → **idempotent draft creation (dedup by subject)**; MIME builder attaches CV; never sends.
- `pipeline/contacts.py`: `Contact` dataclass with `email_is_real()`; provider functions `_hunter_people(domain)` / `_apollo_people(domain)`; `_classify_title(title)` → recruiter/TA classification; `resolve_domain()`; `_pick(people, limit)`.
- `pipeline/scraper.py`: JSON-LD `JobPosting` extraction — clean structured-data parsing.

**Best features:** anti-fabrication guardrail is the best concrete implementation across all five repos; Gmail draft idempotency; conservative tailoring philosophy; domain-resolve + title-classification for contacts.
**Weak features:** one-shot CLI (no persistence/DB, no scheduler, no API/UI); providers hard-wired (functions, not interface); single resume file (no verified-evidence model); no dedup beyond draft subject; no matching/scoring engine.

**Reusable concepts/code (MIT):** fabrication-check algorithm (number-set diff + similarity floor — port and extend into EvidenceChecker); draft-dedup approach (extend to thread-level); title classification heuristics; JSON-LD extraction; OAuth desktop-flow pattern.

---

## 4. shashikirandevadiga/apply-pilot — OUTREACH STRATEGY + VERIFIER GATES

| | |
|---|---|
| Purpose | Claude-Code skill system: JD → fit assessment → tailored resume (bullet library) → cover letter → multi-track outreach strategy → DOCX |
| License | **MIT** (attribution "[Your Name]" placeholder) ✅ |
| Stack | Prompt-defined agents (8) + python-docx; no runtime framework |

**Best features:**
1. **Creator→Verifier gate pattern** with auto-retry — quality firewall per artifact.
2. **Outreach is multi-track and audience-specific** (recruiter vs hiring manager vs referral; connection note / InMail / email; 3-tier escalation over days) — matches Phase 20/21 exactly.
3. Evidence-style inputs: USER_PROFILE + USER_BULLETS (a curated, human-authored bullet library = poor-man's evidence store).
4. 6-point bullet framework (Action/Context/Method/Result/Impact/Outcome) — good formatting discipline.
5. Output layout `APPLICATIONS/[Company]_[Role]/` — matches Phase 19.

**Weak features:** prompt-only (no deterministic code, no DB/API/scheduler); 240–260 char bullet constraint is arbitrary; "spinning" language borders on embellishment — we must keep the stricter evidence rules; profile files are unversioned/unverified.

**Reusable concepts:** verifier-gate workflow (reimplement as code, not prompts); audience-differentiated outreach templates + sequence/escalation config; bullet library concept (superseded by our evidence store); DOCX generation script (reference only).

---

## 5. AgentWong/ai-job-search — ATS ADAPTERS + DETERMINISTIC/LLM SPLIT

| | |
|---|---|
| Purpose | Claude-Code orchestrated search: ATS public APIs + LinkedIn guest API + Built In API → Python filters/scoring → LLM fuzzy review → tailored resume/cover letter (no fabrication) |
| License | **MIT** ✅ |
| Stack | Claude Code slash commands + subagents; Python scripts; Firecrawl (optional); DOCX |

**Verified implementation highlights:**
- `scripts/ats_scraper/platforms/`: **22 adapters** — ashby, bamboohr, breezy, careerpuck, comeet, dayforce, eightfold, gem, greenhouse, isolvedhire, lever, oracle, pinpoint, polymer, recruitee, rippling, smartrecruiters, trakstar, workable, workday, + utils. Direct public ATS APIs, no scraping credits.
- `scripts/ats_scraper/filters.py`: `FilterStats`/`FilterResult` with **reject(reason)** accounting; `build_target_roles_pattern`; `_parse_posted_date` (handles unknown dates); `apply_filters`; `title_passes`.
- `scripts/ats_scraper/scorer.py` + `shared/scoring_framework.md`: boosters/penalties/**disqualifiers** (clearance, on-call, crypto, seniority) — a configurable rules-based score with hard disqualifiers.
- `docs/llm-deterministic-offload-strategy.md`: the "Python-stages, LLM-reviews" pattern written up — pagination/regex/filters/math/CSV in Python; LLM only for fuzzy disqualification + prose.
- `config/exclusions.yml`; effectiveness_tracker + data_analysis (monthly aggregation, config tuning recommendations); queue_writer → `results/application_queue.csv`.
- LinkedIn via **public guest API only** (ToS-aware), validation probe for ATS domains before adding to config.

**Best features:** breadth of ATS adapters (port the 4 we need from here); reject-reason telemetry; hard-disqualifier framework; the deterministic/LLM split as an explicit design doc; cost discipline (~$20–39/mo); candidate-config-as-code (config.yml + exclusions.yml).
**Weak features:** no database, no web app, no CRM/timeline; spreadsheet results; no contacts module; no Gmail; resumes tailored from a single CV file (no evidence status); Claude-Code-coupled execution model.

**Reusable concepts/code (MIT):** platform adapter shapes for greenhouse/lever/ashby/smartrecruiters (port + wrap in our `JobSourceAdapter` interface); FilterStats reject-reason pattern (→ EligibilityEngine); scoring framework with disqualifiers (→ matching weights + hard_blockers); deterministic/LLM split doctrine; exclusions config; effectiveness tracking schema ideas.

---

## CROSS-CUTTING FINDINGS

| Dimension | Winner | Notes |
|---|---|---|
| Overall architecture / app shell | **CareerPulse** | FastAPI + SQLite + scheduler + SPA + tests |
| Scraper resilience | **CareerPulse** | base class backoff/rate-limit/UA; adopt for all adapters |
| ATS API adapters | **ai-job-search** | 22 platforms; port Greenhouse/Lever/Ashby/SmartRecruiters |
| Deterministic vs LLM doctrine | **ai-job-search** | adopt as binding rule (master prompt Phase 14 agrees) |
| Anti-fabrication | **job-application-pipeline** | number-diff + similarity floor; port into EvidenceChecker |
| Gmail drafts | **job-application-pipeline** | draft-only + dedup; extend, keep never-send default |
| Contacts | **job-application-pipeline** | Hunter/Apollo patterns; generalize into ContactProvider |
| Outreach design | **apply-pilot** | audience-specific multi-track + sequences; make config-driven |
| Deterministic ATS scoring | **job_search_agent** | TF-IDF concept (reimplement; NO code — unlicensed) |
| RAG over candidate evidence | **job_search_agent** | concept only (no license); embed provider-agnostic |
| Feedback loop | **job_search_agent** + ai-job-search | outcome tracking → human-reviewed recommendations |
| CRM / events / approvals | **CareerPulse** | applications + app_events + queue approval |

**Gaps in ALL five (must be NEW):**
- Candidate evidence store with VERIFIED/UNVERIFIED/DISPUTED/DO_NOT_USE lifecycle + EvidenceChecker gate.
- Country as first-class YAML config (visa/sponsorship keywords, outreach windows, per-country targets).
- Multi-component weighted matching with component breakdown (no single-magic-LLM-score).
- Multi-pass self-correcting search with stop-reason telemetry.
- Freshness states VERIFIED_FRESH / STALE / DATE_UNKNOWN with evidence.
- Contact confidence model (HIGH/MEDIUM/LOW + relationship type + why-selected).
- Response-email classifier with low-confidence→REVIEW routing.
- Application package directory layout (Phase 19) with hashes/versioning.

**License summary:** 4× MIT (CareerPulse, job-application-pipeline, apply-pilot, ai-job-search) → code porting permitted with attribution. job_search_agent: **unlicensed → concepts only, zero code**.
