import asyncio
import logging
import time

from app.circuit_breaker import CircuitBreaker
from app.database import Database, make_dedup_hash

logger = logging.getLogger(__name__)

_scraper_breaker = CircuitBreaker(failure_threshold=5, cooldown_seconds=300.0)
_enrichment_semaphore = asyncio.Semaphore(3)

# Track consecutive zero-result runs per scraper for health monitoring
_consecutive_zero_runs: dict[str, int] = {}
ZERO_RESULT_WARN_THRESHOLD = 3

# Per-scraper hard timeout — a single hung source must never block the cycle.
PER_SCRAPER_TIMEOUT = 120
# Heartbeat the progress state every N listings inside the insert loop
# so large payloads do not trip client-side stall detection.
_HEARTBEAT_EVERY = 25


async def run_scrape_cycle(db: Database, scrapers: list, search_terms: list[str] | None = None, progress: dict | None = None, scraper_keys: dict | None = None, force: bool = False) -> int:
    """Scrape job boards and insert new listings. Scrape-only — no enrichment or scoring.

    Progress contract: this function updates `completed`, `current`, `new_jobs`, `sources`,
    and bumps `last_updated_at` on every mutation. It never touches `active` or `phase` —
    the router owns lifecycle. Each scraper is wrapped in `asyncio.wait_for` so a single
    hung source cannot block the whole cycle.
    """
    total_new = 0
    total_scrapers = len(scrapers)
    if progress is not None and "sources" not in progress:
        progress["sources"] = []

    def _heartbeat():
        if progress is not None:
            progress["last_updated_at"] = time.monotonic()

    for i, scraper_instance in enumerate(scrapers):
        if isinstance(scraper_instance, type):
            scraper_instance = scraper_instance(search_terms=search_terms, scraper_keys=scraper_keys or {})
        source_name = scraper_instance.source_name

        src: dict | None = None
        if progress is not None:
            src = {
                "name": source_name,
                "status": "running",
                "listings_found": 0,
                "new_jobs": 0,
                "error": None,
                "duration_ms": None,
            }
            progress["sources"].append(src)
            progress["current"] = source_name
            progress["completed"] = i
            progress["total"] = total_scrapers
            progress["new_jobs"] = total_new
            _heartbeat()

        # Check per-source schedule (bypass for manual triggers)
        if not force and not await db.should_scraper_run(source_name):
            logger.info(f"Skipping {source_name} — not yet due")
            if src is not None:
                src["status"] = "skipped"
                src["error"] = "not yet due"
            if progress is not None:
                progress["completed"] = i + 1
                _heartbeat()
            continue
        if _scraper_breaker.is_open(f"scraper:{source_name}"):
            logger.info(f"Circuit breaker open for {source_name}, skipping")
            if src is not None:
                src["status"] = "skipped"
                src["error"] = "circuit breaker open"
            if progress is not None:
                progress["completed"] = i + 1
                _heartbeat()
            continue

        logger.info(f"Scraping {source_name}...")
        t0 = time.monotonic()
        try:
            listings = await asyncio.wait_for(
                scraper_instance.scrape(), timeout=PER_SCRAPER_TIMEOUT
            )
            _scraper_breaker.record_success(f"scraper:{source_name}")
        except asyncio.TimeoutError:
            if src is not None:
                src["status"] = "timeout"
                src["error"] = f"exceeded {PER_SCRAPER_TIMEOUT}s"
                src["duration_ms"] = int((time.monotonic() - t0) * 1000)
            _scraper_breaker.record_failure(f"scraper:{source_name}")
            logger.warning(f"{source_name}: timeout after {PER_SCRAPER_TIMEOUT}s")
            if progress is not None:
                progress["completed"] = i + 1
                _heartbeat()
            continue
        except Exception as e:
            if src is not None:
                src["status"] = "failed"
                src["error"] = str(e)[:200]
                src["duration_ms"] = int((time.monotonic() - t0) * 1000)
            _scraper_breaker.record_failure(f"scraper:{source_name}")
            logger.error(f"Scraper {source_name} failed: {e}")
            if progress is not None:
                progress["completed"] = i + 1
                _heartbeat()
            continue

        # Pre-filter: skip listings from disallowed regions at scrape time
        from app.location_classifier import classify_location_rule_based, classify_work_type
        allowed_regions = await db.get_allowed_regions()
        allowed_set = {r.lower() for r in allowed_regions}
        remote_only = await db.get_remote_only()
        # Also allow unknown/ambiguous through (conservative)
        skipped_region = 0
        skipped_work_type = 0
        src_new_jobs = 0
        skipped_title = 0

        # Load user search terms once per source for the title gate.
        _cfg = await db.get_search_config()
        _user_terms = (_cfg or {}).get("search_terms") or []

        for li, listing in enumerate(listings):
            # Quick rule-based check before inserting
            region = classify_location_rule_based(listing.location)
            if region is not None and region.lower() not in allowed_set:
                skipped_region += 1
                continue

            if remote_only:
                work_type = classify_work_type(listing.location, listing.title, listing.description)
                if work_type is not None and work_type != "remote":
                    skipped_work_type += 1
                    continue

            # Deterministic title-relevance gate (no AI cost): feed sources
            # return whole feeds; only plausible target-role titles pass.
            from app.title_filter import is_relevant_title
            if not is_relevant_title(listing.title, _user_terms):
                skipped_title += 1
                continue

            dedup = make_dedup_hash(listing.title, listing.company, listing.url)
            existing = await db.find_job_by_hash(dedup)
            if existing:
                await db.insert_source(existing["id"], source_name, listing.url)
                await db.update_last_seen(existing["id"])
            else:
                job_id = await db.insert_job(
                    title=listing.title,
                    company=listing.company,
                    location=listing.location,
                    salary_min=listing.salary_min,
                    salary_max=listing.salary_max,
                    description=listing.description,
                    url=listing.url,
                    posted_date=listing.posted_date,
                    application_method=listing.application_method,
                    contact_email=listing.contact_email,
                )
                if job_id:
                    # Check for cross-source duplicates
                    dupes = await db.find_cross_source_dupes(job_id, listing.title, listing.company)
                    if dupes:
                        # Merge: add source to oldest existing job, dismiss this new one
                        oldest = dupes[0]
                        await db.insert_source(oldest["id"], source_name, listing.url)
                        await db.dismiss_job(job_id)
                        logger.debug(f"Dedup: merged '{listing.title}' @ {listing.company} into job {oldest['id']}")
                    else:
                        await db.insert_source(job_id, source_name, listing.url)
                        total_new += 1
                        src_new_jobs += 1
                    # Pre-classify if rule-based matched
                    if region is not None:
                        await db.set_job_location_region(job_id, region)

            if progress is not None and (li + 1) % _HEARTBEAT_EVERY == 0:
                progress["new_jobs"] = total_new
                if src is not None:
                    src["listings_found"] = li + 1
                    src["new_jobs"] = src_new_jobs
                _heartbeat()

        if src is not None:
            src["status"] = "ok"
            src["listings_found"] = len(listings)
            src["new_jobs"] = src_new_jobs
            src["duration_ms"] = int((time.monotonic() - t0) * 1000)

        skip_parts = []
        if skipped_region:
            skip_parts.append(f"{skipped_region} outside allowed regions")
        if skipped_work_type:
            skip_parts.append(f"{skipped_work_type} non-remote")
        if skipped_title:
            skip_parts.append(f"{skipped_title} off-topic titles")
        if skip_parts:
            logger.info(f"{source_name}: found {len(listings)} listings, skipped {', '.join(skip_parts)}")
        else:
            logger.info(f"{source_name}: found {len(listings)} listings")

        # Health tracking: warn on consecutive zero-result runs
        if len(listings) == 0:
            _consecutive_zero_runs[source_name] = _consecutive_zero_runs.get(source_name, 0) + 1
            zeros = _consecutive_zero_runs[source_name]
            if zeros >= ZERO_RESULT_WARN_THRESHOLD:
                logger.warning(
                    f"SCRAPER HEALTH: {source_name} returned 0 results for "
                    f"{zeros} consecutive runs — may be broken or blocked"
                )
        else:
            _consecutive_zero_runs[source_name] = 0

        await db.mark_scraper_ran(source_name)

        if progress is not None:
            progress["completed"] = i + 1
            progress["new_jobs"] = total_new
            _heartbeat()

    if progress is not None:
        progress["current"] = None
        progress["new_jobs"] = total_new
        _heartbeat()
    logger.info(f"Scrape cycle complete. {total_new} new jobs added.")
    return total_new


