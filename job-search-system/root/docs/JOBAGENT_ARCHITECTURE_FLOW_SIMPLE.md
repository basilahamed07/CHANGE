# JobAgent Architecture and Flow

Generated: 2026-10-04

This document explains the current repo in simple terms: what happens when you run scraping, discovery, daily pipeline, scoring, resume/package generation, and outreach.

## 1. Big Picture

JobAgent is a local job-search pipeline.

The main flow is:

1. User profile and resume are loaded.
2. Jobs are discovered from job boards, ATS feeds, and country-specific sources.
3. Jobs are normalized and deduplicated.
4. Locations are classified.
5. Eligibility rules decide whether a job can move forward.
6. Matching/scoring ranks the eligible jobs.
7. Top jobs can be researched for contacts.
8. Application packages are prepared as Markdown, PDF, and DOCX.
9. Outreach drafts can be created, but the system does not send automatically.

The app is a FastAPI backend with a static browser UI.

Key entry files:

- Backend app: `app/main.py`
- Database layer: `app/database.py`
- Browser UI: `app/static/index.html` and `app/static/js/views/*`
- Manual scrape API: `app/routers/scraping.py`
- Country-aware discovery API: `app/routers/discovery.py`
- Daily pipeline API: `app/routers/crm.py`
- Eligibility: `app/eligibility.py`, `app/routers/eligibility.py`
- Hybrid match: `app/hybrid_matcher.py`, `app/matching_service.py`
- AI scoring: `app/matcher.py`
- Resume/package generation: `app/tailoring.py`, `app/application_builder.py`, `app/routers/packages.py`

## 2. Current Local State

From `data/users/1-basil/jobagent.db` at generation time:

- Total jobs: 565
- Live jobs: 409
- Dismissed jobs: 156
- Scored jobs: 103
- Applications: 6
- Packages ready for review: 4

Eligibility status:

- INELIGIBLE: 421
- ELIGIBLE: 103
- REVIEW_REQUIRED: 40
- Not evaluated: 1

Live jobs by region:

- Remote: 131
- Singapore: 129
- UK: 54
- Canada: 35
- India: 25
- Germany: 20
- Poland: 5
- Ireland: 4
- Australia: 4
- Netherlands: 2

Top stored sources:

- mycareersfuture: 157
- ashby: 157
- greenhouse: 108
- dice: 72
- wellfound: 26
- arbeitnow: 13
- hackernews: 11
- jobicy: 7

## 3. Two Ways Jobs Enter The System

There are two job-ingestion paths in the repo.

### Path A: Manual Scrape

API:

- `POST /api/scrape`
- Progress: `GET /api/scrape/progress`
- Cancel: `POST /api/scrape/cancel`

Code:

- Router: `app/routers/scraping.py`
- Scrape engine: `app/scheduler.py::run_scrape_cycle`
- Scraper list: `app/scrapers/__init__.py::ALL_SCRAPERS`

What it does:

1. Requires a resume/search profile first.
2. Creates scraper instances from `ALL_SCRAPERS`.
3. Runs scrapers concurrently with timeout protection.
4. Inserts new jobs.
5. Enriches missing descriptions.
6. Classifies job locations.
7. Runs eligibility before scoring.
8. Runs AI scoring when an AI provider and matcher are available.

Manual scrape sources currently include:

- HackerNews
- Remotive
- USAJobs
- LinkedIn guest API
- Dice
- Arbeitnow
- Jobicy
- Indeed
- RemoteOK
- Himalayas
- Wellfound
- BuiltIn
- Greenhouse
- Adzuna
- WeWorkRemotely
- WorkingNomads
- Recruitee
- MyCareersFuture
- Ashby
- LandingJobs
- 4dayweek

Important: this path is older. It uses scraper classes from `app/scrapers`.

### Path B: Country-Aware Discovery

API:

- `POST /api/discovery/run`
- Status: `GET /api/discovery/status`
- Source registry: `GET /api/discovery/registry`
- Source health: `GET /api/discovery/health`

Code:

- Router: `app/routers/discovery.py`
- Engine: `app/discovery.py::run_discovery_cycle`
- Adapter list: `app/adapters/__init__.py::ALL_ADAPTERS`
- Source metadata: `app/source_registry.py`
- Country registry: `app/country_registry.py`

What it does:

