# Discovery + Scoring Redesign — Plan

Status: **Phases 1–3 IMPLEMENTED AND VERIFIED. Phases 4–6 still open.**
Branch `user_change_before_new_feature`. Date: 2026-10-07.
Written against the live DBs on Basil's machine.

**Decisions taken (Basil, 2026-10-07):** hybrid-first scoring with the AI on a
shortlist; measure first, then target ~100 per batch; prune the 1,245-job
backlog behind a dry run.

Basil's request, in his words:

1. Discovery should be **role-based** — only fetch jobs for *my* job role. Other job
   details are not needed. "That 1002 jobs are not worth it even scraping."
2. **No one-by-one AI calls.** Chunk it — take only what matters (my resume content
   + the job description), **batch 100–200**, and call **in parallel**.
3. **A report** showing all the job scores, properly checked.
4. Refine the structure and the scoring.
5. **PDF/DOCX are good — do not touch them.**

---

## 1. What I measured (real numbers, not estimates)

### Discovery is over-broad

| Measure | Value |
|---|---|
| Jobs in `root/data/jobagent.db` | **1,245** |
| Distinct job titles | **940** |
| Jobs with a usable description (>200 chars) | 1,001 |
| Configured `search_terms` | **10** |
| Configured `job_titles` | 8 |
| Registered scrapers | 23 |
| Registered adapters | 10 |

`app/discovery.py` builds the work list as a **cross product**:

```
for country in enabled_countries:        # app/country_registry.py
    for term in search_terms:            # 10
        for source in registry:          # ~33 total
            adapter = adapter_cls(search_terms=[term])   # NEW instance per pass
```

With 10 terms × N countries × ~33 sources, the pass count is in the
**hundreds to low thousands**, and every pass is an independent HTTP fetch that
returns the source's *entire feed* for that term. 940 distinct titles out of
1,245 jobs is the signature of exactly that.

### The role gate exists — but it runs *after* the fetch

`app/title_filter.py` is a deterministic, zero-AI title gate
(`is_relevant_title()`) that correctly rejects `Graphic Designer`,
`Billing Specialist`, `Actuarial Director`, interns, recruiters, nurses. But it
is applied **at ingest**, i.e. **after** the HTTP request and after the source
has already sent the whole feed. It saves database space; it does not save
bandwidth, request budget, or rate-limit exposure.

Meanwhile the scrapers **already accept a query**: `JobListing` scrapers take
`search_terms` (`app/scrapers/base.py:104`) and pass them upstream —
LinkedIn `keywords=query` (`linkedin.py:23`), Dice `q=query` (`dice.py:27`),
Indeed one search per keyword (`indeed.py:194,239`). So role-targeted discovery
is a **plumbing + configuration problem, not a scraper rewrite**.

### Eligibility is already doing the heavy lifting

| `eligibility_status` | Jobs |
|---|---|
| INELIGIBLE | **962** |
| ELIGIBLE | **240** |
| REVIEW_REQUIRED | 42 |
| NULL (never evaluated) | 1 |

So the pipeline already discards ~77% of what discovery brings in. The waste is
upstream of the gate.

### Scoring: the free engine has never run, and the AI paid for everything

From `job_scores` in the workspace DB:

| Measure | Value |
|---|---|
| Score rows | 240 |
| With `ai_score` | **240** |
| With `hybrid_score` | **0** |
| Eligible jobs with no score row | 0 |

Two conclusions:

- **Every eligible job has been scored by the paid AI.** 240 jobs ≈ 12 batches of 20.
- **`hybrid_score` is 0 — the free, deterministic `HybridMatcher` has never
  produced a live score.** `app/matching_service.py::score_all_unscored()` is
  wired to three endpoints but is not the path that scores on the scheduled run;
  the scheduled path writes `db.insert_score()` (AI) directly.

This is the single largest cost lever in the system, and it is currently unused.

### Why "batch 200" cannot work as written

`app/main.py:518 _score_unscored()`:

```python
batch_size = max(1, min(int(os.getenv("JOBAGENT_SCORE_BATCH_SIZE", "20")), 25))
for i in range(0, total, batch_size):          # SEQUENTIAL
    results = await matcher.score_batch(batch)
    ...
    await asyncio.sleep(0.5)                    # yield between batches
```

`app/matcher.py:246`:

```python
max_tokens = 512 * len(jobs)                    # 200 jobs => 102,400
```

`app/ai_client.py:237,243`:

```python
_MAX_OUTPUT = {"deepseek": 16384, ...}
def output_budget(self, requested): return max(256, min(max(requested, floor), cap))
```

The requested budget is **clamped to the provider cap**:

| Batch | `512 × n` requested | actual budget |
|---|---|---|
| 20 | 10,240 | 10,240 |
| 25 (current max) | 12,800 | 12,800 |
| 32 | 16,384 | 16,384 (= cap) |
| **100** | 51,200 | **16,384** |
| **200** | 102,400 | **16,384** |

So raising the env var to 100 or 200 gives the model **the same 16,384 tokens as
a 32-job batch** while asking it to describe 100–200 jobs. The JSON gets
truncated mid-string, `_extract_array()` raises, and `score_batch()` falls
through to:

```python
return await self._fallback_individual(jobs)     # ONE API CALL PER JOB
```

**That is the one-by-one behaviour Basil is describing.** Today it is a silent
failure mode: a batch that is too large degrades into N calls, and nothing
records that it happened.

Batch size is therefore governed by **output tokens per job**, not by want.

### Measured (Phase 1, complete — from 240 real AI-scored rows)

The per-job output entry (`job_index`/`score`/`role_match`/`reasons`/`concerns`/
`keywords`) reconstructed from `job_scores` is **411–1,306 JSON chars**, i.e.
**~186 tokens at p50 and ~230 at p90**. Against the 16,384 cap:

| Batch | Output tokens needed | Verdict |
|---|---|---|
| 50 | ~7,400 (45%) | comfortable |
| **68–71** | **~15,700 (~96%)** | **the real ceiling at p90** |
| 100 | ~16,000 (97.5%) | no safety margin — one verbose job truncates |
| 150 | ~25,500 (155%) | overflows |
| 200 | ~35,900 (219%) | overflows badly |

So **200 jobs cannot fit in one completion with the current output schema**.
100 fits only with zero headroom. Two honest options:

1. **Target 100, clamp to what fits** (implemented): `plan_batches()` sizes each
   call from the measured p90 and a 0.9 safety factor, giving **~64 jobs/call**
   on deepseek (16,384 × 0.9 ÷ 230). A request for 100 or 200 is honoured as
   "as many as fit", and the clamp is logged rather than silently applied.
2. **Shrink the output** (not implemented): dropping `concerns` and `keywords`
   from the AI response would roughly halve the payload and let 200 fit. Real
   saving, but it changes the score record, so it is a separate decision.

Also dead-but-dangerous: `app/matcher.py:375 batch_score()` is a true N+1 loop
(one call per job, `delay=2.0s`). It has **no callers** — remove it so nobody
revives it.

---

## 2. Root causes, ranked

| # | Cause | Effect |
|---|---|---|
| 1 | Cross-product fan-out (term × country × source), each fetching a whole feed | 1,245 jobs / 940 titles, most irrelevant |
| 2 | Role gate applied after the fetch, not in the query | Wasted bandwidth, requests, rate-limit budget |
| 3 | AI scoring runs on **all** eligible jobs | Pays for jobs already rankable for free |
| 4 | Free `HybridMatcher` never runs on the scheduled path | The cheap lever is dead |
| 5 | `max_tokens = 512 × n` clamped to the 16,384 cap | Batches >32 silently truncate |
| 6 | Truncation falls back to **N individual calls** | The N+1 blowup Basil sees |
| 7 | Batch loop is strictly sequential | Wall-clock = Σ every batch |
| 8 | No per-job score provenance/coverage report | "Check properly" is impossible today |

---

## 3. Target design

### 3.1 Role-targeted discovery (fix causes 1, 2)

Keep the fan-out shape but stop treating it as unbounded, and push the role
filter into the request:

1. **Query-first.** Keep passing `search_terms` to adapters (already supported).
   Add a per-source capability flag `supports_query` in `app/source_registry.py`
   so feed-only sources (USAJobs-wide, HackerNews, Arbeitnow) are known to be
   post-filtered and get a **tight ingest cap** instead.
2. **Bound the cross product in config, not in hope.** Add an explicit
   `search_max_passes_per_cycle` and a per-source `max_results_per_pass`
   (today the source decides). Log the planned pass count *before* starting so
   the cost is visible up front.
