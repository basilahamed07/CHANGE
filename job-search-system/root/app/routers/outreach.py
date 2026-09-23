"""M9: /api/outreach — audience-specific outreach + Gmail DRAFTS (never send).

Safety model:
- create → returns a DRAFT (Gmail draft when a token is configured, otherwise a
  local draft). Identical repeat calls return the SAME message (Critical Test #4).
- There is no send endpoint here. Sending is an M10+ approval-flow concern and
  additionally gated by JOBAGENT_ALLOW_SEND.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from app.main import _db  # M15b: per-user workspace DB

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/outreach")


def _service(request: Request):
    from app.outreach import GmailProvider, OutreachService, load_sequences
    ws = getattr(request.state, "workspace", None)
    settings_dir = ws.dir if ws else (request.app.state.db_path.rsplit("/", 1)[0] if "/" in getattr(
        request.app.state, "db_path", "") else ".")
    sequences, limits, identity = load_sequences()
    gmail = GmailProvider()
    return OutreachService(_db(request), sequences, limits, identity, gmail)


@router.post("/jobs/{job_id}/create")
async def create_outreach(request: Request, job_id: int):
    """Create (or return the existing) outreach draft for a job.

    Body (all optional): {audience, contact_email, contact_name}
    Audience defaults deterministically from the contact on file.
    """
    body = await request.json()
    audience = body.get("audience")
    if audience is not None and audience not in (
            "recruiter", "hiring_manager", "referral", "followup"):
        raise HTTPException(422, f"unknown audience: {audience}")
    service = _service(request)
    try:
        result = await service.create_outreach(
            job_id,
            audience=audience,
            contact_email=body.get("contact_email", ""),
            contact_name=body.get("contact_name", ""),
        )
    except ValueError as e:
        raise HTTPException(404, str(e))
    code = {"created": 200, "already_exists": 200,
            "capped": 429}.get(result["status"], 200)
    return result


@router.post("/jobs/{job_id}/followup")
async def create_followup(request: Request, job_id: int):
    """Follow-up draft — allowed only after the configured wait (default 6 days)."""
    service = _service(request)
    try:
        return await service.create_followup(job_id)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/jobs/{job_id}")
async def job_outreach(request: Request, job_id: int):
    rows = await _db(request).list_outreach(500)
    return {"count": len([r for r in rows if r["job_id"] == job_id]),
            "messages": [r for r in rows if r["job_id"] == job_id]}


@router.get("/messages")
async def all_messages(request: Request, limit: int = 100):
    return {"count": 0, "messages": await _service(request).list_messages(min(limit, 500))}


@router.get("/config")
async def outreach_config(request: Request):
    from app.outreach import load_sequences
    sequences, limits, identity = load_sequences()
    return {
        "audiences": list(sequences.keys()),
        "limits": {"max_outreach_per_day": limits.max_outreach_per_day,
                   "per_company_daily_cap": limits.per_company_daily_cap,
                   "followup_wait_days": limits.followup_wait_days},
        "identity": {"sender_name": identity.sender_name},
        "gmail_connected": bool(request.app.state and
                                __import__("os").getenv("JOBAGENT_GMAIL_TOKEN", "")),
    }