1. Reads enabled countries.
2. Reads search terms from the user resume/search config.
3. Runs source adapters in registry order.
4. Skips sources that do not apply to the current country.
5. Records honest source health such as PASS, NO_RESULTS, CONFIGURATION_REQUIRED, RATE_LIMITED, FAILED, NOT_APPLICABLE.
6. Normalizes jobs into one common format.
7. Applies title relevance gate.
8. Applies region gate.
9. Inserts jobs.
10. Detects same-source and cross-source duplicates.
11. Stamps source provenance and canonical source.

Country-aware adapters currently include:

- Greenhouse
- Lever
- Ashby
- SmartRecruiters
- Jooble
- Adzuna
- Reed
- Arbeitnow
- Remotive
- Jobicy
- WeWorkRemotely
- RemoteOK
- Himalayas
- 4dayweek
- LandingJobs
- Recruitee
- MyCareersFuture
- Wellfound
- WorkingNomads
- Builtin

This is the newer and cleaner discovery architecture.

## 4. Is There A Web Search Source?

There is now a non-Google web discovery source named `tavily_search`.

It uses the Tavily Search API. It does not scrape search result pages.

Required configuration:

- `tavily_search`: Tavily API key

Environment variable fallbacks:

- `JOBAGENT_TAVILY_API_KEY`

If the key is missing, the source is still registered but reports configuration required in discovery health.

The old Google Custom Search and Vertex AI Search discovery adapters were removed. Current LinkedIn scraping uses LinkedIn's guest jobs endpoint:

- `https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search`

Current Dice scraping does not use Google. It reads Dice search pages and embedded Next.js job data.

## 5. Discovery Logic

The country-aware discovery cycle is controlled by `app/discovery.py`.

Loop shape:

1. For each enabled country
2. For each search term
3. For each source adapter in tier order
4. Run source search under concurrency limit
5. Ingest results serially to avoid DB/dedup races

Budget:

- Default max adapter passes per discovery cycle: 50
- Daily run defaults to `JOBAGENT_DAILY_DISCOVERY_PASSES`, default 4
- API supports `POST /api/discovery/run?passes=N`, N from 1 to 50

Concurrency:

- Default max concurrent source searches: 5
- Env override: `JOBAGENT_DISCOVERY_CONCURRENCY`

Source order:

- Tier 1: ATS and strong local/country sources
- Tier 2: global boards, remote boards, keyed aggregators
- Tier 3: long-tail feeds

The source registry decides source type, countries, access mode, tier, and priority.

## 6. Scrape Cycle Logic

Manual scrape uses `run_scrape_cycle`.

Important rules:

- Per-source timeout: `JOBAGENT_PER_SCRAPER_TIMEOUT`, default 60 seconds
- Scraper concurrency: `JOBAGENT_SCRAPE_CONCURRENCY`, default 4
- Circuit breaker skips a scraper after repeated failures
- Per-source schedule is respected unless force is true
- Title relevance gate removes off-topic jobs
- Region filter removes jobs outside allowed regions
- Remote-only filter can remove non-remote jobs
- Existing jobs are updated with last-seen/source info
- Cross-source duplicates are merged into the oldest job

Manual scrape progress phases:

- scraping
- enriching
- classifying
- scoring
- done
- error

## 7. Location Classification

Code:

- `app/scheduler.py::run_location_classification`
- `app/classification.py`
- `app/location_classifier.py`

The classifier tries cheap deterministic logic first:

1. Structured country data
2. Location text
3. City map
4. Description evidence
5. ATS/source metadata as low-confidence hint
6. AI fallback only for ambiguous residue
7. UNKNOWN if still unresolved

It stores:

- `location_region`
- `country_code`
- `classification_confidence`
- `classification_source`
- `classification_reason`
- conflict evidence

This stage is important because eligibility and country-specific resumes depend on the target country.

## 8. Eligibility: Pipeline Action M5

UI label:

- Eligibility (M5)

Code:

- `app/eligibility.py`
- `app/routers/eligibility.py`
- `app/scheduler.py::run_eligibility_pass`

Purpose:

Eligibility answers: "Should this job be allowed to move into scoring?"

It is deterministic. It does not use LLM.

Gate order:

1. DATA_SANITY: title, company, URL
2. DISMISSED: user or strategy dismissed
3. ALREADY_APPLIED: already submitted
4. JOB_STATUS: closed/expired evidence
5. FRESHNESS: fresh, stale, or unknown posted date
6. LOCATION: country/region target check
7. EVIDENCE: description/evidence available
8. FINAL_ELIGIBILITY