def _classification_row(job: dict, result) -> tuple:
    """Build the 8-tuple persisted by `set_job_classifications_batch`.

    Region-string contract with the existing pipeline: `jobs.location_region`
    holds names like 'Germany'/'UK'/'Remote'. Country-classified jobs use the
    registry region string; region-only/unknown keep their bucket. Conflict
    evidence (description disagreeing with the location) is appended to the
    reason and returned in slot 7 for metrics.
    """
    from app.classification import detect_conflict
    conflict = detect_conflict(job, result)
    return (job["id"], result.region or "Unknown", result.country_code,
            result.classification_confidence, result.classification_source,
            result.classification_reason, result.supported_countries, conflict)


async def run_location_classification(db: Database, ai_client=None) -> int:
    """Stage-2 CLASSIFY: classify job locations + record confidence/evidence.

    Priority chain (app/classification.py): structured country → location text
    → city map → description evidence → ATS metadata → source hint (LOW only)
    → LLM batch for the residue → honest UNKNOWN. Source country is a HINT,
    never the answer. Persists confidence/source/reason so unchanged jobs are
    never re-classified (idempotent; task §16/§17). Then dismisses jobs
    outside allowed regions — that dismissal IS Stage-3 territory but is the
    pre-existing behavior of this pass (kept; eligibility re-checks anyway).
    """
    from app.classification import (classify_job, classify_job_ai, SRC_UNKNOWN)
    from app.country_registry import CountryRegistry
    from app.config import get_settings

    # code → region-string mapper from the country registry (GB → 'UK' etc.)
    code_to_region: dict[str, str] = {}
    try:
        _reg = CountryRegistry(get_settings().countries_dir).load()
        for c in _reg.countries.values():
            code_to_region[c.code] = c.region
    except Exception:
        logger.warning("classification: country registry unavailable — using defaults")

    def _region_of(code: str) -> str:
        return code_to_region.get(code) or code

    total_classified = 0
    metrics = {"total": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "UNKNOWN": 0,
               "remote": 0, "hybrid": 0, "onsite": 0,
               "ai_fallback": 0, "conflicts": 0,
               "no_ai_needed": 0, "same_country": 0, "other_country": 0}
    t0 = asyncio.get_event_loop().time()
    while True:
        jobs = await db.get_unclassified_jobs(limit=500)
        if not jobs:
            break

        decisions: list[tuple] = []   # (job, final Classification)
        residues: list[tuple] = []    # deterministic UNKNOWNs eligible for AI

        # Pass 1: deterministic priority chain (no API cost)
        for job in jobs:
            result = classify_job(job, region_of=_region_of)
            # Residue = deterministic chain returned honest UNKNOWN. Those —
            # and ONLY those — are eligible for the bounded AI tier (§10).
            if result.classification_source == SRC_UNKNOWN and ai_client is not None:
                residues.append((job, result))
            else:
                decisions.append((job, result))
            await asyncio.sleep(0)

        # Pass 2: bounded, validated AI fallback for the residue (semantics
        # only). One job per call, short bounded prompt; a rejected or
        # low-confidence answer stays UNKNOWN (never fabricate).
        for job, det_result in residues:
            final = det_result
            try:
                ai_result = await classify_job_ai(job, ai_client,
                                                  region_of=_region_of)
                if ai_result.classification_source != SRC_UNKNOWN:
                    final = ai_result
            except Exception as exc:  # noqa: BLE001 — never block the pipeline
                logger.warning("classification: AI fallback error job=%s: %s",
                               job["id"], exc)
            decisions.append((job, final))
            await asyncio.sleep(0)

        # Rows + metrics over the FINAL decisions (deterministic + AI-resolved)
        batch_updates = []
        for job, result in decisions:
            row = _classification_row(job, result)
            batch_updates.append(row)
            m = metrics
            m["total"] += 1
            m[result.classification_confidence] = \
                m.get(result.classification_confidence, 0) + 1
            if result.remote_type == "REMOTE":
                m["remote"] += 1
            elif result.remote_type == "HYBRID":
                m["hybrid"] += 1
            elif result.remote_type == "ONSITE":
                m["onsite"] += 1
            if result.classification_source == "AI_FALLBACK":
                m["ai_fallback"] += 1
            else:
                m["no_ai_needed"] += 1
            if row[7]:  # conflict recorded
                m["conflicts"] += 1
            logger.info(
                "[CLASSIFY][job=%s] raw_location=%r country=%s confidence=%s source=%s",
                job["id"], (job.get("location") or "")[:50],
                result.country_code or "UNKNOWN",
                result.classification_confidence, result.classification_source)

        # Write classification results (one batch)
        if batch_updates:
            await db.set_job_classifications_batch(batch_updates)

        total_classified += len(decisions)
        await asyncio.sleep(0)

    if total_classified:
        duration = asyncio.get_event_loop().time() - t0
        logger.info(
            "[CLASSIFY] done: %s jobs, %s | avg %.1fms/job | conflicts=%s",
            total_classified, {k: v for k, v in metrics.items() if v},
            duration * 1000 / max(1, total_classified), metrics["conflicts"])
    try:
        await db.set_classification_metrics({**metrics,
                                             "duration_s": round(
                                                 asyncio.get_event_loop().time() - t0, 1)})
    except Exception:
        pass  # metrics are best-effort; never block the pipeline

    # Pass 3: dismiss outside allowed regions (pre-existing pass behavior).
    # "Unknown" is kept (conservative — don't dismiss what we can't classify).
    allowed = await db.get_allowed_regions()
    allowed_with_unknown = allowed + ["Unknown"]
    dismissed = await db.dismiss_jobs_outside_regions(allowed_with_unknown)

    if total_classified:
        logger.info(f"Location classification: {total_classified} jobs classified, {dismissed} dismissed")
    return total_classified


