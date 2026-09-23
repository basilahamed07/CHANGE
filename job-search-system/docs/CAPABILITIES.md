# jobagent — Complete Capability Reference

**Product:** Personal international AI job-search + recruiter-outreach system for
**Basil Ahamed H.** — target roles: AI Engineer · Generative AI Engineer · AI Application
Developer · Python AI Developer · LLM Engineer · RAG Engineer · Agentic AI Engineer ·
Backend/AI Engineer.

**Status:** milestones **M1–M14 complete**, E2E-verified (Golden Rule #11).
**Last verified:** 2026-09-23.

---

## 1. At a glance

| Dimension | Count / value |
|---|---|
| API endpoints | **206** operations |
| Database tables | **45** application (+ 10 `sqlite-vec` shadow) |
| Job sources (scrapers) | **21** |
| ATS adapters | **4** (Greenhouse · Lever · Ashby · SmartRecruiters) |
| Target countries | **6** (Germany · Ireland · Netherlands · Singapore · UAE · UK) |
| AI providers | **7** (OpenRouter · DeepSeek · Anthropic · OpenAI · Google · AWS Bedrock · Ollama) |
| Distance-to-apply stages | **10** (discover → … → digest) |
| Backend tests | **906** passing |
| Frontend tests | **180** passing |
| E2E harness | **178+ checks**, 0 FAIL |
| Cost per full application | ≈ **$0.00525** on DeepSeek Flash → **~380 applications per $2** |

---

## 2. Job discovery — 21 sources

Every scraper runs through one resilient chassis (`app/scrapers/base.py`):
rotating user-agents, per-domain token-bucket rate limiting, exponential backoff with
`Retry-After` support, HTML-entity/mojibake cleaning, and salary sanity bounds
($10k–$2M). One failing source never stops a run.

| Source | Kind | Auth | Notes |
|---|---|---|---|
| Hacker News "Who is Hiring" | JSON (Algolia + Firebase) | none | parses thread comments into listings |
| Remotive | JSON API | none | remote-first |
| USAJOBS | REST | API key | US federal |
| LinkedIn | guest search API | none | paginated |
| Dice | HTML | none | high volume |
| Arbeitnow | JSON API | none | EU/DE heavy |
| Jobicy | JSON API | none | tag-based |
| Indeed | HTML + Playwright | none | **IP-blocked from datacenters** — see limits |
| RemoteOK | JSON API | none | remote-first |
| Himalayas | JSON API | none | remote-first |
| Wellfound | Next.js Apollo state | none | 188 live jobs after the 2026-09 fix |
| BuiltIn | HTML | none | US tech |
| Greenhouse | ATS JSON | none | configurable company list |
| Adzuna | REST | app id + key | aggregated |
| **WeWorkRemotely** | RSS | none | *registered 2026-09-23 — was orphaned* |
| **Working Nomads** | JSON API | none | *new — global remote* |
| **Recruitee** | ATS JSON | none | *new — EU boards, configurable list* |
| **MyCareersFuture** | JSON API | none | *new — Singapore government board, salaries annualised* |
| **Ashby** | ATS JSON | none | *new — 20 verified boards, 1.7k live jobs, **real salary bands*** |
| **Landing.jobs** | JSON API | none | *new — EU tech board (DE/NL/PT/ES), company recovered from URL* |
| **4dayweek.io** | JSON API | none | *new — remote / 4-day-week board, paginated* |

**Plus the M4 discovery layer:** `JobSourceAdapter` implementations for
Greenhouse/Lever/Ashby/SmartRecruiters with `health_check()`, canonical
`CanonicalJob` normalization, cross-source content hashing, multi-pass
country × term × adapter orchestration, budget caps and per-pass stop-reason
telemetry.

**Deterministic gates applied at ingest** (no AI cost):
- cross-source **dedup** by content hash (Critical Test #2 — the same job from two
  sources becomes ONE job with two source rows)
- **repost graph** (`job_duplicates`) with manual-approve gate
- **freshness** states — `VERIFIED_FRESH` / `STALE` / `DATE_UNKNOWN`
  (`DATE_UNKNOWN` is terminal and never upgraded — Critical Test #3), default max age 7 days
- **eligibility chain** with reason codes: dismissed → freshness → evidence → repost-pending
- **title relevance gate** (`title_filter.py`) to drop off-topic noise before scoring

---

## 3. Matching & scoring

Three layers, cheapest first (Golden Rule 3 — deterministic before LLM):

1. **Hybrid deterministic matcher** (`hybrid_matcher.py`) — 6 weighted components:
   skills .35 · role .15 · location .10 · visa .10 · recency .10 · semantic .20,
   with **hard-blocker short-circuit** (`NO_SPONSORSHIP_STATED`,
   `DO_NOT_USE_SKILL_*` capping the score at 25). Pure-Python TF-IDF, zero AI cost —
   the whole pool is always scored, so nothing is left invisible.
2. **RAG semantic component** over **VERIFIED evidence only** (local TF-IDF default,
   optional embedding provider).
3. **AI scoring** for depth: per-job `match_score`, matched/missing requirements,
   concerns, suggested keywords — with circuit breaker + graceful quota degradation.

Output per job: `component_scores`, `hard_blockers`, explanation strings persisted for audit.

---

## 4. Anti-hallucination evidence gate (Critical Test #1)

- `data/profile/*.yaml` claim store — every claim carries `value`, `status`
  (`VERIFIED`/`UNVERIFIED`/`DISPUTED`/`DO_NOT_USE`), `source`, `last_verified`.
- `EvidenceChecker` hard gate: number-diff + similarity floor + forbidden-claim checks.
- **Unverified claims can never render as verified.** `DO_NOT_USE` and `DISPUTED`
  never appear in generated output. `EvidenceViolationError` is the last line —
  generation refuses rather than fabricates.
- Verified live: a candidate without skill X cannot produce a resume claiming X.

---

## 5. Country strategy engine

Adding a country = adding **one YAML file**, zero code.

- 6 country configs with salary floors, visa keywords, work-type flags.
- Deterministic visa/sponsorship keyword engine (word-boundary matching).
- `apply_country_strategy` classifies jobs → syncs allowed regions →
  restore-then-dismiss with a **reversible** `strategy_dismissed` flag (no data loss).
- Verified live round trip: **disable UAE → Dubai job dismissed → re-enable → job restored.**

---

## 6. Company + contact research

- `ContactProvider` interface with a **never-raises** contract and a fallback chain:
  **Manual → Hunter → Apollo → WebSearch**.
- Deterministic role taxonomy (recruiter / hiring manager / referrer / other) +
  confidence 0–100 + machine-readable *why selected*.
- Cache-first service (7-day TTL) with email dedup; company enrichment
  (careers URL, LinkedIn, AI clues) with 30-day cache — all regex, **zero LLM**.
- Works fully with **no paid keys** (manual + web fallback).

---

## 7. Application packages (M8)

One call produces a review-ready package:

```
resume.docx  ·  cover_letter.docx  ·  cover_letter.txt  ·  resume.txt  ·  metadata.json
```

- **DOCX-first** renderer (modular for PDF later).
- Fingerprint idempotency: identical inputs ⇒ `noop`, byte-identical output (no rewrite).
- `metadata.json` audit trail: hashes, profile version, evidence-check result, model, status.
- Packages are born **`ready_for_review`** — never auto-submitted.
- `?refresh=true` repackages from stored text with **zero AI** (quota-proof, verified live during a dead-quota run).

---

## 8. Outreach — DRAFT-ONLY by construction (Critical Test #4)

- 4 config-driven audiences: recruiter · hiring manager · referral · follow-up.
- **No send method exists in the codebase.** Gmail integration is REST draft-only;
  without a token it falls back to local drafts. Sending would require
  `JOBAGENT_ALLOW_SEND=true` *and* per-draft approval.
- Anti-spam caps: 12/day, 2/company/day, 6-day follow-up gate.
- **Critical Test #4 at three layers:** service dedup-first → DB `UNIQUE(job_id, audience)`
  → Gmail thread lookup. Running outreach twice yields exactly one draft.

---

## 9. CRM + follow-ups (M10)

- Validated pipeline: `interested → prepared → applied → interviewing → offered`
  (+ `rejected/withdrawn/closed/ghosted`).
- **Forward skips allowed** (applications happen off-platform), but `→ offered`
  shortcuts and **terminal resurrection** are blocked — even for the engine.
- Cadence-based follow-up engine (3/7/5 days) with one-pending-reminder rule and
  terminal stop rules; entering a terminal state auto-completes pending reminders.
- **Append-only** event history (`app_events`).
- Approval matrix (Phase 34): `auto` / `review` / `explicit` per action.

---

## 10. Daily pipeline (M11)

10 stages in dependency order: `discover → classify → eligibility → score →
hybrid_score → select → research → packages → outreach → digest`.

- **`daily_target` counts NEW QUALIFYING PACKAGES** — never scrapes, never scores (Golden Rule 4).
- **Never lowers the bar:** shortfalls are reported with machine-readable reasons
  (`AI_QUOTA_EXHAUSTED`, `ALL_SCORED_BELOW_CUTOFF`, `TARGET_REACHED`, `RUN_INTERRUPTED`, …).
- **Crash-resumable:** state is persisted *before* each stage; completed stages never
  re-run, a crashed stage re-runs with an explicit reason.

---

## 11. Analytics, response monitoring, feedback (M12)

- **8-class email classifier** (rule-based, deterministic): interview invite ·
  rejection · availability request · more-info request · offer · auto-ack ·
  out-of-office · unrelated — with a **0.70 confidence floor routing to REVIEW**.
  Low confidence never silently changes state.
- Response-rate analytics, funnel, per-source/per-role breakdowns, score calibration,
  weekly velocity, outreach↔response correlation, time-to-first-response.
- **Feedback loop proposes only** (`auto_rewrite_performed: false`); recommendations
  need a minimum sample size before they appear.

---

## 12. Observability & cost control (M14)

- `GET /api/analytics/monitoring` — spend (all-time + today), calls, tokens,
  per-model breakdown, avg cost/call, budget projection, cache hit-rate, daily-run state.
- Static pricing table with family matching; `:free` models billed **$0**;
  metering can never break a real AI call.
- **AI Usage & Cost** panel on the Stats page.
- Cache-hit metrics for research lookups.

---

## 13. Interfaces

**Web SPA** (vanilla JS, no build step): feed, job detail, pipeline Kanban
(drag-and-drop through the validated engine), triage, queue/approval, calendar,
network/contacts, stats + usage, settings, onboarding wizard.

**CLI** (`root/cli.py` — same service layer, no parallel implementation):
```bash
jobagent health                     # DB + pipeline status
jobagent search "AI Engineer" --min-score 70 --limit 10
jobagent prepare <job_id>           # status → prepared
jobagent contacts <job_id>          # contact research
jobagent daily                      # today's target/package accounting
jobagent followups                  # due follow-ups (terminal stop respected)
jobagent analytics                  # funnel + feedback recommendations
jobagent status <job_id> --set interviewing
```

---

## 14. AI providers

| Provider | Base URL | Notes |
|---|---|---|
| OpenRouter | `https://openrouter.ai/api/v1` | **default**; free tier has a daily cap |
| DeepSeek | `https://api.deepseek.com` | OpenAI-compatible; `deepseek-flash` |
| Anthropic | SDK | Claude family |
| OpenAI | `https://api.openai.com/v1` | GPT family |
| Google | Gemini OpenAI-compat endpoint | Gemini family |
| AWS Bedrock | SDK | Claude on Bedrock |
| Ollama | local | fully offline, $0 |

Shared plumbing: retry with `Retry-After` awareness, per-service circuit breaker,
token/cost metering, masked keys in every settings response.

---

## 15. Golden rules enforced in code

1. **Draft, never send** — no send path exists; `JOBAGENT_ALLOW_SEND` defaults false.
2. **Never hallucinate** — evidence gate refuses unverified claims.
3. **Deterministic before LLM** — filters, dedup, arithmetic are Python.
4. **Packages ≠ scraped URLs** — the daily target counts qualifying packages.
5. **Country = config** — one YAML per country, zero code.
6. **Human approval gates** — packages are review-ready; outreach is drafted.
10. **Job freshness max 7 days**; `DATE_UNKNOWN` never becomes fresh.
11. **E2E verification** — a module is done only when proven through the live API.

---

## 16. Honest limits (what it cannot do today)

| Limit | Detail | Workaround |
|---|---|---|
| **Indeed is IP-blocked** | Cloudflare serves a challenge to datacenter IPs even with Playwright + stealth. | Residential proxy, or a paid job-data API. Other 20 sources still run. |
| **USAJOBS / Adzuna need keys** | They skip cleanly when keys are absent (`found 0`). | Add keys in Settings → scraper keys. |
| **AI quota is the real bottleneck** | OpenRouter free tier = 50 requests/day; when exhausted, AI scoring/tailoring **skips honestly** (hybrid scoring still covers the pool for free). | Add a DeepSeek key ($2 ≈ 380 applications). |
| **No auto-submission** | By design: the system prepares and drafts; you approve and send. | — |
| **Gmail OAuth flow** | Draft-only REST provider is implemented; the interactive OAuth consent UI is not. | Local-draft fallback works with no token. |
| **Currency not converted** | Salaries stay in source currency (MCF = SGD, others USD/EUR). | Salary floors are compared per-country config. |
| **Classification is rule-based** | The 8-class reply classifier uses keyword rules, not an LLM. | Ambiguity routes to REVIEW rather than guessing. |
| **Docs gaps** | Standalone DATABASE / PROVIDERS / SECURITY / DEPLOYMENT pages are still to write. | This document + `ARCHITECTURE_DECISION.md` cover most of it. |

---

## 17. Running it

```bash
cd job-search-system/root
cp .env.example .env          # add JOBAGENT_OPENROUTER_API_KEY (and optionally DEEPSEEK)
uv sync                       # add --extra playwright for the Indeed browser path
uv run pytest                 # 886 backend tests
cd app/static && npx vitest run   # 180 frontend tests

# E2E harness — MUST run from root/ so relative config paths resolve
cd ..                         # back to job-search-system/
cd root && .venv/bin/python ../analysis/e2e_module_test.py

# server
cd root && .venv/bin/python -m uvicorn app.main:create_app --factory \
    --host 0.0.0.0 --port 8085
# then open http://localhost:8085
```

**Getting started in the UI:** upload your resume → analyze (fills search terms) →
Settings → AI (pick provider + model) → Countries (enable targets) → Scrape →
review scores in the Feed → build a package → approve → draft outreach → track in
the Pipeline. Stats shows cost/usage.

---

## 18. Cost economics (DeepSeek Flash, off-peak)

| Operation | Tokens (in/out) | Cost | $2 buys |
|---|---|---|---|
| Read a resume | 2K / 0.5K | $0.0006 | ~3,300 |
| Analyze a resume | 4K / 1K | $0.0012 | ~1,660 |
| Score a job | 6K / 1.5K | $0.0018 | ~1,110 |
| **Full application package** | **15K / 5K** | **$0.00525** | **~380** |
| Heavy agent run | 30K / 8K | $0.0093 | ~215 |

Metered live in-app; the monitoring endpoint reports real spend so projections are
measured, not guessed.
