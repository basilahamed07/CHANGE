"""M4: /api/discovery — orchestrated multi-country discovery + source health."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Query, Request
from app.main import _db  # M15b: per-user workspace DB

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


@router.get("/discovery/adapters")
async def list_adapters(request: Request):
    from app.adapters import ALL_ADAPTERS
    return {"adapters": [a.source_name for a in ALL_ADAPTERS]}


@router.get("/discovery/health")
async def discovery_health(request: Request):
    """Per-source reachability probe (cheap, parallel)."""
    from app.adapters import ALL_ADAPTERS
    keys = await _db(request).get_scraper_keys()

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
                            None, ge=1, le=24,
                            description="Adapter-passes to spend this cycle "
                                        "(1-24). Omit for the full budget.")):
    """One orchestrated discovery pass: enabled countries × search terms × adapters.
    Runs in the background; poll GET /api/discovery/status for progress.

    `passes` bounds the sweep so a caller (UI button, CLI, E2E) can run a short
    predictable cycle; without it the 24-pass budget is used in full.
    """
    app = request.app
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
            telemetry = await run_discovery_cycle(
                bg_db, registry, ALL_ADAPTERS,
                progress=app.state.discovery_progress,
                max_passes=passes)
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
