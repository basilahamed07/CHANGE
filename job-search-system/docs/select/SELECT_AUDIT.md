# STAGE-6 SELECT — AUDIT

> Static audit from reading the code. **Not executed** — the environment's command classifier was
> unavailable throughout, so nothing below was reproduced live. Every finding cites `file:line`.
>
> Stage 6 of `app/daily_run.py:29` (`STAGES`). Upstream: Stage-5 HYBRID_SCORE.
> Downstream: Stage-7 RESEARCH.

---

## 1. What the stage does today

| Piece | Location |
|---|---|
| **Documented** entry point | `select_candidates(db, cutoff, limit)` — `app/daily_run.py:189` |
| **Actually-used** selection | `db.get_top_unpackaged_jobs(cutoff, limit)` — `app/database.py:3744` |
| Live caller (API path) | `_select` inside `POST /api/crm/...` daily-run trigger — `app/routers/crm.py:176-181` |
| Second caller (listing) | `app/routers/crm.py:185` |
| Package counting (Rule 7) | `db.count_packages_created_on` — `database.py:3733` |

```python
# app/database.py:3744
async def get_top_unpackaged_jobs(self, cutoff: int = 60, limit: int = 10) -> list[dict]:
    cursor = await self.db.execute(
        """SELECT js.job_id, js.match_score FROM job_scores js
           INNER JOIN jobs j ON j.id = js.job_id
           LEFT JOIN applications a ON a.job_id = js.job_id
           WHERE j.dismissed = 0 AND j.strategy_dismissed = 0
           AND js.match_score >= ?
           AND (a.package_dir IS NULL OR a.package_dir = '')
           ORDER BY js.match_score DESC LIMIT ?""",
        (cutoff, limit))
```

## 2. Contract vs reality

| Claimed | Actual |
|---|---|
| `select_candidates` is the Stage-6 entry point (`docs/STAGE_ROADMAP.md:33`) | **It has zero callers** — the live path is the inline `_select` in `routers/crm.py:176` (S1) |
| "eligible + scored above cutoff" (`daily_run.py:190`) | Scored only; **eligibility is never re-checked** (S3) |
| "Returns counts + shortfall reasons" (`daily_run.py:191`) | Returns neither a reason nor a why — just `selected` + `job_ids` (S4) |
| Selection is deterministic | `ORDER BY match_score DESC` with **no tie-break** (S2) |
| Target counts packages, not jobs (Golden Rule 7) | True at the reporting layer (`_finish` → `count_packages_created_on`), but **selection is a job count** |

---

## 3. Defects found

### S1 — the documented entry point is dead code
`app/daily_run.py:189` (definition), `app/routers/crm.py:176` (the real one)

`select_candidates` is defined and never called anywhere in `app/`. The selection that actually runs is
an inline closure inside the CRM daily-run trigger:

```python
# app/routers/crm.py:176
async def _select(report, stage):
    rows = await db.get_top_unpackaged_jobs(cutoff=60, limit=max(0, report.daily_target))
```

**Why it matters:** the roadmap, the docstrings, and any future hardening aimed at `select_candidates`
would be aimed at code that never executes. Both the real logic and its `cutoff=60` literal live in a
router, where stage logic does not belong.

### S2 — no tie-break: selection is not fully deterministic
`app/database.py:3753`

```sql
ORDER BY js.match_score DESC LIMIT ?
```

Only `match_score` is ordered. When several jobs share the score at the cutoff boundary, SQLite returns
them in an unspecified row order — which can differ between runs and after writes. Selecting the same
`limit` from a tied set can therefore yield **different job sets on unchanged data**, so Stage-6 is not
idempotent at the boundary and Goldens Rule 11's "same set twice" cannot hold.

### S3 — eligibility is never re-checked, so a job that turned ineligible stays selectable
`app/database.py:3750-3752`

