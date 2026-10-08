"""M4: /api/discovery — orchestrated multi-country discovery + source health.

Endpoints:
  POST /api/discovery/run            start a bounded cycle (background)
  GET  /api/discovery/status         progress + last telemetry for this user
  GET  /api/discovery/report         read-only Phase-4 report (config + run)
  GET  /api/discovery/registry       central source registry (read-only)
  GET  /api/discovery/health         cheap per-source reachability probe
  GET  /api/discovery/prune-preview  dry-run of the backlog prune
  POST /api/discovery/prune          apply the prune (needs confirm=true)

The report is READ-ONLY: it exposes the config discovery will use and the
telemetry the last cycle actually produced, so the run is checkable (pass
budget vs pass count, per-source query, reject counts, dedup) instead of
taken on faith. Discovery telemetry is not persisted — it lives in the
per-user run slot (app.run_state) — so the report returns `has_run: false`
until a cycle has run in this process.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time

from fastapi import APIRouter, HTTPException, Query, Request

from app import source_registry as sr
from app.discovery import (
    DEFAULT_ROLE_TERMS,
    MAX_REQUEST_PASSES_PER_CYCLE,
    MAX_RESULTS_PER_PASS,
    QUERYABLE_SOURCES,
    role_terms_from_config,
)
from app.main import _db  # M15b: per-user workspace DB
from app.search_gate import require_resume_for_search

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


def _env_scraper_keys() -> dict:
    """Env-var fallbacks for keyed sources (same pattern as usajobs.py).

    DB keys (Settings UI) always win; env fills the gap for headless setups.
    Only sources with dedicated env vars are listed here.
    """
    env_keys = {}
    if os.environ.get("JOBAGENT_JOOBLE_API_KEY"):
        env_keys["jooble"] = {"api_key": os.environ["JOBAGENT_JOOBLE_API_KEY"], "email": ""}
    if os.environ.get("JOBAGENT_ADZUNA_APP_KEY"):
        env_keys["adzuna"] = {"api_key": os.environ["JOBAGENT_ADZUNA_APP_KEY"], "email": ""}
    if os.environ.get("JOBAGENT_ADZUNA_APP_ID"):
        env_keys["adzuna-id"] = {"api_key": os.environ["JOBAGENT_ADZUNA_APP_ID"], "email": ""}
    if os.environ.get("JOBAGENT_REED_API_KEY"):
        env_keys["reed"] = {"api_key": os.environ["JOBAGENT_REED_API_KEY"], "email": ""}
    if os.environ.get("JOBAGENT_TAVILY_API_KEY"):
        env_keys["tavily_search"] = {
            "api_key": os.environ["JOBAGENT_TAVILY_API_KEY"],
            "email": "",
        }
    return env_keys


# ---------------------------------------------------------------------------
# Phase 4: per-source query capability (report view)
# ---------------------------------------------------------------------------


def _truncate_query(query: str, max_len: int = 120) -> str:
    """Truncate a query for telemetry so a long job_title is never echoed whole."""
    return query if len(query) <= max_len else query[:max_len] + "..."


def _role_queries(cfg: dict) -> list[str]:
    """The role queries discovery sends: the candidate's job_titles, the board
    search terms as fallback, then the product defaults."""
    roles = role_terms_from_config(cfg)
    if not roles:
        roles = [str(t).strip() for t in (cfg.get("search_terms") or []) if str(t).strip()]
    if not roles:
        roles = list(DEFAULT_ROLE_TERMS)
    return [_truncate_query(r) for r in roles][:10]


def _query_overrides(cfg: dict) -> dict:
    """Per-source query plan: what each registered source WILL be asked.

    Queryable sources (app.discovery.QUERYABLE_SOURCES) receive the candidate's
    role queries; whole-feed sources report `queryless: true` and an empty list
    because their feed does not depend on a term (they are post-filtered by the
    title gate). This mirrors the orchestrator's own plan, so the report and the
    run agree.
    """
    queries = _role_queries(cfg)
    return {
        name: {
            "queries": list(queries) if name in QUERYABLE_SOURCES else [],
            "queryless": name not in QUERYABLE_SOURCES,
        }
        for name in sr.SOURCES
    }


def _last_discovery_run(request: Request) -> dict | None:
    """The last cycle's telemetry for THIS user (in-process run state)."""
    try:
        from app.run_state import run_slot
        return run_slot(request).get("discovery_telemetry")
    except Exception:
        return None


