"""M7: /api/research — company + contact research surface.

Contact research: cache-first with provider fallback chain
(manual → hunter → apollo → web_search). Company research: cached rich fields.
All classification/confidence logic is deterministic (no LLM).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/research")


# ---------------------------------------------------------------- contacts

@router.post("/contacts/job/{job_id}")
async def research_contacts(request: Request, job_id: int, force: bool = False):
    """Research contacts for a job (cache-first, provider fallback chain)."""
    from app.contact_providers import ContactResearchService, default_provider_chain
    db = request.app.state.db
    job = await db.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    service = ContactResearchService(db, default_provider_chain(db))
    result = await service.research(job, force=force)
    return result


@router.get("/contacts/job/{job_id}")
async def get_contact_research(request: Request, job_id: int):
    db = request.app.state.db
    cached = await db.get_contact_research(job_id)
    if not cached:
        raise HTTPException(404, "No contact research for this job yet")
    return cached


@router.post("/contacts/job/{job_id}/select")
async def select_contact(request: Request, job_id: int):
    """Pick one researched candidate (body: {index}) → job + contacts table."""
    from app.contact_providers import ContactResearchService, default_provider_chain
    db = request.app.state.db
    job = await db.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    body = await request.json()
    index = body.get("index")
    if not isinstance(index, int):
        raise HTTPException(422, "body must be {\"index\": <int>}")
    service = ContactResearchService(db, default_provider_chain(db))
    try:
        return await service.select_candidate(job, index)
    except ValueError as e:
        raise HTTPException(404, str(e))
    except IndexError as e:
        raise HTTPException(422, str(e))


@router.get("/providers")
async def provider_status(request: Request):
    """Which contact providers are configured/available right now."""
    from app.contact_providers import (
        ApolloProvider, HunterProvider, ManualResearchProvider, WebSearchProvider)
    db = request.app.state.db
    providers = [ManualResearchProvider(db), HunterProvider(),
                 ApolloProvider(), WebSearchProvider()]
    return {"providers": [
        {"name": p.name, "available": bool(p.available)} for p in providers]}


# ---------------------------------------------------------------- companies

@router.post("/company/{company_name}")
async def research_company(request: Request, company_name: str,
                           website: str = "", force: bool = False):
    """Rich company research, cache-first (30-day TTL)."""
    from app.company_enrichment import COMPANY_CACHE_TTL_DAYS, company_cache_fresh, enrich_company
    db = request.app.state.db
    if not company_name.strip():
        raise HTTPException(400, "company name required")
    cached = await db.get_company(company_name)
    if cached and not force and cached.get("researched_at") and company_cache_fresh(cached):
        return {**cached, "cache_hit": True}
    info = await enrich_company(company_name, website_hint=website)
    fields = {}
    for key in ("website", "description", "careers_url", "linkedin_url", "research_status"):
        if info.get(key):
            fields[key] = info[key]
    if info.get("ai_clues"):
        import json as _json
        fields["ai_clues"] = _json.dumps(info["ai_clues"])
    from datetime import datetime, timezone
    fields["researched_at"] = datetime.now(timezone.utc).isoformat()
    if info.get("glassdoor_rating"):
        fields["glassdoor_rating"] = info["glassdoor_rating"]
    await db.save_company(company_name, **fields)
    saved = await db.get_company(company_name) or fields
    return {**saved, "cache_hit": False, "ttl_days": COMPANY_CACHE_TTL_DAYS}


@router.get("/company/{company_name}")
async def get_company_cache(request: Request, company_name: str):
    from app.company_enrichment import company_cache_fresh
    db = request.app.state.db
    cached = await db.get_company(company_name)
    if not cached:
        raise HTTPException(404, "No cached research for this company")
    return {**cached, "cache_fresh": company_cache_fresh(cached)}
