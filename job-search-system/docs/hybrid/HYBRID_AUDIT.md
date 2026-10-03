# STAGE-5 HYBRID_SCORE — AUDIT

> Static audit from reading the code. **Not executed** — the environment's command classifier was
> unavailable throughout, so nothing below was reproduced live. Every finding cites `file:line`.
>
> Stage 5 of `app/daily_run.py:29` (`STAGES`). Upstream: Stage-4 SCORE (AI).
> Downstream: Stage-6 SELECT.
>
> The headline: **the stage has zero LLM by construction (verified) and its batch path is correctly
> gated by Stage-3 — but two reachable API paths score against an empty or wrong profile, and one
> silently destroys the AI score.**

---

## 1. What the stage does today

| Piece | Location |
|---|---|
| Deterministic engine | `HybridMatcher` — `app/hybrid_matcher.py:392` |
| Scoring entry (batch) | `score_all_unscored` — `app/matching_service.py:122` |
| Profile assembly | `build_candidate_profile` — `app/matching_service.py:24` |
| Router surface | `app/routers/matching.py` |
| Weights | `DEFAULT_WEIGHTS` — `hybrid_matcher.py:380`; validated by `_validated_weights:453` |
| Blocker cap | `BLOCKER_CAP = 25` — `hybrid_matcher.py:389` |
| Persistence | `db.upsert_hybrid_score` — `app/database.py:1174` |
| Input query | `db.get_scoreable_jobs` — `app/database.py:1722` |
| Live scheduler call | `app/main.py:285-288` |

The engine combines six 0–100 components by weights and writes the result into the **same
`job_scores` table** the AI scorer uses:

```python
# app/index… app/hybrid_matcher.py:380
DEFAULT_WEIGHTS = {"skills": 0.35, "role": 0.15, "location": 0.10,
                   "visa": 0.10, "recency": 0.10, "semantic": 0.20}
```

## 2. Contract vs reality

| Claimed | Actual |
|---|---|
| "No LLM" (`hybrid_matcher.py:5`) | **True** — the module imports no AI client; the whole path is arithmetic |
| "whatever AI could not [score]" (`daily_run.py:34`) | **True for the batch path** — `get_scoreable_jobs` filters `js.id IS NULL` (`database.py:1731`) |
| "the AI scorer … refines on top" (`matching.py:4`) | **Inverted.** AI runs first (`STAGES` order), hybrid is the *fallback* beneath it |
| "Same inputs => same outputs" (`hybrid_matcher.py:393`) | Numbers yes; **stored reason lists no** (H7) |
| `/score-all` runs "the hybrid engine" (`matching.py:62`) | Runs it against an **empty profile** (H2) |
| Optional remote embeddings are used when configured (`matching_service.py:103-106`) | **Never used** — the async path has no caller (H3) |
| Blocker cap is consistent | **True** — `weighted = min(weighted, BLOCKER_CAP)` at `hybrid_matcher.py:426` |

---

## 3. Defects found

### H1 — a manual hybrid re-score permanently destroys the AI score
**✅ FIXED 2026-10-03** — found already implemented in the working tree; verified, docs were stale.
`app/routers/matching.py:32-47`, `app/database.py:1180`, `app/database.py:1731`

```python
# routers/matching.py:44
await db.upsert_hybrid_score(job_id, ...)      # INSERT OR REPLACE INTO job_scores (job_id UNIQUE)
```

`job_scores.job_id` is `UNIQUE`, and `upsert_hybrid_score` is `INSERT OR REPLACE` (`database.py:1180`).
So `POST /api/matching/jobs/{id}/score` **replaces the whole row** — the AI's `match_reasons`,
`concerns`, and `suggested_keywords` are overwritten with the deterministic engine's.

The damage is permanent because `get_scoreable_jobs` only returns jobs with **no** score row:

```sql
-- database.py:1731
WHERE js.id IS NULL AND j.dismissed = 0
```

Once a job has a hybrid row it is no longer "unscored", so **no automated path will ever re-score it**
with the AI. An explicit "re-score this job" click silently downgrades the primary signal to the free
baseline, and only `clear_failed_scores` / `clear_all_scores` can undo it.

**Why it matters:** the AI score is the expensive, semantic signal; the hybrid score is the cheap
fallback. A one-click action converts the former into the latter with no warning and no return path.