async def run_eligibility_pass(db: Database, registry=None, force: bool = False,
                               limit: int = 2000) -> int:
    """Stage-3 ELIGIBILITY: evaluate the deterministic gate chain and PERSIST
    the decision (status/gate/reason/evidence) per job.

    This is the bridge that stops INELIGIBLE / REVIEW_REQUIRED jobs from
    leaking into SCORE: `db.get_scoreable_jobs()` only returns ELIGIBLE rows.
    Deterministic, no AI. Idempotent — only un-evaluated jobs are processed
    unless `force=True`.
    """
    from datetime import datetime, timezone
    from app.eligibility import build_eligibility_engine
    from app.country_registry import CountryRegistry
    from app.config import get_settings

    if registry is None:
        try:
            registry = CountryRegistry(get_settings().countries_dir).load()
        except Exception:
            logger.warning("eligibility: country registry unavailable — region-only gating")
            registry = None
    engine = await build_eligibility_engine(db, registry)

    metrics = {"total_evaluated": 0, "eligible": 0, "ineligible": 0,
               "review_required": 0, "unknown": 0,
               "by_gate": {}, "by_reason": {}}
    t0 = asyncio.get_event_loop().time()
    evaluated = 0
    while True:
        jobs = await db.get_jobs_for_eligibility(
            limit=(limit if force else 500), force=force)
        if not jobs:
            break
        now_iso = datetime.now(timezone.utc).isoformat()
        updates = []
        for job in jobs:
            app = None
            if job.get("application_status"):
                app = {"status": job["application_status"],
                       "id": job.get("application_id")}
            result = engine.check(job, application=app)
            # SQL parameter order: (status, gate, reason, evidence, ts, job_id)
            updates.append((result.status, result.gate, result.reason,
                            result.to_evidence_json(), now_iso, job["id"]))
            m = metrics
            m["total_evaluated"] += 1
            m[result.status.lower()] = m.get(result.status.lower(), 0) + 1
            m["by_gate"][result.gate] = m["by_gate"].get(result.gate, 0) + 1
            m["by_reason"][result.reason] = m["by_reason"].get(result.reason, 0) + 1
            logger.info("[ELIGIBILITY][job=%s] status=%s gate=%s reason=%s",
                        job["id"], result.status, result.gate, result.reason)
        if updates:
            await db.set_job_eligibility_batch(updates)
        evaluated += len(updates)
        if force:
            break
        await asyncio.sleep(0)
    metrics["duration_s"] = round(asyncio.get_event_loop().time() - t0, 1)
    try:
        await db.set_eligibility_metrics(metrics)
    except Exception:
        pass  # metrics are best-effort; never block the pipeline
    if evaluated:
        logger.info("[ELIGIBILITY] done: %s jobs, %s", evaluated,
                    {k: v for k, v in metrics.items()
                     if v and k not in ("by_gate", "by_reason")})
    return evaluated