async def _pool_counts(db) -> dict:
    """Live/dismissed job counts (bounded, single query)."""
    try:
        cursor = await db.db.execute(
            "SELECT (SELECT COUNT(*) FROM jobs WHERE dismissed = 0), "
            "(SELECT COUNT(*) FROM jobs WHERE dismissed = 1)")
        live, dismissed = await cursor.fetchone()
        return {"live_jobs": int(live or 0), "dismissed_jobs": int(dismissed or 0)}
    except Exception:
        return {"live_jobs": None, "dismissed_jobs": None}


def _last_error(rows: list[dict]) -> str | None:
    """The most recent honest problem for a source, or None."""
    for pass_rec in reversed(rows):
        status = pass_rec.get("health_status") or ""
        if status in ("CONFIGURATION_REQUIRED", "FAILED", "RATE_LIMITED"):
            return pass_rec.get("error") or status
    return None


@router.get("/discovery/report")
async def discovery_report(request: Request):
    """Read-only Phase-4 discovery report for the UI.

    Shows what discovery should look like (config + per-source query plan) and
    what the last cycle actually did (pass count vs budget, per-source rows,
    reject counts, dedup, caps). Nothing here writes to the database.
    """
    db = _db(request)
    cfg = await db.get_search_config() or {}
    registry = getattr(request.app.state, "country_registry", None)
    keys = await db.get_scraper_keys()
    overrides = _query_overrides(cfg)

    config = {
        "job_titles": role_terms_from_config(cfg),
        "search_terms": [str(t) for t in (cfg.get("search_terms") or [])],
        "enabled_countries": [c.code for c in registry.enabled_countries()] if registry else [],
        "scrapers": sorted(keys),
        "query_plan": overrides,
    }

    telemetry = _last_discovery_run(request) or {}
    passes = list(telemetry.get("passes") or [])

    per_source = {}
    for name in sr.SOURCES:
        rows = [p for p in passes if p.get("source") == name]
        plan = overrides.get(name, {"queryless": True, "queries": []})
        per_source[name] = {
            "queryless": plan["queryless"],
            "queries": plan["queries"],
            "passes": len(rows),
            "found": sum(int(p.get("found") or 0) for p in rows),
            "ingested": sum(int(p.get("ingested") or 0) for p in rows),
            "duplicates": sum(int(p.get("duplicates") or 0) for p in rows),
            "truncated": sum(int(p.get("truncated") or 0) for p in rows),
            "last_error": _last_error(rows),
        }

    reject_counts = telemetry.get("reject_counts") or {
        "by_role_gate": 0, "by_region_gate": 0, "not_ingestible": 0,
        "duplicates": 0, "total": 0,
    }

    dedup = {"total": 0, "by_source": {}}
    for pass_rec in passes:
        count = int(pass_rec.get("duplicates") or 0)
        dedup["total"] += count
        source = pass_rec.get("source")
        if source and count:
            dedup["by_source"][source] = dedup["by_source"].get(source, 0) + count

    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "has_run": bool(telemetry),
        "nature": {
            "description": "Role-targeted discovery: queryable sources run once "
                           "per role term, whole-feed sources run once per country.",
            "queryable_sources": sorted(QUERYABLE_SOURCES & set(sr.SOURCES)),
            "queryless_sources": sorted(set(sr.SOURCES) - QUERYABLE_SOURCES),
            "telemetry_source": "run_discovery_cycle (per-user run slot)",
        },
        "config": config,
        "per_source": per_source,
        "pass_budget": int(telemetry.get("pass_budget") or MAX_REQUEST_PASSES_PER_CYCLE),
        "planned_passes": int(telemetry.get("planned_passes") or 0),
        "pass_count": len(passes),
        "budget_exhausted": bool(telemetry.get("budget_exhausted")),
        "cap": {"max_results_per_pass": MAX_RESULTS_PER_PASS},
        "reject_counts": reject_counts,
        "dedup": dedup,
        "telemetry": telemetry or None,
        "db": await _pool_counts(db),
    }