Possible statuses:

- ELIGIBLE
- INELIGIBLE
- REVIEW_REQUIRED
- UNKNOWN

Only ELIGIBLE jobs can enter scoring.

## 9. Matching And Scoring: Pipeline Action M6

UI label:

- Hybrid Match (M6)

There are two scoring layers.

### AI Scoring

Code:

- `app/matcher.py`
- `app/main.py::_score_unscored`

Uses the configured AI provider to score jobs against the resume.

Scoring rubric:

- Role type match: 30 percent
- Core skills match: 30 percent
- Seniority and experience fit: 20 percent
- Culture/logistics fit: 20 percent

Hard rule:

- If role_match is false, score is capped at 50.

### Hybrid Scoring

Code:

- `app/hybrid_matcher.py`
- `app/matching_service.py`
- `app/routers/matching.py`

This is deterministic and free. It uses:

- Verified evidence skills
- Search config target titles
- Country/visa keywords
- Local TF-IDF/RAG style matching
- Optional embeddings if configured

Endpoints:

- `POST /api/matching/score-all`
- `POST /api/matching/jobs/{job_id}/score`
- `GET /api/matching/jobs/{job_id}/explain`
- `GET /api/matching/top-jobs`

Important:

- Hybrid scoring does not block later AI scoring.
- AI scoring only reads jobs with `eligibility_status = ELIGIBLE`.

## 10. Contact Research: Pipeline Action M7

UI label:

- Contact Research (M7)

Code:

- `app/routers/research.py`
- `app/contact_providers.py`

Flow:

1. Check cached research first.
2. Try configured/manual providers.
3. Try provider fallback chain.
4. Save contact candidates.
5. User can select one contact for the job.

Endpoints:

- `POST /api/research/contacts/job/{job_id}`
- `GET /api/research/contacts/job/{job_id}`
- `POST /api/research/contacts/job/{job_id}/select`

If UI says "No contacts on file", it means no selected/saved contact exists for that job yet.

## 11. Application Package: Pipeline Action M8

UI label:

- Application Package (M8)

Code:

- `app/tailoring.py`
- `app/routers/tailoring.py`
- `app/application_builder.py`
- `app/html_renderer.py`
- `app/pdf_renderer.py`
- `app/html_docx.py`
- `app/country_resume_profile.py`

Flow:

1. User runs prepare for a job.
2. LLM creates tailored resume JSON, resume Markdown, and cover letter.
3. Evidence checker verifies generated claims against verified profile/resume evidence.
4. If evidence check fails, output is not saved as application-ready.
5. If evidence check passes, application row is updated.
6. Package builder writes:
   - `resume.md`
   - `resume.pdf`
   - `resume.docx`
   - `resume.txt`
   - cover letter files when available
   - `metadata.json`

Country-specific resume behavior:

- Target country is detected from job country/location.
- Contact line changes dynamically.
- Prompt receives country-specific resume guidance.
- PDF/DOCX use country-specific render style.

Examples:

- Singapore: UK English, compact A4, skills near top, work pass sponsorship line.
- Germany: conservative Lebenslauf-like structure, clear dates, factual bullets.
- Canada: no photo, no unnecessary personal info, concise achievements.

Package status:

- `ready_for_review` means files exist for human review.
- The system does not submit automatically.

## 12. Outreach Drafts: Pipeline Action M9

UI label:

- Outreach Drafts (M9 - draft only)

Code:

- `app/routers/outreach.py`
- `app/outreach.py`

Flow:

1. Requires package/application context.
2. Uses outreach sequence config.
3. Creates Gmail draft when Gmail credential is available.
4. Enforces daily limits.
5. Does not send email automatically.

If UI says "No outreach yet", no draft has been created for that job.

## 13. Daily Pipeline

API:

- `POST /api/daily-run/run`
- `GET /api/daily-run/today`

Code:

- `app/daily_run.py`
- `app/routers/crm.py::daily_run_trigger`

Stage order:

1. discover
2. classify
3. eligibility
4. score
5. hybrid_score
6. select
7. research
8. packages
9. outreach
10. digest

Daily target:

- Default target is 5 packages.
- The target counts qualifying packages, not raw scraped jobs.

Important behavior:

