# CLAUDE.md

This file gives coding agents the minimum high-signal context needed to work safely in this repository.

## Project

`jobagent` is a personal AI-assisted international job search, application package, and recruiter outreach system.

Primary flow:

```text
resume upload -> discover jobs -> classify location -> eligibility gate -> score
-> hybrid score -> select -> research -> package -> outreach draft -> digest
```

Target roles are AI/backend roles such as AI Engineer, Generative AI Engineer, LLM Engineer, RAG Engineer, Agentic AI Engineer, Python AI Developer, and Backend/AI Engineer.

The runnable app root is this directory:

```text
job-search-system/root
```

Broader project docs live one level up:

```text
job-search-system/docs
```

Read these first when starting substantial work:

1. `../PROJECT_MEMORY.md`
2. `../docs/AGENT_CONTEXT.md`
3. `../docs/NEXT_5_PLAN.md`
4. `README.md`
5. The tests for the area being changed

Some README milestone text may be stale. Prefer code, tests, `PROJECT_MEMORY.md`, and the docs above as source of truth.

## Claude Skills And Token Reduction

At the start of a Claude Code session, check `/skills`.

If a `token-reducer` or equivalent context-reduction skill is available and working, use it for broad repository inspection before opening large files. This repository has several large/high-context files, especially `app/database.py`, `app/main.py`, and broad router/test directories.

Before relying on `token-reducer`, verify its required files exist. In particular, if its instructions reference a script such as:

```text
${CLAUDE_PLUGIN_ROOT}/scripts/context_pipeline.py
```

then confirm that script is actually installed and that the referenced environment variable/path resolves correctly. If the skill install is incomplete, do not invoke the broken command. Fall back to targeted `rg`, focused file reads, and the read order in this file.

Use token-reduction tooling for:

- broad architecture scans
- large-file summarization
- searching pipeline contracts
- finding invariants across code and tests
- avoiding repeated full reads of `app/database.py`

Do not use token-reduction output as sole authority for behavior-changing edits. Confirm important invariants directly in source code and tests before editing.

## Do Not Break These Invariants

- Authenticated workspace users must upload a usable resume before discovery/scraping/search. Missing resume should return HTTP `428`.
- Gmail outreach creates drafts by default. Do not add sending behavior unless explicitly requested and covered by tests.
- Unknown dates must remain unknown. Never guess job freshness.
- Ineligible jobs must not be scored by normal scoring flows.
- Eligibility is deterministic. Do not move eligibility decisions into LLM prompts.
- Evidence-gated generation must fail closed. Do not save generated resumes/packages containing unsupported claims.
- Never invent skills, dates, employers, education, certifications, metrics, visa facts, or work history.
- Workspace isolation is critical. One user must not see or mutate another user's jobs, resumes, settings, Gmail token, evidence, contacts, packages, or applications.
- Raw secrets must never be returned by API responses or written to logs.
- Masked API keys/settings must preserve existing stored values.
- Gmail token fallback from env is allowed only when no workspace token exists.
- Cross-source dedupe must not rely only on URL.
- Source provenance must be preserved.
- Country expansion should be config-first through `config/countries/*.yaml`.
- Daily success target means qualifying application packages, not scraped URL count.
- Application package generation should remain idempotent.

## Architecture

Backend:

- FastAPI app factory: `app/main.py`
- SQLite async database layer: `app/database.py`
- Auth/session system DB: `app/auth.py`
- Per-user workspaces: `app/workspace.py`, `app/workspace_middleware.py`
- Background scheduling: APScheduler setup in `app/main.py`, jobs in `app/scheduler.py`
- Runtime config: `app/config.py`

Frontend:

- Vanilla JS SPA in `app/static`
- Frontend tests use Vitest/jsdom

Browser extension:

- Chrome Manifest V3 extension in `extension`
- Supports ATS/application autofill behavior

Database:

- SQLite, accessed through `aiosqlite`
- Workspace data is per-user
- Schema and migrations are created idempotently in `app/database.py`
- There is no Alembic migration workflow in the current codebase

AI providers:

- Main client: `app/ai_client.py`
- Supported providers include Anthropic, OpenAI, OpenRouter, Google, DeepSeek, Bedrock, and Ollama
- Usage/cost tracking: `app/ai_usage.py`

Deployment:

- `Dockerfile`
- `docker-compose.yml`
- Container command runs `uv run uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8085`

## Important Directories And Files

`app/main.py`

- Creates FastAPI app
- Initializes DB, auth, workspaces, AI clients, evidence services, scheduler, and routers
- Contains per-user AI state handling

`app/database.py`

- Owns SQLite schema, migrations, and data access
- Large file; search before reading entire file

`app/auth.py`

- System DB, users, sessions, password hashing, auth middleware

`app/workspace.py`

- Creates and migrates per-user workspace directories and DBs

`app/workspace_middleware.py`

- Attaches workspace DB/profile/evidence context to authenticated requests

`app/routers`

