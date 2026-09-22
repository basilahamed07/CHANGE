# ARCHITECTURE DECISION

Date: 2026-09-21
Decision: **CareerPulse (tcpsyn/CareerPulse, MIT) is the base.** Four other repos
contribute ported modules (MIT only) and concepts. Every significant decision below
is classified KEEP / EXTEND / REPLACE / REMOVE / NEW with rationale.

Governing rules (from master prompt, enforced everywhere):
- extend > rewrite · interfaces/adapters > hard-coded vendors · deterministic code >
  unnecessary LLM calls · verified evidence > impressive hallucinations · direct
  employer/ATS links > aggregator links · ONE coherent product, ONE DB model, ONE
  config system, ONE UX.

---

## D1 — Base application shell: KEEP (CareerPulse)

Keep from CareerPulse: FastAPI `create_app` factory + lifespan with dual DB
connections (request + background), vanilla-JS SPA (no build step), OpenAPI at /docs,
12-router API layout, health/progress endpoints, Docker + uv setup.

**Why:** it is the only reference that is a complete, self-hosted web product with
1,248 tests, CI, and operational tooling. Rewriting the shell would spend weeks
reproducing what already works.

**Adaptations:** rename env prefix `JOBFINDER_` → `JOBAGENT_`; strip recording
scripts and extension demo assets; DB file renamed; all AI provider keys via
`JOBAGENT_*` env vars.

## D2 — Database: EXTEND (CareerPulse schema)

Keep the proven table set: jobs, sources, job_scores, applications, app_events,
companies, contacts, contact_interactions, job_contacts, search_config, ai_settings,
saved_views, resumes, application_queue, follow_up_templates, reminders, work_history,
education, certifications, skills, languages.

Add (NEW tables): `candidate_evidence` (value/status/source/last_verified),
`countries`, `job_duplicates` (repost relationships), `job_contacts` gains
confidence + relationship fields, `outreach_messages` (audience/channel/sequence
position), `email_threads` (Gmail ids), `followups`, `search_runs` +
`generation_runs` (run telemetry: counts, provider_errors, llm_cost),
`analytics_events`, `documents` (generated DOCX versions + hashes).

**Why:** SQLite + WAL + auto-migration matches the single-user personal-tool
profile; CareerPulse's migrations pattern makes adding tables low-risk. All
unique constraints designed so a duplicate job can never become a second
application (Phase 9/31 critical test).

## D3 — Scraper/discovery layer: KEEP base, PORT ATS adapters

Keep `BaseScraper` (backoff on 429/5xx, Retry-After, per-domain rate limiting, UA
rotation) as the execution chassis for ALL source adapters.

Introduce `JobSourceAdapter` interface (search / get_job / normalize /
health_check) as the formal contract (NEW), then:
- **PORT** Greenhouse/Lever/Ashby/SmartRecruiters logic from ai-job-search
  (MIT) wrapped in the interface → structured ATS-first discovery.
- Keep CareerPulse's remotive/arbeitnow/jobicy/remoteok/himalayas as secondary
  sources; keep greenhouse.py as an additional reference but supersede with the
  ported ATS adapter.
- Design stubs for Workday/Rippling/Dayforce/career pages (implement later).
- LinkedIn: guest-API style only, off by default (ToS discipline inherited from
  ai-job-search).

**Why:** ATS endpoints give fresher, structured, first-party listings; aggregators
are demoted to fallback. Discovery stays fully decoupled from scoring.

## D4 — Job normalization + dedup: EXTEND + NEW

Keep JobListing normalization discipline; extend the canonical `Job` model with
the master prompt's field set (canonical_url, direct_apply_url, company_domain,
work_type, salary range/currency, visa_information, sponsorship_status,
required/preferred_skills, experience bounds, freshness fields, content_hash).

