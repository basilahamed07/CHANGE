# AGENT CONTEXT — jobagent system brain (read this FIRST)

> **What this file is:** the ONE self-contained context file for any AI agent
> (or human) working on this repository. It explains **what the system is able
> to do**, **the full flow** (inputs → pipeline → outputs), the **invariants
> that must never be broken**, and **where the project stands right now**.
>
> Everything here is sourced from the actual code and verified E2E reports —
> not from aspirations. When this file and the code disagree, THE CODE WINS:
> inspect it, then fix this file.

---

## 1. System identity (30 seconds)

**jobagent** is a personal international AI job-search + recruiter-outreach
system for **Basil Ahamed H** (target roles: AI Engineer · GenAI Engineer ·
LLM/RAG/Agentic AI Engineer · Python AI Developer · Backend/AI Engineer).

One product takes the user from *"I need a job"* to *"a reviewed application
package and an outreach draft are ready"*:

```
discover → normalise → dedupe → freshness → eligibility → match/score
  → company & contact research → tailor resume (evidence-gated)
  → cover letter → application package → outreach DRAFT (never sent)
  → CRM tracking → follow-up reminders → response monitoring → feedback
```

**Stack:** FastAPI + SQLite (46 tables) backend · vanilla-JS SPA (no build
step) · CLI over the same service layer · per-user workspaces (M15b).
**Base:** CareerPulse (MIT), extended — never rewritten (Golden Rule 3).

---

## 2. The flow diagram (inputs → agent pipeline → outputs)

```
═════════════════════════════ INPUTS ═══════════════════════════════════════
  Resume (.docx/.pdf/.txt, ≤10 MB)  ── required: search/discovery gated (428)
  AI provider key (per user)        ── OpenRouter default · DeepSeek rec.
  Countries (10 × one YAML each)    ── DE NL IE UK SG AE + IN CA AU PL
  Scraper keys (optional)           ── Jooble, Adzuna, USAJobs…
  Contact keys (optional)           ── Hunter, Apollo (manual + web = free)
  Gmail token (optional, per user)  ── drafts only; absent ⇒ local drafts
            │
            ▼
══════════════════ DAILY PIPELINE — 10 STAGES IN ORDER ═════════════════════
                    (app/daily_run.py — one button, idempotent,
                     state saved BEFORE each stage ⇒ crash-resumable)

  1. DISCOVER ──────── 21 scrapers + 15 ATS adapters × countries × terms
  │                    budget-capped (24 passes × 200 listings); ingest gates:
  │                    title filter → cross-source DEDUP (content hash)
  │                    → freshness (≤7d; DATE_UNKNOWN is terminal)
  ▼
  2. CLASSIFY ──────── deterministic region rules first, LLM only if ambiguous
  ▼
  3. ELIGIBILITY ───── gate chain w/ reason codes (dismissed → freshness →
  │                    evidence → repost-pending) — ZERO LLM on rejects
  ▼
  4. SCORE (AI) ────── per-job relevance/concerns/keywords; circuit breaker
  │                    + graceful quota degradation (never blocks pipeline)
  ▼
  5. HYBRID_SCORE ──── FREE deterministic engine scores whatever AI couldn't:
  │                    skills .35 · role .15 · location .10 · visa .10 ·
  │                    recency .10 · semantic .20 + hard blockers (cap 25)
  │                    ⇒ the pool is NEVER left unscored
  ▼
  6. SELECT ────────── top eligible+scored jobs toward today's target
  │                    (default: 5 qualifying PACKAGES/day, cutoff 60)
  ▼
  7. RESEARCH ──────── company enrichment (regex, zero LLM) + contact
  │                    chain Manual → Hunter → Apollo → WebSearch,
  │                    confidence-scored, cache-first (7d TTL)
  ▼
  8. PACKAGES ──────── AI tailors resume + cover letter THROUGH THE
  │                    EVIDENCE GATE (fabricated claim → 1 regen → 422)
  │                    ⇒ resume.docx + cover_letter.docx + .txt + metadata.json
  ▼
  9. OUTREACH ──────── DRAFT-ONLY (no send method exists in the codebase);
  │                    4 audiences; idempotent (never 2 drafts/job+audience)
  ▼
 10. DIGEST ────────── honest daily report incl. machine-readable shortfall
                       reasons (AI_QUOTA_EXHAUSTED, ALL_SCORED_BELOW_CUTOFF…)

            │
            ▼
══════════════════════════ OUTPUTS (all per-user) ══════════════════════════
  • Job pool (SQLite workspace) with scores, reasons, audit trails
  • Application packages in data/applications/{id}-{company}/  (ready_for_review)
  • Outreach drafts (Gmail DRAFT or local) — the human presses Send, always
  • CRM: interested → prepared → applied → interviewing → offered
         (+ rejected/withdrawn/closed/ghosted) · append-only events
  • Follow-up reminders (cadence 3/7/5d, one-pending rule, terminal stop)
  • Response monitoring: 8-class rule-based classifier (0.70 floor → REVIEW)
  • Analytics: funnel, source quality, skill gaps, AI cost meter per model
  • Feedback: PROPOSES ONLY (auto_rewrite_performed: false), min-sample gated

════════════════════ CROSS-CUTTING (every stage) ═══════════════════════════
  Auth: session cookie (7d) → workspace middleware binds request.state.db
        to the logged-in user's own data/users/{id}-{username}/ workspace
  Multi-user: own DB, pool, resume, evidence, keys, drafts, cost meter
  Cost control: every AI call metered (ai_usage); :free models = $0
  Determinism: Python for dates/pagination/dedup/math — LLM ONLY for
               semantics/phrasing (Golden Rule 4)
```

