# jobagent — Complete User Guide

> **Product:** Personal International AI Job Search + Recruiter Outreach System
> **Owner:** Basil Ahamed H
> **Last updated:** 2026-09-23 (all milestones M1–M14 complete)
>
> This guide explains **every process** in the system, **what each one does**,
> **what YOU can do**, and **exactly how to use it** — step by step.

---

## Table of Contents

1. [What This System Is (Big Picture)](#1-what-this-system-is)
2. [The 10 Processes of the Daily Pipeline](#2-the-10-processes)
3. [Every Feature, Grouped](#3-every-feature)
4. [Step-by-Step: First-Time Setup](#4-first-time-setup)
5. [Step-by-Step: Daily Usage](#5-daily-usage)
6. [Step-by-Step: After You Apply (CRM + Follow-ups)](#6-crm--follow-ups)
7. [Using the CLI](#7-using-the-cli)
8. [AI Providers & DeepSeek (your $2 setup)](#8-ai-providers--deepseek)
9. [Response Monitor & Feedback Loop](#9-response-monitor)
10. [Costs, Budget & Monitoring](#10-costs)
11. [Safety Rules the System Enforces](#11-safety)
12. [Troubleshooting](#12-troubleshooting)
13. [Command Cheat-Sheet](#13-cheat-sheet)

---

<a name="1-what-this-system-is"></a>
## 1. What This System Is (Big Picture)

One coherent product that takes you from **"no applications"** to **"tracked, followed-up interviews"**:

```
discover → normalize → dedupe → verify freshness → eligibility →
match/score → rank → research company & contacts → tailor resume (DOCX) →
cover letter → outreach DRAFTS (never auto-send) → you review & send →
track status → follow-up reminders → response monitoring → feedback loop
```

**Hard guarantees baked into the code:**

| Rule | What it means for you |
|------|----------------------|
| Evidence system is sacred | The AI can NEVER invent a skill, date, employer, metric, or certification on your resume. Every generated resume passes a hard EvidenceChecker gate. |
| Drafts, never sends | Outreach emails are created as **Gmail drafts** (or local draft files). The system has **no send method at all** — nothing goes out without YOU clicking send in Gmail. |
| Deterministic for deterministic problems | Dates, dedup, filters, math, status transitions = pure Python. The LLM only writes phrasing/research interpretation. |
| Country is config | Adding a country = drop one YAML file in `config/countries/`. Zero code changes. |
| Daily target counts PACKAGES | The daily goal is qualifying, evidence-gated application packages — never raw scraped URLs. |

---

<a name="2-the-10-processes"></a>
## 2. The 10 Processes of the Daily Pipeline

The daily run (`POST /api/daily-run/run`) executes these stages **in this exact order**, persisting state before each stage so a crash resumes where it stopped:

| # | Stage | What it does | AI? |
|---|-------|--------------|-----|
| 1 | **discover** | Runs job discovery: enabled countries × search terms × adapters (Greenhouse, Lever, Ashby, SmartRecruiters) + feed scrapers (Remotive, Arbeitnow, Jobicy, HN, etc.). Budget-capped (24 passes/cycle, 200 listings/pass). | No |
| 2 | **classify** | Assigns each job to a target country/region (rule-based first; LLM only for ambiguous ones). Syncs your enabled countries. | Mostly no |
| 3 | **eligibility** | Deterministic gate chain on every new job: dismissed → freshness (max 7 days, DATE_UNKNOWN is terminal) → evidence → repost-pending. Ineligible jobs get a machine-readable reason code. | No |
| 4 | **score** | AI scores eligible jobs (title, skills, seniority, ATS fit). Circuit-breaker: if quota dies, it stops gracefully and hands over. | Yes |
| 5 | **hybrid_score** | Free deterministic scoring of whatever AI could not score: skills 0.35 / role 0.15 / location 0.10 / visa 0.10 / recency 0.10 / semantic-TF-IDF 0.20. Hard blockers (no sponsorship, DO_NOT_USE skills) cap the score at 25. **The pool is never left unscored.** | No |
| 6 | **select** | Picks top eligible + scored jobs (above cutoff, best score first) toward today's target. | No |
| 7 | **research** | For selected jobs: company careers/LinkedIn URL discovery + contact research through the provider chain: **Manual (your saved contacts) → Hunter → Apollo → Web search**. Cache-first (7-day TTL). | No* |
| 8 | **packages** | Builds the application package per selected job: `resume.docx` (DOCX-first) + `cover_letter.docx` + `.txt` versions + `metadata.json` (audit trail: fingerprints, hashes, model used). Evidence gate applies — anything unverified is refused, nothing is written. | Yes |
| 9 | **outreach** | Creates **DRAFT-ONLY** outreach email for packages that have a contact: recruiter / hiring_manager / referral / followup sequence, placeholders filled, caps enforced (12/day, 2/company/day). | Yes |
| 10 | **digest** | Closes the run: counts today's NEW qualifying packages vs target, writes shortfall reasons. | No |

\* Hunter/Apollo are external APIs, not LLMs.

**Your daily target** = number of NEW qualifying packages per day (default 5, cutoff score 60). Shortfall is reported honestly with reasons like `AI_QUOTA_EXHAUSTED`, `NO_ELIGIBLE_JOBS`, `SOURCES_EXHAUSTED` — the bar is never lowered.

**Where to run it:**
- **UI:** Settings → Daily Run panel, or Queue page
- **API:** `POST /api/daily-run/run` (idempotent — safe to call again; completed stages are never re-run)
- **Check status:** `GET /api/daily-run/today` or CLI `jobagent daily`

---

<a name="3-every-feature"></a>
## 3. Every Feature, Grouped

### 3.1 Discovery (finding jobs)
- **4 ATS adapters** (Greenhouse, Lever, Ashby, SmartRecruiters) — real ATS APIs, health-probed live.
- **Feed scrapers** (Remotive, Arbeitnow, Jobicy, RemoteOK, Himalayas, HN Who's Hiring, LinkedIn, Indeed, Dice, Working Nomads, Landing.Jobs, MyCareersFuture, 4-Day Week, Recruitee).
- **Cross-source dedup** — the same job from 2 sources = 1 job + 2 source records (Critical Test #2).
- **Search self-correction telemetry** — each pass records stop reason: TARGET_REACHED / NO_MORE_RESULTS / SOURCES_EXHAUSTED / RATE_LIMITED / SOURCE_FAILURE.
- **UI:** Jobs page (`#/`) — feed with filters. API: `GET /api/discovery/adapters|health|status`, `POST /api/discovery/run`.

### 3.2 Country Strategy (where you want to work)
- 6 seeded countries: **Germany, Netherlands, Ireland, UK, Singapore, UAE** (`config/countries/*.yaml`).
- Per-country: cities, work types (remote/hybrid/onsite), visa/sponsorship keywords, salary floor, extra search terms.
- Enable/disable a country → jobs auto re-classified (disable dismisses reversible-flagged jobs; re-enable RESTORES them).
- Visa engine is deterministic keyword scan — no LLM.
- **UI/API:** `GET /api/countries`, `PUT /api/countries/{region}`, `POST /api/countries/{region}/visa-check`, `POST /api/countries/apply|reload`.

### 3.3 Evidence System (your verified profile)
- 8 YAML profile files in `data/profile/`: candidate, skills, experience, projects, achievements, education, preferences, exclusions.
- Every claim has a status: **VERIFIED / UNVERIFIED / DISPUTED / DO_NOT_USE**. New claims default UNVERIFIED (fail-closed).
- **EvidenceChecker** is a HARD gate on resume/cover-letter generation: fabricated numbers, unsupported claims, unsupported skills → generation refused + regenerated once → persistent failure = 422, nothing saved.
- **YOU control it:** flip claims to VERIFIED with a source in `data/profile/*.yaml`, then `POST /api/evidence/sync`. The more you verify, the better your resumes.
- **API:** `GET /api/evidence`, `POST /api/evidence/sync|check`.

### 3.4 Freshness + Eligibility (only real, fresh jobs)
- 3 freshness states: VERIFIED_FRESH / STALE / DATE_UNKNOWN. Max age 7 days (configurable `MAX_JOB_AGE_DAYS`). DATE_UNKNOWN never upgrades (Critical Test #3).
- Eligibility gate chain with reason codes; zero AI on ineligible jobs.
- **API:** `POST /api/jobs/{id}/eligibility`, `GET /api/eligibility/eligible-jobs`, `GET /api/jobs/{id}/freshness`.

### 3.5 Matching Engine (scoring jobs for YOU)
- **AI scoring** — analyzes resume vs job (search terms, skills, seniority, ATS fit). Free OpenRouter models or DeepSeek.
- **Hybrid deterministic scoring** — always available, zero cost, full breakdown per component, hard blockers, matched/missing requirements, human-readable explanation.
- Weights are configurable: `GET/PUT /api/matching/config`.
- **API:** `POST /api/jobs/{id}/score`, `POST /api/matching/score-all`, `GET /api/jobs/{id}/explain`, `GET /api/matching/top-jobs`.

### 3.6 Company & Contact Research
- Company enrichment: careers page + LinkedIn URL discovery, AI-clue extraction, 30-day cache.
- Contact chain: **Manual → Hunter → Apollo → Web**, deterministic role classification (recruiter / hiring_manager / referrer), confidence 0–100, email dedup.
- Manual provider reads YOUR saved contacts first — always free.
- **API:** `POST /api/research/contacts/job/{id}`, `POST /api/research/company/{name}`, `GET /api/research/providers`.

### 3.7 Resume Tailoring & Packages
- Package per job at `data/applications/{id}-{company-slug}/`: `resume.docx` + `cover_letter.docx` + `.txt` + `metadata.json`.
- **Idempotent:** same inputs (fingerprint) = zero rewrites. Changed inputs = rebuilt.
- **DOCX-first:** the .docx is the primary artifact; .txt is a plain-text companion.
- Download any of the 5 allowed files via `GET /api/packages/jobs/{id}/download/{file}`.
- Every package born **ready_for_review** — YOU approve before anything moves.
- **API:** `POST /api/packages/jobs/{id}/build` (AI path; `?refresh=true` repackages stored text with ZERO AI — quota-proof), `GET /api/packages`, `GET /api/packages/jobs/{id}`.

### 3.8 Outreach (DRAFT-ONLY)
- 4 config-driven sequences (`config/outreach_sequences.yaml`): recruiter / hiring_manager / referral / followup — message bodies, identity, anti-spam limits.
- Audience picked deterministically from the contact on file.
- **Triple duplicate protection (Critical Test #4):** service dedup → DB UNIQUE constraint → Gmail thread lookup. Creating outreach twice = one draft, always.
- Caps: 12/day, 2 per company/day, follow-up gated by 6-day wait window.
- **Gmail is DRAFT-ONLY** — if `JOBAGENT_GMAIL_TOKEN` is not set, drafts land as local files (provider=`local`) so the pipeline still completes.
- **API:** `POST /api/outreach/jobs/{id}/create`, `POST /api/outreach/jobs/{id}/followup` (too_soon gate), `GET /api/outreach/messages`, `GET /api/outreach/config`.

### 3.9 CRM (tracking your applications)
- Forward-only pipeline: `interested → prepared → applied → interviewing → offered → accepted`, plus `rejected / withdrawn` (terminal).
- `interested → applied` is allowed (that's the "Mark applied" button). `→ offered` shortcuts and terminal resurrection are blocked.
- **Kanban dashboard** on the Pipeline page — drag & drop updates status through the validated endpoint.
- Append-only events log every change (who/what/when).
- **API:** `GET /api/crm/statuses`, `POST /api/jobs/{id}/status?to_status=…`, `POST /api/crm/followups/run`, `POST /api/jobs/{id}/bulk-status`.

### 3.10 Follow-up Engine
- One-pending-reminder rule; country cadence; stop rules for rejected/withdrawn/closed/ghosted/offered/accepted.
- Follow-ups are also DRAFT-ONLY and respect the 6-day wait + caps.
- Run anytime: `POST /api/crm/followups/run` or CLI `jobagent followups`.

### 3.11 Daily Automation (M11)
- 10-stage resumable pipeline (Section 2) + `daily_runs` table with persisted state.
- Daily target = NEW qualifying packages. Never lowers the bar; shortfall reasons are machine-readable.
- **API:** `GET /api/daily-run/today`, `POST /api/daily-run/run`.

### 3.12 Response Monitor + Feedback Loop (M12)
- Classifies every reply into 8 classes (deterministic) with a 0.70 confidence floor — below floor → human REVIEW, never silent.
- No-reply sender signal for jobs with no response.
- `recommend()` suggests targeting changes (min-sample gated; `auto_rewrite_performed:false` always).
- **API:** `POST /api/responses/classify`, `GET /api/analytics/feedback`.

### 3.13 Analytics & Monitoring
- Funnel, source performance, response rates, per-model AI cost, cache hit-rate.
- **API:** `GET /api/analytics`, `GET /api/analytics/response-rates`, `GET /api/analytics/monitoring`, `GET /api/analytics/feedback`.
- **UI:** Dashboard page (`#/stats`) — including the **AI Usage & Cost** panel.

### 3.14 Rest of the UI (8 pages)
| Page | What's on it |
|------|--------------|
| **Login / Bootstrap** | M15a auth — first visit creates the admin, then sign-in (7-day sessions) |
| **Jobs** (`#/`) | Live job feed, filters, scores, open a job for detail |
| **Dashboard** (`#/stats`) | Funnel, analytics, **Daily Run pipeline panel (run + stage status + shortfall reasons)**, **Targeting Feedback (M12)**, AI Usage & Cost panel |
| **Pipeline** (`#/pipeline`) | Kanban CRM board — drag & drop statuses (M10 engine) |
| **Calendar** (`#/calendar`) | Interviews & events |
| **Queue** (`#/queue`) | Approval queue + daily-run controls |
| **Network** (`#/network`) | Contacts, **Outreach Drafts list (M9)** + **"Draft Due Follow-ups" button (M10)** |
| **Calculator** (`#/calculator`) | Salary calculator (feature-flag gated, OFF by default) |
| **Settings** (`#/settings`) | Profile, Resumes, Job Search, **Countries & Discovery tab (M3+M4: enable/disable countries, apply strategy, run discovery, adapter health)**, Alerts, Follow-Ups, AI & Integrations, Data Management |
| **Job detail page** | Adds **Pipeline Actions panel (M5–M9): re-check eligibility, free hybrid score + component breakdown, find contacts, build/repackage application package (+download), create outreach draft — all per job, all in the UI** |

---

<a name="4-first-time-setup"></a>
## 4. Step-by-Step: First-Time Setup

### Step 1 — Get the code
```bash
git clone https://github.com/basilahamed07/CHANGE.git
cd CHANGE/job-search-system/root
```
(Guide assumes this directory — all commands run from `root/`.)

### Step 2 — Install dependencies
```bash
uv sync
```

### Step 3 — Environment variables
```bash
cp .env.example .env
```
Edit `.env` — minimum:
```
JOBAGENT_OPENROUTER_API_KEY=sk-or-v1-...   # or DeepSeek key (Section 8)
```
Optional:
```
JOBAGENT_DEEPSEEK_API_KEY=sk-...           # DeepSeek ($2 top-up path)
JOBAGENT_GMAIL_TOKEN=...                   # Gmail drafts; omit = local drafts
JOBAGENT_HUNTER_API_KEY=...                # contact discovery
JOBAGENT_APOLLO_API_KEY=...                # contact discovery
```
**Never commit `.env` — it is gitignored.**

### Step 4 — Start the server
```bash
uv run uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8085
```
Verify:
```bash
curl http://127.0.0.1:8085/api/system/health
```
Open **http://127.0.0.1:8085** →

**M15a — Login first:**
- **First ever visit:** the app shows **"Create Admin Account"** — pick your username and a password (min 8 chars). This one-time bootstrap creates the administrator and locks itself forever.
- **Every visit after:** you land on the **Sign In** page. Sessions last 7 days; "Log out" is in the top-right nav.
- 5 failed logins = 15-minute lockout (brute-force protection).
- The onboarding flow then walks you through the rest.

> The whole API is now protected: every `/api/*` endpoint except `/api/system/health`
> and `/api/auth/*` returns **401** without a valid session.

### Step 5 — Upload your resume
- Settings (or onboarding) → upload your **.docx resume**.
- The AI analyzes it: search terms, key skills, seniority, ATS score — persisted to `search_config`.
- Verify: `curl http://127.0.0.1:8085/api/evidence` shows your claims.

### Step 6 — Verify your evidence (IMPORTANT — do not skip)
- Open `data/profile/*.yaml`.
- For every true claim, set `status: VERIFIED` and add `source:` (e.g. "resume 2026", "LinkedIn").
- Then:
```bash
curl -X POST http://127.0.0.1:8085/api/evidence/sync
```
Everything stays UNVERIFIED = fail-closed = resumes can barely claim anything.

### Step 7 — Choose countries
- Settings → Countries, or:
```bash
curl http://127.0.0.1:8085/api/countries
curl -X POST http://127.0.0.1:8085/api/countries/apply
```
Disable countries you don't want; enable the 6 you target.

### Step 8 — Configure AI provider (DeepSeek for you)
See **Section 8** below — pick DeepSeek (`deepseek-flash`) or keep OpenRouter free models.

### Step 9 — First discovery run
```bash
curl -X POST http://127.0.0.1:8085/api/discovery/run
# poll:
curl http://127.0.0.1:8085/api/discovery/status
```

### Step 10 — Score everything
```bash
curl -X POST http://127.0.0.1:8085/api/matching/score-all
```
AI scores what it can (quota allowing); hybrid scores the rest for free.

---

<a name="5-daily-usage"></a>
## 5. Step-by-Step: Daily Usage

Your daily routine is **one command + a review session**:

### Step 1 — Run the daily pipeline
```bash
curl -X POST http://127.0.0.1:8085/api/daily-run/run
```
This executes all 10 stages (discover → … → digest). It is **idempotent and resumable** — if it crashes or you close the terminal, run the same command again; completed stages are never repeated.

### Step 2 — Check today's result
```bash
curl http://127.0.0.1:8085/api/daily-run/today
```
Look at: `packages_created` vs `daily_target`, `shortfall_reasons`, per-stage status.

### Step 3 — Review the top matches
```bash
curl "http://127.0.0.1:8085/api/matching/top-jobs?limit=10"
```
Open each job in the UI (Jobs page → click job) → **Explain** shows exactly why it scored what it did (component breakdown, matched/missing requirements, hard blockers).

### Step 4 — Build packages for jobs you want
```bash
# AI path (uses quota):
curl -X POST http://127.0.0.1:8085/api/packages/jobs/JOB_ID/build
# Quota-proof path (repackages stored text, ZERO AI):
curl -X POST "http://127.0.0.1:8085/api/packages/jobs/JOB_ID/build?refresh=true"
```
Find files at `data/applications/{id}-{company-slug}/` — open `resume.docx` and **review every line**.

### Step 5 — Create the outreach draft
```bash
curl -X POST http://127.0.0.1:8085/api/outreach/jobs/JOB_ID/create
```
- With Gmail token → appears in your Gmail **Drafts**.
- Without → local draft file (path returned in the response).

### Step 6 — YOU send (the only manual send step)
Open Gmail → Drafts → review the email → click **Send**. The system never sends anything itself.

### Step 7 — Mark as applied
- Pipeline page → drag the card to **applied**, or:
```bash
curl -X POST "http://127.0.0.1:8085/api/jobs/JOB_ID/status?to_status=applied"
```

### Step 8 — Follow-ups (when due)
```bash
curl -X POST http://127.0.0.1:8085/api/crm/followups/run
```
This drafts follow-up emails for applications whose wait window has passed (stops automatically for terminal statuses).

---

<a name="6-crm--follow-ups"></a>
## 6. CRM & Follow-ups — Step by Step

### Status pipeline
```
interested → prepared → applied → interviewing → offered → accepted
                                  ↘ rejected / withdrawn (terminal)
```

### Rules the engine enforces
- **Forward-only.** Terminal states (rejected, withdrawn, closed, ghosted) never come back to life.
- **No offered-shortcuts.** You can't jump `interested → offered` — must pass through applied/interviewing.
- Forward skips within the pipeline are allowed (real life: you sometimes apply directly).
- Every transition is validated — the UI, CLI and API all go through the same `check_transition()`.

### How to move a job through
1. **UI (recommended):** Pipeline page → drag the card. The drag maps to the validated endpoint.
2. **API:** `POST /api/jobs/{id}/status?to_status=interviewing`
3. **CLI:** `uv run python cli.py status JOB_ID --set interviewing`

### How follow-ups decide
- A follow-up is due when: status is not terminal AND no pending reminder AND the last touch is older than the cadence (default 6 days, country-aware).
- When a job enters a terminal state, its pending reminders auto-complete.
- Follow-up emails are drafted (never sent), same caps as outreach.

---

<a name="7-using-the-cli"></a>
## 7. Using the CLI

`root/cli.py` — the `jobagent` command. Same service layer as the web UI, so what the CLI reports is exactly what the API reports.

```bash
cd job-search-system/root

# Health + pipeline snapshot
uv run python cli.py health

# Search scored jobs
uv run python cli.py search "AI Engineer" --min-score 70 --limit 10

# Mark a job prepared (creates application row if needed)
uv run python cli.py prepare 42

# Research contacts for a job (uses the manual→hunter→apollo→web chain)
uv run python cli.py contacts 42

# Today's daily-run state + packages created today
uv run python cli.py daily

# Which follow-ups are due right now
uv run python cli.py followups

# Analytics + recommendations
uv run python cli.py analytics

# Change status (validated by the same CRM engine)
uv run python cli.py status 42 --set applied
```

---

<a name="8-ai-providers--deepseek"></a>
## 8. AI Providers & DeepSeek (Your Setup)

### Available providers (7)
`openrouter` (default) · `deepseek` · `anthropic` · `openai` · `google` · `groq`/`bedrock`/`ollama` — env fallback order: **OpenRouter → DeepSeek → Anthropic**.

### Why DeepSeek (your decision, Session 22)
- OpenRouter free tier = 50 requests/day → constant 429 quota pain.
- You approved a **$2 top-up**. Cost math: **$2 ≈ 380 full tailoring packages** (~$0.00525 each: 15K input tokens @ $0.15/M + 5K output @ $0.60/M, off-peak; resume text is cache-eligible, so real cost is lower).

### Step-by-step: switch to DeepSeek
1. Top up $2 at platform.deepseek.com → copy your API key (starts with `sk-`).
2. **Either** paste it in the UI: **Settings → AI → Provider = DeepSeek, model = `deepseek-flash`**,
   **or** put it in `.env`:
   ```
   JOBAGENT_DEEPSEEK_API_KEY=sk-...
   ```
3. Restart the server. Test:
   ```bash
   curl http://127.0.0.1:8085/api/ai-settings/test
   ```
   Expect `{ok: true}`.
4. Verify the whole path end-to-end:
   ```bash
   curl -X POST http://127.0.0.1:8085/api/packages/jobs/JOB_ID/build
   ```
   Then check the cost meter: `curl http://127.0.0.1:8085/api/analytics/monitoring` — the spend should now appear under the DeepSeek model.

### Current model notes
- `deepseek-flash` = DeepSeek-V4.1-Flash (current name; legacy `deepseek-v4-flash` accepted but retired).
- DeepSeek rides the same OpenAI-compatible spine as OpenRouter → retry, circuit-breaker, health checks all inherited, zero new code.
- OpenRouter free models still work as fallback (env fallback order keeps OpenRouter first — free tier first, paid DeepSeek on demand).

---

<a name="9-response-monitor"></a>
## 9. Response Monitor & Feedback Loop

When recruiters reply to your outreach/Gmail:

### Step 1 — Classify a response
```bash
curl -X POST http://127.0.0.1:8085/api/responses/classify \
  -H "Content-Type: application/json" \
  -d '{"job_id": 42, "text": "We would like to schedule a call..."}'
```
8 deterministic classes; confidence < 0.70 → flagged for **REVIEW** (never silently classified).

### Step 2 — See the feedback loop
```bash
curl http://127.0.0.1:8085/api/analytics/feedback
```
Shows: response rate per source, median days-to-response, and targeting recommendations (min-sample gated — the system never auto-rewrites your targeting, `auto_rewrite_performed: false`).

---

<a name="10-costs"></a>
## 10. Costs, Budget & Monitoring

### The cost meter (M14 observability)
- Every AI call is metered (tokens + USD) per model, in-process + DB sink.
- `:free` models = $0. DeepSeek billed at real rates.
- **Dashboard → AI Usage & Cost panel**: spend today/all-time, calls, tokens, avg per call, budget bar, per-model table, cache hit-rate.
- **API:** `GET /api/analytics/monitoring` (usage, budget projection, cache hit-rate, daily-run state).

### Budget rule of thumb
| Action | Approx cost (DeepSeek off-peak) |
|--------|--------------------------------|
| Score 1 job (hybrid) | $0 (deterministic) |
| Score 1 job (AI) | ~$0.001–0.002 |
| Full package (resume + cover letter) | ~$0.005 |
| **$2 top-up** | **≈ 380 packages** |

### Cache
- Research (company/contacts) is cache-first with TTLs (7d contacts, 30d companies) — repeats cost nothing.
- Cache hit-rate visible in the monitoring endpoint.

---

<a name="11-safety"></a>
## 11. Safety Rules the System Enforces

1. **Nothing is ever auto-sent.** The Gmail provider class physically has no send method. Local fallback writes draft files.
2. **Evidence gate.** Unverified claims can never reach a .docx. Generation is refused + regenerated once + 422.
3. **The bar never drops.** Daily target counts qualifying packages only.
4. **Idempotent everywhere.** Re-running daily-run, re-creating outreach, rebuilding identical packages — all safe no-ops.
5. **Reversible strategy.** Country auto-dismissals are flagged and restored when you re-enable a country.
6. **Terminal is terminal.** Rejected/withdrawn applications can't resurrect; follow-ups stop.
7. **No secrets in git.** `.env`, `data/`, `*.docx`, references/ are gitignored; secret scan ran clean pre-push.
8. **Auth required (M15a).** Every API route needs a session (HttpOnly cookie, 7-day). scrypt-hashed passwords, login lockout, one-time admin bootstrap. The E2E harness logs in as part of every run.

---

<a name="12-troubleshooting"></a>
## 12. Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `401 Authentication required` | Session missing/expired | Log in again; sessions last 7 days |
| `429 too many failed logins` | 5 wrong attempts | Wait 15 minutes (lockout) |
| "Create Admin Account" shows again | system.db was deleted | Expected only on a wiped system.db — recreate admin |
| `429` / quota errors on scoring | OpenRouter free-tier 50/day limit | Switch to DeepSeek (Section 8) or wait for reset; hybrid scoring keeps the pool scored anyway |
| Packages build but score filter shows nothing above cutoff | Everything scored below 60 | `GET /api/matching/top-jobs?limit=50` — check hard blockers (sponsorship keywords) and lower cutoff only consciously |
| Daily run shows `AI_QUOTA_EXHAUSTED` | Quota died mid-run | Re-run the same command after reset — completed stages are never re-run |
| Resume refused with 422 evidence violation | A generated line failed the EvidenceChecker | Verify the relevant claims in `data/profile/*.yaml` → `POST /api/evidence/sync` → rebuild |
| Outreach says `too_soon` | Follow-up wait window (6d) not elapsed | Wait, or check `GET /api/outreach/jobs/{id}` for the timestamp |
| Country jobs disappeared after disabling | Restore-then-dismiss strategy ran | Re-enable the country → jobs are RESTORED automatically |
| `gmail_connected: false` in outreach config | No `JOBAGENT_GMAIL_TOKEN` | Expected — drafts go to local files; add token to use Gmail drafts |
| Server won't boot / 503 evidence | Missing evidence store on app.state | Make sure you start via `uv run uvicorn app.main:app` from `root/` (lifespan wires store+checker) |
| E2E harness gives 0 countries / 11 fails | Run from wrong directory | Harness MUST run from `root/`: `cd root && .venv/bin/python ../analysis/e2e_module_test.py` |

---

<a name="13-cheat-sheet"></a>
## 13. Command Cheat-Sheet

```bash
# ---- server ----
cd job-search-system/root && uv sync
uv run uvicorn app.main:app --host 127.0.0.1 --port 8085

# ---- daily loop (the big 4) ----
curl -X POST http://127.0.0.1:8085/api/daily-run/run       # full pipeline
curl http://127.0.0.1:8085/api/daily-run/today             # what happened
curl "http://127.0.0.1:8085/api/matching/top-jobs?limit=10" # best matches
curl -X POST http://127.0.0.1:8085/api/packages/jobs/ID/build  # package a job

# ---- per-job manual flow ----
curl -X POST http://127.0.0.1:8085/api/research/contacts/job/ID
curl -X POST http://127.0.0.1:8085/api/outreach/jobs/ID/create
curl -X POST "http://127.0.0.1:8085/api/jobs/ID/status?to_status=applied"

# ---- CRM / follow-ups ----
curl -X POST http://127.0.0.1:8085/api/crm/followups/run
curl http://127.0.0.1:8085/api/crm/statuses

# ---- evidence ----
curl http://127.0.0.1:8085/api/evidence
curl -X POST http://127.0.0.1:8085/api/evidence/sync

# ---- countries ----
curl http://127.0.0.1:8085/api/countries
curl -X POST http://127.0.0.1:8085/api/countries/apply

# ---- monitoring ----
curl http://127.0.0.1:8085/api/analytics/monitoring
curl http://127.0.0.1:8085/api/analytics/feedback

# ---- CLI ----
uv run python cli.py health | search | prepare | contacts | daily | followups | analytics | status

# ---- tests (development) ----
uv run pytest                    # backend (872 green)
cd app/static && npx vitest run  # frontend (180 green)
```

---

*Generated for Basil by the jobagent project — one coherent system, never five taped-together repos.*