The `WHERE` clause filters `dismissed` and `strategy_dismissed` but **not** `j.eligibility_status`. The
`INNER JOIN job_scores` means only *previously scored* jobs are considered — and only `ELIGIBLE` jobs are
ever scored (Stage-4's gate), so at score time eligibility held.

But nothing prunes the score when eligibility later flips. The only `DELETE FROM job_scores` sites in the
whole app are `clear_failed_scores` (`database.py:1139`) and `clear_all_scores` (`database.py:1152`);
`app/eligibility.py` never touches the table. So:

> Job scored on day 6 (still fresh) → its `posted_date` goes past `MAX_JOB_AGE_DAYS=7` → the next
> `run_eligibility_pass` marks it `INELIGIBLE` → its `job_scores` row survives → **`get_top_unpackaged_jobs`
> still selects it and a package gets built for a stale job.**

This directly undercuts the Stage-3 hardening, which exists to keep ineligible jobs out of the package
pipeline.

### S4 — the shortfall reason is a hardcoded guess
`app/routers/crm.py:179-180`

```python
if len(rows) < report.daily_target:
    stage.detail["shortfall_reasons"] = ["ALL_SCORED_BELOW_CUTOFF"]
```

`ALL_SCORED_BELOW_CUTOFF` is asserted whenever fewer rows come back than the target — but `len(rows) <
target` has at least three different causes: everything scored below the cutoff, nothing eligible was
ever scored (`NO_ELIGIBLE_JOBS`), or there simply are not that many jobs in the pool. The real cause is
never distinguished, and `select_candidates`'s own docstring (`daily_run.py:191`) promises shortfall
reasons it never returns.

**Why it matters:** Stage-10 DIGEST is supposed to report the shortfall honestly. It inherits a reason
that is often simply wrong.

### S5 — the cutoff is duplicated as a magic literal
`app/routers/crm.py:177`, `:185` (`cutoff=60`), `app/database.py:3745` (`cutoff: int = 60`)

`DailyRun` already owns `self.score_cutoff` (`daily_run.py:114`), but the live selection path ignores it
and passes a bare `60`. Changing the cutoff in one place silently does not change selection.

### S6 — the API daily-run can never reach its target
`app/routers/crm.py:182-187`

The triggered run supplies `"packages": _packages`, and `_packages` does **not** build anything — it
counts pending rows and returns a note. So `packages_created` stays 0, `target_met` is always false, and
every API-triggered run reports a shortfall. The comment says this is deliberate ("out of scope for the
trigger path"), but it means the daily run reachable from the UI is not end-to-end.

---

## 4. What hardening should do

1. **Move selection into the stage (S1).** Make `select_candidates` the real, called entry point; have the
   router call it instead of inlining its own closure.
2. **Add a deterministic tie-break (S2).** `ORDER BY js.match_score DESC, js.job_id ASC` — a stable,
   total order. Add a test that runs selection twice and asserts an identical set.
3. **Re-check eligibility in the selection query (S3).** Add `AND j.eligibility_status = 'ELIGIBLE'`.
   This is the single most important fix here.
4. **Distinguish the shortfall causes (S4).** Return a real reason from the selection query — count
   eligible-unscored vs scored-below-cutoff vs pool-exhausted and emit
   `NO_ELIGIBLE_JOBS` / `ALL_SCORED_BELOW_CUTOFF` / `SOURCES_EXHAUSTED` accordingly.
5. **Take the cutoff from `DailyRun` (S5)**, and make it configurable rather than a literal.
6. **Make the API path honest (S6)** — either build packages, or state plainly in the report that the
   trigger path computes selection only and cannot meet the target.

---

## 5. Open questions

- Should a job whose eligibility flipped after scoring have its `job_scores` row **deleted**, or just be
  filtered at selection? Deleting is cleaner but loses the score if it becomes eligible again.
- Is `strategy_dismissed` still meaningful now that Stage-3's `ELIGIBLE` status supersedes it? Both are
  filtered, which suggests overlapping concerns.
- `limit` is a job count while `daily_target` is a package count. Should selection over-fetch (e.g. 2×)
  so that jobs lost to the Stage-8 evidence gate do not silently cost packages?