async def apply_country_strategy(db: Database, registry, sync_allowed_regions: bool = True) -> dict:
    """M3: apply the country strategy to the EXISTING job pool (no scraping).

    1. Classify any unclassified jobs (rule-based pass, no AI cost).
    2. Sync allowed_regions to enabled countries + Remote (keeps scrape-time
       prefilter and future M5 eligibility consistent with strategy).
    3. Dismiss classified jobs outside the enabled countries
       (respects active applications — never touches those).

    Returns machine-readable stats for the API/report.
    """
    enabled = registry.enabled_countries() if registry else []
    enabled_regions = [c.region for c in enabled]

    # 1. Classify unclassified (rule-based only — no AI spend in a strategy apply)
    classified = await run_location_classification(db, ai_client=None)

    # 2. Sync allowed_regions so scrape-time prefilter matches strategy
    allowed = enabled_regions + ["Remote"]
    if sync_allowed_regions:
        await db.update_allowed_regions(allowed)

    # 3. Re-admit jobs a previous NARROWER strategy had auto-dismissed, THEN
    #    dismiss against the new strategy. Order matters: restore first makes
    #    strategy changes fully reversible (e.g. adding UAE re-admits Dubai jobs).
    restored = await db.restore_strategy_dismissed_jobs()
    dismissed = await db.dismiss_jobs_outside_regions(allowed + ["Unknown"])

    # Stats: how many live jobs per enabled country now
    per_country = {}
    for region in enabled_regions:
        cur = await db.db.execute(
            "SELECT COUNT(*) FROM jobs WHERE location_classified=1 "
            "AND dismissed=0 AND location_region=?", (region,))
        per_country[region] = (await cur.fetchone())[0]
    cur = await db.db.execute(
        "SELECT COUNT(*) FROM jobs WHERE location_classified=1 AND dismissed=0 "
        "AND location_region='Remote'")
    per_country["Remote"] = (await cur.fetchone())[0]

    logger.info("Country strategy applied: %d enabled, classified=%d, restored=%d, dismissed=%d, live=%s",
                len(enabled), classified, restored, dismissed, per_country)
    return {
        "enabled_countries": [c.code for c in enabled],
        "allowed_regions": allowed,
        "classified_now": classified,
        "restored_now": restored,
        "dismissed_now": dismissed,
        "live_jobs_per_region": per_country,
    }