**Resolution (2026-10-03):** when this stage was picked up, the ownership split was **already present in
the working tree** (`job_scores` had gained `ai_score` / `ai_scored_at` / `ai_model` / `hybrid_score` /
`hybrid_scored_at`, with an idempotent migration that backfills legacy rows by `component_scores`). Each
engine now owns its own column: `insert_score` never touches the hybrid columns, `upsert_hybrid_score`
never touches the AI columns, and `match_score` mirrors whichever score is *effective* (AI if present,
else hybrid). `get_scoreable_jobs` keys off `js.ai_score IS NULL` instead of `js.id IS NULL`, so a hybrid
row can no longer lock a job out of AI scoring. `clear_failed_scores` preserves a hybrid score while
freeing the job. Covered by `tests/test_scoring_ownership.py` — **8 passed**. The DEFECT_BACKLOG entry is
therefore stale; no code change was needed.

### H2 — `/api/matching/score-all` scores against an EMPTY candidate profile
`app/routers/matching.py:68-71`, `app/matching_service.py:94-106`

```python
# routers/matching.py:68
ai = await request.app.state.ai_state_for(request)
fake_state = type("_PerUserAIState", (), {})()
fake_state.matcher = ai["matcher"]           # ← only attribute set
result = await score_all_unscored(fake_state, _db(request))
```

`score_all_unscored` never reads `.matcher`. It calls `build_hybrid_matcher_async(app_state, db)`, which
reads three attributes off the state:

```python
# matching_service.py:94-101
build_candidate_profile(getattr(app_state, "evidence_store", None), ...)
weights = ... await db.get_hybrid_weights() ...
keywords = collect_visa_keywords(getattr(app_state, "country_registry", None))
```

On the fake state all three are absent, so:

- `profile.verified_skills = ∅`, `profile.verified_corpus = []` → `component_skills` hits the `denom == 0`
  branch and returns **50.0 for every job** (`hybrid_matcher.py:209-210`);
- empty corpus → `similarity_score` returns **50.0 for every job** (`hybrid_matcher.py:300`);
- `collect_visa_keywords(None) → []` → sponsorship scanning is disabled.

So the endpoint returns a plausible summary (`scored: N`) while every job received an evidence-blind
score. The scheduler path (`main.py:286`) passes the **real** `app.state` and is unaffected — only the
user-facing API is wrong, which is the one a person actually clicks.

### H3 — the async embedding RAG provider is dead code
`app/hybrid_matcher.py:322-346`, `:278-281`, `:412`

`OpenAIRagProvider` adds `similarity_score_async` (`:329`) — and **nothing calls it**. A repository-wide
search finds only its definition. `HybridMatcher.score_job` calls the synchronous method:

```python
# hybrid_matcher.py:412
sem_score = self.rag.similarity_score(text, self.profile.verified_corpus)
```

`OpenAIRagProvider` does not override `similarity_score`, so the base `RagProvider.similarity_score`
(local TF-IDF, `:298`) runs **even when an embedding client is configured**. The comment
`# has sync fallback via base class` (`matching_service.py:106`) is backwards — the base class is not a
fallback, it is the only path. `RagProvider.embed` (`:295`) raises `NotImplementedError` and is likewise
never invoked.

**Effect:** configuring an embedding provider changes nothing for Stage-5; the semantic component is
always local TF-IDF.

### H4 — the skills component measures the wrong direction
`app/hybrid_matcher.py:188-213`

```python
for raw in profile.verified_skills:      # ← iterates the CANDIDATE's skills
    if _skill_in_text(job_text.lower(), raw): matched.append(raw)
    else: missing.append(raw)
denom = len(matched) + len(missing)
```

The denominator counts only the candidate's own verified skills. The score is therefore *"what fraction
of my skills does this listing mention"*, not *"do I meet the listing's requirements"*. A posting
demanding twenty skills the candidate lacks incurs **no penalty** as long as it mentions a few of the
candidate's. The requirement-level view exists — `_requirement_terms` (`:353`) extracts "must have /
required / expertise" sentences — but it is written only to `matched_requirements` /
`missing_requirements`, and never enters the score.

### H5 — weights are silently renormalised after defaults are injected
`app/hybrid_matcher.py:453-459`, `app/routers/matching.py:113`

```python
merged = {**DEFAULT_WEIGHTS, **{k: float(v) for k, v in w.items() if k in DEFAULT_WEIGHTS}}
total = sum(merged.values())
return {k: v / total for k, v in merged.items()}
```

A user submitting `{"skills": 0.7, "role": 0.3}` intends "only these two matter". They get `merged` with
the four omitted components restored to their defaults (0.10/0.10/0.10/0.20), then everything divided by
1.5: skills ≈ 0.467, role ≈ 0.20, and 0.067/0.067/0.067/0.133 for the rest. The submitted intent is
discarded without a warning, and `PUT /api/matching/config` stores the rewritten weights.

### H6 — `role_match` is derived, so "no targets declared" reports as a match
`app/hybrid_matcher.py:104`, `:216-235`

