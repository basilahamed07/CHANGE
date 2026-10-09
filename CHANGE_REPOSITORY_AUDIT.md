# CHANGE Repository Audit

Audit date: 2026-10-08  
Repository: `job-search-system/root`  
Branch: `fine-define-arch`

## Scope and evidence

This audit was produced from the actual FastAPI application, workspace and
database code, routers, adapters, scrapers, tests, and the repository's
architecture/status documents. The runnable application root is
`job-search-system/root`; the surrounding `CHANGE` directory is a repository
container and prompt/documentation area.

The repository already contains substantial functionality. This work therefore
extends the existing CareerPulse-derived architecture instead of introducing a
second application or database.

## A. Current architecture

```text
Vanilla JS SPA / Chrome MV3 extension / CLI
                         |
                      FastAPI
                         |
       AuthGuardMiddleware + session cookie auth
                         |
              WorkspaceMiddleware
                         |
       request.state.workspace / request.state.db
                         |
     Domain routers -> services -> workspace SQLite
                         |
     discovery / classification / eligibility / matching
                         |
   research / package generation / outreach / analytics
                         |
       APScheduler + explicit scheduler service calls
```

`app/main.py:create_app` builds the FastAPI application. The lifespan creates
the system auth store and a default/admin workspace DB, initializes services,
and installs background jobs. `app/auth.py` owns users, sessions, password
hashing, throttling, and auth middleware. `app/workspace.py` creates one
workspace directory and SQLite DB per user. `app/workspace_middleware.py`
resolves the authenticated user's workspace and binds it to the request.

Global/system concerns are kept in process configuration or the system auth DB:
source registry, country configuration, adapter classes, source health rules,
and users/sessions. User data is stored in the user's workspace DB and related
profile, evidence, applications, and draft directories.

## B. Actual request and runtime flow

### Login and workspace resolution

1. `POST /api/auth/login` in `app/routers/auth.py` authenticates through the
   `SystemStore` in `app/auth.py` and returns a session cookie.
2. `AuthGuardMiddleware` rejects unauthenticated protected requests.
3. `WorkspaceMiddleware` resolves the session user through
   `WorkspaceManager.workspace_dir(user_id, username)`, opens the user's
   `jobagent.db`, and attaches the DB/profile/evidence context to
   `request.state`.
4. Routers use their `_db(request)` helpers and request-bound services. Tests
   in `tests/test_workspaces.py` and `tests/test_multiuser_real_scenario.py`
   verify that users cannot read each other's workspace data.

### Resume onboarding

```text
POST /api/resume/upload (app/routers/settings.py)
  -> file validation and text extraction
  -> app/resume_analyzer.py:analyze_resume
  -> app/resume_analyzer.py:parse_resume_to_profile (when AI is available)
  -> search_config + resumes persistence
  -> profile tables and candidate_evidence via evidence_autofill/evidence_store
  -> user-visible keyword confirmation through /api/settings/search-config/keywords
```

The upload accepts PDF, TXT, MD, DOC, DOCX, and RTF, caps files at 10 MB, and
can succeed without an AI provider. Missing resume blocks search/discovery with
HTTP 428 through the search gate.

### Search configuration

`GET/POST /api/settings/search-config` and the keyword endpoints read and write
the workspace DB. Resume-derived `search_terms`, `job_titles`, and
`key_skills` are editable by the user. `app/discovery.py:role_terms_from_config`
derives the role terms used by discovery, while country and remote targeting is
loaded from the workspace search configuration and `config/countries/*.yaml`.

### Discovery to job persistence

```text
POST /api/discovery/run
  -> resume/search gate
  -> app/discovery.py:run_discovery_cycle
  -> source_registry.SOURCES ordering and country applicability
  -> adapters from app/adapters/ and legacy scrapers where selected
  -> bounded source concurrency with per-source failure isolation
  -> CanonicalJob normalization
  -> serial DB ingest and cross-source dedupe
  -> sources/provenance/canonical-source/source-health persistence
  -> jobs in the requesting workspace DB
```

Interactive scraping also exists at `app/scheduler.py:run_scrape_cycle` and
`POST /api/scraping/run`. This is a compatibility path for the legacy scraper
collection; the source-registry discovery path is the newer canonical path.

### Classification, eligibility, and matching

