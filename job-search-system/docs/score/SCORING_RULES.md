# STAGE-4 SCORE — SCORING RULES

> The explicit rules the code enforces. Before the Stage-4 hardening several of these existed only as
> instructions inside a prompt — i.e. deterministic rules delegated to an LLM (a Golden Rule 4
> violation). They are now enforced in `app/matcher.py`.

---

## R1 — Entry gate (deterministic, no LLM)

A job may be scored **only** if `db.get_scoreable_jobs()` returns it:

```sql
SELECT j.* FROM jobs j LEFT JOIN job_scores js ON j.id = js.job_id
WHERE js.id IS NULL AND j.dismissed = 0
  AND j.location_classified = 1 AND j.eligibility_status = 'ELIGIBLE'
```

`INELIGIBLE` and `REVIEW_REQUIRED` jobs cannot reach the matcher. Stage-3 runs again at the top of
`_score_unscored` so newly-evaluated rows are picked up in the same pass.

## R2 — Batch parsing: align or refuse

`JobMatcher._parse_batch_response(raw, jobs)`

1. Strip ``` fences; `json.loads`; unwrap a single-key object.
2. If **every** entry carries an integer `job_index`, match by index. An index outside
   `[0, len(jobs))` is a hard error.
3. Otherwise, positional alignment is used **only if `len(data) == len(jobs)`** — the order the prompt
   promises.
4. Otherwise, **raise**. The caller falls back to individual scoring rather than guessing.

> **Never** interpolate a score from a neighbouring position. A wrong score is undetectable downstream;
> an omitted one is not.

## R3 — Never fabricate a score

A job the model did not return is **omitted from the result**, not scored `0`. Its row simply does not
exist, so it re-enters the pool on the next cycle.

Before hardening, the parser padded the result to `len(jobs)` with
`{"score": 0, "concerns": ["Missing from batch response"]}`. `clear_failed_scores()`
(`app/database.py:1136`) does not match that string in its `LIKE` patterns, so those fabricated zeros
were permanent.

## R4 — An entry with no usable score is skipped

`JobMatcher._normalise_entry(entry, job_id)` returns `None` — and the entry is dropped — when `score` is
missing, non-numeric, or a `bool` (`True` is an `int` in Python and must not become score 1).

## R5 — Scores are bounded

Persisted scores are clamped to `[0, 100]`. A model returning `150` records `100`; `-20` records `0`.

## R6 — The role-mismatch cap is enforced in code

If the model **explicitly** reports `role_match: false`, the score is capped at
`ROLE_MATCH_SCORE_CAP = 50`.

- The cap is applied on **both** the batch path and the single-job path.
- A string `"false"` is understood; `"true"` / `"yes"` / `"1"` mean matched.
- **An absent `role_match` does NOT trigger the cap.** The cap is a *penalty*; deriving a penalty from a
  field the model never sent would be the same class of fabrication as inventing a score. Absence means
  "not stated" — weaker evidence than an explicit `false`.

> This reverses the initial audit finding, which had called the default-to-`True` a fail-closed
> violation. See `SCORE_AUDIT.md` §3 D3 for the corrected reasoning.

## R7 — Fallback discipline

| Situation | Behaviour |
|---|---|
| Batch call raises | `_fallback_individual(jobs)` |
| Batch parses but yields nothing usable | `_fallback_individual(jobs)` |
| A single job fails | `score_job` returns `None`; the job is skipped |
| 3 consecutive individual failures | abort the fallback — the provider is down |
| 2 consecutive empty batches in `_score_unscored` | stop the run — provider likely down |

No path writes a score for a job that was not successfully scored.

## R8 — Idempotency

`job_scores.job_id` is `UNIQUE`; `insert_score` uses `INSERT OR REPLACE`. Re-scoring the same job
overwrites its previous row — it never appends a second opinion.

## R9 — Prompt injection is bounded

Both prompts wrap the resume and the job description in explicit
`--- BEGIN … (untrusted content) ---` fences and instruct the model to ignore embedded instructions.
This is a mitigation, not a guarantee — see `KNOWN_LIMITATIONS.md`.