- API routers grouped by domain
- Important routers: `auth.py`, `settings.py`, `jobs.py`, `scraping.py`, `discovery.py`, `eligibility.py`, `matching.py`, `research.py`, `packages.py`, `outreach.py`, `tailoring.py`, `analytics.py`, `crm.py`, `queue.py`, `evidence.py`, `countries.py`

`app/adapters`

- Canonical discovery adapters for job sources

`app/scrapers`

- Legacy scraper implementations

`config/countries`

- Country-specific aliases, cities, work types, visa terms, salary floors, and search expansion

`config/profile_templates`

- Default evidence/profile templates copied into new workspaces

`config/outreach_sequences.yaml`

- Outreach templates, identity, follow-up behavior, and anti-spam limits

`tests`

- Backend pytest suite

`app/static/tests`

- SPA Vitest tests

`extension/tests`

- Extension Vitest tests

`data`

- Runtime data only: DBs, user workspaces, profile data, generated packages, Gmail fallback drafts
- Treat as private/sensitive local state

## Pipeline Map

### Resume Upload

Main files:

- `app/routers/settings.py`
- `app/resume_analyzer.py`
- `app/resume_profile.py`
- `app/evidence_autofill.py`
- `app/evidence_store.py`

Behavior:

- Endpoint: `POST /api/resume/upload`
- Accepts PDF, TXT, MD, DOC, DOCX, and RTF
- Max upload size is 10 MB
- Extracts text, optionally analyzes with AI, updates `search_config`, stores resume row, extracts verified evidence claims
- Upload can still succeed without AI, but with reduced analysis

### Discover

Main files:

- `app/discovery.py`
- `app/source_registry.py`
- `app/job_adapter.py`
- `app/adapters`
- `app/scheduler.py`
- `app/scrapers`
- `app/routers/discovery.py`
- `app/routers/scraping.py`

Behavior:

- Uses enabled countries and resume-derived search terms
- Newer path uses source registry and adapters
- Legacy path uses scrapers
- Stores jobs, sources, duplicate/canonical records, and source health/provenance
- Discovery concurrency defaults to 5

### Classify

Main files:

- `app/classification.py`
- `app/scheduler.py`

Behavior:

- Determines country, city, region, remote type, confidence, source, and reason
- Deterministic signals first
- Source country is a weak hint, not proof
- AI fallback only handles unresolved cases

### Eligibility

Main files:

- `app/eligibility.py`
- `app/routers/eligibility.py`
- `app/scheduler.py`

Behavior:

- Deterministic gate after classification
- Checks data sanity, dismissed/applied status, job status, freshness, location, salary/evidence, and final eligibility
- `DATE_UNKNOWN` is not fresh
- Unknown or low-confidence location generally requires review
- Normal scoring should use only eligible jobs

### AI Score

Main files:

- `app/matcher.py`
- `app/main.py`

Behavior:

- Scores eligible jobs against resume/profile
- Uses batch scoring with fallback individual scoring
- Transient AI failures are retried
- Do not fabricate scores after unrecoverable AI failure

### Hybrid Score

Main files:

- `app/hybrid_matcher.py`
- `app/matching_service.py`
- `app/routers/matching.py`

Behavior:

- Combines deterministic components and verified evidence
- Stores component scores and hard blockers
- Hard blockers cap scores

### Select

Main files:

- `app/daily_run.py`
- `app/database.py`

Behavior:

- Selects eligible/scored jobs for package work
- Package count is the meaningful target, not raw discovered jobs

### Research

Main files:

- `app/contact_providers.py`
- `app/company_research.py`
- `app/company_enrichment.py`
- `app/company_careers.py`
- `app/ats_detect.py`
- `app/routers/research.py`

Behavior:

- Finds company/contact context
- Uses provider abstraction for manual, Hunter, Apollo, and web search style providers
- Stores contacts, job-contact links, and contact research cache

### Packages

Main files:

- `app/routers/tailoring.py`
- `app/application_builder.py`
- `app/tailoring.py`
- `app/cover_letter.py`
- `app/docx_generator.py`
- `app/pdf_generator.py`
- `app/evidence.py`
- `app/evidence_store.py`

Behavior:

- Generates tailored resume and cover letter
- Builds DOCX/PDF/text package artifacts
- EvidenceChecker must pass before generated package is saved
- Package generation should be idempotent

### Outreach

Main files:

- `app/outreach.py`
- `app/routers/outreach.py`
- `config/outreach_sequences.yaml`

Behavior:

- Creates Gmail drafts or local fallback draft records
- Stores outreach messages and contact interactions
- Enforces one outreach per `(job_id, audience)`
- Uses configured daily/per-company/follow-up limits

### Digest

Main files:

- `app/digest.py`
- `app/routers/analytics.py`
- `app/main.py`

Behavior:

- Generates recent high-value job digest
- Can send via SMTP settings when enabled
- Scheduled daily by APScheduler

## Data Model

Important tables are created or migrated in `app/database.py`.