Dedup replaces single SHA-256(title+company+url) with multi-signal matching:
source_job_id, canonical URL, normalized company, normalized title, location,
description hash, fuzzy similarity — with repost relationships stored in
`job_duplicates`. A repost can never auto-create an application (manual approval).

## D5 — Freshness verification: NEW

Three states: VERIFIED_FRESH / STALE / DATE_UNKNOWN with posted-date evidence
stored on the job. `MAX_JOB_AGE_DAYS` default 7. DATE_UNKNOWN is NEVER treated
as fresh (must go to REVIEW). This has no equivalent in any reference — CareerPulse's
last_seen_at is kept as *secondary* corroboration.

## D6 — Eligibility engine: NEW (PORT FilterStats pattern)

Deterministic pre-LLM gate returning ELIGIBLE / REVIEW / INELIGIBLE with reason
codes (EXPERIENCE_TOO_HIGH, UNSUPPORTED_REQUIRED_SKILL, COUNTRY_RESTRICTION,
CLEARANCE_REQUIRED, ROLE_MISMATCH, STALE_JOB, EXCLUDED_COMPANY, ...). Port the
FilterStats/FilterResult reject-reason accounting style from ai-job-search (MIT).
**No LLM call ever runs on an INELIGIBLE job** (cost rule).

## D7 — Matching engine: REPLACE CareerPulse matcher

CareerPulse's JobMatcher returns a single LLM-generated score. Replace with the
hybrid engine: deterministic components (skill, experience, role, location, visa,
recency, preference; TF-IDF ATS overlap ported as a concept from job_search_agent —
reimplemented, zero code taken) + LLM-assisted semantic_match (RAG-retrieved
evidence) → configurable weighted overall_score with component breakdown,
matched/missing requirements, hard_blockers, advantages, plain explanation.
Python owns the arithmetic; the LLM never emits the final number.

## D8 — RAG / semantic layer: EXTEND CareerPulse embeddings + NEW abstraction

Keep CareerPulse's embeddings job + `embedding_settings`; wrap behind an
EmbeddingProvider abstraction (local sentence-transformers default — no API cost;
OpenAI-compatible optional). Collections over VERIFIED evidence only
(experience/projects/skills/achievements). Retrieval selects the narrow evidence
slice sent to any generation prompt — never the full candidate history.

## D9 — Candidate evidence system: NEW (core differentiator)

`data/profile/*.yaml` with per-claim status VERIFIED/UNVERIFIED/DISPUTED/
DO_NOT_USE, source, last_verified. `EvidenceChecker` validates every generated
resume/cover letter/outreach: invented numbers → fail (algorithm ported from
job-application-pipeline `_fabrication_check`, MIT, hardened from warning →
hard gate); unsupported skills/employers/certs/dates → fail + log + regenerate.
LLMs are contractually forbidden from introducing skills, metrics, employers,
titles, certifications, education, visa status, or project outcomes.

## D10 — Country strategy: NEW

`config/countries/*.yaml` per Phase 5 (targets, keywords, locations, visa/
sponsorship keywords, sources, thresholds, daily targets, outreach windows,
follow-up days). Loaded by a CountryRegistry; adding a country = adding a YAML
file. Scheduler creates independent per-country jobs. No core code changes for
a new country.

## D11 — Company research: KEEP+EXTEND

Keep company_research.py + cache-per-company (never re-research for every job).
Extend stored fields: domain, careers URL, LinkedIn URL, industry, description,
team/AI-product clues, recruiting info, evidence links.

## D12 — Contacts: PORT + NEW interface

`ContactProvider` interface with adapters: Hunter (port from
job-application-pipeline, MIT), Apollo (port), ManualResearch (human-in-loop).
Contact model gains role_type (RECRUITER / TALENT_ACQUISITION / LIKELY_HIRING_MANAGER
/ TEAM_MEMBER / POTENTIAL_REFERRAL / UNKNOWN), confidence HIGH/MEDIUM/LOW,
relationship_to_job, and a human-readable "why selected". Title classification
heuristics ported from job-application-pipeline `_classify_title`. Low-confidence
contacts require approval before outreach.

