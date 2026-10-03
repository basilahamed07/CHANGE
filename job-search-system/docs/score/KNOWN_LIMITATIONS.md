# STAGE-4 SCORE — KNOWN LIMITATIONS

> Honest limits as of the Stage-4 hardening pass. Several of these are **unverified** because the
> environment could not execute code — those are marked.

---

## 1. The hardening itself is unverified (highest priority)

`app/matcher.py` was rewritten (batch parser, normalisation, cap) and `tests/test_scoring.py` written,
but **nothing has been executed**. The classifier outage blocked every `pytest` invocation.

Until the suite runs green, treat Stage-4 as **code-complete, unproven**. This is the single thing
standing between this stage and "done" (Golden Rule 11).

## 2. `clear_failed_scores()` does not match the D1 marker

`app/database.py:1136` purges transient-error zeros by matching concerns against
`'unavailable' | 'unreachable' | 'Scoring error' | 'circuit breaker' | 'rate limit'`.

The pre-hardening padding branch wrote `"Missing from batch response"` — **not in that list**. Any
fabricated zeros already written to a real workspace by the old code are therefore still there, and the
new parser cannot retroactively remove them.

**Action:** `analysis/verify_score_live.py` counts them (`d1_fabricated_zero_total`). If the count is
non-zero on Basil's workspace, either widen the `LIKE` set or run a one-off delete.

## 3. No score provenance (defect D4, deferred)

`job_scores` records score/reasons/concerns/keywords/scored_at/role_match — **not** the model, prompt
version, attempt count, or which path produced the row (`batch` / `fallback` / `single`). It is
therefore impossible to tell, from the DB alone, which rows came from a fallback or from an older
prompt revision.

Deferred deliberately: it needs `ALTER TABLE` work in `app/database.py`, and doing a schema change in
the same pass as an unverified parser rewrite would make any failure ambiguous.

## 4. No score metrics (deferred)

The plan called for `search_config.score_metrics` (scored / skipped / failed). Not implemented. Skipped
jobs currently surface only as a `logger.warning` inside `_parse_batch_response`, so they are visible
in logs but not queryable. Same deferral reason as §3.

## 5. Prompt injection is mitigated, not solved

Both prompts fence the resume and the job description as untrusted and instruct the model to ignore
embedded instructions. A sufficiently adversarial posting could still influence a score. The blast
radius is bounded — eligibility is deterministic and upstream, and the evidence gate is downstream —
but the score itself is model-authored and cannot be fully trusted.

## 6. `scoring_progress` is a process-global, not per-user

`app.state.scoring_progress` (`app/main.py:476`) is a single dict on the app, not per workspace. With
concurrent per-user runs, one user's progress overwrites another's. This is an **N3** (per-user
background run state) item, recorded here because Stage-4 is where it lives.

## 7. The `country_code` NULL gap widens this stage's input pool

~1,962 legacy rows have `country_code IS NULL`, so Stage-3's LOCATION gate never engaged on them. Those
rows can reach Stage-4 that arguably should not. This is a **Stage-3 carry-in**, not a Stage-4 defect —
but it means Stage-4 scores a wider set than the gate was designed to allow.

## 8. Two scoring methods exist

`JobMatcher.score_batch` (`matcher.py:227`, used by `_score_unscored`) and `JobMatcher.batch_score`
(`matcher.py:375`, used elsewhere). They have different fallback behaviour — `score_batch` falls back to
per-job scoring on failure; `batch_score` never does, it just loops the jobs itself. Both now normalise
through `_normalise_entry`, but the duplication is a maintenance hazard worth collapsing later.

## 9. Batch size and token budget are coupled

`batch_size = 5` (`main.py:479`) exists partly because `max_tokens = 512 * len(jobs)` (`matcher.py:245`).
Changing one without the other risks truncation — which, before this hardening, silently produced
fabricated zeros rather than an error.

---

## Recommendations, in order

1. **Run the tests.** Nothing else is worth doing first.
2. Run `analysis/verify_score_live.py` (free mode) to count D1 artifacts on the real workspace.
3. If D1 artifacts exist, widen `clear_failed_scores` or delete them once.
4. Land D4 provenance + `score_metrics` as a **separate** commit once §1 is green.
5. Resolve the `country_code` carry-in (Stage-2 reclassification) before trusting Stage-4's pool size.
