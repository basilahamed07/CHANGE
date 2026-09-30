"""M4 → Stage-1 DISCOVER orchestration (Phases 6/7 + discovery upgrade).

For every ENABLED country (M3) × every search term (user's AI-analyzed
search_terms), run every REGISTERED source adapter in TIER order (task §7:
direct/ATS/major-local first), ingest through the SAME pipeline as the legacy
scrapers (title gate → region gate → insert → source attribution), and record
honest per-pass telemetry AND source-health results (task §21).

Stage-1 upgrade (behavior preserved):
  * adapter order comes from app/source_registry (tier, priority) — the most
    authoritative sources run first and win canonical attribution;
  * single-country sources skip other countries HONESTLY at the orchestrator
    (NOT_APPLICABLE) before any HTTP is spent;
  * every pass produces a SourceRunHealth record (PASS / NO_RESULTS /
    CONFIGURATION_REQUIRED / RATE_LIMITED / FAILED / NOT_APPLICABLE …);
  * canonical_source + source_types are stamped whenever a second source
    confirms a job (task §17/§19 provenance);
  * structured [DISCOVERY] log lines (task §48) — no secrets, ever.

PERFORMANCE — safe bounded concurrency (2026-09-30):
  Source searches within one country are INDEPENDENT (different hosts), so
  they run concurrently under a semaphore (default 5, configurable via the
  `max_concurrent_sources` argument / JOBAGENT_DISCOVERY_CONCURRENCY env).
  What stays SERIAL per country on purpose:
    * INGEST (dedup, insert, provenance) — shared DB rows + the in-cycle
      seen_hashes set must not race; ingest happens after each search
      returns, on the one event loop, in completion order;
    * the tier ORDER seeds task submission order (tier-1 sources start
      first, so they keep winning canonical attribution — §19 preference);
    * budget accounting happens at submission (a pass counts when its task
      is created), so the 1..50 cap semantics are unchanged.
  Failure isolation: each task wraps its source in try/except and always
  returns its health record — one source crash can never cancel siblings
  (asyncio.gather with return_exceptions=True as a second belt).

Request budget is still capped per cycle (cost/resilience control): a country
whose adapters all rate-limit stops consuming budget this cycle.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time

from app import source_registry as sr
from app.job_adapter import STOP_SOURCE_FAILURE

logger = logging.getLogger(__name__)

# 2026-09-28: 10 countries × 20 adapters = up to 200 passes/term — the old 24
# cap would starve the sweep after ~2 countries. 50 lets a cycle cover 2-3
# countries fully; scheduled cycles rotate through the rest.
MAX_REQUEST_PASSES_PER_CYCLE = 50      # adapter-passes per orchestrated cycle
MAX_LISTINGS_PER_PASS = 200            # ingest cap per pass

# Canonical-source ranking lives in the registry (single source of truth).
_canonical_rank = sr.canonical_rank

# Safe default bounded concurrency (task: start conservative at 5).
# Override per call (`max_concurrent_sources=`) or via env for ops, without
# code changes. Clamped to a sane range; 1 reproduces the old serial runs.
DEFAULT_MAX_CONCURRENT_SOURCES = 5


def _env_concurrency() -> int:
    try:
        return int(os.environ.get("JOBAGENT_DISCOVERY_CONCURRENCY",
                                  DEFAULT_MAX_CONCURRENT_SOURCES))
    except (TypeError, ValueError):
        return DEFAULT_MAX_CONCURRENT_SOURCES


async def _run_one_source(adapter_cls, term: str, country, keys: dict,
                          semaphore: asyncio.Semaphore, inflight: dict):
    """Search ONE source for ONE country under the concurrency semaphore.

    Returns (result, source_name, health, wall_ms). NEVER raises — a source
    crash becomes an honest SOURCE_FAILURE health record (isolation contract:
    one source's failure must not cancel the others).
    """
    adapter = adapter_cls(search_terms=[term], scraper_keys=keys)
    source = adapter.source_name
    spec = sr.get(source)
    health = sr.new_run_health(country.code, source)

    # NOT_APPLICABLE: immediate skip, NO HTTP, no semaphore time (the check
    # is registry-only). Keeps the zero-wasted-request guarantee.
    if (spec is not None and "*" not in spec.countries
            and country.code not in spec.countries):
        health.status = sr.HEALTH_NOT_APPLICABLE
        health.finished_at = health.started_at
        return None, source, health, 0

    t0 = time.monotonic()
    async with semaphore:
        # max-active tracking (for the concurrency report)
        inflight["active"] += 1
        inflight["max_active"] = max(inflight["max_active"], inflight["active"])
        sr.log_source_start(country.code, source)
        try:
            result = await adapter.search([term], country=country)
        except Exception as e:  # defensive: contract says never raise
            # AdapterResult import is local to dodge a circular import at
            # module load; building the honest failure record HERE keeps the
            # isolation contract: this task never propagates an exception.
            from app.job_adapter import AdapterResult
            result = AdapterResult(source=source,
                                   stop_reason=STOP_SOURCE_FAILURE,
                                   error=str(e)[:160])
        finally:
            inflight["active"] -= 1
    wall_ms = int((time.monotonic() - t0) * 1000)
    health.raw_jobs = health.parsed_jobs = len(result.listings)
    health.errors = result.error or ""
    health.status = sr.status_from_result(
        result.stop_reason, len(result.listings), spec, has_key=True)
    health.duration_ms = wall_ms
    health.finished_at = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
    sr.log_source_done(country.code, source, wall_ms, health.status)
    return result, source, health, wall_ms


async def run_discovery_cycle(db, registry, all_adapters, ai_client=None,
                              progress: dict | None = None,
                              max_passes: int | None = None,
                              scraper_keys: dict | None = None,
                              max_concurrent_sources: int | None = None) -> dict:
    """One orchestrated discovery pass across enabled countries × search terms.

    `max_passes` bounds the adapter-passes consumed this cycle (1..50). The UI
    and CLI use it to run a short, predictable sweep instead of always burning
    the full budget; omit it for the default cap. `scraper_keys` (optional)
    overrides the per-user DB keys — used by env-fallback wiring.
    `max_concurrent_sources` bounds how many source searches run at once per
    country (default 5; env JOBAGENT_DISCOVERY_CONCURRENCY; pass 1 for the
    old serial behavior). Returns machine-readable telemetry (per-pass source
    health + concurrency stats) for the API/report.
    """
    from app.title_filter import is_relevant_title
    from app.location_classifier import classify_location_rule_based

    # Registry ↔ adapters: warn on drift (focused subsets are legitimate in
    # tests/bounded sweeps); the STRICT full-list check runs at app startup.
    sr.validate_against({cls.source_name for cls in all_adapters}, strict=False)

    concurrency = max_concurrent_sources or _env_concurrency()
    concurrency = max(1, min(int(concurrency), len(all_adapters) or 1))

    t0 = time.monotonic()
    countries = registry.enabled_countries() if registry else []
    cfg = await db.get_search_config()
    search_terms = (cfg or {}).get("search_terms") or []
    if not search_terms:
        search_terms = ["AI Engineer", "Machine Learning Engineer"]

    keys = scraper_keys if scraper_keys is not None else await db.get_scraper_keys()
    keyed_sources = {"jooble", "adzuna", "reed"}

    telemetry = {
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "countries": [c.code for c in countries],
        "search_terms": search_terms,
        "passes": [],
        "source_health": [],
        "new_jobs": 0,
        "duplicates_seen": 0,
        "budget_exhausted": False,
        "concurrency": {
            "max_concurrent_sources": concurrency,
            "max_active_observed": 0,
        },
    }
    if max_passes is None:
        budget = MAX_REQUEST_PASSES_PER_CYCLE
    else:
        budget = max(1, min(int(max_passes), MAX_REQUEST_PASSES_PER_CYCLE))
    telemetry["pass_budget"] = budget
    seen_hashes: set[str] = set()
    # High-water mark BEFORE any ingest this cycle: insert_job returns the
    # existing id for a re-see, so "id > mark" distinguishes genuinely NEW
    # rows from re-seen ones (telemetry honesty).
    _max_row = await db.db.execute("SELECT COALESCE(MAX(id), 0) FROM jobs")
    pre_cycle_max_id = (await _max_row.fetchone())[0]

    country_summaries: list[dict] = []
    all_runs: list[sr.SourceRunHealth] = []

    # Tier-ordered source run order (registry data, not import order). The
    # ORDER is preserved where it matters (§19 canonical preference): tasks
    # are SUBMITTED in tier order, so tier-1 sources enter the semaphore
    # first even though they may complete out of order.
    ordered_adapters = sorted(
        all_adapters,
        key=lambda cls: ((sr.get(cls.source_name).tier if sr.get(cls.source_name) else 9),
                         (sr.get(cls.source_name).priority if sr.get(cls.source_name) else 99)))

    for country in countries:
        if budget <= 0:
            telemetry["budget_exhausted"] = True
            break
        country_t0 = time.monotonic()
        country_runs: list[sr.SourceRunHealth] = []
        allowed_regions = set(await db.get_allowed_regions()) | {"Unknown"}
        semaphore = asyncio.Semaphore(concurrency)
        inflight = {"active": 0, "max_active": 0}

        for term in search_terms:
            if budget <= 0:
                telemetry["budget_exhausted"] = True
                break

            # --- plan this term's passes (serial, cheap, no HTTP) ---------
            tasks = []           # (adapter_cls, source, has_key)
            skip_records = []    # immediate NOT_APPLICABLE passes
            for adapter_cls in ordered_adapters:
                if budget <= 0:
                    telemetry["budget_exhausted"] = True
                    break
                budget -= 1  # a pass counts at SUBMISSION (cap semantics unchanged)
                source = adapter_cls.source_name
                spec = sr.get(source)
                if (spec is not None and "*" not in spec.countries
                        and country.code not in spec.countries):
                    health = sr.new_run_health(country.code, source)
                    health.status = sr.HEALTH_NOT_APPLICABLE
                    health.finished_at = health.started_at
                    country_runs.append(health)
                    all_runs.append(health)
                    skip_records.append({
                        "country": country.code, "term": term, "source": source,
                        "stop_reason": "NOT_APPLICABLE", "found": 0,
                        "ingested": 0, "duplicates": 0, "error": "",
                        "health_status": sr.HEALTH_NOT_APPLICABLE,
                    })
                    continue
                has_key = source not in keyed_sources or bool(keys.get(
                    "jooble" if source == "jooble" else
                    "adzuna" if source == "adzuna" else "reed"))
                tasks.append((adapter_cls, source, has_key))

            # --- run the independent source searches CONCURRENTLY ---------
            # Each task carries its own has_key; _search_with_key decides the
            # keyed-source honesty inside the task.
            coros = []
            for adapter_cls, source, has_key in tasks:
                coros.append(_search_with_key(
                    adapter_cls, term, country, keys, semaphore, inflight, has_key))

            results = await asyncio.gather(*coros, return_exceptions=True)

            # --- INGEST: serial, completion order (shared DB + seen_hashes)
            telemetry["passes"].extend(skip_records)
            for outcome in results:
                if isinstance(outcome, BaseException):
                    # gather(return_exceptions=True) second belt — a task that
                    # somehow raised still must not kill the country.
                    logger.error("[DISCOVERY][%s] task crashed: %s",
                                 country.code, str(outcome)[:160])
                    continue
                result, source, health, wall_ms = outcome
                spec = sr.get(source)
                has_key = source not in keyed_sources or bool(keys.get(
                    "jooble" if source == "jooble" else
                    "adzuna" if source == "adzuna" else "reed"))
                if health.status == sr.HEALTH_NOT_APPLICABLE:
                    continue  # already recorded pre-task
                if spec is not None and spec.access == sr.Access.API_KEY and not has_key:
                    health.status = sr.HEALTH_CONFIGURATION_REQUIRED

                country_runs.append(health)
                all_runs.append(health)

                pass_rec = {
                    "country": country.code, "term": term, "source": source,
                    "duration_ms": wall_ms,
                }
                ingested = dupes = 0
                for job in result.listings[:MAX_LISTINGS_PER_PASS]:
                    if not job.is_ingestible():
                        continue
                    # Source attribution is enforced by the ORCHESTRATOR, not
                    # trusted from the listing (Critical Test #2).
                    job.source = source
                    key = (job.source, job.content_hash)
                    if key in seen_hashes:
                        dupes += 1
                        continue
                    seen_hashes.add(key)

                    # SAME gates as legacy ingest (no lowering of the bar)
                    if not is_relevant_title(job.title, search_terms):
                        continue
                    region = classify_location_rule_based(job.location)
                    if region is not None and region not in allowed_regions:
                        continue

                    job_id = await db.insert_job(
                        title=job.title, company=job.company, location=job.location,
                        salary_min=job.salary_min, salary_max=job.salary_max,
                        description=job.description, url=job.url,
                        posted_date=job.posted_date,
                        application_method="direct",
                        contact_email=job.contact_email,
                    )
                    if not job_id:
                        dupes += 1
                        continue
                    was_new = job_id > pre_cycle_max_id
                    cross_dupes = await db.find_cross_source_dupes(job_id, job.title, job.company)
                    if cross_dupes:
                        oldest = cross_dupes[0]
                        if was_new:
                            await db.insert_source(oldest["id"], source, job.url)
                            await db.dismiss_job(job_id)
                            await db.add_duplicate_link(
                                oldest["id"], job_id,
                                f"cross-source:{source}")
                        await db.update_last_seen(oldest["id"])
                        await _stamp_provenance(db, oldest["id"], source)
                        dupes += 1
                    else:
                        await db.insert_source(job_id, source, job.url)
                        if was_new:
                            from app.freshness import assess_freshness
                            await db.record_freshness(
                                job_id, assess_freshness(job.posted_date))
                            ingested += 1
                        else:
                            await db.update_last_seen(job_id)
                            dupes += 1
                            await _stamp_provenance(db, job_id, source)

                health.valid_jobs = ingested
                health.duplicates = dupes
                sr.log_source_end(health)

                pass_rec["stop_reason"] = result.stop_reason
                pass_rec["found"] = len(result.listings)
                pass_rec["ingested"] = ingested
                pass_rec["duplicates"] = dupes
                pass_rec["error"] = result.error
                pass_rec["health_status"] = health.status
                telemetry["passes"].append(pass_rec)
                telemetry["new_jobs"] += ingested
                telemetry["duplicates_seen"] += dupes
                if progress is not None:
                    progress.update({
                        "country": country.code, "term": term,
                        "completed_passes": len(telemetry["passes"]),
                        "new_jobs": telemetry["new_jobs"],
                    })

        telemetry["concurrency"]["max_active_observed"] = max(
            telemetry["concurrency"]["max_active_observed"], inflight["max_active"])
        telemetry["source_health"].extend(r.to_dict() for r in country_runs)
        country_summaries.append(sr.log_country_summary(
            country.code, country_runs, time.monotonic() - country_t0))

    telemetry["country_summaries"] = country_summaries
    telemetry["global_summary"] = sr.log_global_summary(
        telemetry["countries"], all_runs, time.monotonic() - t0)
    telemetry["duration_s"] = round(time.monotonic() - t0, 1)
    telemetry["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    logger.info("Discovery cycle: %d passes, %d new, %d dupes (%.1fs, concurrency=%d, max_active=%d)",
                len(telemetry["passes"]), telemetry["new_jobs"],
                telemetry["duplicates_seen"], telemetry["duration_s"],
                telemetry["concurrency"]["max_concurrent_sources"],
                telemetry["concurrency"]["max_active_observed"])
    return telemetry


async def _search_with_key(adapter_cls, term: str, country, keys: dict,
                           semaphore: asyncio.Semaphore, inflight: dict,
                           has_key: bool):
    """Thin wrapper so keyed-source honesty is decided INSIDE the task."""
    result, source, health, wall_ms = await _run_one_source(
        adapter_cls, term, country, keys, semaphore, inflight)
    if has_key:
        return result, source, health, wall_ms
    # Without a key a keyed source already returned SOURCE_FAILURE; surface
    # the honest CONFIGURATION_REQUIRED status for the report.
    spec = sr.get(source)
    if spec is not None and spec.access == sr.Access.API_KEY:
        health.status = sr.HEALTH_CONFIGURATION_REQUIRED
    return result, source, health, wall_ms


async def _stamp_provenance(db, job_id: int, source: str) -> None:
    """Upgrade the stored canonical_source when a higher-priority source
    confirms the job (task §19), keeping full provenance in source_types."""
    try:
        sources = await db.get_sources(job_id)
    except Exception:
        sources = []
    names = [s.get("source_name") for s in sources if s.get("source_name")]
    if source not in names:
        names.append(source)
    best = min(names, key=_canonical_rank)
    type_map = {}
    for n in names:
        spec = sr.get(n)
        type_map[n] = spec.source_type if spec else "UNKNOWN"
    await db.set_canonical_source(job_id, best, type_map)
