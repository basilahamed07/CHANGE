"""M5: /api/eligibility — deterministic eligibility gate surface."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException, Request
from app.main import _db  # M15b: per-user workspace DB

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


async def _engine(request: Request):
    """Build the engine from live config (allowed regions + country codes)."""
    from app.eligibility import build_eligibility_engine
    db = _db(request)
    registry = getattr(request.app.state, "country_registry", None)
    return await build_eligibility_engine(db, registry, max_age_days=7)


@router.post("/jobs/{job_id}/eligibility")
async def check_job_eligibility(request: Request, job_id: int):
    """Run the deterministic eligibility gate on one job — full gate chain."""
    db = _db(request)
    job = await db.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    engine = await _engine(request)
    application = await db.get_application(job_id)
    result = engine.check(job, application=application)
    return {
        "job_id": job_id,
        "eligible": result.eligible,
        "status": result.status,
        "gate": result.gate,
        "reason": result.reason,
        "reasons": result.reasons,
        "primary_reason": result.primary_reason,
        "evidence": result.evidence,
        "details": result.details,
    }


@router.get("/eligibility/review-jobs")
async def list_review_jobs(request: Request, limit: int = 100):
    """Jobs the gate chain routed to human review (never auto-scored)."""
    limit = max(1, min(limit, 500))
    jobs = await _db(request).get_eligibility_review_jobs(limit=limit)
    return {"count": len(jobs), "jobs": jobs}


@router.get("/eligibility/metrics")
async def eligibility_metrics(request: Request):
    """Persisted Stage-3 metrics + live status/reason tallies (task §28)."""
    db = _db(request)
    stored = None
    cursor = await db.db.execute(
        "SELECT eligibility_metrics FROM search_config WHERE id = 1")
    row = await cursor.fetchone()
    if row and row[0]:
        try:
            stored = json.loads(row[0])
        except (ValueError, TypeError):
            stored = None
    return {"last_run": stored, "live": await db.get_eligibility_stats()}


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
