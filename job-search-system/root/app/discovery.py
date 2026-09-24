"""M4: Multi-role × per-country discovery orchestration (Phases 6/7).

For every ENABLED country (M3) × every search term (user's AI-analyzed
search_terms), run every adapter, ingest through the SAME pipeline as the
legacy scrapers (title gate → region gate → insert → source attribution),
and record honest stop-reason telemetry per pass.

Request budget is capped per cycle (cost/resilience control, Phase 35/36):
a country whose adapters all rate-limit stops consuming budget this cycle.
"""

from __future__ import annotations

import logging
import time

from app.job_adapter import (
    STOP_RATE_LIMITED,
    STOP_SOURCES_EXHAUSTED,
    STOP_SOURCE_FAILURE,
)

logger = logging.getLogger(__name__)

MAX_REQUEST_PASSES_PER_CYCLE = 24      # adapter-passes per orchestrated cycle
MAX_LISTINGS_PER_PASS = 200            # ingest cap per pass


async def run_discovery_cycle(db, registry, all_adapters, ai_client=None,
                              progress: dict | None = None,
                              max_passes: int | None = None) -> dict:
    """One orchestrated discovery pass across enabled countries × search terms.

    `max_passes` bounds the adapter-passes consumed this cycle (1..24). The UI
    and CLI use it to run a short, predictable sweep instead of always burning
    the full budget; omit it for the default cap. Returns machine-readable
    telemetry for the API/report.
    """
    from app.title_filter import is_relevant_title
    from app.location_classifier import classify_location_rule_based

    t0 = time.monotonic()
    countries = registry.enabled_countries() if registry else []
    cfg = await db.get_search_config()
    search_terms = (cfg or {}).get("search_terms") or []
    if not search_terms:
        search_terms = ["AI Engineer", "Machine Learning Engineer"]

    telemetry = {
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "countries": [c.code for c in countries],
        "search_terms": search_terms,
        "passes": [],
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

    for country in countries:
        if budget <= 0:
            telemetry["budget_exhausted"] = True
            break
        for term in search_terms:
            if budget <= 0:
                telemetry["budget_exhausted"] = True
                break
            for adapter_cls in all_adapters:
                if budget <= 0:
                    telemetry["budget_exhausted"] = True
                    break
                budget -= 1
                adapter = adapter_cls(search_terms=[term], scraper_keys=await db.get_scraper_keys())
                pass_rec = {
                    "country": country.code, "term": term,
                    "source": adapter.source_name,
                }
                try:
                    result = await adapter.search([term], country=country)
                except Exception as e:  # defensive: contract says never raise
                    result = type(result)(source=adapter.source_name,
                                          stop_reason=STOP_SOURCE_FAILURE,
                                          error=str(e)[:160])
                pass_rec["stop_reason"] = result.stop_reason
                pass_rec["found"] = len(result.listings)
                pass_rec["error"] = result.error

                ingested = dupes = 0
                for job in result.listings[:MAX_LISTINGS_PER_PASS]:
                    if not job.is_ingestible():
                        continue
                    # Source attribution is enforced by the ORCHESTRATOR, not
                    # trusted from the listing — a mislabeled listing must not
                    # corrupt cross-source dedup (found by Critical Test #2 test).
                    job.source = adapter.source_name
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
                    allowed = set(await db.get_allowed_regions()) | {"Unknown"}
                    if region is not None and region not in allowed:
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
                    # Cross-source identity: same title+company (fuzzy) already
                    # live from ANOTHER source → attribute source to the oldest
                    # row and dismiss this duplicate (same merge policy as the
                    # legacy scrape ingest).
                    cross_dupes = await db.find_cross_source_dupes(job_id, job.title, job.company)
                    if cross_dupes:
                        oldest = cross_dupes[0]
                        await db.insert_source(oldest["id"], job.source, job.url)
                        await db.dismiss_job(job_id)
                        await db.update_last_seen(oldest["id"])
                        # M5: record the repost edge (repost graph, audit + UI)
                        await db.add_duplicate_link(
                            oldest["id"], job_id,
                            f"cross-source:{job.source}")
                        dupes += 1
                    else:
                        await db.insert_source(job_id, job.source, job.url)
                        await db.update_last_seen(job_id)
                        # M5: freshness evidence recorded at ingest (audit trail)
                        from app.freshness import assess_freshness
                        await db.record_freshness(
                            job_id, assess_freshness(job.posted_date))
                        ingested += 1

                pass_rec["ingested"] = ingested
                pass_rec["duplicates"] = dupes
                telemetry["passes"].append(pass_rec)
                telemetry["new_jobs"] += ingested
                telemetry["duplicates_seen"] += dupes
                if progress is not None:
                    progress.update({
                        "country": country.code, "term": term,
                        "completed_passes": len(telemetry["passes"]),
                        "new_jobs": telemetry["new_jobs"],
                    })

    telemetry["duration_s"] = round(time.monotonic() - t0, 1)
    telemetry["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    logger.info("Discovery cycle: %d passes, %d new, %d dupes (%.1fs)",
                len(telemetry["passes"]), telemetry["new_jobs"],
                telemetry["duplicates_seen"], telemetry["duration_s"])
    return telemetry
