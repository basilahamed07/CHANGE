"""M9: /api/outreach — audience-specific outreach + Gmail DRAFTS (never send).

Safety model:
- create → returns a DRAFT (Gmail draft when a token is configured, otherwise a
  local draft). Identical repeat calls return the SAME message (Critical Test #4).
- There is no send endpoint here. Sending is an M10+ approval-flow concern and
  additionally gated by JOBAGENT_ALLOW_SEND.
"""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, HTTPException, Request
from app.main import _db  # M15b: per-user workspace DB

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/outreach")


async def _gmail_credential(request: Request) -> tuple[str, str]:
    """The Gmail (token, source) belonging to the REQUESTING user — N1.

    The token lives in this user's own workspace `email_settings` row, so two
    users' drafts land in two different mailboxes. The process env
    `JOBAGENT_GMAIL_TOKEN` is only the legacy single-user fallback, and the raw
    token never leaves this function.
    """
    try:
        settings = await _db(request).get_email_settings()
    except Exception:
        logger.exception("per-user email settings unreadable — falling back to env")
        settings = None
    token = str((settings or {}).get("gmail_token") or "").strip()
    if token:
        return token, "workspace"
    token = os.getenv("JOBAGENT_GMAIL_TOKEN", "").strip()
    return token, ("env" if token else "")


async def _service(request: Request):
    from app.outreach import GmailProvider, OutreachService, load_sequences
    token, _source = await _gmail_credential(request)
    sequences, limits, identity = load_sequences()
    gmail = GmailProvider(token=token)
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
    service = await _service(request)
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
    service = await _service(request)
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
    return {"count": 0, "messages": await (await _service(request)).list_messages(min(limit, 500))}


@router.get("/config")
async def outreach_config(request: Request):
    from app.outreach import load_sequences
    sequences, limits, identity = load_sequences()
    token, source = await _gmail_credential(request)
    return {
        "audiences": list(sequences.keys()),
        "limits": {"max_outreach_per_day": limits.max_outreach_per_day,
                   "per_company_daily_cap": limits.per_company_daily_cap,
                   "followup_wait_days": limits.followup_wait_days},
        "identity": {"sender_name": identity.sender_name},
        # N1: this user's connection, not the process-wide one. The token itself
        # is never included — only whether one exists and where it came from.
        "gmail_connected": bool(token),
        "gmail_source": source,
    }