async def run_enrichment_cycle(db: Database, limit: int = 30) -> int:
    """Enrich jobs with short/missing descriptions. Runs independently of scraping."""
    from app.enrichment import enrich_job_description

    async with _enrichment_semaphore:
        jobs_to_enrich = await db.get_jobs_needing_enrichment(limit=limit)
        enriched_count = 0
        for job in jobs_to_enrich:
            sources = await db.get_sources(job["id"])
            source = sources[0]["source_name"] if sources else "unknown"
            attempts = (job.get("enrichment_attempts") or 0) + 1
            desc = await enrich_job_description(job["url"], source)
            if desc and len(desc) > len(job.get("description") or ""):
                await db.update_job_description(job["id"], desc)
                await db.update_enrichment_status(job["id"], "enriched", attempts)
                enriched_count += 1
            else:
                await db.update_enrichment_status(job["id"], "failed", attempts)
        if enriched_count:
            logger.info(f"Enriched {enriched_count}/{len(jobs_to_enrich)} job descriptions")
        return enriched_count


async def run_maintenance_cycle(db: Database) -> int:
    """M5 maintenance: record freshness evidence + auto-dismiss stale jobs.

    Golden Rule 10: MAX_JOB_AGE_DAYS default = 7 (was 30). DATE_UNKNOWN jobs
    get evidence recorded but are NOT dismissed by age (no reliable date);
    they are excluded from eligibility instead (Critical Test #3).
    """
    from app.freshness import assess_freshness

    # Refresh freshness evidence on live, unclassified-age jobs (bounded batch)
    cursor = await db.db.execute(
        """SELECT id, posted_date FROM jobs
           WHERE dismissed = 0 AND freshness_evidence IS NULL LIMIT 500""")
    rows = await cursor.fetchall()
    assessed = 0
    for row in rows:
        evidence = assess_freshness(row["posted_date"])
        await db.record_freshness(row["id"], evidence)
        assessed += 1

    dismissed = await db.auto_dismiss_stale(max_age_days=7, no_date_max_days=30)
    if dismissed or assessed:
        logger.info(f"Maintenance: {assessed} jobs freshness-assessed, {dismissed} stale dismissed")
    return dismissed