- State is persisted after every stage.
- If a run crashes mid-stage, a later run resumes safely.
- The bar is never lowered to hit the target.
- Packages are created as `ready_for_review`.
- Outreach remains draft-only.

Shortfall reasons include:

- NO_AI_PROVIDER
- AI_QUOTA_EXHAUSTED
- NO_ELIGIBLE_JOBS
- ALL_SCORED_BELOW_CUTOFF
- SOURCES_EXHAUSTED
- RATE_LIMITED
- EVIDENCE_GATE
- PACKAGE_ERROR
- RUN_INTERRUPTED
- TARGET_REACHED

## 14. What Happens If You Run Scraper Now?

When you click/run `POST /api/scrape`:

1. Resume/search config gate checks that search is configured.
2. The app creates a background task.
3. `ALL_SCRAPERS` run with concurrency.
4. New jobs are inserted into `jobs`.
5. Duplicate jobs are merged or marked.
6. Job descriptions are enriched.
7. Locations are classified.
8. Eligibility is run before scoring.
9. AI scoring runs if AI provider is reachable.
10. UI progress updates until done/error.

This path can add jobs and scores, but it does not automatically prepare packages.

## 15. What Happens If You Run Discovery?

When you run `POST /api/discovery/run`:

1. Enabled countries are loaded.
2. Search terms are loaded from your profile/search config.
3. Adapters run by source tier and country relevance.
4. Keyed sources without keys report CONFIGURATION_REQUIRED.
5. Non-relevant sources report NOT_APPLICABLE.
6. Valid jobs are inserted after title and region gates.
7. Source health telemetry is saved in the in-memory run slot.
8. You poll `/api/discovery/status` to see last telemetry.

This path focuses on country-aware discovery and source health. It does not, by itself, run the full application package flow.

## 16. What Happens If You Run Daily Pipeline?

When you run `POST /api/daily-run/run`:

1. Discovery runs with a small pass budget.
2. Classification updates job countries/regions.
3. Eligibility filters jobs.
4. AI scoring runs when available.
5. Hybrid scoring fills deterministic score gaps.
6. Select picks top eligible/scored unpackaged jobs.
7. Contact research runs for selected jobs.
8. Package generation prepares selected jobs.
9. Outreach drafts are attempted for packaged jobs.
10. Digest summary is generated.

This is the closest thing to "do the whole workflow".

## 17. Main Data Tables

Important tables:

- `jobs`: raw/normalized job records
- `sources`: source provenance for jobs
- `job_scores`: AI and hybrid scoring results
- `applications`: prepared/applied/package status
- `app_events`: job timeline events
- `contact_research`: researched contacts
- `contacts`: selected/saved contacts
- `outreach_messages`: outreach draft records
- `application_queue`: queue/review workflow
- `daily_runs`: daily pipeline state/report
- `resumes`: uploaded resumes
- `candidate_evidence`: verified/disputed/do-not-use evidence
- `search_config`: resume-derived search configuration
- `scraper_keys`: API keys for keyed sources

## 18. Why A Job Page Shows Some Actions As Empty

Example:

- Eligibility not evaluated: M5 has not been run or no stored eligibility result exists.
- Hybrid Match not scored yet: M6 hybrid/AI score has not been stored.
- No contacts on file: M7 contact research has not found/selected contacts.
- Application Package ready_for_review: M8 generated package files and metadata.
- No outreach yet: M9 draft was not created.

Timeline messages like "Second evidence check failed" mean the LLM generated claims that the EvidenceChecker could not verify. The app correctly refused to save that output as application-ready.

## 19. What Is Working Now

Based on local DB and files:

- Job ingestion is working. There are 565 stored jobs.
- Country classification is working. Live jobs are distributed across Remote, Singapore, UK, Canada, India, Germany, and more.
- Eligibility is working. 103 jobs are eligible and 421 are blocked as ineligible.
- Scoring is working. 103 scored rows exist.
- Application prep/package generation is working. 4 packages are ready for review.
- Country-specific resume rendering is now wired into prompts and PDF/DOCX output.
- Source provenance is working through the `sources` table.

## 20. Simple Mental Model

Use this model:

Scrape/discovery finds jobs.

Classification understands where they are.

Eligibility decides whether they are allowed to continue.

Scoring decides how good they are.

Research tries to find people.

Prepare builds the resume and cover letter.

Package saves real files.

Outreach drafts messages only.

Nothing should auto-send or auto-apply without human review.