`app/scheduler.py:run_location_classification` calls the deterministic priority
chain in `app/classification.py`, using AI only for unresolved residue.
`run_eligibility_pass` calls `app/eligibility.py` and persists status, gate,
reason, evidence, and evaluation time. `Database.get_scoreable_jobs()` limits
normal scoring to `ELIGIBLE` jobs. AI scoring is implemented in `app/matcher.py`;
deterministic/hybrid scoring is in `app/hybrid_matcher.py` and
`app/matching_service.py`.

### Research, packages, outreach, analytics

Research routes use `app/company_research.py`, `company_enrichment.py`,
`company_careers.py`, `contact_providers.py`, and `ats_detect.py`. Package
generation is routed through `app/application_builder.py`,
`app/tailoring.py`, `app/cover_letter.py`, `app/evidence_checker.py`, and the
DOCX/PDF/Markdown renderers. `app/routers/packages.py` exposes prepare/build
and downloads. Outreach is draft-first through `app/outreach.py` and
`app/routers/outreach.py`; Gmail credentials are workspace-aware with local
fallback drafts. Analytics and digest behavior is in `app/digest.py`,
`app/routers/analytics.py`, and `app/ai_usage.py`.

### Scheduler

`app/main.py` installs APScheduler jobs which call functions in
`app/scheduler.py` for scraping, scoring/maintenance, reminders, enrichment,
embeddings, alerts, and digest work. The current scheduled implementation
resolves `app.state.bg_db` once at startup, which is the admin workspace DB.
That is the main remaining multi-user scheduler leak.

### Browser extension

`extension/` is a Chrome Manifest V3 extension. `content.js`, `background.js`,
`popup.js`, and `ats-adapters.js` support job capture and ATS/application
autofill. It communicates with the API using the configured backend URL and has
separate Vitest coverage under `extension/tests`.

## C. Current discovery architecture

### Adapters and source registry

`app/job_adapter.py` defines `JobSourceAdapter`, `AdapterResult`, and the
`CanonicalJob` dataclass. `app/source_registry.py` defines `SourceSpec`, source
families/access, country applicability, canonical priority, and
`SourceRunHealth`. `app/adapters/__init__.py:ALL_ADAPTERS` is the runtime
adapter list and is checked against the registry by tests.

The repository has direct/country-scoped adapters for Greenhouse, Lever,
Ashby, SmartRecruiters, Recruitee and related providers, plus aggregators such
as Remotive, Arbeitnow, Reed, Jooble, Adzuna, and other configured sources.
Legacy implementations remain in `app/scrapers/` and include Himalayas,
Remotive, Indeed, LinkedIn, Glassdoor-adjacent and remote-board scrapers.
The registry marks source type, tier, access mode, supported countries, and
whether configuration such as an API key is required.

### ATS design

Existing Greenhouse/Lever/Ashby adapters are the correct integration boundary.
They are board/company scoped, so a configurable company/board registry is
needed for broad ATS coverage; the current code does not yet provide the
prompt's dedicated dynamic `config/job_sources/company_registry.yaml`.

### Normalization and deduplication

`CanonicalJob` normalizes title, company, location, description, URLs, source,
source job ID, dates, remote/employment metadata, and content hash. Discovery
ingest prefers deterministic identity keys and preserves source observations in
the existing `sources` rows. Cross-source dedupe uses normalized job identity
and content/title/company/location fallbacks; `job_duplicates` records the
relationship. Canonical source is recalculated using source registry priority.

### Freshness and provenance

`app/freshness.py` preserves unknown dates as `DATE_UNKNOWN`; it never assigns
`first_seen_at` as a fabricated publication date. Job rows retain first/last
seen information, source URL/provenance, classification metadata, eligibility
evidence, and canonical source/source types.

### Retries, limits, and health

Discovery uses bounded `asyncio.Semaphore` concurrency, per-source result
isolation, configurable concurrency, source stop reasons, and source health
records. Legacy scraping uses a circuit breaker, bounded concurrency, per-source
timeouts, and configurable batch limits. The source registry exposes
`SUCCESS`, `PARTIAL_SUCCESS`, `RATE_LIMITED`, `TIMEOUT`, `AUTH_REQUIRED`,
`NOT_APPLICABLE`, `CONFIGURATION_REQUIRED`, `FAILED`, and `DISABLED`-style
outcomes through its health mapping.

## D. Existing database model and migrations