async def run_alert_check(db: Database) -> int:
    """Check enabled job alerts for new matching jobs. Creates notifications."""
    alerts = await db.get_job_alerts()
    total_notifications = 0
    for alert in alerts:
        if not alert.get("enabled"):
            continue
        new_jobs = await db.get_new_jobs_for_alert(alert)
        for job in new_jobs:
            title = f"Alert: {alert['name']}"
            message = f"{job['title']} at {job['company']}"
            score = job.get("match_score")
            if score:
                message += f" (Score: {score})"
            await db.insert_notification(job["id"], "alert", title, message)
            total_notifications += 1
        await db.mark_alert_checked(alert["id"])
    if total_notifications:
        logger.info(f"Job alerts: {total_notifications} notifications created")
    return total_notifications


async def run_reminder_check(db: Database, embedding_client=None) -> list[dict]:
    """Check for due follow-up reminders. Auto-drafts if configured. Returns list of due reminders."""
    due = await db.get_due_reminders()
    if due:
        logger.info(f"Found {len(due)} due follow-up reminders")
    for reminder in due:
        if reminder.get("auto_draft") and not reminder.get("draft_text"):
            try:
                from app.follow_up import draft_follow_up
                ai_settings = await db.get_ai_settings()
                if ai_settings and ai_settings.get("provider"):
                    from app.ai_client import AIClient
                    client = AIClient(
                        ai_settings["provider"],
                        api_key=ai_settings.get("api_key", ""),
                        model=ai_settings.get("model", ""),
                    )
                    app_data = await db.get_application(reminder["job_id"])
                    applied_at = app_data.get("applied_at", "") if app_data else ""
                    days = 0
                    if applied_at:
                        from datetime import datetime, timezone
                        try:
                            days = (datetime.now(timezone.utc) - datetime.fromisoformat(applied_at)).days
                        except (ValueError, TypeError):
                            pass

                    # Retrieve past contact interactions for this company via embeddings
                    template_text = None
                    if embedding_client and getattr(db, "_vec_loaded", False):
                        from app.embeddings import retrieve_relevant_context
                        company = reminder.get("company", "")
                        query = f"follow-up with {company} {reminder.get('title', '')}"
                        context_items = await retrieve_relevant_context(
                            db.db, embedding_client, query, limit=3
                        )
                        if context_items:
                            template_text = "Previous interactions:\n" + "\n".join(
                                f"- {c['text'][:200]}" for c in context_items
                            )

                    draft = await draft_follow_up(
                        client,
                        title=reminder.get("title", ""),
                        company=reminder.get("company", ""),
                        applied_at=applied_at,
                        days_since=days,
                        template_text=template_text,
                    )
                    if draft:
                        await db.update_reminder_draft(reminder["id"], draft)
                        logger.info(f"Auto-drafted follow-up for reminder {reminder['id']}")
            except Exception as e:
                logger.error(f"Auto-draft failed for reminder {reminder['id']}: {e}")
    return due