@router.get("/discovery/registry")
async def source_registry_view(request: Request):
    """Central source registry (Stage-1 upgrade): every source's type, tier,
    country relevance, access mode + per-country coverage buckets.

    Read-only report data for UI/analytics — the DISCOVER engine reads the
    same registry directly (app/source_registry.py).
    """
    registry = getattr(request.app.state, "country_registry", None)
    countries = {}
    if registry:
        for c in registry.countries.values():
            countries[c.code] = {
                "region": c.region, "enabled": c.enabled,
                "coverage_buckets": sr.coverage_summary(c.code),
                "coverage_status": sr.coverage_status(c.code),
            }
    return {
        "sources": sr.to_dict(),
        "run_order": sr.adapter_order(),
        "category_counts_global": sr.category_counts(),
        "countries": countries,
    }


@router.get("/discovery/health")
async def discovery_health(request: Request):
    """Per-source reachability probe (cheap, parallel)."""
    from app.adapters import ALL_ADAPTERS
    keys = await _db(request).get_scraper_keys()
    for name, entry in _env_scraper_keys().items():
        keys.setdefault(name, entry)

    async def probe(cls):
        adapter = cls(scraper_keys=keys)
        try:
            return await adapter.health_check()
        except Exception as e:
            return {"source": cls.source_name, "ok": False, "error": str(e)[:120]}

    results = await asyncio.gather(*(probe(cls) for cls in ALL_ADAPTERS))
    return {"sources": list(results)}


@router.post("/discovery/run")
async def run_discovery(request: Request,
                        passes: int | None = Query(
                            None, ge=1, le=50,
                            description="Adapter-passes to spend this cycle "
                                        "(1-50). Omit for the full budget.")):
    """One orchestrated discovery pass: enabled countries × role terms × adapters.
    Runs in the background; poll GET /api/discovery/status for progress.

    `passes` bounds the sweep so a caller (UI button, CLI, E2E) can run a short
    predictable cycle; without it the full budget is used.
    """
    app = request.app
    # Resume-driven keywords are a precondition: without them discovery would
    # fall back to hardcoded defaults instead of the candidate's own targets.
    await require_resume_for_search(request)
    registry = getattr(app.state, "country_registry", None)
    if not registry or not registry.enabled_countries():
        raise HTTPException(503, "No countries enabled — configure /api/countries first")
    from app.adapters import ALL_ADAPTERS
    # Lazy import on purpose: tests/bounded sweeps monkeypatch
    # app.discovery.run_discovery_cycle, which only works if the router
    # resolves the name at call time instead of binding it at import time.
    from app.discovery import run_discovery_cycle
    from app.run_state import run_slot

    slot = run_slot(request)
    if slot["discovery_running"]:
        return {"status": "already_running", "progress": slot["discovery_progress"]}

    slot["discovery_running"] = True
    slot["discovery_progress"] = {"completed_passes": 0, "new_jobs": 0}
    ws = getattr(request.state, "workspace", None)
    bg_db = ws.db if ws else (getattr(app.state, "bg_db", None) or app.state.db)

    async def _run():
        try:
            keys = await bg_db.get_scraper_keys()
            for name, entry in _env_scraper_keys().items():
                keys.setdefault(name, entry)
            telemetry = await run_discovery_cycle(
                bg_db, registry, ALL_ADAPTERS,
                progress=slot["discovery_progress"],
                max_passes=passes,
                scraper_keys=keys)
            slot["discovery_telemetry"] = telemetry
        except Exception:
            logger.exception("Discovery cycle crashed")
            slot["discovery_telemetry"] = {"error": "crashed — see server log"}
        finally:
            slot["discovery_running"] = False

    asyncio.create_task(_run())
    return {"status": "discovery_started", "passes": passes,
            "countries": [c.code for c in registry.enabled_countries()]}


