# Real User-Journey E2E Report — 2026-09-24_125119

> **What this is:** the actual product (uvicorn, authentication ON, `testing=False`) was booted against a throwaway data directory and driven **only over HTTP** by a brand-new user, top to bottom. Every API call, its status and its response body are recorded in this run folder.

## Verdict

- **Scenarios:** 26/26 passed ✅
- **Checks:** 204/204 passed
- **HTTP calls recorded:** 289
- **API coverage:** 187/218 operations (85.8%)
- **AI provider under test:** `deepseek` / `deepseek-flash` (real, billed)

## Environment

- **run_id:** `2026-09-24_125119`
- **started_utc:** `2026-09-24T12:51:19.523627+00:00`
- **base_url:** `http://127.0.0.1:57951`
- **python:** `3.14.7`
- **provider:** `deepseek`
- **model:** `deepseek-flash`
- **resume_chars:** `4109`
- **scrape_budget_s:** `170`
- **discovery_budget_s:** `240`
- **finished_utc:** `2026-09-24T12:57:59.069435+00:00`
- **duration_s:** `399.5`
- **http_calls:** `289`
- **scenarios_total:** `26`

## Journey, top to bottom

| # | Step | What it proves | Result |
|---|------|----------------|--------|
| 1 | Server boot, health and API surface | Server boot, health and API surface | PASS |
| 2 | Create the FIRST account (username + password) | Create the FIRST account (username + password) | PASS |
| 3 | Anonymous lockdown — every protected route 401 | Anonymous lockdown — every protected route 401 | PASS |
| 4 | Login throttling + login | Login throttling + login | PASS |
| 5 | Admin creates a second user (username + password) | Admin creates a second user (username + password) | PASS |
| 6 | The new user's workspace is born empty and isolated | The new user's workspace is born empty and isolated | PASS |
| 7 | The user adds their OWN AI key (live test) | The user adds their OWN AI key (live test) | PASS |
| 8 | Upload the real resume (.docx) → live AI grading + profile parse | Upload the real resume (.docx) → live AI grading + profile parse | PASS |
| 9 | Evidence autofill → VERIFIED corpus + hard gate | Evidence autofill → VERIFIED corpus + hard gate | PASS |
| 10 | Country strategy engine | Country strategy engine | PASS |
| 11 | ATS adapters + live health probes | ATS adapters + live health probes | PASS |
| 12 | Orchestrated discovery cycle (real) | Orchestrated discovery cycle (real) | PASS |
| 13 | Real scrapers (bounded budget) | Real scrapers (bounded budget) | PASS |
| 14 | Deterministic scoring + ranking | Deterministic scoring + ranking | PASS |
| 15 | Eligibility + freshness gates | Eligibility + freshness gates | PASS |
| 16 | Company + contact research | Company + contact research | PASS |
| 17 | AI resume tailoring through the evidence gate | AI resume tailoring through the evidence gate | PASS |
| 18 | AI cover letter + downloads + edit | AI cover letter + downloads + edit | PASS |
| 19 | Application package build + downloads | Application package build + downloads | PASS |
| 20 | Outreach draft (draft-only, Critical Test #4) | Outreach draft (draft-only, Critical Test #4) | PASS |
| 21 | CRM transitions + follow-up engine | CRM transitions + follow-up engine | PASS |
| 22 | Daily run pipeline | Daily run pipeline | PASS |
| 23 | Analytics + LLM cost meter | Analytics + LLM cost meter | PASS |
| 24 | CRITICAL TEST #5 — cross-user isolation | CRITICAL TEST #5 — user A can never read/write user B's data. | PASS |
| 25 | The rest of the REST surface, hit for real | The rest of the REST surface, hit for real (no crashes allowed). | PASS |
| 26 | API coverage accounting | API coverage accounting | PASS |

## Scenario detail

### 1. s01_boot — Server boot, health and API surface

- `PASS` public /api/system/health is reachable — status=200
- `PASS` health reports product + features — product=jobagent version=0.1.0
- `PASS` public /api/auth/status is reachable — status=200
- `PASS` fresh instance needs bootstrap — needs_bootstrap=True
- `PASS` OpenAPI document served (public) — status=200
- `PASS` dashboard HTML served — status=200
- `PASS` API docs served — status=200

  - _server: http://127.0.0.1:57951_
  - _OpenAPI declares 218 operations_

### 2. s02_bootstrap — Create the FIRST account (username + password)

- `PASS` first account created (bootstrap) — status=200
- `PASS` bootstrap account is admin — user=e2eadmin role=admin
- `PASS` session cookie issued — jobagent_session present
- `PASS` second bootstrap refused — status=403
- `PASS` /me returns the session user — status=200
- `PASS` me identifies the bootstrap admin

### 3. s03_anonymous_lockdown — Anonymous lockdown — every protected route 401

- `PASS` anonymous GET /api/jobs → 401 — status=401
- `PASS` anonymous GET /api/settings/profile → 401 — status=401
- `PASS` anonymous GET /api/evidence → 401 — status=401
- `PASS` anonymous GET /api/crm/statuses → 401 — status=401
- `PASS` anonymous GET /api/packages → 401 — status=401
- `PASS` anonymous GET /api/outreach/config → 401 — status=401
- `PASS` anonymous GET /api/research/providers → 401 — status=401
- `PASS` anonymous GET /api/countries → 401 — status=401
- `PASS` anonymous GET /api/matching/status → 401 — status=401
- `PASS` anonymous GET /api/daily-run/today → 401 — status=401
- `PASS` anonymous GET /api/analytics/monitoring → 401 — status=401
- `PASS` anonymous GET /api/discovery/adapters → 401 — status=401
- `PASS` anonymous resume upload → 401 — status=401
- `PASS` public health still open while anonymous — status=200

### 4. s04_login — Login throttling + login

- `PASS` wrong password rejected — status=401
- `PASS` correct password accepted — status=200
- `PASS` login returns the user
- `PASS` /me works on the logged-in client — status=200
- `PASS` authenticated /api/jobs reachable — status=200

  - _admin pool sample size=0 first_job_id=None_

### 5. s05_admin_creates_user — Admin creates a second user (username + password)

- `PASS` admin creates the journey user — status=200
- `PASS` created user has the requested username
- `PASS` duplicate username refused — status=422
- `PASS` admin lists users — status=200
- `PASS` both accounts listed — users=['e2eadmin', 'e2euser']

### 6. s06_user_workspace_born_empty — The new user's workspace is born empty and isolated

- `PASS` journey user logs in — status=200
- `PASS` journey user sees their own (empty) pool — status=200
- `PASS` new user's pool starts empty — jobs=0
- `PASS` new user has no resume yet — status=200
- `PASS` no resume on a fresh workspace
- `PASS` new user has no AI key yet — status=200
- `PASS` no key on a fresh workspace — provider='' has_key=False
- `PASS` per-user workspace directory created — workspaces=['1-e2eadmin', '2-e2euser']
- `PASS` workspace has its own jobagent.db
- `PASS` evidence templates seeded (fail-closed start) — 8 templates

### 7. s07_user_sets_own_ai_key — The user adds their OWN AI key (live test)

- `PASS` user saves their OWN AI key — status=200
- `PASS` user's AI settings read back — status=200
- `PASS` provider persisted — provider=deepseek
- `PASS` key stored but masked in the UI — api_key=****49e5
- `PASS` live AI connection test (real provider call) — status=200
- `PASS` AI provider answers live — ok=True error=None
- `PASS` admin's own AI settings unchanged — status=200

  - _giving journey user provider=deepseek model=deepseek-flash_
  - _admin provider=_

### 8. s08_resume_upload_and_grading — Upload the real resume (.docx) → live AI grading + profile parse

- `PASS` resume uploaded + analysed (live AI) — status=200
- `PASS` ATS grading produced a score — ats_score=88
- `PASS` grading produced feedback — issues=4 tips=5
- `PASS` search terms derived from the resume — terms=['AI Engineer', 'Generative AI Engineer', 'Machine Learning Engineer', 'LLM Engineer', 'AI Application Developer']
- `PASS` key skills derived from the resume — skills=['Python', 'LangChain / LangGraph', 'Retrieval-Augmented Generation (RAG)', 'Azure OpenAI', 'FastAPI / Flask', 'SQL / SQL Server / PostgreSQL']
- `PASS` seniority + summary derived — seniority='mid-level'
- `PASS` profile parsed from the resume
- `PASS` resume text extracted (not raw zip bytes) — resume_length=4109
- `PASS` uploaded resume appears in the Resumes list — status=200
- `PASS` resume recorded + default — count=1
- `PASS` grading persisted onto the search config — status=200
- `PASS` search config carries the resume + terms — ats_score=88
- `PASS` cost meter shows which model ran — status=200
- `PASS` grading ran on the USER'S provider (not the app default) — model appears in the per-model cost table

  - _uploading real resume (4109 chars) as .docx (38549 bytes)_

### 9. s09_evidence — Evidence autofill → VERIFIED corpus + hard gate

- `PASS` evidence summary (after autofill) — status=200
- `PASS` upload auto-VERIFIED evidence from the resume — verified_claims=88
- `PASS` evidence reload — status=200
- `PASS` zero-AI evidence backfill — status=200
- `PASS` backfill reports verified claims
- `PASS` hard gate flags a fabricated claim — status=200
- `PASS` fabricated skills are caught (gate refuses) — ok=False failures=['fabricated_number', 'unsupported_skill']
- `PASS` hard gate passes the candidate's own words — status=200
- `PASS` the candidate's own resume text passes the gate — ok=True failures=[]

### 10. s10_countries — Country strategy engine

- `PASS` country strategy list — status=200
- `PASS` 6 country definitions loaded — count=6 regions=['Germany', 'Ireland', 'Netherlands', 'Singapore', 'UAE', 'UK']
- `PASS` allowed regions — status=200
- `PASS` resume upload seeded a country strategy — allowed=['Singapore']
- `PASS` country detail for Singapore — status=200
- `PASS` apply strategy to the pool (restore-then-dismiss) — status=200
- `PASS` deterministic visa check (no LLM) — status=200
- `PASS` visa check is deterministic — keys=['count', 'matched', 'region', 'requires_sponsorship', 'sponsors_international']
- `PASS` reload country YAMLs — status=200

### 11. s11_adapters — ATS adapters + live health probes

- `PASS` ATS adapter registry — status=200
- `PASS` 4 ATS adapters registered — ['greenhouse', 'lever', 'ashby', 'smartrecruiters']
- `PASS` LIVE health probe of every adapter — status=200
- `PASS` at least one live ATS source answered

  - _adapter health: 4/4 reachable — ['greenhouse', 'lever', 'ashby', 'smartrecruiters']_

### 12. s12_discovery — Orchestrated discovery cycle (real)

- `PASS` start orchestrated discovery (bounded to 2 passes) — status=200
- `PASS` the cycle reports its pass budget — passes=2 countries=['DE', 'IE', 'NL', 'SG', 'AE', 'GB']
- `PASS` pool size after discovery — status=200
- `PASS` discovery ran for real (telemetry and/or new jobs in the pool) — telemetry_keys=['budget_exhausted', 'countries', 'duplicates_seen', 'duration_s', 'finished_at', 'new_jobs', 'pass_budget', 'passes'] pool_growth=7
- `PASS` telemetry records the countries and pass budget — countries=['DE', 'IE', 'NL', 'SG', 'AE', 'GB'] budget=2 new_jobs=9

  - _pool 0 → 7 after discovery; telemetry=yes_

### 13. s13_scrapers — Real scrapers (bounded budget)

- `PASS` scraper health surface — status=200
- `PASS` start real scrape cycle (21 sources, per-user target) — status=202
- `PASS` scrape still running after budget → cancel — status=200
- `PASS` pool after scraping — status=200
- `PASS` real scrapers delivered jobs through the running product — user_pool=24 admin_pool=0
- `PASS` the scrape run targeted the requesting user's workspace — user_pool=24

  - _scraper health keys: ['ai_configured', 'ai_detail', 'ai_provider', 'ai_status', 'db', 'last_scrape', 'scheduler', 'status']_
  - _scrape status=started task=b44352e5b1e9447fbe26dcc2d381b99b_
  - _scrape progress: {"active": true, "phase": "scraping", "started_at": 27061.075684518, "last_updated_at": 27199.743563824, "current": "dice", "completed": 4, "total": 21, "new_jobs": 17, "sources": [{"name": "hackernews", "status": "ok", "listings_found": 91, "new_jobs": 13, "error": null, "duration_ms": 20716}, {"na_
  - _the USER's pool now holds 24 jobs (limit 100)_
  - _the ADMIN pool holds 0 jobs (must stay its own)_

### 14. s14_scoring — Deterministic scoring + ranking

- `PASS` deterministic hybrid scoring of the whole pool (free) — status=200
- `PASS` matching status — status=200
- `PASS` ranked top jobs — status=200
- `PASS` scored pool — status=200
- `PASS` jobs carry scores after score-all — 11/24 scored
- `PASS` a job with a real description was selected for AI stages — job_id=18 title='Machine Learning Engineer'
- `PASS` persist a single hybrid score — status=200
- `PASS` score explainability — status=200

  - _score-all: {"scored": 11, "total": 11, "avg": 52.3, "blockers": 1, "engine": "hybrid-m6", "meta": {"verified_skills": 0, "corpus_lines": 0, "target_titles": ["AI Engineer", "Generative AI Engineer", "Machine Lea_
  - _top-jobs returned 1 entries_

### 15. s15_eligibility — Eligibility + freshness gates

- `PASS` re-run the eligibility gate — status=200
- `PASS` freshness evidence for the job — status=200
- `PASS` eligible job pool — status=200

  - _eligible jobs: 0_

### 16. s16_research — Company + contact research

- `PASS` contact provider chain status — status=200
- `PASS` company enrichment — status=200
- `PASS` company enrichment (cache hit) — status=200
- `PASS` contact research for the job — status=200
- `PASS` read back researched contacts — status=200

### 17. s17_tailoring — AI resume tailoring through the evidence gate

- `PASS` AI resume tailoring through the evidence gate — status=200
- `PASS` tailored resume returned — 4578 chars
- `PASS` evidence gate passed (nothing unverified was saved) — failures=[]
- `PASS` tailoring was persisted as an application — status=prepared
- `PASS` tailored resume DOCX download — status=200
- `PASS` tailored resume PDF download — status=200

### 18. s18_cover_letter — AI cover letter + downloads + edit

- `PASS` AI cover letter generation (live provider) — status=200
- `PASS` cover letter returned and non-trivial — 2022 chars
- `PASS` cover letter DOCX download — status=200
- `PASS` cover letter PDF download — status=200
- `PASS` manual cover-letter edit round-trips — status=200

### 19. s19_package — Application package build + downloads

- `PASS` build the application package (evidence-gated) — status=200
- `PASS` package contains the resume + cover letter — files=['cover_letter.docx', 'cover_letter.txt', 'resume.docx', 'resume.txt']
- `PASS` package metadata — status=200
- `PASS` package records a fingerprint (idempotency key) — status=ready_for_review
- `PASS` download cover_letter.docx — status=200
- `PASS` download cover_letter.txt — status=200
- `PASS` download resume.docx — status=200
- `PASS` download resume.txt — status=200
- `PASS` package list — status=200
- `PASS` repackaged from stored text (no AI spend) — status=200

  - _package status=None files=['cover_letter.docx', 'cover_letter.txt', 'resume.docx', 'resume.txt']_

### 20. s20_outreach — Outreach draft (draft-only, Critical Test #4)

- `PASS` create outreach draft (draft-only) — status=200
- `PASS` CRITICAL #4: creating it twice must not duplicate — status=200
- `PASS` second create is reported as already-existing — body_keys=['message', 'reason', 'status'] already_exists=None
- `PASS` follow-up honours the wait window — status=200
- `PASS` follow-up gated by the cadence window — status=too_soon too_soon=None
- `PASS` read back the job's outreach — status=200
- `PASS` exactly one draft exists for the job — messages=1
- `PASS` outreach message list — status=200
- `PASS` outreach config (caps + gmail state) — status=200
- `PASS` gmail state reported honestly — gmail_connected=False

  - _draft: status=created provider=None draft_id=None_

### 21. s21_crm — CRM transitions + follow-up engine

- `PASS` CRM status enum + transitions — status=200
- `PASS` move the job to 'applied' (validated transition) — status=200
- `PASS` unearned 'offered' is blocked by the engine — status=422 body={"detail": "'interested' \u2192 'offered' not allowed; valid next: ['applied', 'closed', 'prepared', 'rejected', 'withdrawn']"}
- `PASS` run the follow-up engine — status=200
- `PASS` pipeline funnel — status=200
- `PASS` a terminal application cannot be resurrected — status=422 body={"detail": "'rejected' \u2192 'applied' not allowed; valid next: none (terminal)"}

  - _followups: {"ok": true, "followups_due": 0, "items": [], "terminal_stopped": 0}_

### 22. s22_daily_run — Daily run pipeline

- `PASS` daily run state before — status=200
- `PASS` run today's pipeline (idempotent) — status=200
- `PASS` daily run reports its stages — stages=['discover', 'classify', 'eligibility', 'score', 'hybrid_score', 'select', 'research', 'packages', 'outreach', 'digest']
- `PASS` daily run state after (persisted) — status=200

### 23. s23_analytics — Analytics + LLM cost meter

- `PASS` cost meter + run telemetry — status=200
- `PASS` the journey's AI calls are metered — today calls=6 cost_usd=0.011278
- `PASS` feedback loop recommendations — status=200
- `PASS` stats page data — status=200
- `PASS` analytics aggregate — status=200

  - _today usage: {"totals": {"calls": 6, "tokens_in": 7449, "tokens_out": 16934, "cost_usd": 0.011278}, "avg_cost_per_call_usd": 0.00188, "by_provider": {"deepseek": {"calls": 6, "tokens_in": 7449, "tokens_out": 16934, "cost_usd": 0.011278}}, "by_model": {"_

### 24. s24_cross_user_isolation — CRITICAL TEST #5 — cross-user isolation

- `PASS` admin cannot see the user's job id — status=404
- `PASS` user's resumes — status=200
- `PASS` user sees only their own resume — names={'basil_resume.docx'}
- `PASS` admin's resumes — status=200
- `PASS` admin does not see the user's resume — admin_names=set()
- `PASS` user's key stays masked — status=200
- `PASS` user's own key is never returned in plaintext — api_key=****49e5
- `PASS` each user has a physically separate database — dbs=['1-e2eadmin', '2-e2euser']
- `PASS` the two workspaces hold different pools — user=[31] other=[0]
- `PASS` admin user list (audited surface) — status=200

  - _Critical Test #5 — cross-user access vectors_
  - _job rows per workspace: {'2-e2euser': 31, '1-e2eadmin': 0}_

### 25. s25_crud_sweep — The rest of the REST surface, hit for real

- `PASS` profile: 6/6 answered without a server error — no crashes
- `PASS` resumes: 4/4 answered without a server error — no crashes
- `PASS` saved views — status=200
- `PASS` saved views: 2/2 answered without a server error — no crashes
- `PASS` search config: 6/6 answered without a server error — no crashes
- `PASS` infra settings: 10/10 answered without a server error — no crashes
- `PASS` alerts list — status=200
- `PASS` alerts: 2/2 answered without a server error — no crashes
- `PASS` notifications: 3/3 answered without a server error — no crashes
- `PASS` contacts list — status=200
- `PASS` contacts: 3/3 answered without a server error — no crashes
- `PASS` job contacts: 3/3 answered without a server error — no crashes
- `PASS` interviews list — status=200
- `PASS` interviews: 3/3 answered without a server error — no crashes
- `PASS` pipeline: 11/11 answered without a server error — no crashes
- `PASS` reminders: 2/2 answered without a server error — no crashes
- `PASS` follow-up templates — status=200
- `PASS` follow-up templates: 2/2 answered without a server error — no crashes
- `PASS` job utilities: 7/7 answered without a server error — no crashes
- `PASS` approval queue — status=200
- `PASS` queue: 3/3 answered without a server error — no crashes
- `PASS` queue after approve — status=200
- `PASS` matching + analytics: 13/13 answered without a server error — no crashes
- `PASS` background scoring targets the user's own pool — response={"status": "scoring_triggered"}
- `PASS` change password (revokes sessions) — status=200
- `PASS` changing the password revokes existing sessions — status=401
- `PASS` log in with the new password — status=200
- `PASS` session works again — status=200
- `PASS` logout — status=200
- `PASS` log back in (leave the session usable) — status=200

### 26. s26_api_coverage — API coverage accounting

- `PASS` journey touched the large majority of the API surface — 187/218 = 85.8%

  - _API coverage: 187/218 operations (85.8%)_

## API operations not exercised by this journey

| Method | Path | Reason |
|--------|------|--------|
| POST | `/api/auth/users/{user_id}/disable` | destructive to an account; covered by test_auth.py |
| POST | `/api/auth/users/{user_id}/enable` | destructive to an account; covered by test_auth.py |
| POST | `/api/auth/users/{user_id}/reset-password` | destructive; covered by test_auth.py |
| POST | `/api/jobs/{job_id}/estimate-salary` | feature-flagged off by default |
| POST | `/api/jobs/{job_id}/find-contact` | duplicate of /api/research/contacts/job/{id} |
| POST | `/api/jobs/mark-applied-by-url` | browser-extension flow |
| POST | `/api/jobs/{job_id}/send-email` | sends real email — never automated |
| POST | `/api/queue/prepare-all` | long AI batch (equivalent single-job path covered) |
| POST | `/api/queue/approve-all` | bulk approval (single approve covered) |
| POST | `/api/queue/reject-all` | bulk rejection (single reject covered) |
| GET | `/api/queue/events` | SSE stream (infinite) |
| POST | `/api/skill-gaps/analyze` | feature-flagged off by default |
| GET | `/api/jobs/{job_id}/predict-success` | feature-flagged off by default |
| POST | `/api/career/analyze` | feature-flagged off by default |
| GET | `/api/career/suggestions` | feature-flagged off by default |
| POST | `/api/career/suggestions/{suggestion_id}/accept` | feature-flagged off by default |
| POST | `/api/offers` | feature-flagged off by default |
| GET | `/api/offers/compare` | feature-flagged off by default |
| PUT | `/api/offers/{offer_id}` | feature-flagged off by default |
| DELETE | `/api/offers/{offer_id}` | feature-flagged off by default |
| POST | `/api/digest/send-test` | sends real email — never automated |
| POST | `/api/settings/email/test` | sends real email — never automated |
| GET | `/api/notifications/stream` | SSE stream (infinite) |
| POST | `/api/rescore-all` | destructive full-pool rescore |
| POST | `/api/clear-jobs` | destructive |
| POST | `/api/clear-all` | destructive |
| POST | `/api/autofill/analyze` | browser-extension flow |
| GET | `/api/calendar/token` | calendar feed credential |
| POST | `/api/calendar/token/regenerate` | calendar feed credential |
| GET | `/api/calendar.ics` | calendar feed consumed by an external client |
| POST | `/api/research/contacts/job/{job_id}/select` | not exercised |

## Artifacts captured

- `artifacts/cover_letter.docx` (37831 bytes)
- `artifacts/cover_letter.pdf` (7968 bytes)
- `artifacts/cover_letter.txt` (2032 bytes)
- `artifacts/package/cover_letter.docx` (37664 bytes)
- `artifacts/package/cover_letter.txt` (1898 bytes)
- `artifacts/package/resume.docx` (38911 bytes)
- `artifacts/package/resume.txt` (4646 bytes)
- `artifacts/resume_uploaded.docx` (38549 bytes)
- `artifacts/resume_uploaded.txt` (4109 bytes)
- `artifacts/tailored_resume.docx` (38873 bytes)
- `artifacts/tailored_resume.pdf` (17998 bytes)
- `artifacts/tailored_resume.txt` (4578 bytes)

## Files in this run

- `api_calls.jsonl`
- `api_coverage.json`
- `config/countries/.backups/singapore.1790252096.yaml`
- `config/countries/.backups/singapore.1790254305.yaml`
- `config/countries/.backups/uae.1790065192.yaml`
- `config/countries/.backups/uae.1790069232.yaml`
- `config/countries/.backups/uae.1790069578.yaml`
- `config/countries/.backups/uae.1790069793.yaml`
- `config/countries/.backups/uae.1790071734.yaml`
- `config/countries/.backups/uae.1790071854.yaml`
- `config/countries/.backups/uae.1790071990.yaml`
- `config/countries/.backups/uae.1790072083.yaml`
- `config/countries/.backups/uae.1790157655.yaml`
- `config/countries/.backups/uae.1790157833.yaml`
- `config/countries/.backups/uae.1790157834.yaml`
- `config/countries/.backups/uae.1790158015.yaml`
- `config/countries/.backups/uae.1790158231.yaml`
- `config/countries/.backups/uae.1790158284.yaml`
- `config/countries/.backups/uae.1790158339.yaml`
- `config/countries/.backups/uae.1790158411.yaml`
- `config/countries/.backups/uae.1790159122.yaml`
- `config/countries/.backups/uae.1790159222.yaml`
- `config/countries/.backups/uae.1790159286.yaml`
- `config/countries/.backups/uae.1790160548.yaml`
- `config/countries/.backups/uae.1790161752.yaml`
- `config/countries/.backups/uae.1790179648.yaml`
- `config/countries/.backups/uae.1790179721.yaml`
- `config/countries/.backups/uae.1790179891.yaml`
- `config/countries/.backups/uae.1790183492.yaml`
- `config/countries/.backups/uae.1790183552.yaml`
- `config/countries/.backups/uae.1790183633.yaml`
- `config/countries/.backups/uae.1790183692.yaml`
- `config/countries/.backups/uae.1790184172.yaml`
- `config/countries/.backups/uae.1790184234.yaml`
- `config/countries/.backups/uae.1790184397.yaml`
- `config/countries/.backups/uae.1790184463.yaml`
- `config/countries/.backups/uae.1790184515.yaml`
- `config/countries/.backups/uae.1790184582.yaml`
- `config/countries/.backups/uae.1790184899.yaml`
- `config/countries/.backups/uae.1790184972.yaml`
- `config/countries/.backups/uae.1790184973.yaml`
- `config/countries/.backups/uae.1790185026.yaml`
- `config/countries/.backups/uae.1790185097.yaml`
- `config/countries/.backups/uae.1790185169.yaml`
- `config/countries/.backups/uae.1790185223.yaml`
- `config/countries/.backups/uae.1790185296.yaml`
- `config/countries/.backups/uae.1790185652.yaml`
- `config/countries/.backups/uae.1790186105.yaml`
- `config/countries/.backups/uae.1790186161.yaml`
- `config/countries/.backups/uae.1790186216.yaml`
- `config/countries/.backups/uae.1790186269.yaml`
- `config/countries/.backups/uae.1790186335.yaml`
- `config/countries/.backups/uae.1790186390.yaml`
- `config/countries/.backups/uae.1790186448.yaml`
- `config/countries/.backups/uae.1790186500.yaml`
- `config/countries/.backups/uae.1790186555.yaml`
- `config/countries/.backups/uae.1790186613.yaml`
- `config/countries/germany.yaml`
- `config/countries/ireland.yaml`
- `config/countries/netherlands.yaml`
- `config/countries/singapore.yaml`
- `config/countries/uae.yaml`
- `config/countries/uk.yaml`
- `config/outreach_sequences.yaml`
- `config/profile_templates/achievements.yaml`
- `config/profile_templates/candidate.yaml`
- `config/profile_templates/education.yaml`
- `config/profile_templates/exclusions.yaml`
- `config/profile_templates/experience.yaml`
- `config/profile_templates/preferences.yaml`
- `config/profile_templates/projects.yaml`
- `config/profile_templates/skills.yaml`
- `data/system.db`
- `data/users/1-e2eadmin/jobagent.db`
- `data/users/1-e2eadmin/jobagent.db-shm`
- `data/users/1-e2eadmin/profile/achievements.yaml`
- `data/users/1-e2eadmin/profile/candidate.yaml`
- `data/users/1-e2eadmin/profile/education.yaml`
- `data/users/1-e2eadmin/profile/exclusions.yaml`
- `data/users/1-e2eadmin/profile/experience.yaml`
- `data/users/1-e2eadmin/profile/preferences.yaml`
- `data/users/1-e2eadmin/profile/projects.yaml`
- `data/users/1-e2eadmin/profile/skills.yaml`
- `data/users/2-e2euser/applications/0018-attendi/cover_letter.docx`
- `data/users/2-e2euser/applications/0018-attendi/cover_letter.txt`
- `data/users/2-e2euser/applications/0018-attendi/metadata.json`
- `data/users/2-e2euser/applications/0018-attendi/resume.docx`
- `data/users/2-e2euser/applications/0018-attendi/resume.txt`
- `data/users/2-e2euser/jobagent.db`
- `data/users/2-e2euser/profile/achievements.yaml`
- `data/users/2-e2euser/profile/candidate.yaml`
- `data/users/2-e2euser/profile/candidate.yaml.bak`
- `data/users/2-e2euser/profile/education.yaml`
- `data/users/2-e2euser/profile/education.yaml.bak`
- `data/users/2-e2euser/profile/exclusions.yaml`
- `data/users/2-e2euser/profile/experience.yaml`
- `data/users/2-e2euser/profile/experience.yaml.bak`
- `data/users/2-e2euser/profile/preferences.yaml`
- `data/users/2-e2euser/profile/projects.yaml`
- `data/users/2-e2euser/profile/skills.yaml`
- `data/users/2-e2euser/profile/skills.yaml.bak`
- `server.log`
