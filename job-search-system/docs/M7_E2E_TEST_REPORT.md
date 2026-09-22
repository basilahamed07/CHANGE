# M7 E2E TEST REPORT — Company + Contact Research

**Date:** 2026-09-23 (UTC)
**Milestone:** M7 — Company research cache + ContactProvider interface (Hunter/Apollo/Manual adapters) + contact confidence
**Method:** `analysis/e2e_module_test.py` section 16e — isolated instance of the real app
(fresh DB, evidence profile seeded from **Basil's real uploaded resume**), every check
exercised through the **live HTTP API** per Golden Rule #11.

**Harness result this run:** **129/129 passed** (119 PASS · 10 SKIP · 0 FAIL)
- The 10 SKIPs remain the pre-existing AI-quota checks (OpenRouter free tier, resets
  00:00 UTC). **M7 adds zero AI dependencies — all 13 M7 checks ran for real.**
- Full-suite unit regression: **776 passed** (747 + 29 new M7 tests).

---

## What was verified (13 new checks, all PASS)

| # | Check | Result |
|---|-------|--------|
| 1 | `GET /api/research/providers` — chain exposed | PASS |
| 2 | manual + web_search available; hunter/apollo correctly OFF (no keys configured) | PASS |
| 3 | Seed manual contact (Basil's saved contact in `contacts` table) | PASS |
| 4 | Research via real chain: **manual provider found the saved contact** (status=found, provider=manual, cache_hit=False) | PASS |
| 5 | Candidate classified `recruiter` + confidence=100 + rationale filled (deterministic) | PASS |
| 6 | Cached research returned with candidates intact | PASS |
| 7 | `select` → job gains hiring manager email | PASS |
| 8 | `job.hiring_manager_email` persisted (`jane.doe@e2eprobecorp.com`) | PASS |
| 9 | **Double-select does NOT duplicate the contact** (email dedup) | PASS |
| 10 | `force=true` bypasses cache and re-runs the chain | PASS |
| 11 | Company research 200 + persisted (graceful `not_found` when network blocked) | PASS |
| 12 | Company cache row readable + fresh | PASS |
| 13 | Second company call within TTL = cache hit (no re-research) | PASS |

## Architecture delivered (M7)

| Piece | File | Notes |
|-------|------|-------|
| Contact model | `app/contact_providers.py` | role_type taxonomy (recruiter / hiring_manager / referrer / other), confidence 0–100, relationship_to_job, why_selected rationale |
| Provider interface | `ContactProvider` | `find(job)` **never raises** (M4 adapter discipline); per-provider token-bucket rate limiting via existing `AsyncRateLimiter` |
| Hunter adapter | `HunterProvider` | hunter.io domain-search (ported from job-application-pipeline, MIT); `JOBAGENT_HUNTER_API_KEY` |
| Apollo adapter | `ApolloProvider` | apollo.io people search scoped by org + titles; `JOBAGENT_APOLLO_API_KEY` |
| WebSearch adapter | `WebSearchProvider` | wraps the existing DuckDuckGo heuristic (`contact_finder.py`) as an adapter |
| Manual adapter | `ManualResearchProvider` | surfaces contacts Basil already saved — **first in the chain, his own data wins** |
| Fallback chain | `default_provider_chain` | manual → hunter (if key) → apollo (if key) → web_search; first provider with results wins |
| Research service | `ContactResearchService` | cache-first (7-day TTL), classify → score → rank; `select_candidate` writes job + dedupes contacts table |
| Company enrichment | `app/company_enrichment.py` | deterministic careers/LinkedIn URL discovery + AI-clue extraction (regex, no LLM); 30-day cache TTL |
| API | `app/routers/research.py` | contacts/job/{id} POST+GET · select · providers · company/{name} POST+GET |
| DB | `contact_research` table (snapshot per job, UPSERT); `companies` + careers_url/linkedin_url/ai_clues/research_status/researched_at (+ allowlist update) | |

## Determinism proof (Golden Rule 4)

Classification and confidence are pure Python regex + arithmetic:
- `Technical Recruiter` → recruiter; `Head of AI` / `VP Engineering` → hiring_manager;
  `Senior Software Engineer` → referrer; `Accountant` → other (9-case table test)
- Confidence = provider base (manual 90 / hunter 70 / apollo 65 / web 40) + title
  overlap + role weight + personal-mailbox bonus − generic-inbox penalty − no-email penalty
- Same inputs ⇒ same score (unit-tested); E2E: recruiter with personal mailbox → 100

## Bugs found by E2E and fixed in this session

1. **Harness: `await (await client.get(...)).json()`** — httpx `.json()` is sync;
   `object dict can't be used in 'await' expression`. Fixed to two-step await.
2. **`_COLUMN_ALLOWLISTS["companies"]` missing the 5 new M7 columns** — `save_company`
   rejected `research_status`/`researched_at` with `Invalid columns for companies`.
   The allowlist must be updated whenever a table gains columns (lesson recorded).

## Definition-of-done evidence

- Unit: 29 new tests in `tests/test_contact_providers.py` — taxonomy table,
  confidence components, **provider failure → [] not raise**, hunter parse via respx,
  manual provider scoping, fallback order, **cache hit skips providers (calls==1)**,
  force bypass, double-select dedup, company link/AI-clue extraction, TTL math, DB round-trip.
- E2E: section 16e — real app, real HTTP, real DB, real provider chain with the
  manual adapter proving the fallback + cache semantics end-to-end.
- Golden Rule 9 honored: adapters over vendors — Hunter/Apollo are swappable behind
  one interface, and the system is fully functional with NO paid keys (manual + web).

**M7 = DONE.** Next: M8 (application package generation — DOCX-first, evidence-gated).