async def run_context_embedding_cycle(db: Database, embedding_client, batch_size: int = 20) -> int:
    """Sync context items (work history, contact interactions) and embed them."""
    if not embedding_client:
        return 0
    if not getattr(db, "_vec_loaded", False):
        return 0

    from app.embeddings import upsert_embedding

    # Sync work history descriptions into context_items
    cursor = await db.db.execute(
        """SELECT id, job_title, company, description FROM work_history
           WHERE description != ''"""
    )
    for row in await cursor.fetchall():
        text = f"{row['job_title']} at {row['company']}: {row['description']}"
        existing = await db.db.execute(
            "SELECT id FROM context_items WHERE type = 'work_history' AND source_id = ?",
            (row["id"],),
        )
        if not await existing.fetchone():
            await db.db.execute(
                "INSERT INTO context_items (type, source_id, text) VALUES (?, ?, ?)",
                ("work_history", row["id"], text),
            )

    # Sync contact interaction notes
    cursor = await db.db.execute(
        """SELECT ci.id, ci.notes, c.name, c.company
           FROM contact_interactions ci
           JOIN contacts c ON c.id = ci.contact_id
           WHERE ci.notes != ''"""
    )
    for row in await cursor.fetchall():
        text = f"Interaction with {row['name']} ({row['company']}): {row['notes']}"
        existing = await db.db.execute(
            "SELECT id FROM context_items WHERE type = 'contact_interaction' AND source_id = ?",
            (row["id"],),
        )
        if not await existing.fetchone():
            await db.db.execute(
                "INSERT INTO context_items (type, source_id, text) VALUES (?, ?, ?)",
                ("contact_interaction", row["id"], text),
            )

    await db.db.commit()

    # Embed unembedded context items
    cursor = await db.db.execute(
        "SELECT id, text FROM context_items WHERE embedded = 0 LIMIT ?",
        (batch_size,),
    )
    items = await cursor.fetchall()
    embedded = 0
    for item in items:
        try:
            vector = await embedding_client.embed(item["text"][:8000])
            await upsert_embedding(db.db, "vec_context", item["id"], vector)
            await db.db.execute(
                "UPDATE context_items SET embedded = 1 WHERE id = ?", (item["id"],)
            )
            embedded += 1
        except Exception as e:
            logger.warning("Failed to embed context item %d: %s", item["id"], e)

    if embedded:
        await db.db.commit()
        logger.info(f"Context embedding cycle: embedded {embedded}/{len(items)} items")
    return embedded


async def run_job_embedding_cycle(db: Database, embedding_client, batch_size: int = 20) -> int:
    """Embed jobs that don't have embeddings yet. Runs every 2 hours."""
    if not embedding_client:
        return 0
    if not getattr(db, "_vec_loaded", False):
        return 0

    from app.embeddings import upsert_embedding

    cursor = await db.db.execute(
        """SELECT j.id, j.title, j.company, j.description
           FROM jobs j
           LEFT JOIN vec_jobs v ON v.item_id = j.id
           WHERE j.dismissed = 0 AND v.item_id IS NULL
           LIMIT ?""",
        (batch_size,),
    )
    jobs = await cursor.fetchall()
    if not jobs:
        return 0

    embedded = 0
    for job in jobs:
        text = f"{job['title']} at {job['company']}\n{job['description'] or ''}"
        try:
            vector = await embedding_client.embed(text[:8000])
            await upsert_embedding(db.db, "vec_jobs", job["id"], vector)
            embedded += 1
        except Exception as e:
            logger.warning("Failed to embed job %d: %s", job["id"], e)

    if embedded:
        logger.info(f"Embedding cycle: embedded {embedded}/{len(jobs)} jobs")
    return embedded


async def run_digest_cycle(db: Database) -> bool:
    """Check if digest is enabled and send it. Called by APScheduler."""
    from app.digest import send_digest
    try:
        return await send_digest(db)
    except Exception as e:
        logger.error(f"Digest cycle failed: {e}")
        return False
