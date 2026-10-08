"""M4 → Stage-1 DISCOVER orchestration (Phases 6/7 + discovery upgrade).

For every ENABLED country (M3) × every ROLE term (the candidate's own job
titles), run every REGISTERED source adapter in TIER order (task §7:
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

PHASE 4 — ROLE-TARGETED DISCOVERY (2026-10-07, Basil):
  Discovery used to fan every whole-feed source out across every generic
  search term, which is how 1,245 mostly-irrelevant jobs landed in the pool.
  Two rules replace that cross product:

  1. QUERY CAPABILITY. Only some adapters accept a query; the rest return a
     whole board feed. QUERYABLE_SOURCES names the adapters that really send
     the term to the source (keywords/q/what/search). Each queryable source
     runs once per ROLE term and asks for the candidate's own role.
  2. COUNTRY/TERM PAIRING. Queryless whole-feed sources run exactly ONCE per
     country (their feed does not change with the term) and are post-filtered
     by the title gate. Terms therefore multiply only where they mean
     something, and the total pass count is bounded by MAX_REQUEST_PASSES_PER_CYCLE.

  Every pass is also capped (MAX_RESULTS_PER_PASS) so one source can never
  flood the DB, and the run reports `reject_counts` — how many listings the
  role gate and the region gate refused — so the discipline is checkable from
  GET /api/discovery/report instead of taken on faith.

PERFORMANCE — safe bounded concurrency (2026-09-30):
  Source searches within one country are INDEPENDENT (different hosts), so
  they run concurrently under a semaphore (default 5, configurable via the
  `max_concurrent_sources` argument / JOBAGENT_DISCOVERY_CONCURRENCY env).
  What stays SERIAL per country on purpose:
    * INGEST (dedup, insert, provenance) — shared DB rows + the in-cycle
      seen_hashes set must not race; ingest happens after each search
      returns, on the one event loop, in plan order;
    * the tier ORDER seeds task submission order (tier-1 sources start
      first, so they keep winning canonical attribution — §19 preference);
    * budget accounting happens at PLAN time (a pass counts when it is
      planned), so the 1..50 cap semantics are unchanged.
  Failure isolation: each task wraps its source in try/except and always
  returns its health record — one source crash can never cancel siblings
  (asyncio.gather with return_exceptions=True as a second belt).
"""

from __future__ import annotations

import asyncio
import logging
import os
import time

from app import source_registry as sr
from app.job_adapter import STOP_SOURCE_FAILURE

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Phase 4 constants
# ---------------------------------------------------------------------------

# Per-source cap per pass: the max listings accepted from ONE adapter pass.
# Whole feeds are truncated to this before ingest and the truncation is
# reported (`truncated` on the pass record) — never silently dropped.
MAX_RESULTS_PER_PASS = 100

# Sources whose adapter actually sends the role term to the remote source.
# Queryless sources (ATS boards, RSS feeds, category feeds) always include
# their default roles/categories, so running them per role would repeat the
# same requests — they run once per country instead. The set must be a subset
# of the registry (asserted by test_discovery_report).
QUERYABLE_SOURCES: frozenset[str] = frozenset({
    "jooble",          # POST keywords
    "adzuna",          # what=
    "reed",            # keywords=
    "tavily_search",   # search queries
    "mycareersfuture", # the API requires a query term
})

DEFAULT_ROLE_TERMS = ["AI Engineer", "Machine Learning Engineer"]

# 2026-09-28: 10 countries × ~21 adapters = up to 210 passes/term — the old 24
# cap would starve the sweep after ~2 countries. 50 lets a cycle cover 2-3
# countries fully; scheduled cycles rotate through the rest.
MAX_REQUEST_PASSES_PER_CYCLE = 50      # adapter-passes per orchestrated cycle

# Legacy ingest ceiling kept as an explicit alias of the Phase-4 cap so any
# older caller keeps working without a second, confusing limit.
MAX_LISTINGS_PER_PASS = MAX_RESULTS_PER_PASS

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


# ---------------------------------------------------------------------------
# Phase 4 helpers
# ---------------------------------------------------------------------------


def role_terms_from_config(cfg: dict | None) -> list[str]:
    """The candidate's own role titles, normalized and deduped.

    `job_titles` is normally a list of strings, but the resume analyzer has
    also produced [{title, why}] dicts, so both shapes are accepted. Order is
    preserved (most-relevant first, per the analyzer) and blanks dropped.
    """
    out: list[str] = []
    for raw in (cfg or {}).get("job_titles") or []:
        name = raw
        if isinstance(raw, dict):
            name = raw.get("title") or raw.get("role") or raw.get("name") or ""
        if not isinstance(name, str):
            continue
        name = " ".join(name.split())
        if name and name not in out:
            out.append(name[:140])
    return out