`app/database.py` owns schema creation and idempotent migrations; there is no
Alembic workflow. Core workspace tables include `jobs`, `sources`,
`job_duplicates`, `job_scores`, `applications`, `companies`, `contacts`,
`job_contacts`, `outreach_messages`, `contact_interactions`, `resumes`,
`search_config`, `user_profile`, profile detail tables, `candidate_evidence`,
AI/email/scraper settings, queue/alerts/notifications, `daily_runs`,
`ai_usage`, embeddings, and runtime metrics.

The system auth DB separately contains `users`, `sessions`, and
`admin_actions`. Workspace isolation is physical (one SQLite DB per user), not
only a convention in SQL. Existing schema already covers source provenance,
scores, applications, evidence, and outreach. There is no first-class
`search_profiles`, `profile_versions`, `discovery_cycles`, or `source_runs`
entity matching the master prompt's ideal model; adding those should be done
only where reproducibility or observability cannot be represented by the
existing tables/run telemetry.

## E. Gap analysis

| Area | Existing | Missing or weak | Reuse | Replace |
|---|---|---|---|---|
| Auth | Session auth, throttling, admin APIs | Unified admin UI/impersonation flow | `auth.py`, auth router | None |
| Workspace | Per-user DB, profile, evidence, packages, Gmail | Background state/scheduled work is still admin/global in places | `workspace.py`, middleware | Global scheduler state |
| Resume | Multi-format upload, extraction, AI profile analysis, evidence autofill | Explicit versioned candidate/search-profile entity | Settings router, analyzer, evidence store | None |
| Profile extraction | Structured profile tables and search config | Stronger evidence-vs-keyword model and version history | Existing profile/evidence services | None |
| Search config | Editable resume-derived terms and country settings | Bounded query generator and persisted profile version | `discovery.py`, country registry | None |
| Discovery | Registry, adapter contract, bounded concurrency, telemetry | Per-user scheduled orchestration and dedicated cycle records | `discovery.py`, `source_registry.py` | Legacy paths only when converged |
| ATS | Greenhouse, Lever, Ashby and more adapters | Dynamic company/board registry and refresh strategy | Existing ATS adapters | No wholesale scraper |
| Job boards | Many legacy scrapers/adapters | No dedicated JobSpy adapter; paid providers disabled policy should be explicit | Adapter contract and failure isolation | Avoid direct scraper calls from routers |
| Remote APIs | Remotive and other remote sources | Himalayas/Remotive roadmap should be normalized under one adapter path | Existing adapters/scrapers | None |
| Dedup | Content hash, URL/source rows, duplicate table, provenance | Explicit observation entity and stronger external-ID precedence | `job_adapter.py`, database ingest | None |
| Eligibility | Deterministic classification/freshness/location/evidence gates | Ensure every package/select/digest path rechecks eligibility | `eligibility.py`, scheduler | No LLM gate |
| Matching | AI matcher plus hybrid matcher with hard blockers | Profile-versioned score history and protection from destructive overwrite | `matcher.py`, `hybrid_matcher.py` | Do not create second engine |
| Research | Provider chain, ATS detection, company enrichment | SSRF hardening and transient-failure cache semantics | Research modules | None |
| Package | Evidence gate, structured ATS Markdown, PDF/DOCX, idempotence | Build must ship reviewed text by default; personal-facts guard | `application_builder.py`, evidence checker | Current default build behavior |
| Outreach | Draft-only Gmail/local fallback, dedupe and caps | Verify all send-like endpoints are approval-gated | `outreach.py` | Remove/guard ungated pipeline send |
| Scheduler | APScheduler and service passes | Iterate active users, stagger, user-keyed state, run IDs | `main.py`, `scheduler.py` | Admin-only background targeting |
| Analytics | Digest, source health, AI usage, pipeline metrics | Per-user scheduled cycle/run visibility | Existing analytics and metrics | None |

## F. External reference evaluation

The repository should use the external projects as bounded references, not as
replacement architecture.

| Reference | Decision |
|---|---|
| JobSpy | Evaluate as the acquisition/reference layer for Indeed, LinkedIn and Glassdoor. Wrap it behind `JobSourceAdapter`, enforce timeouts/budgets, and normalize into `CanonicalJob`. Do not let it own workspace, eligibility, deduplication, or package logic. Dependency and scraping terms/rate-limit behavior require review before adding it. |
| mherzog4/job-boards | Useful model for discovering and validating company ATS identifiers. Port the concept into a config-backed registry with refresh/cache metadata; do not copy its application architecture or hardcode thousands of companies in Python. |
| noble-ronin/ats-job-apis | Compact endpoint/schema reference only. Official provider APIs remain the source of truth. |
| GregoryBolshakov/ats-job-boards-reference | Useful for comparing real provider field differences and test fixtures; not a blind schema. |
| Greenhouse official Job Board API | Use the public board-token endpoint for published jobs and full content where needed. |
| Lever official postings API | Use company/site-scoped published postings with pagination; it does not provide universal cross-company full-text discovery, so the registry is mandatory. |
| Ashby public Job Posting API | Use listed public postings only; preserve organization/board identity and do not expose unlisted data. |

