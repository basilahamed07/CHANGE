import logging

from fastapi import APIRouter, HTTPException, Request

from app.evidence_checker import EvidenceChecker
from app.main import _db  # M15b: per-user workspace DB

router = APIRouter(prefix="/api", tags=["evidence"])
logger = logging.getLogger(__name__)

STATUSES = ("VERIFIED", "UNVERIFIED", "DISPUTED", "DO_NOT_USE")


def _get_store(request: Request):
    store = getattr(request.state, "_evidence_store", None) or getattr(request.app.state, "evidence_store", None)
    if store is None:
        raise HTTPException(503, "Evidence store not loaded (no profile dir?)")
    return store


@router.post("/evidence/backfill")
async def backfill_evidence(request: Request):
    """Populate VERIFIED evidence from data already stored in this workspace
    (resume text + analysed skills + parsed profile). ZERO AI calls.

    Use this when resume generation reports unsupported claims: it turns the
    user's own already-uploaded resume into the verified corpus.
    """
    from app.evidence_backfill import backfill_workspace
    store = _get_store(request)
    result = await backfill_workspace(_db(request), store)
    # Rebuild the request-scoped checker so the new corpus applies immediately.
    if store is not None:
        try:
            request.state._evidence_checker = EvidenceChecker(store.verified_values())
            request.app.state.evidence_checker = EvidenceChecker(store.verified_values())
        except Exception:
            pass
    return {"ok": True, "summary": result,
            "verified_claims": len(store.verified_values()) if store else 0}


@router.get("/evidence")
async def list_evidence(request: Request, status: str | None = None):
    store = _get_store(request)
    claims = store.all_claims()
    if status:
        wanted = status.upper()
        if wanted not in STATUSES:
            raise HTTPException(400, f"status must be one of {STATUSES}")
        claims = [c for c in claims if c.status == wanted]
    return {
        "loaded_at": store.loaded_at,
        "counts": {s: len(store.by_status(s)) for s in STATUSES},
        "claims": [c.to_dict() for c in claims],
    }


@router.post("/evidence/reload")
async def reload_evidence(request: Request):
    """Reload YAML from disk (after Basil edits his profile) + rebuild gate + sync DB."""
    store = _get_store(request)
    count = store.reload()
    request.app.state.evidence_checker = EvidenceChecker(store.verified_values())
    synced = await store.sync_to_db(_db(request))
    return {
        "ok": True,
        "claims": count,
        "synced": synced,
        "verified": len(store.verified_values()),
    }


@router.post("/evidence/check")
async def check_text(request: Request):
    """Run the hard gate against arbitrary text (used by UI review + tests)."""
    store = _get_store(request)
    checker = getattr(request.state, "_evidence_checker", None) or getattr(request.app.state, "evidence_checker", None)
    if checker is None:
        raise HTTPException(503, "EvidenceChecker not initialized")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "JSON body required")
    text = str(body.get("text", ""))
    if not text.strip():
        raise HTTPException(400, "text is required")
    result = checker.check(text, candidate_skill_values=store.skill_values_all_statuses())
    return result.to_dict()
