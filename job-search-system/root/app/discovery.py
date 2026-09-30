"""M4 → Stage-1 DISCOVER orchestration (Phases 6/7 + discovery upgrade).

For every ENABLED country (M3) × every search term (user's AI-analyzed
search_terms), run every REGISTERED source adapter in TIER order (task §7:
direct/ATS/major-local first), ingest through the SAME pipeline as the legacy
scrapers (title gate → region gate → insert → source attribution), and record
honest per-pass telemetry AND source-health results (task §21).

What changed in the Stage-1 upgrade (behavior preserved otherwise):
  * adapter order comes from app/source_registry (tier, priority) instead of
    module import order — most authoritative sources run (and win canonical
    attribution) first;
  * single-country sources skip other countries HONESTLY at the orchestrator
    (NOT_APPLICABLE) before any HTTP is spent — same semantics as the old
    region_hint empty pass, now data-driven from the registry;
  * every pass produces a SourceRunHealth record; PASS/PARTIAL/NO_RESULTS/
    CONFIGURATION_REQUIRED/RATE_LIMITED/FAILED/BLOCKED/NOT_APPLICABLE;
  * canonical_source + source_types are stamped on every job the moment a
    second (higher-tier) source confirms it (task §17/§19 provenance);
  * structured [DISCOVERY] log lines (task §48) — no secrets, ever.

Request budget is still capped per cycle (cost/resilience control): a country
whose adapters all rate-limit stops consuming budget this cycle.
"""

from __future__ import annotations

import logging
import time

from app import source_registry as sr
from app.job_adapter import (
    STOP_RATE_LIMITED,
    STOP_SOURCE_FAILURE,
)

logger = logging.getLogger(__name__)

# 2026-09-28: 10 countries × 19 adapters = up to 190 passes/term — the old 24
# cap would starve the sweep after ~2 countries. 50 lets a cycle cover 2-3
# countries fully; scheduled cycles rotate through the rest.
MAX_REQUEST_PASSES_PER_CYCLE = 50      # adapter-passes per orchestrated cycle
MAX_LISTINGS_PER_PASS = 200            # ingest cap per pass

# Canonical-source ranking lives in the registry (single source of truth).
_canonical_rank = sr.canonical_rank


