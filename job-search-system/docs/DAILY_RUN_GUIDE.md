# DAILY RUN GUIDE — the daily loop, every stage explained, what to press and why

> **What this is:** the deep, step-by-step manual for STAGE 5 of the user
> process — the **Daily Run** and everything around it: where the button is,
> what each of the 10 stages does, what it costs, what can go wrong, and how to
> read the results. Everything here is taken from the actual code
> (`app/daily_run.py`, `app/routers/crm.py`, `app/static/js/views/stats.js`).

---

## 1. What the daily loop IS, in one sentence

**Every day, the system must turn fresh job listings into reviewed application
packages ready for you to send** — and the Daily Run is the one button (plus a
few clicks) that drives that pipeline end to end.

The target is **qualifying application PACKAGES created today**, not scraped
URLs and not emails sent. The system will never lower the eligibility bar or
invent evidence just to hit the number (Golden Rules #5, #6, #7).

## 2. Why it exists

| Without the daily loop | With the daily loop |
|---|---|
| You manually scrape, manually score, manually open jobs | One click computes everything computable |
| You forget which jobs you already processed | The run is **idempotent** — done stages never re-run today |
| You never know why there are no applications | Every miss has a **machine-readable shortfall reason** you can read |
| Spend is uncontrolled | AI stages are circuit-broken; the free hybrid layer scores the rest |

## 3. Where the button is (exact location)

1. Log in at `http://<server-ip>:8085`.
2. Left navigation → **Stats**.
3. Find the card titled **"Daily Run Pipeline (M11)"**.
4. Press the blue **"Run Daily Pipeline"** button (top-right of that card).

What you see there:

- **Packages today: N / target M** — today's progress against your target
  (default target: **5 packages/day**, score cutoff: **60**).
- **Target met ✓** or a **Shortfall:** line listing the reasons (see §6).
- A **stage list with colored dots**: green = done, amber = running,
  red = failed, grey = skipped/pending.
- The button disables and shows a spinner while running; results render in place.

## 4. The 10 stages — what each one does

Stage order = dependency order (`app/daily_run.py#STAGES`). A stage is
**skipped** if its inputs were produced by an earlier stage today and nothing
new is pending — that's what makes the run safe to press repeatedly.

| # | Stage | What it actually does | Cost |
|---|-------|----------------------|------|
| 1 | **discover** | Runs the scrape/adapter cycle over your enabled countries × search terms, budget-capped (24 passes max, 200 listings/pass). New listings enter **your** workspace pool. | Free (network only) |
| 2 | **classify** | Assigns each job a **region** (Germany/UK/UAE/NL/IE/SG/Remote…) using deterministic rules first, LLM only for ambiguous ones. Jobs that never classify stay invisible to scoring. | ~Free |
| 3 | **eligibility** | Deterministic gate chain on each job: dismissed? → region allowed? → **freshness** (posted ≤ 7 days; DATE_UNKNOWN is terminal) → description present? → repost pending? Ineligible jobs get machine-readable reason codes, zero LLM. | Free |
| 4 | **score** | AI scores each eligible job (relevance, concerns, keywords, role-match). Circuit breaker stops gracefully if the provider dies mid-run — never blocks the pipeline. | **AI spend** |
| 5 | **hybrid_score** | The free deterministic engine scores whatever AI could not: 6 components (skills .35 / role .15 / location .10 / visa .10 / recency .10 / semantic .20) + hard blockers (no sponsorship stated, DO_NOT_USE skills). The pool is **never left unscored**. | Free |
| 6 | **select** | Picks the top eligible+scored jobs **toward today's target** (cutoff 60 by default). Not enough good jobs? It reports the shortfall honestly instead of digging into the unqualified pile. | Free |
| 7 | **research** | Company enrichment (careers/LinkedIn URLs) + contact discovery (recruiter/hiring manager) per selected job, cache-first (7-day TTL), ranked by confidence. | Mostly free (Hunter/Apollo if you configured keys) |
| 8 | **packages** | Builds each package through the **evidence gate**: AI-tailored resume + cover letter that may only use your VERIFIED evidence, then `resume.docx`, `cover_letter.docx`, `metadata.json` written to your workspace. Fabricated claim → regenerate once → **422 refused**. | **AI spend** |
| 9 | **outreach** | Creates **DRAFT-ONLY** Gmail drafts (or local fallback) for packages with contacts. Idempotent: the same job+audience never gets a second draft. **Nothing is ever sent.** | Free |
| 10 | **digest** | Writes today's run summary (what was discovered, scored, packaged, what fell short) as your daily digest notification. | Free |

## 5. What pressing the button really runs (honest detail)

`POST /api/daily-run/run` is **idempotent and resumable** — state is saved to
the `daily_runs` table **before each stage**, so:

- A run that crashed mid-stage re-runs **only the crashed stage** (marked
  `RUN_INTERRUPTED`), never double-running paid AI stages.
- Completed stages today are skipped on re-press.
- The API trigger path computes what is computable right now: **select** (from
  the already-scored pool) and the **packages/outreach report**; discovery and
  AI scoring also run continuously on the **scheduler** (scrape every N hours,
  scoring hourly, maintenance daily). In other words: even if you never press
  the button, the pool keeps filling and scoring — the button closes the loop
  **now** and gives you the visible report.
- Packages are born `ready_for_review`; outreach is DRAFT-ONLY; the engine
  never sends anything.

## 6. Reading the shortfall reasons (never guess again)

| Reason | Meaning | What you do |
|---|---|---|
| `TARGET_REACHED` | Target met — nothing to fix | Continue: review packages |
| `NO_AI_PROVIDER` | No AI key configured for your user | Settings → AI & Integrations → add key |
| `AI_QUOTA_EXHAUSTED` | Provider rate-limited mid-run | Wait for quota reset / top up; hybrid scores still exist |
| `NO_ELIGIBLE_JOBS` | Everything was dismissed/stale/wrong region | Check Settings → Countries & Discovery; widen countries or wait for fresh listings |
| `ALL_SCORED_BELOW_CUTOFF` | Candidates exist but none reached 60 | Lower expectations or improve targeting: check Stats → Targeting Feedback |
| `SOURCES_EXHAUSTED` | All sources returned nothing new | Normal on quiet days; run again tomorrow |
| `RATE_LIMITED` | Scrapers got rate-limited early | Discovery will retry on the schedule; don't hammer |
| `EVIDENCE_GATE` | Packages refused — text claimed unverified facts | Settings → Evidence → verify the flagged claims, re-run |
| `PACKAGE_ERROR` | Generation failed | Check Stats → AI Usage; retry; report if persistent |
| `RUN_INTERRUPTED` | A previous run crashed mid-stage | Just press Run again — it resumes |

## 7. The rest of the daily loop (5–10 minutes of human work)

The button produces ready-to-review material; these steps are yours:

| # | You do | Where | Why |
|---|--------|-------|-----|
| 7.1 | Open **Jobs**, sort by score, open the top ones | Jobs page | Check the hybrid breakdown: matched skills, missing requirements, hard blockers |
| 7.2 | For a good job: **Prepare application** → **Build package** | Job detail → Pipeline Actions | AI-tailored resume + cover letter through the evidence gate; download and read the .docx |
| 7.3 | **Create outreach draft** (optional here; auto for selected jobs in the run) | Job detail | DRAFT-only; pick the right contact if several were found |
| 7.4 | Review every package before anything else | your `applications/` folder | You are the approval gate (Golden Rule #6) |
| 7.5 | Mark the job **applied** once YOU sent it | Job detail → status | Moves the CRM forward and starts follow-up cadence |
| 7.6 | **Pipeline / Network**: check follow-ups due | Network page | The engine drafts follow-ups after your configured wait (6d default); terminal states stop them |
| 7.7 | **Stats**: read AI Usage & Cost + Targeting Feedback | Stats page | Spend this month, cache hit-rate, what to target more/less |

## 8. Troubleshooting the daily loop

| Symptom | Cause / fix |
|---|---|
| "No run yet today" stays forever | You never pressed Run AND the scheduler is idle — press the button |
| Stage `score` failed instantly | No AI key or wrong key → Settings → AI & Integrations → Test |
| `packages` says pending, nothing built | The trigger path reports rather than half-builds: open each selected job → Pipeline Actions → Build package |
| Packages today = 0 but jobs are scored | See the shortfall line — usually `ALL_SCORED_BELOW_CUTOFF` or `NO_ELIGIBLE_JOBS` |
| Another user's run says `already_running` | Known M15c gap (per-user run-state is item N3 in `docs/NEXT_5_PLAN.md`) — retry after their run finishes |
| Packages today > 0 but you can't find them | Each package lives in **your** workspace: `data/users/<id>-<username>/applications/`, and on the job detail page |

## 9. The daily loop in one picture

```
        ┌──────────────────── automated (button + scheduler) ────────────────────┐
        │ discover → classify → eligibility → score → hybrid_score → select      │
        │   → research → packages (evidence gate) → outreach drafts → digest     │
        └────────────────────────────┬───────────────────────────────────────────┘
                                     ▼
        ┌──────────────────── human (5–10 min) ──────────────────────────────────┐
        │ review packages → (you approve) → YOU send the draft → mark applied    │
        │ → CRM tracks it → follow-ups drafted for you → responses classified    │
        └────────────────────────────────────────────────────────────────────────┘
```

## 10. Quick reference

| Thing | Value / place |
|---|---|
| Button | **Stats → Daily Run Pipeline → "Run Daily Pipeline"** |
| API | `GET /api/daily-run/today` · `POST /api/daily-run/run` |
| Daily target | **5 packages/day** (default) |
| Score cutoff | **60** |
| Freshness limit | **7 days** (older = STALE, never eligible) |
| Stage order | discover → classify → eligibility → score → hybrid_score → select → research → packages → outreach → digest |
| Never happens | auto-sending email, lowering the bar, inventing evidence |
| Code | `app/daily_run.py`, `app/routers/crm.py` (`/daily-run/*`), UI in `app/static/js/views/stats.js` |