## D13 — Resume/cover letter generation: EXTEND CareerPulse tailoring

Keep tailoring.py + docx_generator.py + pdf_generator.py (DOCX primary, PDF
optional later via renderer abstraction). Bind generation to the evidence store:
reorder/select/rephrase/terminology/ATS-alignment allowed; invention forbidden.
Verifier-gate pattern (apply-pilot concept, implemented in Python): generate →
EvidenceChecker → on failure log offending claims and regenerate once → else
mark for human review.

## D14 — Application package: NEW layout

`root/applications/{country}/{company}/{role}/` with job.json, research.md,
match_report.md, resume.docx, cover_letter.docx, outreach.md, contacts.json,
metadata.json (hashes, profile version, evidence-check result, model, status).
Hash-based idempotency: unchanged inputs → no regeneration.

## D15 — Outreach: PORT apply-pilot structure, config-driven

Audience-specific generators (recruiter / hiring manager / referral), channels
(LinkedIn note, LinkedIn DM, email, follow-up email), sequence steps defined in
config (Day 0 apply → Day 0/1 recruiter → Day 2 referral → Day 4/5 follow-up →
Day 7+ final) with anti-spam guards (per-contact caps, dedup across duplicate
jobs, stop-on-terminal-status). Same message never sent to two audiences.

## D16 — Gmail: PORT job-application-pipeline behind NEW GmailProvider

GmailProvider interface: create_draft / update_draft / find_thread / find_replies.
Draft-only default; sending requires an explicit, separately-configured approval
mechanism (`JOBAGENT_ALLOW_SEND=true` + per-draft approval). Idempotency extended
from subject-dedup to subject+thread dedup; draft/thread ids persisted in
`email_threads`. OAuth desktop flow ported (MIT).

## D17 — CRM/statuses/events: KEEP+EXTEND

Keep applications + app_events append-only history. Extend status enum to the
Phase 23 set (DISCOVERED → … → OFFER / WITHDRAWN / ARCHIVED). Status changes
create events; history never overwritten.

## D18 — Scheduler + daily run: KEEP APScheduler + NEW daily pipeline

Keep the 8-job schedule; make scrape jobs per-country. New daily orchestration
(Phases 25–26): discover → normalize → dedupe → verify → eligibility → score →
select → research → contacts → package → outreach → drafts → follow-ups → digest.
`daily_target` counts NEW QUALIFYING PACKAGES (not URLs); shortfall reported with
reasons; eligibility bar never lowered to hit targets.

## D19 — Response monitor + follow-ups: NEW

Email classifier (RECRUITER_REPLY / APPLICATION_CONFIRMATION / ASSESSMENT /
INTERVIEW_INVITATION / REJECTION / OFFER / DELIVERY_FAILURE / OTHER) with
confidence; low confidence → REVIEW, never silent high-impact state change.
Follow-up engine tracks dates/counts, generates reminders, hard-stops after
rejection/withdrawal/closed/no-contact. Sequence config governs cadence.

## D20 — Feedback loop: NEW + CONCEPT (job_search_agent, no code)

Outcome tracking by country/role/source/company-type/score/skills/resume-version/
contact strategy; funnel metrics; recommendations generated for HUMAN review.
Scoring weights are never auto-rewritten on small samples.

## D21 — API + UI: KEEP+EXTEND

Keep all CareerPulse routers (jobs, tailoring, pipeline, queue, contacts,
analytics, settings, alerts, scraping, autofill, interviews, calendar). Add:
/api/jobs/{id}/score|research|contacts|prepare, /api/applications/{id}/status,
/api/outreach/{id}/draft, /api/countries (+PUT), /api/search/run,
/api/analytics/summary, /api/system/health. UI: keep SPA structure; add Kanban
board, Job Detail (full Phase 33 spec), Contacts, Countries, Search Runs,
Analytics pages. Extension: KEEP autofill/overlay (bonus value) but it is
non-core to this build.