@router.get("/discovery/status")
async def discovery_status(request: Request):
    from app.run_state import run_slot
    slot = run_slot(request)
    return {
        "running": slot["discovery_running"],
        "progress": slot["discovery_progress"],
        "last_telemetry": slot["discovery_telemetry"],
    }


# ---------------------------------------------------------------------------
# Job hygiene — prune the backlog discovery over-fetched
#
# Basil (2026-10-07): "that 1002 jobs are not worth it even scraping."
# Discovery fans out across roles × countries × sources and over-fetches; the
# eligibility gate then discards most of it, leaving a large dead backlog that
# every later stage still has to read. This is the opt-in, reversible cleanup.
#
# Safety rules, in order of importance:
#   1. NEVER delete. Pruning sets `dismissed = 1`, which every query already
#      respects, so it is reversible per job id.
#   2. NEVER touch a job that was applied to (`applications.job_id`).
#   3. NEVER touch ELIGIBLE (still worth looking at) or REVIEW_REQUIRED
#      (a human still has to decide).
#   4. Dry run by default: nothing is dismissed without `confirm=true`.
# ---------------------------------------------------------------------------


async def _prune_candidates(db, limit: int = 5000) -> list[dict]:
    """Jobs that are safe to dismiss: INELIGIBLE, live, and never applied to."""
    cursor = await db.db.execute(
        """SELECT j.id, j.title, j.company,
                  j.eligibility_gate, j.eligibility_reason
           FROM jobs j
           WHERE j.dismissed = 0
             AND j.eligibility_status = 'INELIGIBLE'
             AND NOT EXISTS (
                 SELECT 1 FROM applications a WHERE a.job_id = j.id)
           ORDER BY j.id
           LIMIT ?""", (limit,))
    return [dict(r) for r in await cursor.fetchall()]


def _prune_summary(rows: list[dict], dry_run: bool) -> dict:
    by_reason: dict[str, int] = {}
    for r in rows:
        key = r.get("eligibility_reason") or r.get("eligibility_gate") or "unknown"
        by_reason[key] = by_reason.get(key, 0) + 1
    return {
        "dry_run": dry_run,
        "would_dismiss" if dry_run else "dismissed": len(rows),
        "by_reason": dict(sorted(by_reason.items(), key=lambda kv: -kv[1])),
        "sample": rows[:25],
        "rule": ("INELIGIBLE + not dismissed + never applied to. ELIGIBLE and "
                 "REVIEW_REQUIRED jobs are never touched, and rows are dismissed "
                 "rather than deleted."),
    }


async def apply_prune(db, limit: int = 5000, confirm: bool = False) -> dict:
    """Dry run unless `confirm=True`.

    Kept as a plain function (not endpoint-only) so the safety behaviour —
    "no confirm means nothing changes" — is directly testable.
    """
    rows = await _prune_candidates(db, limit)
    if not confirm:
        return _prune_summary(rows, dry_run=True)

    ids = [r["id"] for r in rows]
    for job_id in ids:
        await db.db.execute("UPDATE jobs SET dismissed = 1 WHERE id = ?", (job_id,))
    await db.db.commit()
    logger.info("Pruned (dismissed) %d ineligible, unapplied jobs", len(ids))
    summary = _prune_summary(rows, dry_run=False)
    summary["job_ids"] = ids
    summary["note"] = "Flagged dismissed=1, not deleted — reversible per job id."
    return summary


@router.get("/discovery/prune-preview")
async def prune_preview(request: Request, limit: int = 5000):
    """DRY RUN — what a prune WOULD dismiss. Changes nothing."""
    return await apply_prune(_db(request), limit, confirm=False)


@router.post("/discovery/prune")
async def prune(request: Request, limit: int = 5000, confirm: bool = False):
    """Apply the prune. Without `confirm=true` this only previews."""
    return await apply_prune(_db(request), limit, confirm=confirm)
