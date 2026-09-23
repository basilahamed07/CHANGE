"""M5: /api/eligibility — deterministic eligibility gate surface."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException, Request
from app.main import _db  # M15b: per-user workspace DB

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


async def _engine(request: Request):
    """Build the engine from live config (allowed regions from search_config)."""
    from app.eligibility import EligibilityEngine
    db = _db(request)
    allowed = await db.get_allowed_regions()
    registry = getattr(request.app.state, "country_registry", None)
    floors = {}
    if registry:
        for c in registry.enabled_countries():
            if c.salary_min:
                floors[c.region] = c.salary_min
    return EligibilityEngine(allowed_regions=allowed,
                             max_age_days=7,
                             min_salary_by_region=floors)


@router.post("/jobs/{job_id}/eligibility")
async def check_job_eligibility(request: Request, job_id: int):
    """Run the deterministic eligibility gate on one job — full reason codes."""
    db = _db(request)
    job = await db.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    engine = await _engine(request)
    result = engine.check(job)
    return {
        "job_id": job_id,
        "eligible": result.eligible,
        "reasons": result.reasons,
        "primary_reason": result.primary_reason,
        "details": result.details,
    }


@router.get("/eligibility/eligible-jobs")
async def list_eligible_jobs(request: Request, limit: int = 100):
    """Jobs currently eligible for the pipeline (fresh, in-region, complete)."""
    limit = max(1, min(limit, 500))
    jobs = await _db(request).get_eligible_jobs(limit=limit)
    return {"count": len(jobs), "jobs": jobs}


@router.get("/jobs/{job_id}/freshness")
async def job_freshness(request: Request, job_id: int):
    """Freshness evidence for a job (recorded at ingest + refreshable)."""
    from app.freshness import assess_freshness
    db = _db(request)
    job = await db.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    stored = None
    if job.get("freshness_evidence"):
        try:
            stored = json.loads(job["freshness_evidence"])
        except (ValueError, TypeError):
            stored = None
    return {"job_id": job_id, "stored": stored,
            "recomputed": assess_freshness(job.get("posted_date"))}