## D22 — REMOVE (from CareerPulse base, with reasons)

- Salary calculator / offer comparison / W2-1099-C2C tax estimation — US-centric,
  out of scope for international AI-role search. (Revisit post-MVP if Basil wants it.)
- Career trajectory intelligence, success predictor — nice-to-have; keep code
  dormant behind feature flag until M12+ (do not delete working features
  unnecessarily; disabled, not removed, where removal is risky).
- US-specific EEO/military profile sections — replaced by evidence YAML model.
- Aggregator-first source defaults — demoted in favor of ATS adapters.
- Recording/demo scripts (record-*.mjs, take-*.mjs, workday-*.mjs) — dev tooling,
  not product. Deleted in root/.

## D23 — CLI: NEW (`jobagent`)

Typer-based CLI: search --country X / --all, prepare JOB_ID, contacts JOB_ID,
daily, followups, analytics, health. CLI and web UI call the SAME service layer;
zero business logic in either entrypoint.

## D24 — Config: NEW unified system

One config spine: `JOBAGENT_` env vars (secrets/runtime) + YAML files
(countries/, search profiles, outreach sequences, scoring weights, exclusions)
+ DB-backed settings (UI-editable, CareerPulse pattern). Precedence: env > DB
settings > YAML defaults. `.env.example` documents every key; secrets never in
YAML/git; values masked in logs.

## D25 — Testing: KEEP philosophy + NEW critical suite

Keep CareerPulse's pytest structure and provider-mock approach. Required new
critical tests: (1) evidence gate blocks unverified skill claims; (2) cross-source
duplicate cannot create two applications; (3) DATE_UNKNOWN never VERIFIED_FRESH;
(4) outreach double-run never creates duplicate Gmail drafts. Plus unit/integration/
API/DB/dedup/eligibility/scoring/scheduler tests.

## D26 — Resilience & cost control: KEEP+NEW

Keep BaseScraper backoff/rate-limit/circuit-breaker; extend to all providers
(contact, email, embeddings, LLM) with provider fallback (Hunter down ≠ pipeline
down). NEW: run telemetry (run_id, counts, provider_errors, LLM cost), caches for
research/embeddings/contacts/analysis, eligibility-before-LLM gating.

## Target data flow (final)

```
JOB SOURCES (ATS adapters → aggregators → career pages)
   → Discovery Engine (multi-pass, per-country roles × sources)
   → Normalization (canonical Job model)
   → Deduplication (multi-signal + repost links)
   → Freshness Verification (FRESH/STALE/DATE_UNKNOWN + evidence)
   → Eligibility Engine (deterministic, reason codes)
   → Matching Engine (deterministic components ⊕ RAG semantic)
   → Priority Engine (weighted score + human targets)
   → Research Engine (company cache ⊕ ContactProvider)
   → Application Builder (resume ⊕ CL ⊕ outreach, EvidenceChecker-gated)
   → Human Review (approval gates)
   → GmailProvider (DRAFT ONLY)
   → Application Tracker (append-only events)
   → Follow-Up Engine (sequence config) ←→ Response Monitor (classify→review)
   → Analytics → Feedback Loop (recommendations to human)
```

## Risks acknowledged in this decision

1. CareerPulse is feature-rich; root/ must stay ONE product — aggressive pruning
   (D22) and strict milestone scoping mitigate sprawl.
2. Porting ai-job-search adapter code requires reformatting to our interface —
   budgeted in M4, tests in M14.
3. Contact-provider data quality (Hunter free tier limits) — confidence model +
   manual provider mitigate.
4. LLM cost creep — eligibility gating + caching + local-Ollama option control it.
5. job_search_agent has no license — concept-only usage is enforced in review.
