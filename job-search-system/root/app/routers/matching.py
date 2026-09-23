"""M6: /api/matching — hybrid matching engine surface.

All endpoints are deterministic (zero LLM cost). The hybrid engine provides the
free baseline scoring layer; the AI scorer (when quota allows) refines on top.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from app.main import _db  # M15b: per-user workspace DB

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/matching")


@router.get("/status")
async def matching_status(request: Request):
    """Engine status: profile sizes, weights, provider, preferences."""
    from app.matching_service import build_hybrid_matcher_async
    db = _db(request)
    matcher, meta = await build_hybrid_matcher_async(request.app.state, db)
    prefs = await db.get_hybrid_prefs()
    scored_rows = await db.db.execute(
        """SELECT COUNT(*) FROM job_scores WHERE component_scores IS NOT NULL""")
    n_hybrid = (await scored_rows.fetchone())[0]
    return {"engine": "hybrid-m6", **meta, "prefs": prefs,
            "hybrid_scored_jobs": n_hybrid}


@router.post("/jobs/{job_id}/score")
async def score_one(request: Request, job_id: int, persist: bool = True):
    """Score a single job with the hybrid engine. Deterministic, instant, free."""
    from app.matching_service import build_hybrid_matcher_async
    db = _db(request)
    job = await db.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    matcher, meta = await build_hybrid_matcher_async(request.app.state, db)
    result = matcher.score_job(job)
    if persist:
        d = result.to_db_dict()
        await db.upsert_hybrid_score(
            job_id, d["match_score"], d["match_reasons"], d["concerns"],
            d["suggested_keywords"], d["role_match"],
            d["component_scores"], d["hard_blockers"])
    return {
        "job_id": job_id,
        "overall_score": result.overall_score,
        "component_scores": result.component_scores,
        "matched_requirements": result.matched_requirements,
        "missing_requirements": result.missing_requirements,
        "hard_blockers": result.hard_blockers,
        "advantages": result.advantages,
        "explanation": result.explanation,
        "profile_meta": meta,
    }


@router.post("/score-all")
async def score_all(request: Request):
    """Run the hybrid engine over every unscored, classified, alive job.

    Free + fast (no AI). Safe to run any time; skips already-scored jobs.
    """
    from app.matching_service import score_all_unscored
    ai = await request.app.state.ai_state_for(request)
    fake_state = type("_PerUserAIState", (), {})()
    fake_state.matcher = ai["matcher"]
    result = await score_all_unscored(fake_state, _db(request))
    return result


@router.get("/jobs/{job_id}/explain")
async def explain(request: Request, job_id: int):
    """Human-readable breakdown of the stored hybrid score for a job."""
    db = _db(request)
    score = await db.get_score(job_id)
    if not score:
        raise HTTPException(404, "No score for this job yet — POST /api/matching/jobs/{id}/score first")
    components = score.get("component_scores") or {}
    if not components:
        raise HTTPException(404, "Job has no hybrid component breakdown (scored by AI only)")
    return {
        "job_id": job_id,
        "overall_score": score.get("match_score"),
        "component_scores": components,
        "hard_blockers": score.get("hard_blockers") or [],
        "matched": score.get("match_reasons") or [],
        "missing": score.get("concerns") or [],
        "advantages": score.get("suggested_keywords") or [],
    }


@router.get("/config")
async def get_config(request: Request):
    db = _db(request)
    return {"weights": await db.get_hybrid_weights(),
            "prefs": await db.get_hybrid_prefs()}


@router.put("/config")
async def put_config(request: Request):
    """Update weights/prefs. Body: {weights?, prefers_remote?, requires_sponsorship?}"""
    from app.hybrid_matcher import _validated_weights
    db = _db(request)
    body = await request.json()
    weights = body.get("weights")
    if weights is not None:
        if not isinstance(weights, dict):
            raise HTTPException(422, "weights must be an object")
        await db.save_hybrid_weights(_validated_weights(weights))
    pr = body.get("prefers_remote")
    rs = body.get("requires_sponsorship")
    if pr is not None or rs is not None:
        cur = await db.get_hybrid_prefs()
        await db.save_hybrid_prefs(
            bool(pr) if pr is not None else cur["prefers_remote"],
            bool(rs) if rs is not None else cur["requires_sponsorship"])
    return {"ok": True, "weights": await db.get_hybrid_weights(),
            "prefs": await db.get_hybrid_prefs()}


@router.get("/top-jobs")
async def top_jobs(request: Request, limit: int = 10, min_score: int = 60):
    """Highest-scoring eligible jobs with component breakdowns."""
    limit = max(1, min(limit, 100))
    db = _db(request)
    cur = await db.db.execute(
        """SELECT j.id, j.title, j.company, j.location, j.url,
                  js.match_score, js.component_scores, js.hard_blockers
           FROM jobs j JOIN job_scores js ON js.job_id = j.id
           WHERE j.dismissed = 0 AND js.match_score >= ?
           ORDER BY js.match_score DESC LIMIT ?""",
        (min_score, limit))
    rows = await cur.fetchall()
    import json as _json
    out = []
    for r in rows:
        d = dict(r)
        for k in ("component_scores", "hard_blockers"):
            raw = d.get(k)
            if isinstance(raw, str) and raw:
                try:
                    d[k] = _json.loads(raw)
                except (ValueError, TypeError):
                    d[k] = {} if k == "component_scores" else []
        out.append(d)
    return {"count": len(out), "jobs": out}
