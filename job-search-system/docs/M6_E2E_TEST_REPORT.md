# M6 E2E TEST REPORT — Hybrid Matching Engine

**Date:** 2026-09-23 (UTC)
**Milestone:** M6 — Hybrid matching (deterministic components + TF-IDF ATS overlap + RAG semantic layer)
**Method:** `analysis/e2e_module_test.py` section 16d — isolated instance of the real app
(fresh DB, evidence profile seeded from **Basil's real uploaded resume**), every check
exercised through the **live HTTP API** per Golden Rule #11.

**Harness result this run:** **116/116 passed** (106 PASS · 10 SKIP · 0 FAIL)
- All 10 SKIPs are the pre-existing AI-dependent checks (OpenRouter free-tier daily
  quota exhausted — `429 free-models-per-day`, resets 00:00 UTC). Environmental, not
  product failures. **M6 adds ZERO new AI dependencies — every M6 check ran for real.**
- Full-suite unit regression: **747 passed** (723 pre-existing + 24 new M6 tests).

---

## What was verified (17 new checks, all PASS)

| # | Check | Result |
|---|-------|--------|
| 1 | `GET /api/matching/status` — engine status | PASS |
| 2 | Verified skills (3) + corpus (4 lines) loaded from evidence store | PASS |
| 3 | Default weights normalized: sum=1.0 across 6 components | PASS |
| 4 | `POST /api/matching/score-all` — 12/12 unscored jobs, avg=39.0, zero AI cost | PASS |
| 5 | Score job → overall + all 6 components returned (overall=76) | PASS |
| 6 | Matched/missing requirement lists + explanation present | PASS |
| 7 | AI job skills component = **100.0** (Python/LangChain/RAG/Azure OpenAI matched) | PASS |
| 8 | **Determinism:** rescore returns identical overall (76 vs 76) | PASS |
| 9 | Noise job (Graphic Designer) skills=0.0 — far below AI job | PASS |
| 10 | **BLOCKER:** no-sponsorship job → `NO_SPONSORSHIP_STATED`, score capped at 25 | PASS |
| 11 | **BLOCKER:** DO_NOT_USE skill (COBOL) → capped at 25, Python still matched | PASS |
| 12 | Config PUT persists prefs (`requires_sponsorship=false`) | PASS |
| 13 | Wider prefs → no-sponsorship job unblocked (score 25→53) | PASS |
| 14 | Weights PUT normalized to sum=1.0 (custom 2:1 ratio preserved) | PASS |
| 15 | Hybrid scores persisted with component breakdowns (14 jobs) | PASS |
| 16 | `explain` endpoint returns stored breakdown (overall=76) | PASS |
| 17 | `top-jobs` ranked desc with breakdowns; AI job #1, noise job #9 | PASS |

## Score composition (AI job, the perfect-fit case)

```
overall = 76
skills=100.0  role=50.0  location=100.0  visa=40.0  recency=100.0  semantic=47.0
weights: skills .35 · role .15 · location .10 · visa .10 · recency .10 · semantic .20
```

## Architecture delivered (M6)

| Piece | File | Notes |
|-------|------|-------|
| Hybrid engine | `app/hybrid_matcher.py` | 6 deterministic components, configurable weights, hard-blocker short-circuit (cap=25), pure-Python TF-IDF (no new deps), `HybridScore` machine-readable output |
| Application service | `app/matching_service.py` | Builds `CandidateProfile` from VERIFIED evidence only (Golden Rule 5); visa keywords from M3 country registry; `score_all_unscored()` free baseline |
| RAG layer | `RagProvider` / `OpenAIRagProvider` | Local TF-IDF default (zero cost); retrieval feeds only relevant VERIFIED evidence; remote embeddings optional, never fail scoring |
| API | `app/routers/matching.py` | status · score-one · score-all · explain · config GET/PUT · top-jobs |
| DB | `job_scores.component_scores/hard_blockers`, `search_config.hybrid_weights/prefers_remote/requires_sponsorship` | Audit trail for every score; UPSERT pattern (M4 lesson) |
| Scheduler integration | `app/main.py` | After AI scoring attempt, hybrid scores whatever AI could not (quota/provider down) — the pool is never left unscored |

## Bugs found by E2E and fixed in this session

1. **`TfidfIndex` AttributeError** — doc vectors were computed before `idf` existed
   (ordering bug). Caught by unit tests pre-E2E.
2. **Word-boundary matcher stripped spaces** — `_boundary_count` collapsed whitespace,
   so "with python" → "withpython" and the lookbehind failed. Replaced with
   `_skill_in_text`: single-word boundary regex + word-sequence phrases for
   multi-word skills ("Azure OpenAI", "ci/cd").
3. **Normalized skills killed phrase matching** — `verified_skill_values()` returns
   normalized forms (`"azureopenai"`); matching job text against that can never hit.
   Profile now keeps **raw** values (normalized only as dedup key). Found live:
   skills component was 66.7, should be 100.0 → fixed, E2E re-run green.
4. **`Country.visa` attribute** — the visa dict exists only in `to_dict()`; the real
   attribute is `sponsorship_keywords`. Fixed `collect_visa_keywords()`.

## Definition-of-done evidence

- Unit: 24 new tests in `tests/test_hybrid_matcher.py` (weight math, determinism,
  blockers, evidence discipline, retrieval sanity, DB round-trips, fresh-DB UPSERT).
- E2E: section 16d in the shared harness — real app, real HTTP, real DB, Basil's real
  resume-derived evidence. Determinism proven through the API (same inputs ⇒ same score).
- Golden Rule 4 honored: no LLM anywhere in M6. Python owns 100% of the arithmetic.
- Golden Rule 5 honored: matching corpus = VERIFIED claims only; DO_NOT_USE skills
  hard-block instead of credit; UNVERIFIED never enters the corpus.

**M6 = DONE.** Next: M7 (company + contact research).
