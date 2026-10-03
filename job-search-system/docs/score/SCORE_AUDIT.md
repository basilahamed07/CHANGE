# STAGE-4 SCORE — AUDIT

> **Status:** static audit from reading the code. **Not yet verified by execution** — the
> sandbox's command classifier was refusing all execution at the time of writing, so no test
> was run and no behaviour below was reproduced live. Every finding cites `file:line` so it can
> be checked directly.
>
> Stage-4 is the fourth entry in `app/daily_run.py:29` (`STAGES`), sitting under Stage-3
> ELIGIBILITY, which is now the only gate into it.

---

## 1. What the stage does today

| Piece | Location |
|---|---|
| Entry point | `app/main.py#_score_unscored(db, matcher=None)` — `main.py:458`, exposed as `app.state.score_unscored` (`main.py:575`) |
| Scheduled caller | `scheduled_scoring()` — `main.py:271-279`, hourly |
| Scoring engine | `JobMatcher` — `app/matcher.py:179` |
| Batch path | `JobMatcher.score_batch()` — `matcher.py:212`; parser `_parse_batch_response()` — `matcher.py:235` |
| Fallback path | `JobMatcher._fallback_individual()` — `matcher.py:262` |
| Single path | `JobMatcher.score_job()` — `matcher.py:185` |
| Persistence | `db.insert_score(...)` — called at `main.py:492` |
| Guards | Stage-3 gate `run_eligibility_pass` (`main.py:470`) then `db.get_scoreable_jobs()` (`main.py:472`) |

**Control flow:** the eligibility pass runs first, so only `eligibility_status='ELIGIBLE'` rows are
read. Jobs are taken in chunks of 5 (`batch_size = 5`, `main.py:479`), sent to `score_batch`, and
each result is written with `insert_score`. Two consecutive empty batches trip a provider-down
breaker (`main.py:486`).

---

## 2. Contract claims vs reality

| Claimed | Actual |
|---|---|
| "Do not fabricate scores after unrecoverable AI failure" (CLAUDE.md invariants) | **Partial.** `score_job` correctly returns `None` on error (`matcher.py:210`) and callers skip it. But the batch parser **invents a score of 0** for entries the model omitted (`matcher.py:258-259`). That is a fabricated score written to the DB. |
| "role_match false ⇒ score capped at 50" (stated in both prompts, `matcher.py:66`, `matcher.py:127`) | **Prompt-only.** Nothing in code enforces the cap. A response with `role_match:false, score:80` is persisted verbatim. |
| Batch failure ⇒ individual fallback | **Holds** (`matcher.py:231-233`), with a 3-consecutive-failure abort (`matcher.py:269`). |
| Scores are attributable to their job | **At risk** — see D2. |

---

## 3. Defects found

### D1 — Batch parser fabricates a `score: 0` for missing entries
`app/matcher.py:258-259`

```python
results.append({"score": 0, "role_match": True, "reasons": [],
                "concerns": ["Missing from batch response"], "keywords": []})
```

`_parse_batch_response` pads its output to exactly `expected_count` (`matcher.py:246`). If the model
returns fewer entries than jobs — truncation, a dropped object — the missing jobs are **not skipped**;
they are given a synthetic score of `0` and written to `job_scores` by `main.py:492`.

**Why it matters:** a fabricated `0` is indistinguishable downstream from a genuine "this job is a
terrible fit". Stage-6 SELECT reads these scores. A provider hiccup silently converts real candidates
into bottom-ranked jobs, and because the padded result is non-empty, the `empty_batches` breaker at
`main.py:484` never trips to catch it.

### D2 — Silent score misattribution when the model omits `job_index`
`app/matcher.py:246-249`

```python
entry = next((d for d in data if d.get("job_index") == i), None)
if entry is None and i < len(data):
    entry = data[i]
```

If the model returns correct `job_index` values, this is fine. If it omits the field entirely,
`d.get("job_index")` is `None` for every entry, so the index match fails for all `i` and the code
falls back to **positional** `data[i]`. Positional alignment is assumed, never checked. A model that
returns the same objects in a different order causes job A to receive job B's score, reasons, and
concerns — and it is persisted as though genuine.

**Why it matters:** this is worse than D1. A wrong score is not detectable as an anomaly; it looks
like a normal result.