```python
"role_match": self.component_scores.get("role", 0) >= 50,
```

`component_role` returns **50.0** when `profile.target_titles` is empty (`:222`) — its "neutral, nothing
declared" value. `50 >= 50` is `True`, so a candidate with no target titles is recorded as
`role_match = 1` on **every job**, even though nothing was compared. This matters because `role_match`
is the flag Stage-4's documented 50-point cap keys off.

### H7 — stored reason lists are non-deterministic
`app/matching_service.py:41-57`, `app/hybrid_matcher.py:120` (`_tokens`), `:188-213`

`profile.verified_skills` and `profile.do_not_use_skills` are Python **sets** (`matching_service.py:41`,
`:50`). `component_skills` iterates them to build `matched`/`missing`, which are persisted as
`match_reasons` / `concerns`. Set iteration order varies between interpreter processes, so two runs on
identical inputs can store the **same numbers in different list orders**. The module's own docstring
promises "Same inputs => same outputs" (`:393`); that holds for `overall_score` and `component_scores`
but not for the persisted lists.

### H8 — the scheduled call site uses the global DB
`app/main.py:285-288`

```python
await score_all_unscored(app.state, app.state.bg_db)
```

The production (scheduler) call passes `app.state.bg_db` — the shared background DB — not a requesting
user's workspace. This is the known **N3** per-user run-state gap, recorded here because Stage-5 is its
live call site. The per-user router path is separate and has the opposite problem (H2).

---

## 4. What holds (verified, not assumed)

- **Zero LLM.** `hybrid_matcher.py` imports `json`, `math`, `re`, `collections`, `dataclasses` and two
  local deterministic modules (`evidence_store.normalize_skill`, `freshness.assess_freshness`,
  `visa_engine.scan_visa_mentions`). No AI client anywhere in the path. Golden Rule 4 holds.
- **Stage-3 containment holds on the batch path.** `get_scoreable_jobs` requires
  `eligibility_status = 'ELIGIBLE'` AND `location_classified = 1` AND `js.id IS NULL`
  (`database.py:1731-1733`), so `score_all_unscored` cannot touch an INELIGIBLE job.
- **Blocker cap is applied consistently** — after weighting, before rounding (`:426`).
- **The audit trail exists.** `component_scores` + `hard_blockers` are persisted
  (`database.py:1181-1186`) and surfaced by `GET /api/matching/jobs/{id}/explain`.

---

## 5. What hardening should do

1. **Stop H1 destroying AI scores.** Either give hybrid scores a separate table/column, or make
   `upsert_hybrid_score` refuse to overwrite a row whose `component_scores` is already a *AI-authored*
   row, or make the manual endpoint `regenerate`-style explicit. At minimum, do not silently replace.
   A `source` column (`'ai' | 'hybrid'`) would make the collision visible and cheap to reason about.
2. **Fix the empty profile (H2).** Pass the real per-user state (the workspace-bound evidence store and
   country registry) into `score_all_unscored`, not a duck-typed stub.
3. **Delete or wire up H3.** Either call `similarity_score_async` when an embedding client exists, or
   remove `OpenAIRagProvider` so the code does not claim a capability it never exercises.
4. **Make the skills component mean what it says (H4).** Score requirement coverage (job requirements
   met) rather than candidate-skill coverage, or rename the component and document the inversion.
5. **Reject partial weight sets (H5)** instead of silently renormalising, or require all six keys.
6. **Record `source` provenance (H1/H8)** so a score's origin is queryable — this is the same deferred
   D4 item from Stage-4; the two should land in one schema change.
7. **Tests:**
   - Scoring with an AI row present then a manual hybrid score ⇒ the AI reasons are **not** silently lost
     (or an explicit error is raised).
   - `/score-all` with a workspace that has verified skills ⇒ skills component ≠ 50 for a job that
     mentions them (guards H2).
   - Two runs, same inputs, same profile ⇒ identical `overall_score` **and** identical reason lists
     (guards H7).
   - A job demanding only un-held skills scores lower than one demanding held skills (guards H4).
   - `_validated_weights({"skills": 0.7, "role": 0.3})` raises or preserves intent (guards H5).

---

## 6. Open questions

- Is a single `job_scores` table for two different scorers the right model at all, or should the hybrid
  layer write to its own table so both signals survive?
- `component_recency` uses `posted_date or created_at` (`:268`). `created_at` is when *we* first saw the
  job, not when it was posted — for a job scraped late this reports a fresh score for a stale posting.
  Worth separating explicitly (Golden Rule 10).
- Should `strategy_dismissed` (Stage-6 filter) also suppress hybrid scoring? Today only `dismissed` does
  (`database.py:1731`).