def _dedupe(values) -> list[str]:
    out: list[str] = []
    for value in values or []:
        if isinstance(value, str):
            value = value.strip()
        if value and value not in out:
            out.append(value)
    return out


def _order_adapters(all_adapters) -> list:
    """Registry tier order (1 first). Unregistered (test) stubs run last."""
    def key(cls):
        spec = sr.get(cls.source_name)
        return (spec.tier if spec else 9, spec.priority if spec else 99)
    return sorted(all_adapters, key=key)


def _entry_has_value(entry) -> bool:
    if isinstance(entry, dict):
        return any(str(v).strip() for v in entry.values() if v is not None)
    return bool(entry)


def _source_has_key(source: str, keys: dict | None) -> bool:
    """Honest key check for a keyed source (registry-driven, not a hardcoded set).

    Adzuna needs BOTH its app_key ('adzuna') and app_id ('adzuna-id'), so a
    single key is not enough. Public sources are always "keyed" (True).
    """
    spec = sr.get(source)
    if spec is None or spec.access != sr.Access.API_KEY:
        return True
    keys = keys or {}
    if source == "adzuna":
        return _entry_has_value(keys.get("adzuna")) and _entry_has_value(keys.get("adzuna-id"))
    return _entry_has_value(keys.get(source))


def _build_plan(countries, ordered_adapters, role_terms) -> list[dict]:
    """The pass plan: one entry per adapter-pass, in tier order.

    * a single-country source pointed at a wrong country → one NOT_APPLICABLE
      entry (no HTTP);
    * a QUERYABLE source → one entry per role term (role-targeted);
    * a queryless whole-feed source → exactly one entry per country.
    """
    plan: list[dict] = []
    for country in countries:
        for adapter_cls in ordered_adapters:
            source = adapter_cls.source_name
            spec = sr.get(source)
            na = (spec is not None and "*" not in spec.countries
                  and country.code not in spec.countries)
            if na:
                plan.append({"country": country, "adapter": adapter_cls,
                             "source": source, "term": None, "terms": [],
                             "na": True})
            elif source in QUERYABLE_SOURCES:
                for term in role_terms:
                    plan.append({"country": country, "adapter": adapter_cls,
                                 "source": source, "term": term,
                                 "terms": [term], "na": False})
            else:
                plan.append({"country": country, "adapter": adapter_cls,
                             "source": source, "term": None,
                             "terms": list(role_terms), "na": False})
    return plan


async def _run_one_source(adapter_cls, terms: list[str], country, keys: dict,
                          semaphore: asyncio.Semaphore, inflight: dict):
    """Search ONE source for ONE country under the concurrency semaphore.

    Returns (result, source_name, health, wall_ms). NEVER raises — a source
    crash becomes an honest SOURCE_FAILURE health record (isolation contract:
    one source's failure must not cancel the others).
    """
    terms = list(terms or [])
    adapter = adapter_cls(search_terms=terms, scraper_keys=keys)
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
            result = await adapter.search(terms, country=country)
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


async def _search_with_key(adapter_cls, terms: list[str], country, keys: dict,
                           semaphore: asyncio.Semaphore, inflight: dict,
                           has_key: bool):
    """Thin wrapper so keyed-source honesty is decided INSIDE the task."""
    result, source, health, wall_ms = await _run_one_source(
        adapter_cls, terms, country, keys, semaphore, inflight)
    if has_key:
        return result, source, health, wall_ms
    # Without a key a keyed source already returned SOURCE_FAILURE; surface
    # the honest CONFIGURATION_REQUIRED status for the report.
    spec = sr.get(source)
    if spec is not None and spec.access == sr.Access.API_KEY:
        health.status = sr.HEALTH_CONFIGURATION_REQUIRED
    return result, source, health, wall_ms