3. **Country-term pairing.** Do not fan all 10 terms across all countries.
   A term belongs to a country only when that country is a target
   (`supported_countries` / `country_code`) — the classification layer already
   knows this. This alone cuts passes by roughly the country count.
4. **Prune before scrape.** Rank existing jobs by the free hybrid score and
   *dismiss* the tail instead of carrying 1,245 rows forward. Add an explicit
   `POST /api/admin/prune-jobs` (dry-run by default) that reports what it would
   remove before removing it.
5. **Keep `title_filter.py`** as the last line of defence, and add its reject
   counts to the run telemetry so "how much noise did each source send" is
   measurable.

### 3.2 Chunked + parallel scoring (fix causes 3–7)

Flip the order to **free first, paid on the shortlist**:

```
eligible jobs
   │
   ▼
① hybrid score (deterministic, zero AI, in-process, ~all jobs at once)
   │
   ▼
② shortlist = top N by hybrid score  (N configurable, default 100–150)
   │
   ▼
③ AI scoring in parallel batches of ~100 (measured), inside the 16,384 cap
   │
   ▼
④ report
```

Concretely:

- **Enforce a real per-batch safety.** Replace `512 * len(jobs)` with a
  *measured* per-job output estimate, and **pre-split** any requested batch so
  the requested budget never exceeds the cap:
  `jobs_per_call = min(requested, floor(cap / measured_output_per_job))`.
- **Parallelise** the batch loop with `asyncio.gather` + `asyncio.Semaphore`,
  exactly as `discovery.py` already does
  (`JOBAGENT_DISCOVERY_CONCURRENCY`, default 5). New
  `JOBAGENT_SCORE_CONCURRENCY` (default 4). Accepts `1` = serial, preserving
  today's behaviour for tests.
- **Never explode on truncation.** Replace `_fallback_individual` with a
  **bisect**: on a truncated/parse-failed batch, split in half and retry; only
  fall back to single calls at size 1. This turns "N calls" into `log2(N)`.
- **Record every call.** Write batch size, tokens, finish_reason, retries and
  fallbacks to `ai_usage` so the cost is auditable, not inferred.
- **Recommend flipping the scheduled path to hybrid-first**, so the AI only sees
  the shortlist. This is the change that makes 1,245 jobs cheap; it is also the
  one that changes scoring semantics, so it is an open decision (§7).

### 3.3 Score report (fix cause 8)

`GET /api/scores/report` (+ an on-disk JSON/MD artifact), per job:

- hybrid score, AI score, effective score, and **which engine decided it**;
- component scores and hard blockers;
- eligibility status/gate/reason;
- **coverage line**: eligible / hybrid-scored / AI-scored / unscored, and any
  job that is eligible but unscored (must be 0, or explain why);
- **integrity checks** the report itself asserts: no INELIGIBLE/REVIEW job
  present, `scored + skipped == requested` per batch, no fabricated zeros, no
  batch that fell back to individual calls unless declared.

Written as `docs/score/SCORE_REPORT_<date>.md` + `results/score_report.json`,
reusing the existing verifier style in `analysis/`.

---

## 4. Research: existing GitHub scrapers — what to adopt

Basil asked for this explicitly. Findings:

| Project | Licence | Coverage | Verdict |
|---|---|---|---|
| **speedyapply/JobSpy** | MIT | LinkedIn, Indeed, Glassdoor, ZipRecruiter, Google, Bayt, BDJobs. Query-driven (`search_term`, `location`, `results_wanted`). ~4.1k stars, active. | **Strongest candidate.** MIT (no AGPL trap, unlike `junian.css`). Query-first matches exactly what §3.1 wants. |
| **kalil0321/ats-scrapers** | open | Reusable adapters: Workday, Greenhouse, Lever, Ashby, SmartRecruiters, SuccessFactors | **Useful reference.** We already ship greenhouse/lever/ashby/smartrecruiters scrapers; **Workday is the gap** (we have `ats_detect` URL rules but no adapter). |
| **Feashliaa/job-board-aggregator** | open | Claims 1M+ positions across Greenhouse/Lever/Ashby/Workday | Reference only — indexes others' data. |
| Apify / commercial ATS scrapers | paid | 7 ATS platforms, from $0.60/1k postings | Out of scope (paid, external). |

