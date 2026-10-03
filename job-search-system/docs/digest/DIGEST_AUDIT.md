# STAGE-10 DIGEST — AUDIT

> Static audit from reading the code. **Not executed** — the environment's command classifier was
> unavailable throughout, so nothing below was reproduced live. Every finding cites `file:line`.
>
> Stage 10 of `app/daily_run.py:29` (`STAGES`) — the last stage. Upstream: Stage-9 OUTREACH.
>
> The headline: **what ships as "DIGEST" is a job-listing digest, not a run report.** It cannot tell a
> met target from a missed one, which is the one thing the plan asks this stage to guarantee.

---

## 1. What the stage does today

| Piece | Location |
|---|---|
| Digest generation | `generate_digest(db, min_score=60, hours=24)` — `app/digest.py:9` |
| HTML rendering | `_render_html_digest` — `digest.py:64` |
| SMTP send (optional) | `send_digest` — `digest.py:112` |
| Scheduler entry | `run_digest_cycle` — `app/scheduler.py:733`; scheduled at `app/main.py:309` |
| API surface | `GET /api/analytics/digest` and `POST /api/analytics/digest/send-test` — `app/routers/analytics.py:334`, `:344` |
| Settings | `email_settings.digest_enabled / digest_schedule / digest_min_score` — `database.py:477-480` |

## 2. Contract vs reality

| Claimed | Actual |
|---|---|
| "Generates recent high-value job digest" (`CLAUDE.md`) | **True** — it lists high-scoring *jobs* |
| "explicit report contract with the machine-readable shortfall vocabulary" (`plan`) | **False** — the digest never reads `SHORTFALL_REASONS` (G1) |
| "a run that reached 0 packages reports the shortfall reason, never 'success'" (`plan`) | **False** — it reports *matches*, not packages (G1) |
| Runs as pipeline Stage-10 | **False in the API path** — `crm.py:192` passes `"digest": None` → `not_implemented` (G2) |
| Reports what the run did | **False** — no packages, no drafts, no target, no shortfall (G1) |
| SMTP stays optional and honest when unconfigured | **True** — `send_digest` returns `False` and logs (`:117-121`) |
| Output is HTML-safe | **True** — every field is `html.escape`d (`:69-72`) |

---

## 3. Defects found

### G1 — the digest reports listing volume, not the run outcome
`app/digest.py:9-61`

```python
cursor = await db.db.execute("""
    SELECT j.*, js.match_score, js.match_reasons
    FROM jobs j JOIN job_scores js ON j.id = js.job_id
    WHERE js.match_score >= ? AND j.created_at >= ? AND j.dismissed = 0
    ORDER BY js.match_score DESC LIMIT 20
""", (min_score, cutoff))            # :13-20
...
subject = f"jobagent: {len(jobs)} new match{'es' if len(jobs) != 1 else ''}"   # :29
```

The digest counts **newly-scraped high-scoring jobs**. It says nothing about:

- how many **packages** were created today (Golden Rule 7: "daily success target means qualifying
  application packages, not scraped URL count"),
- whether `target_met`,
- **why** the target was missed.

`DailyRunReport.shortfall_reasons()` (`daily_run.py:83-94`) and the `SHORTFALL_REASONS` vocabulary
(`daily_run.py:43-54`) exist precisely for this and are never consulted here. So a run that discovered
40 jobs, scored 12 above 60, and built **zero** packages sends "jobagent: 12 new matches" — a
success-shaped message about a failed day.

**Why it matters:** this is the last thing a user sees, and it is the only place the pipeline could
report honestly. The plan's critical test for this stage — "a run that reached 0 packages reports the
shortfall reason, never success" — fails by construction.

### G2 — the stage is not wired into the daily run
`app/routers/crm.py:188-193`, `app/daily_run.py:158-161`, `app/main.py:309`

```python
# crm.py:188
report = await runner.run({
    "select": _select, "packages": _packages,
    "outreach": None, "digest": None,          # ← digest stage is None
})
```

`DailyRun.run` records a `None` handler as `status="skipped", detail={"reason": "not_implemented"}`
(`daily_run.py:158-161`), so the API-triggered run marks DIGEST as unimplemented. The only real caller is
the APScheduler job `run_digest_cycle(app.state.bg_db)` (`main.py:309`), which uses the **global** DB
rather than a per-user workspace — the same N3 gap recorded in Stage-5 (H8). `run_digest_cycle` itself is
a bare pass-through with a catch-all (`scheduler.py:733-740`).

### G3 — "new in the last 24 hours" means "we scraped it in the last 24 hours"
`app/digest.py:11`, `:17`

```python
cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()   # :11
... WHERE ... j.created_at >= ?                                              # :17
```

The window filters on `jobs.created_at` — discovery time. A posting published 45 days ago and scraped
today counts as a "new match in the last 24 hours". This is the discovery-vs-freshness conflation Golden
Rule 10 guards against ("MAX_JOB_AGE_DAYS=7, DATE_UNKNOWN is not fresh"), and the digest surfaces it to
the user as recency.

### G4 — no eligibility filter, so a job that turned ineligible can still appear
`app/digest.py:17`

The `WHERE` clause filters `dismissed = 0` and a score threshold only. It does not require
`j.eligibility_status = 'ELIGIBLE'`. Since a score row survives an eligibility flip (Stage-6 **S3** — the
only `DELETE FROM job_scores` sites are `clear_failed_scores`/`clear_all_scores`), a job that became stale
or otherwise ineligible after being scored still satisfies this query and is headlined as a match. A
manually hybrid-scored ineligible job (Stage-5 **H1**) lands here too.

### G5 — an empty digest is reported as a configuration failure
`app/digest.py:128-130`, `app/routers/analytics.py:344-349`

```python
if digest["job_count"] == 0:
    logger.info("No jobs for digest, skipping email")
    return False                                   # :130 — same return as "not configured"
```

`send_digest` returns `False` for two very different reasons: *not configured* (`:117-121`) and *nothing
to report* (`:130`). The test endpoint collapses both into:

```python
raise HTTPException(400, "Digest not sent — check email settings and digest configuration")
```

So a correctly-configured user with a genuinely quiet day is told their settings are wrong.

### G6 — schedule values other than "daily" silently mean weekly
`app/digest.py:123-124`

```python
schedule = settings.get("digest_schedule", "daily")
hours = 24 if schedule == "daily" else 168
```

Any typo or future value (`"weekly"`, `"Daily"`, `""`) yields 168 hours. There is no validation and no
warning; the column is free TEXT (`database.py:478`).

### G7 — no deterministic tie-break on the top-20 cut
`app/digest.py:18-19`

```sql
ORDER BY js.match_score DESC LIMIT 20
```

Same class as Stage-6 **S2**: rows tied on `match_score` at the 20-job boundary are returned in an
unspecified order, so two digests over unchanged data can list different jobs. There is no fallback
ordering by id or date.

### G8 — parsed `match_reasons` are discarded
`app/digest.py:25-27`, `:53-60`

`match_reasons` is JSON-parsed per row (`:25-27`) and then never appears in the returned job dict
(`:53-60`) or the rendered body. The digest shows a bare `[87/100]` with no reason — the least
informative form of the score, produced by work that is then thrown away.

---

## 4. What holds (verified, not assumed)

- **HTML output is safely escaped.** `escape()` is applied to title, company, location, and url
  (`:69-72`); `html.escape` defaults to `quote=True`, so the `href="{url}"` attribute cannot be broken
  out of. No injection.
- **SMTP is genuinely optional and fails soft.** With no `digest_enabled`, no `smtp_host`, or no
  `to_address`, `send_digest` logs and returns `False` without raising (`:117-121`).
- **The score threshold is typed.** `digest_min_score` is `INTEGER NOT NULL DEFAULT 60`
  (`database.py:480`) and the UI `parseInt`s it (`settings.js:1735`), so the `>= ?` comparison is
  numeric — the classic "integer column compared to a string" silent-empty bug does not apply here.
- **The digest is per-user.** The query runs on the workspace DB (`analytics.py:341` `_db(request)`), so
  one user's digest cannot include another's jobs.
- **No fabrication.** The digest renders only stored rows; it invents no jobs, scores, or counts.

---

## 5. What hardening should do

1. **Make the digest a run report (G1) — the point of the stage.** Lead with the *outcome*: packages
   created today vs `daily_target`, `target_met`, and the `shortfall_reasons()` list from
   `daily_run.py:83`. Keep the job listing as a secondary section. This is what the plan's critical test
   requires.
2. **Wire the stage or name it honestly (G2).** Give the API daily-run a real `digest` handler built from
   the same `DailyRunReport`, and stop it being reported as `not_implemented`.
3. **Separate discovery from freshness (G3).** Filter on the freshness evidence already computed for
   the job (`assess_freshness` / `posted_date`), or label the count "newly discovered" rather than "new
   matches".
4. **Require eligibility (G4).** Add `AND j.eligibility_status = 'ELIGIBLE'`, mirroring Stage-6.
5. **Distinguish the two `False` returns (G5)** — return a reason (`"not_configured"` vs `"nothing_to_report"`)
   so the test endpoint's 400 is only shown for the genuine configuration case.
6. **Validate the schedule (G6)** against a known set, and warn on an unknown value.
7. **Add a tie-break (G7)** — `ORDER BY js.match_score DESC, j.id ASC`.
8. **Report or drop `match_reasons` (G8)** — one line of "why" per job is the useful part.
9. **Tests:**
   - A run that created 0 packages ⇒ the digest says so and carries a shortfall reason, never a
     success-shaped subject (the plan's critical test).
   - A job whose eligibility flipped after scoring ⇒ absent from the digest (guards G4, pairs with S3).
   - `digest_schedule="weird"` ⇒ validated, not silently weekly (guards G6).
   - Two digests over unchanged data ⇒ identical job set (guards G7).

---

## 6. Open questions

- Should the digest be one artifact (run outcome + listing) or two? The plan implies the run report is
  the point; the listing is the pleasant part. Merging them into one email is likely right, but the
  *order* matters — outcome first.
- Where does `DailyRunReport` live for the digest to read? It is persisted via
  `save_daily_run_state` / `get_daily_run_state` (`daily_run.py:119-123`), so `send_digest` can load
  today's report by date rather than recomputing — worth confirming the state row exists on the day the
  scheduler fires.
- The digest's `hours` window and the daily-run's calendar-day target use different clocks. If the two
  are merged, one of them has to win.