---

## 3. Capability map — what the system IS able to do

| # | Capability | Where (code) | Key fact |
|---|-----------|--------------|----------|
| 1 | **Job discovery** | `app/discovery.py`, `app/scrapers/`, `app/adapters/` | 21 scrapers + 15 adapters; one failing source never stops a run; per-pass stop-reason telemetry |
| 2 | **Normalization** | `app/job_adapter.py` | `CanonicalJob` + `make_content_hash` (title\|company\|city, URL excluded) |
| 3 | **Cross-source dedup** | discovery ingest + `job_duplicates` | same job via 2 sources ⇒ 1 job + 2 source rows (Critical Test #2) |
| 4 | **Freshness gate** | `app/freshness.py` | VERIFIED_FRESH / STALE / DATE_UNKNOWN; unknown date NEVER becomes fresh (Critical Test #3); max age 7d |
| 5 | **Eligibility gate** | `app/eligibility.py` | deterministic chain, reason codes, zero LLM on INELIGIBLE |
| 6 | **Country strategy** | `config/countries/*.yaml`, `app/country_registry.py`, `app/visa_engine.py` | add a country = ONE YAML, zero code (Golden Rule 8); visa engine is word-boundary regex |
| 7 | **Hybrid matching** | `app/hybrid_matcher.py`, `app/matching_service.py` | 6 components + hard blockers; pure-Python TF-IDF; explanation + component audit |
| 8 | **RAG semantic layer** | RagProvider | retrieval over VERIFIED evidence only; local TF-IDF default ($0) |
| 9 | **AI scoring** | `app/ai_client.py` | 7 providers; retry, circuit breaker, quota degradation |
| 10 | **Evidence system** | `app/evidence_store.py`, `app/evidence_checker.py` | claims VERIFIED/UNVERIFIED/DISPUTED/DO_NOT_USE; fail-closed; fabricated claim ⇒ 422, nothing saved (Critical Test #1) |
| 11 | **Company/contact research** | `app/company_enrichment.py`, `app/contact_providers.py` | never-raise provider chain; confidence 0–100; cache-first |
| 12 | **Package builder** | `app/application_builder.py`, `app/routers/packages.py` | fingerprint-idempotent (same inputs ⇒ noop); DOCX-first; born `ready_for_review`; `?refresh=true` = zero-AI repackage |
| 13 | **Outreach drafts** | `app/outreach.py`, `app/routers/outreach.py` | DRAFT-ONLY by construction; caps 12/day, 2/company/day; per-user Gmail token (N1) |
| 14 | **CRM + follow-ups** | `app/crm.py` | validated transitions (no terminal resurrection; no offered-without-applying); append-only events; cadence engine |
| 15 | **Daily pipeline** | `app/daily_run.py` | 10 stages, crash-resumable, target = qualifying PACKAGES, honest shortfall reasons |
| 16 | **Response monitor + feedback** | `app/response_monitor.py` | 8 classes, 0.70 confidence floor → REVIEW; feedback proposes only |
| 17 | **Analytics + cost** | `app/routers/analytics.py`, `app/ai_usage.py` | funnel, per-source, per-model spend, budget projection, cache hit-rate |
| 18 | **Multi-user workspaces** | `app/workspace.py`, `app/workspace_middleware.py`, `app/auth.py` | per-user DB/profile/applications/keys/drafts; server-enforced isolation (Critical Test #5) |
| 19 | **Auth + admin basics** | `app/auth.py`, `app/routers/auth.py` | scrypt hashing, login throttling, one-time admin bootstrap, user create/disable/reset (audit-logged) |
| 20 | **Interfaces** | SPA `app/static/`, `root/cli.py`, REST + OpenAPI | 218 API ops; CLI same service layer; E2E covers 85.8% of API |
| 21 | **Observability** | `app/ai_usage.py`, run_id plumbing | metering can never break a real AI call (swallows its own errors) |

---

## 4. Invariants — an agent must NEVER break these

**Golden rules (enforced in code):**
1. **One coherent product** — extend > rewrite; CareerPulse is the base.
2. **Never hallucinate** — the evidence gate is HARD: UNVERIFIED can never
   render as VERIFIED; generation refuses rather than fabricates.
3. **Deterministic before LLM** — filters, dedup, arithmetic, visa, CRM
   transitions are zero-LLM; LLM only for semantics/phrasing.
4. **Daily target = qualifying PACKAGES**, never scraped URLs; never lower
   the eligibility bar to hit a number.
5. **Draft, never send** — no send method exists; `JOBAGENT_ALLOW_SEND`
   defaults false; the human always presses Send.
6. **Country = config** — one YAML per country, zero core-code changes.
7. **MAX_JOB_AGE_DAYS = 7**; DATE_UNKNOWN is terminal, never upgraded.
8. **Human approval gates** — packages born `ready_for_review`.
9. **Per-user isolation** — every request resolves through the requesting
   user's workspace; no app-state/global mutation on per-user paths.
10. **Fail honestly** — 502 on AI failure, 428 pre-resume, machine-readable
    shortfall reasons; never fake success or swallow errors into 200s.

**The 5 Critical Tests (must keep passing):**
| # | Test |
|---|------|
| 1 | Candidate without skill X + JD requiring X ⇒ generated resume MUST NOT claim X |
| 2 | Same job via 2 sources ⇒ 1 job + 2 source rows (never 2 applications) |
| 3 | DATE_UNKNOWN must never become VERIFIED_FRESH |
| 4 | Creating outreach twice ⇒ exactly one draft (3 dedup layers) |
| 5 | Two users ⇒ fully isolated workspaces (jobs/resumes/keys/CRM/evidence) |

**Definition of done for any new work (Golden Rule #11):** code → real-scenario
test (two logged-in users over live HTTP, or a real server boot — not a mocked
unit test alone) → full repo suite green → docs + PROJECT_MEMORY.md updated →
commit. Unit tests passing ≠ done; **proven through the running product = done.**

---

## 5. Current state (2026-09-28) — and what is NEXT

**Done & E2E-verified:** M1–M14 (all 10 pipeline stages, evidence system,
country engine, research, packages, outreach, CRM, daily run, analytics,
observability, CLI) + M15a auth + M15b workspaces + M15c partial
(per-user scrape/score/discovery, cost meter, **N1 per-user Gmail token**,
resume-first onboarding gate 428). 10 countries, 15 adapters live-verified
(49 real jobs ingested in the sponsor-country E2E). Full suite: 999 backend +
184 frontend green. Real user-journey E2E: **26/26 scenarios, 204/204 checks**.

**Next 5 (docs/NEXT_5_PLAN.md — in order, one at a time):**
| # | Item | The real gap |
|---|------|--------------|
| **N2** | Per-user scheduled cycles | interval jobs in `main.py` run against the ADMIN workspace only — iterate active users + stagger + their own matcher |
| **N3** | Per-user background run state | `discovery_running`/`scrape_progress`/`scoring_progress` are process-global — key by user_id; per-IP advisory cap |
| **N4** | Ship reviewed text + personal-facts gate | `POST /build` re-generates and overwrites reviewed text (flag reads backwards); visa/relocation personal facts need an evidence guard |
| **N5** | Admin panel (M15d) | one admin page: manage users, per-user spend, audited impersonation ("Act as user X") |

**Known honest limits:** Indeed IP-blocked (datacenter); AI quota is the
bottleneck (hybrid scoring covers the pool free); no HTTPS yet (cookie not
secure); API keys plaintext at rest (M15e); Gmail OAuth consent UI not built
(draft REST + local fallback work); currency not converted.

---

## 6. Verification commands (prove, don't assume)

```bash
cd job-search-system/root
.venv/bin/python -m pytest -q --timeout=300          # backend suite (~999)
cd app/static && npx vitest run                      # frontend (~184)

# E2E harness — MUST run from root/ (relative config paths)
cd job-search-system/root && .venv/bin/python ../analysis/e2e_module_test.py
cd job-search-system/root && .venv/bin/python ../analysis/e2e_user_journey.py

# Real-scenario multiuser tests (the N-item bar)
.venv/bin/python -m pytest tests/test_multiuser_real_scenario.py -q

# Server
.venv/bin/python -m uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8085
```

**Key docs if you need depth:** `PROJECT_MEMORY.md` (full history + session
log) · `docs/CAPABILITIES.md` (feature reference) · `docs/USER_PROCESS.md`
(step-by-step user manual) · `docs/DAILY_RUN_GUIDE.md` (stage deep-dive) ·
`docs/NEXT_5_PLAN.md` (current work queue) · `docs/E2E_RUN_STATUS.md` (status
board) · `docs/ARCHITECTURE_DECISION.md` (D1–D26 decisions).