**Recommendation:** do **not** replace our scraper layer. It already covers
LinkedIn/Indeed/Dice/Greenhouse/Lever/Ashby/SmartRecruiters/myCareersFuture and
already accepts queries. The gap is **Workday** and **Glassdoor/ZipRecruiter**
coverage, plus the fan-out discipline in §3.1. Adopt JobSpy *only* as an
optional adapter for the boards we lack, behind the same registry +
`title_filter` + rate-limiter pipeline. Rejected: adopting JobSpy wholesale
(duplicates 8+ working scrapers and adds a heavy dependency).

---

## 5. Phased plan

Each phase ends with a verification I actually run.

### Phase 1 — Measure before changing ✅ DONE
- Measured **output tokens per scored job** from the 240 real AI-scored rows in
  `job_scores` (free — no API call needed; `ai_usage.purpose` is NULL so the
  historical table could not be split by purpose). Result: **p50 ~186, p90 ~230
  output tokens/job**, giving a **~64 job/call** safe batch on deepseek.
- Still open: live pass count for a discovery cycle, and a wall-clock baseline
  for 100 jobs (needs a provider call — deferred, see Phase 3).

### Phase 2 — Scoring: correct + parallel + no N+1 ✅ DONE

Implemented in `app/matcher.py` + `app/main.py::_score_unscored`:

- **Cap-aware pre-split.** `MEASURED_OUTPUT_TOKENS_PER_JOB = 230`,
  `BATCH_SAFETY_FACTOR = 0.9`; `jobs_per_call()` / `plan_batches()` clamp every
  batch to what genuinely fits and log the clamp.
- **Budget from measurement**, not `512 * n`.
- **Bisect recovery.** An unusable/truncated response halves the batch
  (`_bisect`, depth-capped) instead of issuing one call per job.
- **Provider failure aborts immediately** — a smaller batch cannot rescue a
  dead provider, so a dead provider now costs **one** call instead of N.
- **Parallel batches.** `asyncio.gather` + `asyncio.Semaphore`
  (`JOBAGENT_SCORE_CONCURRENCY`, default 4, `1` = serial). Fetches run in
  parallel; SQLite writes stay serial, matching the discovery orchestrator.
- **Observable outcome.** `matcher.stats` = calls / bisects / individual
  fallbacks / aborts, logged at the end of each run — the silent N+1
  degradation can no longer happen unnoticed.
- **Deleted** the dead `JobMatcher.batch_score()` (N+1, per job + 2s delay, no
  callers) so it cannot be revived.

**Verification (all run, exit status preserved):**

- Scoring suites: **57 passed**.
- **Full backend suite: 1371 passed, 0 failed** (`-n 4`, 292s).
- New regression tests:
  - `test_matcher_batch_size_is_clamped_to_the_provider_cap` — a 200-job
    request is clamped, and no job is dropped.
  - `test_oversized_batch_is_bisected_never_one_call_per_job` — 8 jobs in
    **3 calls** (`[8, 4, 4]`) instead of 8, with `individual == 0`.
  - `test_provider_outage_costs_one_call_not_one_per_job` — 10 jobs, **1 call**.
  - `TestBatchRecovery` — 4 jobs in 3 calls, no fabricated scores, correct ids.
- Pre-existing bug found and fixed along the way: `_FakeTailor.prepare()` in
  `tests/test_application_builder.py` had drifted from the real
  `Tailor.prepare()` signature (missing `target_contact_line`/`target_country`),
  so `test_regenerate_true_overwrites_and_records_provenance` was failing with a
  `TypeError` from production code. The stand-in now mirrors the real signature.
- Not yet done: a live provider run proving the wall-clock speedup. Deferred to
  Phase 3, which needs a live call anyway.

### Phase 3 — Hybrid-first shortlist ✅ DONE

**The root cause of `hybrid_score = 0` turned out to be a one-line reuse bug.**
The hybrid pass called `get_scoreable_jobs()`, which filters on
`js.ai_score IS NULL` — correct for the AI entry point, fatal for the free one.
Once the AI had scored every eligible job the hybrid engine was handed an
**empty list**, so it never produced a single score while the paid layer scored
all 240. Proven on the live DB:

| Input set | Jobs |
|---|---|
| old hybrid input (`ai_score IS NULL`) | **0** ← why `hybrid_score` was 0 |
| new hybrid input (all eligible) | **240** |
| AI shortlist (limit 100) | **0** ← all 240 already AI-scored, so nothing to re-pay for |