async def run_discovery_cycle(db, registry, all_adapters, ai_client=None,
                              progress: dict | None = None,
                              max_passes: int | None = None,
                              scraper_keys: dict | None = None) -> dict:
    """One orchestrated discovery pass across enabled countries × search terms.

    `max_passes` bounds the adapter-passes consumed this cycle (1..50). The UI
    and CLI use it to run a short, predictable sweep instead of always burning
    the full budget; omit it for the default cap. `scraper_keys` (optional)
    overrides the per-user DB keys — used by env-fallback wiring. Returns
    machine-readable telemetry (incl. per-pass source health) for the
    API/report.
    """
    from app.title_filter import is_relevant_title
    from app.location_classifier import classify_location_rule_based

    # Registry ↔ adapters: warn on drift (focused subsets are legitimate in
    # tests/bounded sweeps); the STRICT full-list check runs at app startup.
    sr.validate_against({cls.source_name for cls in all_adapters}, strict=False)

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

    # Tier-ordered source run order (registry data, not import order).
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

        for term in search_terms:
            if budget <= 0:
                telemetry["budget_exhausted"] = True
                break
            for adapter_cls in ordered_adapters:
                if budget <= 0:
                    telemetry["budget_exhausted"] = True
                    break
                budget -= 1
                adapter = adapter_cls(search_terms=[term], scraper_keys=keys)
                source = adapter.source_name
                spec = sr.get(source)
                health = sr.new_run_health(country.code, source)
                sr.log_source_start(country.code, source)

                # Honest country skip BEFORE any HTTP: a single-country source
                # pointed elsewhere is NOT_APPLICABLE (registry-driven, was
                # previously a wasted empty pass via region_hint).
                if (spec is not None and "*" not in spec.countries
                        and country.code not in spec.countries):
                    health.status = sr.HEALTH_NOT_APPLICABLE
                    health.finished_at = health.started_at
                    country_runs.append(health)
                    all_runs.append(health)  # global summary must count every pass
                    telemetry["passes"].append({
                        "country": country.code, "term": term, "source": source,
                        "stop_reason": "NOT_APPLICABLE", "found": 0,
                        "ingested": 0, "duplicates": 0, "error": "",
                    })
                    continue

                has_key = source not in keyed_sources or bool(keys.get(
                    "jooble" if source == "jooble" else
                    "adzuna" if source == "adzuna" else "reed"))
                try:
                    result = await adapter.search([term], country=country)
                except Exception as e:  # defensive: contract says never raise
                    result = type(result)(source=source,
                                          stop_reason=STOP_SOURCE_FAILURE,
                                          error=str(e)[:160])

                health.raw_jobs = health.parsed_jobs = len(result.listings)
                health.errors = result.error or ""
                health.status = sr.status_from_result(
                    result.stop_reason, len(result.listings), spec, has_key)

                pass_rec = {
                    "country": country.code, "term": term, "source": source,
                }
                ingested = dupes = 0
                for job in result.listings[:MAX_LISTINGS_PER_PASS]:
                    if not job.is_ingestible():
                        continue
                    # Source attribution is enforced by the ORCHESTRATOR, not
                    # trusted from the listing — a mislabeled listing must not
                    # corrupt cross-source dedup (found by Critical Test #2 test).
                    job.source = source
                    # Only skip re-ingesting the SAME source seeing the SAME job;
                    # cross-source duplicates MUST reach the DB layer so the
                    # second source gets attributed (Critical Test #2).
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
                    # NEW-row vs re-see: insert_job returns the EXISTING id when
                    # the dedup hash is already in the pool (INSERT OR IGNORE +
                    # hash lookup). A re-see must NOT re-attribute the source
                    # (duplicate sources rows) nor count as a new job — only
                    # last_seen_at is refreshed.
                    was_new = job_id > pre_cycle_max_id
                    # Cross-source identity: same title+company (fuzzy) already
                    # live from ANOTHER source → attribute source to the oldest
                    # row and dismiss this duplicate (same merge policy as the
                    # legacy scrape ingest).
                    cross_dupes = await db.find_cross_source_dupes(job_id, job.title, job.company)
                    if cross_dupes:
                        oldest = cross_dupes[0]
                        if was_new:
                            await db.insert_source(oldest["id"], source, job.url)
                            await db.dismiss_job(job_id)
                            # M5: record the repost edge (repost graph, audit + UI)
                            await db.add_duplicate_link(
                                oldest["id"], job_id,
                                f"cross-source:{source}")
                        await db.update_last_seen(oldest["id"])
                        await _stamp_provenance(db, oldest["id"], source)
                        dupes += 1
                    else:
                        # insert_source is idempotent per (job, source, url):
                        # a re-see is a no-op there, so attribution never stacks.
                        await db.insert_source(job_id, source, job.url)
                        if was_new:
                            # M5: freshness evidence recorded at ingest (audit trail)
                            from app.freshness import assess_freshness
                            await db.record_freshness(
                                job_id, assess_freshness(job.posted_date))
                            ingested += 1
                        else:
                            # Re-see of a job already pooled: refresh last_seen,
                            # count honestly as a duplicate — NOT a new job.
                            await db.update_last_seen(job_id)
                            dupes += 1
                            # A DIFFERENT source just confirmed this job (same
                            # dedup hash → same row): upgrade provenance.
                            await _stamp_provenance(db, job_id, source)

                health.valid_jobs = ingested
                health.duplicates = dupes
                health.finished_at = time.strftime(
                    "%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
                health.duration_ms = int((time.monotonic() - country_t0) * 1000)
                sr.log_source_end(health)
                country_runs.append(health)
                all_runs.append(health)

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

        telemetry["source_health"].extend(r.to_dict() for r in country_runs)
        country_summaries.append(sr.log_country_summary(
            country.code, country_runs, time.monotonic() - country_t0))

    telemetry["country_summaries"] = country_summaries
    telemetry["global_summary"] = sr.log_global_summary(
        telemetry["countries"], all_runs, time.monotonic() - t0)
    telemetry["duration_s"] = round(time.monotonic() - t0, 1)
    telemetry["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    logger.info("Discovery cycle: %d passes, %d new, %d dupes (%.1fs)",
                len(telemetry["passes"]), telemetry["new_jobs"],
                telemetry["duplicates_seen"], telemetry["duration_s"])
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