async def run_discovery_cycle(db, registry, all_adapters, ai_client=None,
                              progress: dict | None = None,
                              max_passes: int | None = None,
                              scraper_keys: dict | None = None,
                              max_concurrent_sources: int | None = None) -> dict:
    """One orchestrated discovery pass across enabled countries × ROLE terms.

    `max_passes` bounds the adapter-passes consumed this cycle (1..50). The UI
    and CLI use it to run a short, predictable sweep instead of always burning
    the full budget; omit it for the default cap. `scraper_keys` (optional)
    overrides the per-user DB keys — used by env-fallback wiring.
    `max_concurrent_sources` bounds how many source searches run at once per
    country (default 5; env JOBAGENT_DISCOVERY_CONCURRENCY; pass 1 for the
    old serial behavior). Returns machine-readable telemetry (per-pass source
    health + concurrency stats + reject counts) for the API/report.
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
    cfg = await db.get_search_config() or {}
    search_terms = _dedupe(cfg.get("search_terms") or [])
    # ROLE terms are the candidate's own titles; the generic board search terms
    # are the fallback so an unanalyzed resume still sweeps something sensible.
    role_terms = role_terms_from_config(cfg) or search_terms or list(DEFAULT_ROLE_TERMS)
    # The ingest gates keep anything matching the roles OR the board search
    # terms — never a tighter bar than before.
    gate_terms = _dedupe(role_terms + search_terms)

    keys = scraper_keys if scraper_keys is not None else await db.get_scraper_keys()

    ordered_adapters = _order_adapters(all_adapters)

    # ---- PLAN (serial, cheap, no HTTP) ------------------------------------
    full_plan = _build_plan(countries, ordered_adapters, role_terms)
    if max_passes is None:
        budget = MAX_REQUEST_PASSES_PER_CYCLE
    else:
        budget = max(1, min(int(max_passes), MAX_REQUEST_PASSES_PER_CYCLE))
    plan = full_plan[:budget]
    budget_exhausted = len(full_plan) > budget

    logger.info("[DISCOVERY] plan: %d passes (budget=%d, planned=%d, "
                "%d countries, %d roles)%s",
                len(plan), budget, len(full_plan), len(countries),
                len(role_terms), " BUDGET_EXHAUSTED" if budget_exhausted else "")

    telemetry = {
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "countries": [c.code for c in countries],
        "search_terms": search_terms,
        "roles": role_terms,
        "passes": [],
        "source_health": [],
        "new_jobs": 0,
        "duplicates_seen": 0,
        "truncated": 0,
        "budget_exhausted": budget_exhausted,
        "pass_budget": budget,
        "planned_passes": len(full_plan),
        "reject_counts": {
            "by_role_gate": 0,
            "by_region_gate": 0,
            "not_ingestible": 0,
            "duplicates": 0,
            "total": 0,
        },
        "concurrency": {
            "max_concurrent_sources": concurrency,
            "max_active_observed": 0,
        },
    }
    seen_hashes: set[str] = set()
    # High-water mark BEFORE any ingest this cycle: insert_job returns the
    # existing id for a re-see, so "id > mark" distinguishes genuinely NEW
    # rows from re-seen ones (telemetry honesty).
    _max_row = await db.db.execute("SELECT COALESCE(MAX(id), 0) FROM jobs")
    pre_cycle_max_id = (await _max_row.fetchone())[0]

    country_summaries: list[dict] = []
    all_runs: list[sr.SourceRunHealth] = []
    rejects = telemetry["reject_counts"]

    # Group the planned passes by country, preserving plan (tier) order.
    by_country: dict = {}
    for entry in plan:
        by_country.setdefault(entry["country"].code, (entry["country"], []))[1].append(entry)

    for country_code, (country, entries) in by_country.items():
        country_t0 = time.monotonic()
        country_runs: list[sr.SourceRunHealth] = []
        allowed_regions = set(await db.get_allowed_regions()) | {"Unknown"}
        semaphore = asyncio.Semaphore(concurrency)
        inflight = {"active": 0, "max_active": 0}

        # NOT_APPLICABLE pre-records: registry-only, no HTTP, honest telemetry.
        real: list[dict] = []
        for entry in entries:
            if not entry["na"]:
                real.append(entry)
                continue
            health = sr.new_run_health(country.code, entry["source"])
            health.status = sr.HEALTH_NOT_APPLICABLE
            health.finished_at = health.started_at
            country_runs.append(health)
            all_runs.append(health)
            telemetry["passes"].append({
                "country": country.code, "term": None, "queryless": True,
                "source": entry["source"], "stop_reason": "NOT_APPLICABLE",
                "found": 0, "ingested": 0, "duplicates": 0, "truncated": 0,
                "error": "", "health_status": sr.HEALTH_NOT_APPLICABLE,
            })

        # --- run the independent source searches CONCURRENTLY ---------------
        coros = [_search_with_key(
            entry["adapter"], entry["terms"], country, keys, semaphore,
            inflight, _source_has_key(entry["source"], keys))
            for entry in real]
        results = await asyncio.gather(*coros, return_exceptions=True)

        # --- INGEST: serial, plan order (shared DB + seen_hashes) -----------
        for entry, outcome in zip(real, results):
            if isinstance(outcome, BaseException):
                # gather(return_exceptions=True) second belt — a task that
                # somehow raised still must not kill the country.
                logger.error("[DISCOVERY][%s] task crashed: %s",
                             country.code, str(outcome)[:160])
                continue
            result, source, health, wall_ms = outcome
            spec = sr.get(source)
            if health.status == sr.HEALTH_NOT_APPLICABLE:
                continue  # already recorded pre-task
            if spec is not None and spec.access == sr.Access.API_KEY \
                    and not _source_has_key(source, keys):
                health.status = sr.HEALTH_CONFIGURATION_REQUIRED

            country_runs.append(health)
            all_runs.append(health)

            listings = result.listings[:MAX_RESULTS_PER_PASS]
            truncated = len(result.listings) - len(listings)
            pass_rec = {
                "country": country.code, "term": entry["term"],
                "queryless": entry["term"] is None, "source": source,
                "duration_ms": wall_ms,
            }
            ingested = dupes = 0
            rejected = {"not_ingestible": 0, "role_gate": 0, "region_gate": 0}
            for job in listings:
                if not job.is_ingestible():
                    rejected["not_ingestible"] += 1
                    continue
                # Source attribution is enforced by the ORCHESTRATOR, not
                # trusted from the listing (Critical Test #2).
                job.source = source
                key = (job.source, job.content_hash)
                if key in seen_hashes:
                    dupes += 1
                    continue
                seen_hashes.add(key)

                # SAME gates as legacy ingest (no lowering of the bar) — and
                # each rejection is now COUNTED so the discipline is checkable.
                if not is_relevant_title(job.title, gate_terms):
                    rejected["role_gate"] += 1
                    continue
                region = classify_location_rule_based(job.location)
                if region is not None and region not in allowed_regions:
                    rejected["region_gate"] += 1
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

            # Aggregate the run's reject counts (the report reads these).
            rejects["not_ingestible"] += rejected["not_ingestible"]
            rejects["by_role_gate"] += rejected["role_gate"]
            rejects["by_region_gate"] += rejected["region_gate"]
            rejects["duplicates"] += dupes

            health.valid_jobs = ingested
            health.duplicates = dupes
            sr.log_source_end(health)

            pass_rec.update({
                "stop_reason": result.stop_reason,
                "found": len(result.listings),
                "ingested": ingested,
                "duplicates": dupes,
                "truncated": truncated,
                "rejected": rejected,
                "error": result.error,
                "health_status": health.status,
            })
            telemetry["passes"].append(pass_rec)
            telemetry["new_jobs"] += ingested
            telemetry["duplicates_seen"] += dupes
            telemetry["truncated"] += truncated
            if progress is not None:
                progress.update({
                    "country": country.code, "term": entry["term"],
                    "completed_passes": len(telemetry["passes"]),
                    "new_jobs": telemetry["new_jobs"],
                })

        telemetry["concurrency"]["max_active_observed"] = max(
            telemetry["concurrency"]["max_active_observed"], inflight["max_active"])
        telemetry["source_health"].extend(r.to_dict() for r in country_runs)
        country_summaries.append(sr.log_country_summary(
            country.code, country_runs, time.monotonic() - country_t0))

    rejects["total"] = (rejects["by_role_gate"] + rejects["by_region_gate"]
                        + rejects["not_ingestible"])
    telemetry["country_summaries"] = country_summaries
    telemetry["global_summary"] = sr.log_global_summary(
        telemetry["countries"], all_runs, time.monotonic() - t0)
    telemetry["duration_s"] = round(time.monotonic() - t0, 1)
    telemetry["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    logger.info("Discovery cycle: %d passes, %d new, %d dupes, %d truncated "
                "(%.1fs, concurrency=%d, max_active=%d, rejects=%s)",
                len(telemetry["passes"]), telemetry["new_jobs"],
                telemetry["duplicates_seen"], telemetry["truncated"],
                telemetry["duration_s"],
                telemetry["concurrency"]["max_concurrent_sources"],
                telemetry["concurrency"]["max_active_observed"],
                rejects)
    return telemetry


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