Implemented:

- `Database.get_hybrid_scoreable_jobs()` — every ELIGIBLE job, with or without
  an AI score. The free engine now sees the whole pool.
- `Database.get_ai_shortlist(limit)` — AI-scoreable jobs ordered
  `hybrid_score DESC`, with not-yet-ranked jobs sorted **after** rather than
  dropped, so a big shortlist can never starve an unranked job.
- `matching_service.score_all_unscored()` switched to the new free-layer query.
- `_score_unscored` now runs the **hybrid baseline first**, then AI-scores only
  the shortlist. `JOBAGENT_AI_SHORTLIST` (default **100**); `0` restores the old
  score-everything behaviour. A hybrid failure is caught and logged — the free
  layer can never block the paid one.

**Verification:** 4 new regressions in `tests/test_scoring_ownership.py`
(hybrid not starved by an AI score; shortlist ranks best-hybrid-first and keeps
unranked jobs; the limit is honoured; AI-scored jobs leave the shortlist).
**Full suite: 1375 passed, 0 failed** (`-n 4`, 323s).

Still to check once a live AI run happens: that a real run's AI call count drops
from 240 to the shortlist size, and that shortlist selection agrees with
hand-reviewed quality (a high hybrid score must actually mean a better job).

### Phase 4 — Discovery discipline
- `supports_query` per source; country-term pairing; per-source result caps;
  pass-count logging; title-filter reject counts in telemetry.
- **Verification:** live cycle shows a materially lower pass count and fewer
  irrelevant inserts, with **no loss of relevant jobs** (compare the set of
  role-matching jobs found before vs after).

### Phase 5 — Report
- `/api/scores/report` + `docs/score/SCORE_REPORT_<date>.md` + `results/*.json`.
- **Verification:** report's own integrity assertions pass on live data; a human
  can read one row per job and see which engine decided its score.

### Phase 6 — Prune (opt-in, reversible)
- Dry-run prune endpoint + UI count, then apply on approval.
- **Verification:** dry-run output reviewed before anything is removed; backups
  first.

---

## 6. Explicit non-goals

- **No change to PDF/DOCX/Markdown rendering** — Basil: "that pdf and docx
  format are very good." The one known defect there (DOCX paper = Letter while
  PDF = A4, `app/html_docx.py:210,299`) is tracked separately and is **not** part
  of this work unless asked.
- No change to the evidence gate or tailoring.
- No new paid service. JobSpy is optional and MIT.

---

## 7. Decisions (all answered 2026-10-07)

- **Hybrid-first scoring: YES.** The AI scores a shortlist, not every eligible
  job. Biggest cost win — today `hybrid_score` is 0 on live data while all 240
  eligible jobs were AI-scored.
- **Batch size: measure, then target ~100.** Measured ceiling at p90 is ~68–71;
  the implemented clamp lands on **~64 jobs/call** on deepseek. Pushing to 200
  would require slimming the AI output first (separate decision, option 2 above).
- **Parallelism: yes**, `JOBAGENT_SCORE_CONCURRENCY` default 4, `1` = serial.
- **Backlog: prune the 1,245, dry-run first.** Nothing is deleted until Basil
  has seen the dry-run report.

1. **Hybrid-first scoring (Phase 3)** — AI only on the top N shortlist instead of
   all eligible jobs. Biggest cost win; changes what "score" means for the tail.
   Yes / no / shortlist size?
2. **Recommended batch size** — Phase 1 will give the real number under the
   16,384 cap (expect ~90–135). Target **100** (achievable) rather than 200
   (silently truncates)? Or reduce per-job output (drop `concerns`/`keywords`
   from the AI response) so 200 genuinely fits?
3. **Parallelism** — `JOBAGENT_SCORE_CONCURRENCY` default 4? Higher risks
   provider rate limits; the retry/backoff in `ai_client` handles 429 with
   `retry-after`.
### Still to build

- Phase 3 — hybrid-first shortlist on the scheduled scoring path.
- Phase 4 — discovery discipline (per-source query capability, country/term
  pairing, per-source caps, pass-count logging).
- Phase 5 — the score report endpoint + artifact.
- Phase 6 — the dry-run prune endpoint.
