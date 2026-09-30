"""M4: /api/discovery — orchestrated multi-country discovery + source health."""

from __future__ import annotations

import asyncio
import logging
import os

from fastapi import APIRouter, HTTPException, Query, Request
from app.main import _db  # M15b: per-user workspace DB
from app.search_gate import require_resume_for_search


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
    return env_keys

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


@router.get("/discovery/adapters")
async def list_adapters(request: Request):
    from app.adapters import ALL_ADAPTERS
    return {"adapters": [a.source_name for a in ALL_ADAPTERS]}


@router.get("/discovery/registry")
async def source_registry_view(request: Request):
    """Central source registry (Stage-1 upgrade): every source's type, tier,
    country relevance, access mode + per-country coverage buckets.

    Read-only report data for UI/analytics — the DISCOVER engine reads the
    same registry directly (app/source_registry.py).
    """
    from app import source_registry as sr
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
    """One orchestrated discovery pass: enabled countries × search terms × adapters.
    Runs in the background; poll GET /api/discovery/status for progress.

    `passes` bounds the sweep so a caller (UI button, CLI, E2E) can run a short
    predictable cycle; without it the 24-pass budget is used in full.
    """
    app = request.app
    # Resume-driven keywords are a precondition: without them discovery would
    # fall back to hardcoded defaults instead of the candidate's own targets.
    await require_resume_for_search(request)
    registry = getattr(app.state, "country_registry", None)
    if not registry or not registry.enabled_countries():
        raise HTTPException(503, "No countries enabled — configure /api/countries first")
    if getattr(app.state, "discovery_running", False):
        return {"status": "already_running",
                "progress": getattr(app.state, "discovery_progress", {})}

    from app.adapters import ALL_ADAPTERS
    from app.discovery import run_discovery_cycle

    app.state.discovery_running = True
    app.state.discovery_progress = {"completed_passes": 0, "new_jobs": 0}
    ws = getattr(request.state, "workspace", None)
    bg_db = ws.db if ws else (getattr(app.state, "bg_db", None) or app.state.db)

    async def _run():
        try:
            keys = await bg_db.get_scraper_keys()
            for name, entry in _env_scraper_keys().items():
                keys.setdefault(name, entry)
            telemetry = await run_discovery_cycle(
                bg_db, registry, ALL_ADAPTERS,
                progress=app.state.discovery_progress,
                max_passes=passes,
                scraper_keys=keys)
            app.state.discovery_telemetry = telemetry
        except Exception:
            logger.exception("Discovery cycle crashed")
            app.state.discovery_telemetry = {"error": "crashed — see server log"}
        finally:
            app.state.discovery_running = False

    asyncio.create_task(_run())
    return {"status": "discovery_started", "passes": passes,
            "countries": [c.code for c in registry.enabled_countries()]}


@router.get("/discovery/status")
async def discovery_status(request: Request):
    return {
        "running": getattr(request.app.state, "discovery_running", False),
        "progress": getattr(request.app.state, "discovery_progress", {}),
        "last_telemetry": getattr(request.app.state, "discovery_telemetry", None),
    }