### D3 — `role_match` defaults to `True` — **investigated, then reclassified (not a defect)**
`app/matcher.py:253`, `app/matcher.py:259`

Originally logged as a fail-closed violation: `role_match` falls back to `True` when absent, which
keeps the 50-point cap from applying.

**On closer inspection this is the correct behaviour, not a defect.** The cap is a *penalty*. Deriving
a penalty from an absent field is the same class of error as inventing a score — it would fabricate a
mismatch the model never asserted. A missing field means "not stated", which is weaker evidence than an
explicit `false`. The rule should therefore be: **cap only on an explicit `role_match: false`.**

Confirmed by existing behaviour: `tests/test_matcher.py:14` mocks a response with no `role_match` and
asserts the score survives as `88`. Defaulting to `False` would cap that to 50 and break a test that
reflects real model output.

### D3b — the 50-point cap was prompt-only (real defect)
`app/matcher.py:66`, `app/matcher.py:127`

Both prompts *instruct* the model to cap at 50 when `role_match` is false, but no code enforced it. A
response carrying `role_match:false, score:80` was persisted verbatim — a deterministic rule implemented
only as a request to an LLM (Golden Rule 4). Fixed by enforcing the cap in `_normalise_entry`, applied
to both the batch and single-job paths.

### D4 — No score provenance is persisted
`app/main.py:492-496` → `db.insert_score(...)`

The persisted row carries score, reasons, concerns, keywords, and role_match — but not the model,
the prompt version, the time, or whether the row came from the batch path, the individual fallback,
or the padding branch of D1. There is no way to audit where a score came from or to identify rows
produced by the D1 padding.

### D5 — Partial-JSON truncation currently relies on an exception
`app/matcher.py:224`

`max_tokens = 512 * len(jobs)` — 2,560 for a full batch of 5. If the model truncates, `json.loads`
(`matcher.py:240`) raises and the batch falls back to individual scoring (good). But if truncation
lands on a syntactically valid prefix with fewer objects, parsing **succeeds** and D1 fires silently.

---

## 4. Hardening — what was done, what is deferred

| # | Action | Status |
|---|---|---|
| 1 | Stop padding: `_parse_batch_response` returns only genuinely-scored jobs; unmatched jobs are omitted, not scored 0 (D1) | **done** — `matcher.py._parse_batch_response` |
| 2 | Refuse to guess alignment: match by `job_index` when present; positional only on an exact count match; anything else raises so the caller falls back (D2) | **done** — same method |
| 3 | Reject an entry with no usable `score` instead of defaulting it to 0 | **done** — `matcher.py._normalise_entry` |
| 4 | Clamp scores to the documented 0–100 range | **done** — same |
| 5 | Enforce the 50-point cap in code when `role_match` is explicitly false (D3b) | **done** — same |
| 6 | Apply the same normalisation on the single-job path so batch and fallback agree | **done** — `matcher.py.score_job` |
| 7 | Fall back to individual scoring when a batch parses but yields nothing usable | **done** — `matcher.py.score_batch` |
| 8 | Persist score provenance (model, prompt version, path taken, attempt count) (D4) | **deferred** — needs `job_scores` columns + a migration; doing it after the logic above is proven, so the two changes are not debugged at once |
| 9 | Write `search_config.score_metrics` (scored / skipped / failed) | **deferred** — same reason; D1-class events are currently surfaced via a `logger.warning` |

The two deferred items are D4 and metric persistence. They are additive and low-risk, but they touch
`app/database.py`, so they land only once the parser changes above pass their tests and a live run.

---

## 5. Open questions for the hardening pass

- Should a job whose batch entry is missing be retried individually, or left unscored for the next
  cycle? (Currently it is neither — it is scored 0.)
- `batch_size = 5` (`main.py:479`) is what keeps `512 * len(jobs)` inside a sane budget. Confirm
  before changing either number together.
- Does `insert_score` overwrite or append on a re-score? Relevant to Stage-6 idempotency.

---

## 6. Cross-stage note

Stage-3's quality audit found `country_code` is NULL on ~1,962 legacy rows, so Stage-3's LOCATION
gate never engaged on live data. Until Stage-2 re-runs over those rows, Stage-4 receives a **wider
input pool than intended**. This is a Stage-3 carry-in, not a Stage-4 defect, but it changes what
Stage-4 sees.
