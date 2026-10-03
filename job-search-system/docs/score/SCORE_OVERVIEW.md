# STAGE-4 SCORE — OVERVIEW

> Stage 4 of the 10-stage daily pipeline (`app/daily_run.py:29`, `STAGES`).
> Upstream: Stage-3 ELIGIBILITY. Downstream: Stage-5 HYBRID_SCORE.
> Where this document and the code disagree, the code wins.

---

## What this stage is for

Turn an eligible job posting into a **calibrated 0–100 fit score against Basil's resume**, with the
model's reasons and concerns recorded alongside it. A score is an *estimate*, not a fact — so the
stage's real contract is about what it must **never** do: invent a score, attach a score to the wrong
job, or record a fabricated zero when the model fails.

## Contract

| | |
|---|---|
| **Input** | Jobs where `eligibility_status = 'ELIGIBLE'` **and** no `job_scores` row exists (and not dismissed, and `location_classified = 1`) — exactly `db.get_scoreable_jobs()` (`app/database.py:1722`) |
| **Output** | Rows in `job_scores` (`app/database.py:259`), one per job (`job_id` is `UNIQUE`), written with `INSERT OR REPLACE` |
| **Entry point** | `_score_unscored(db, matcher)` — `app/main.py:458`, exposed as `app.state.score_unscored` |
| **Scheduled by** | `scheduled_scoring()` — `app/main.py:271`, hourly |
| **Engine** | `JobMatcher` — `app/matcher.py:185` |
| **AI calls** | Batch first (5 jobs/request); individual fallback on any batch failure |

### Order of operations

```
run_eligibility_pass(db)          ← Stage-3 gate runs again, so newly-scored-eligible rows are caught
  ↓
db.get_scoreable_jobs(limit=10000)   ← the ONLY input; INELIGIBLE / REVIEW_REQUIRED cannot enter
  ↓
for each batch of 5:
    JobMatcher.score_batch(batch)
        → parse + normalise (see SCORING_RULES.md)
        → on any failure: _fallback_individual(batch)
    db.insert_score(...) for each returned row
    _check_high_score_alerts(...)
  ↓
scoring_progress updated on app.state; finally → active=False
```

## Files

| File | Role |
|---|---|
| `app/matcher.py` | Prompts, `JobMatcher`, batch parser, normalisation, fallback |
| `app/main.py:458` | `_score_unscored` — the stage driver |
| `app/main.py:271` | `scheduled_scoring` — hourly APScheduler job |
| `app/ai_client.py` | Providers, retries, circuit breaker, `parse_json_response` |
| `app/ai_usage.py` | Token/cost tracking |
| `app/database.py:1125` | `insert_score` (INSERT OR REPLACE on a UNIQUE `job_id`) |
| `app/database.py:1722` | `get_scoreable_jobs` — the Stage-3 gate contract |

## Why `job_id` being UNIQUE matters

`insert_score` is `INSERT OR REPLACE`, keyed on `job_id`. Re-scoring a job **overwrites** rather than
appends, so Stage-4 is idempotent per job: a job re-enters the pool only if its score row is deleted
(`clear_all_scores`) or was never written. This is what makes a re-run safe.

## Related documents

- `SCORE_AUDIT.md` — what the code did before hardening; defects D1, D2, D3b, D4, D5
- `SCORING_RULES.md` — the explicit parse/normalise/cap/fallback rules
- `TEST_RESULTS.md` — unit-test inventory
- `LIVE_SAMPLE_RESULTS.md` — results of `analysis/verify_score_live.py`
- `KNOWN_LIMITATIONS.md` — what is still unfixed, honestly
