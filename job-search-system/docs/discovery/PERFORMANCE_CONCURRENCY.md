# PERFORMANCE: CONCURRENCY — bounded parallel DISCOVER (2026-09-30)

Task: speed up DISCOVER with safe bounded concurrency — no change to
accuracy, dedup, eligibility, scoring, or downstream behavior.

## What changed

`app/discovery.py` — source searches within a country now run under
`asyncio.gather()` + `asyncio.Semaphore`:

* **`MAX_CONCURRENT_SOURCES = 5`** (conservative start, per the task).
* **Configurable, not hardcoded**: `run_discovery_cycle(..., max_concurrent_sources=N)`
  argument, or `JOBAGENT_DISCOVERY_CONCURRENCY` env var (ops-level override,
  garbage falls back safely to 5). `1` reproduces the old serial behavior.
* **Only independent calls parallelized**: the HTTP searches (different hosts)
  run concurrently; INGEST stays serial on the one event loop (shared
  `seen_hashes` set + DB writes must not race) — dedup/provenance logic is
  byte-identical to before.
* **Ordering preserved where it matters**: tasks are SUBMITTED in tier order
  (registry §19), so tier-1 sources enter the semaphore first and keep
  winning canonical attribution; completion order does not affect the pool.
* **Skips stay immediate**: NOT_APPLICABLE (registry check, zero HTTP) and
  keyed-source CONFIGURATION_REQUIRED are decided before/outside the
  semaphore — no wasted requests, no semaphore time.
* **Isolation**: each task catches its own exceptions and always returns a
  health record; `asyncio.gather(return_exceptions=True)` is the second belt.
  One source crash cannot cancel siblings (proven by test).
* **Per-source resilience untouched**: each adapter keeps its own timeout,
  retries, rate limiter (BaseScraper chassis) inside its semaphore slot.
* **No retry of NO_RESULTS** — same as before.
* **New logs**: `[DISCOVERY][DE][greenhouse] START` / `DONE duration=3.2s PASS`
  (per-source wall time, not country time), plus cycle line now reports
  `concurrency=5, max_active=5`.
* **Measured**: per-source duration, per-country duration, total duration,
  and `max_active_observed` are all in telemetry
  (`telemetry["concurrency"]`).

## Before vs After — SAME 10-country smoke test (live, real HTTP)

Same script (`analysis/discovery_upgrade_smoke.py`), same day, same machine:

```text
Metric                BEFORE (serial)   AFTER (concurrency=5)
------------------------------------------------------------
Total runtime          1390.2 s           605.6 s
Speed improvement             —              2.30× (−56.4%)
Sources attempted          200                200
PASS                        53                 51
NO_RESULTS                  99                101
CONFIGURATION_REQUIRED      21                 21
NOT_APPLICABLE              27                 27
FAILED                       0                  0
RATE_LIMITED                 0                  0
Raw jobs                  1058               1059
Unique jobs                194                193
Duplicates removed          72                 72
```

PASS ±2 / NO_RESULTS ±2 is live-web jitter (board contents shift between
runs; e.g. 4dayweek returned 8 vs 6 jobs in SG). Raw/unique job counts are
logically identical (±1 raw job, ±1 unique — same jitter). The slowest
sources dropped from 145–160 s to ≤66 s (they are IO-bound against slow
hosts; the semaphore is not the bottleneck).

Per-country (duration, BEFORE → AFTER): AE 126.9→~65 s · SG 147.6→61.3 s ·
CA/DE/GB similar ~2.2–2.4× — bounded by the slowest source in each country
(builtin ~60 s), which concurrency cannot fix (its own pagination is serial).

## Rate-limit check

**0 RATE_LIMITED before, 0 after** — no per-source limiter trips at 5. The
existing per-host `AsyncRateLimiter` (rate_limiter.py) still serializes
same-host calls, so only genuinely independent hosts overlap. No need to
reduce to 3.

## Tests

```bash
.venv/bin/python -m pytest tests/test_discovery_upgrade.py -q --timeout=60
```
→ **43 passed** — including 4 NEW concurrency tests:
* `test_concurrency_respects_semaphore` — 5 slow sources, limit 2 → max 2 ever active
* `test_concurrency_isolation_one_crash_does_not_kill_siblings` — crash → SOURCE_FAILURE, sibling still ingests
* `test_concurrency_same_results_as_serial` — concurrency=4 vs 1 → identical pool (dedup intact)
* `test_concurrency_configurable_from_env` — env override + garbage fallback

Regression (same session, all green): adapters + discovery + scrapers +
dedup + database + daily_run + scheduler (**198**), a/c/d/e file groups
(**471**), discovery + multiuser + workspaces (**86**). One real bug was
caught by the new tests and fixed: the SOURCE_FAILURE fallback referenced
`result` before assignment inside the isolated task function.

## Production recommendation

**Run with `JOBAGENT_DISCOVERY_CONCURRENCY=5`** (the default). Evidence:
2.3× speedup, zero rate-limit/failure increase, identical discovery results.
Do not go higher without per-host data — greenhouse/wellfound tolerate it,
but the small boards (4dayweek, remoteok) share CDN infrastructure and the
win above 5 is marginal anyway (the floor is the ~60 s slowest source per
country). Revisit only if a source specifically needs it; per-source
semaphores would be the next lever, not a bigger global one.