Core:

- `jobs`
- `sources`
- `job_duplicates`
- `job_scores`
- `applications`
- `companies`
- `contacts`
- `job_contacts`
- `outreach_messages`
- `contact_interactions`

User/profile:

- `search_config`
- `user_profile`
- `work_history`
- `education`
- `certifications`
- `skills`
- `languages`
- `user_references`
- `military_service`
- `eeo_responses`
- `custom_qa`
- `resumes`
- `candidate_evidence`

Settings/runtime:

- `ai_settings`
- `email_settings`
- `scraper_keys`
- `scraper_schedule`
- `saved_views`
- `job_alerts`
- `notifications`
- `application_queue`
- `follow_up_templates`
- `metrics`
- `daily_runs`
- `ai_usage`
- `context_items`
- `embedding_settings`

System auth DB:

- `users`
- `sessions`
- `admin_actions`

## Multi-User Rules

- System auth lives separately from workspace data.
- Each user has a workspace under `data/users/{id}-{username}`.
- Each workspace has its own `jobagent.db`, profile files, applications directory, and Gmail draft fallback directory.
- Routes should use request-bound workspace services when available.
- Do not accidentally use global app DB in user-scoped route logic.
- Tests verify that users cannot see each other's jobs, contacts, resumes, settings, evidence, packages, or Gmail token.

## AI Rules

Use AI for:

- Resume analysis/parsing
- Semantic match scoring
- Tailored resume generation
- Cover letter generation
- Classification fallback for unresolved cases
- Interview prep
- Draft text assistance

Do not use AI for:

- Eligibility hard gates
- Security decisions
- Workspace isolation
- Deduplication identity
- Freshness/date guessing
- Evidence validation

AI implementation notes:

- `app/ai_client.py` handles providers, retries, JSON extraction, circuit breaking, and timeouts
- `app/ai_usage.py` tracks token/cost estimates
- Existing code favors deterministic filters before LLM calls to control cost

## Secrets And Security

- Never print `.env` values, API keys, Gmail tokens, SMTP passwords, or resume contents into logs.
- Settings APIs should mask secrets and preserve existing values when masked values are submitted.
- Raw Gmail tokens should never be returned.
- Treat `data` as private runtime state.
- Keep auth-protected routes protected unless deliberately changing public surface.
- Production deployments should review cookie security settings.

## Testing

Backend:

```powershell
uv run pytest
```

Frontend:

```powershell
cd app/static
npx vitest run
```

Extension:

```powershell
cd extension
npx vitest run
```

High-value tests:

- `tests/test_auth.py`
- `tests/test_workspaces.py`
- `tests/test_multiuser_real_scenario.py`
- `tests/test_evidence.py`
- `tests/test_eligibility.py`
- `tests/test_adapters.py`
- `tests/test_outreach.py`
- `tests/test_daily_run.py`
- `tests/test_application_builder.py`

Run targeted tests for the touched area first. Run the full backend suite before broad backend changes are considered complete.

## Useful Search Commands

```powershell
rg -n "require_resume_for_search|HTTP_428|428" app tests
rg -n "Eligibility|DATE_UNKNOWN|get_scoreable_jobs" app tests
rg -n "create_draft|GmailProvider|send" app tests
rg -n "workspace|WorkspaceManager|request.state.workspace" app tests
rg -n "hybrid_score|component_scores|hard_blockers" app tests
rg -n "CREATE TABLE|ALTER TABLE" app/database.py
rg -n "@router\.(get|post|put|patch|delete)" app/routers
```

## Development Workflow

- Do not commit or push unless explicitly asked.
- Do not rewrite unrelated files.
- Do not modify runtime user data under `data` unless the task explicitly requires it.
- Prefer small, tested changes that follow existing service/router patterns.
- Add or update tests for any behavior change touching invariants.
- For schema changes, update `app/database.py` idempotently and add migration-oriented tests.
- For new job sources, prefer the adapter/source registry patterns.
- For country expansion, prefer `config/countries/*.yaml` over hard-coded logic.
- For UI changes, match the existing vanilla SPA structure under `app/static`.
- For extension changes, keep Manifest V3 constraints in mind and run extension Vitest tests.

## Current Known Project Status

Implemented areas include:

- Auth/admin bootstrap
- Multi-user workspaces
- Per-user DB/profile/evidence/package directories
- Per-user Gmail token handling
- Resume-first gate
- Discovery source registry and adapters
- Classification
- Eligibility
- AI and hybrid scoring
- Evidence-gated package generation
- Gmail draft outreach
- Digest and daily-run scaffolding

Known active/pending areas from project memory:

- Per-user scheduled cycles
- Run state
- Ship-reviewed-text workflow
- Admin panel
- Some daily-run execution paths appear scaffolded rather than fully end-to-end automated
- Gmail OAuth UX appears incomplete
- Docker healthcheck may need review because `/api/health` is auth-protected on the inspected branch while `/api/system/health` is public
