"""M3: /api/countries — view and tune the country strategy (config/countries/*.yaml).

The YAML files remain the source of truth. The API exposes the registry and
allows toggling enabled/disabled + work types (writes back to the YAML file,
versioned backup kept in countries_dir/.backups/).
"""

from __future__ import annotations

import logging
import shutil
import time
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


def _registry(request: Request):
    reg = getattr(request.app.state, "country_registry", None)
    if reg is None:
        raise HTTPException(503, "Country registry not loaded (countries_dir missing?)")
    return reg


@router.get("/countries")
async def list_countries(request: Request):
    return _registry(request).summary()


@router.get("/countries/{region}")
async def get_country(request: Request, region: str):
    reg = _registry(request)
    c = reg.get(region)
    if not c:
        raise HTTPException(404, f"Country '{region}' not found. "
                                 f"Loaded: {reg.region_names()}")
    return {"country": c.to_dict()}


@router.put("/countries/{region}")
async def update_country(request: Request, region: str):
    """Update a country's enabled flag / work types (persisted to its YAML)."""
    reg = _registry(request)
    c = reg.get(region)
    if not c:
        raise HTTPException(404, f"Country '{region}' not found")
    body = await request.json()

    data = yaml.safe_load(c.source.read_text()) or {}
    if "enabled" in body:
        data["enabled"] = bool(body["enabled"])
    for key in ("remote", "hybrid", "onsite"):
        if key in body:
            data.setdefault("work_types", {})[key] = bool(body[key])
    if "salary_min" in body:
        data.setdefault("salary", {})["min"] = int(body["salary_min"])

    # Persist: backup then write.
    backup_dir = c.source.parent / ".backups"
    backup_dir.mkdir(exist_ok=True)
    shutil.copy2(c.source, backup_dir / f"{c.source.stem}.{int(time.time())}.yaml")
    c.source.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))

    reg.load()  # reload so in-memory strategy reflects the file immediately
    return {"ok": True, "country": reg.get(region).to_dict()}


@router.post("/countries/{region}/visa-check")
async def visa_check(request: Request, region: str):
    """Deterministic visa/sponsorship scan of {text} against the country's
    keyword list (no AI). Shows which sponsorship signals a job description
    contains — used by the UI and by M5 eligibility later."""
    c = _registry(request).get(region)
    if not c:
        raise HTTPException(404, f"Country '{region}' not found")
    body = await request.json()
    from app.visa_engine import scan_visa_mentions
    result = scan_visa_mentions(body.get("text", ""), c.sponsorship_keywords)
    return {"region": region, "requires_sponsorship": c.requires_sponsorship,
            **result}


@router.post("/countries/apply")
async def apply_strategy(request: Request):
    """Apply the country strategy to the EXISTING job pool: classify any
    unclassified jobs (rule-based), sync allowed_regions to enabled countries
    + Remote, and dismiss jobs outside the enabled countries. Jobs with active
    applications are never touched. This is the button after tuning countries."""
    reg = _registry(request)
    from app.scheduler import apply_country_strategy
    try:
        stats = await apply_country_strategy(request.app.state.db, reg)
    except Exception as e:
        raise HTTPException(500, f"Strategy apply failed: {e}")
    return {"ok": True, **stats}


@router.post("/countries/reload")
async def reload_countries(request: Request):
    """Re-read every YAML — also the hook after dropping a NEW country file in."""
    try:
        reg = _registry(request)
        reg.load()
        # Keep the classifier's rule-based terms in sync with the new YAML set.
        request.app.state.location_classifier_terms = reg.classification_terms()
    except Exception as e:
        raise HTTPException(422, f"Reload failed: {e}")
    return {"ok": True, "count": reg.summary()["count"],
            "enabled": reg.summary()["enabled"]}