Official references consulted: [Greenhouse Job Board API](https://docs.greenhouse.io/job-board.html), [Lever Postings API](https://github.com/lever/postings-api), [Ashby public job posting guidance](https://developers.ashbyhq.com/docs/creating-a-custom-careers-page), and [JobSpy](https://github.com/speedyapply/JobSpy). The Lever documentation explicitly describes site-scoped pagination and the absence of universal full-text search; Greenhouse documents `/v1/boards/{board_token}/jobs`; Ashby documents listed public job retrieval.

## G. Exact change boundaries

### Files intended to change for the next implementation phases

- `app/main.py`, `app/scheduler.py`: user iteration, staggered scheduled runs,
  per-user run state, and run observability.
- Discovery routers and `app/discovery.py`: user-keyed status/progress and
  bounded user-specific orchestration.
- `app/database.py`: only idempotent additions proven necessary for run/profile
  version history or source-run persistence.
- Package/evidence modules and related router tests: reviewed-text default,
  explicit regeneration, personal-facts validation, and metadata provenance.
- Admin router/static UI and auth tests: unified role-gated management and
  audited impersonation.
- `config/job_sources/company_registry.yaml` or an equivalent existing config
  location: dynamic ATS board records.
- Focused regression and real-scenario tests under `tests/` and corresponding
  docs/status files.

### Files that should not change without direct evidence

- Core eligibility rules and freshness semantics.
- Evidence verification semantics except for the required personal-facts
  extension.
- Existing hybrid matcher mathematics and AI matcher contract.
- Outreach draft-first behavior and Gmail token masking.
- Browser-extension behavior unrelated to an API contract change.
- Runtime `data/` user databases, generated packages, and secret-bearing files.
- External repositories copied wholesale or a second database architecture.

## H. Implementation order

1. Complete this audit (Phase 0).
2. Fix per-user scheduled cycles and per-user background run state.
3. Make package build ship stored reviewed content by default and add the
   personal-facts evidence guard.
4. Add/finish the dynamic ATS company registry without expanding provider
   scope unnecessarily.
5. Add the admin UI and audited impersonation only after the underlying routes
   are role-gated and tested.
6. Run focused tests, the real two-user HTTP scenarios, backend suite, and
   frontend/extension suites where dependencies are available.

## Current conclusion

The core product is already a multi-user workspace application at the storage
and request-routing layers. It is not yet complete against the master
specification because background execution, run-state isolation, reviewed
package shipping, personal-fact evidence gates, and admin workflow remain
unfinished. The next implementation should strengthen those boundaries while
reusing the existing adapters, models, matcher, evidence, research, package,
and outreach services.

## Implementation update

The repository was rechecked after the audit. The previously documented N2/N3
and N4 gaps are already implemented in the current branch and are covered by
the focused suites: active-user scheduler iteration and staggering, per-user
run state and per-IP scrape limiting, reviewed-text-first package builds,
explicit regeneration, personal-facts evidence checks, and metadata
provenance. The real multi-user/package/personal-facts verification completed
with 46 passed tests.

This pass also completed the first config-first ATS registry slice:

- Added `config/job_sources/company_registry.yaml` for validated Greenhouse,
  Lever, and Ashby board/site identifiers.
- Added `app/company_registry.py` with safe YAML loading, unique board-token
  extraction, and country-aware record lookup.
- Wired the existing Greenhouse/Ashby scrapers and Lever/Ashby adapters to use
  the registry while preserving explicit scraper-key overrides and hardcoded
  fallback defaults.
- Added `tests/test_company_registry.py` and ran the focused ATS/discovery
  regression set: 79 passed.

No database migration was required. JobSpy remains intentionally unintroduced
as a mandatory dependency: the existing adapter/scraper boundary can host it
later, but the current $0 provider policy and existing source coverage do not
justify adding an unreviewed scraping dependency in this pass. The remaining
known product gap is the unified audited admin impersonation workflow; existing
admin user-management APIs and settings UI remain intact.
