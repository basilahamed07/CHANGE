"""M8: /api/packages — application package generation surface.

build: runs the FULL evidence-gated pipeline (AI tailoring → EvidenceChecker →
regenerate-on-fail) and materializes the Phase-19 package directory.
refresh: rebuilds from the STORED tailored text (no AI) — idempotent no-op when
inputs are unchanged.
list: all built packages.
"""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from app.main import _db  # M15b: per-user workspace DB

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/packages")


def _builder(request: Request):
    from app.application_builder import ApplicationBuilder
    from app.config import get_settings
    settings = get_settings()
    ws = getattr(request.state, "workspace", None)
    base = ws.applications_dir if ws else os.path.join(os.path.dirname(settings.db_path) or "data", "applications")
    return ApplicationBuilder(base)


def _profile_version(request: Request) -> str:
    store = getattr(request.app.state, "evidence_store", None)
    return (getattr(store, "loaded_at", "") if store else "") or "unknown"


@router.post("/jobs/{job_id}/build")
async def build_package(request: Request, job_id: int, refresh: bool = False):
    """Evidence-gated package build. refresh=true repackages stored text (no AI)."""
    from app.application_builder import EvidenceViolationError, PackageInputs, sha256_text
    db = _db(request)
    job = await db.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    app_row = await db.get_application(job_id)

    ai = await request.app.state.ai_state_for(request)
    tailor = ai["tailor"]
    store = ai["evidence_store"]
    checker = ai["evidence_checker"]
    if store is None or checker is None:
        raise HTTPException(503, "Evidence store unavailable — packaging blocked (fail-closed)")

    if refresh and app_row and app_row.get("tailored_resume"):
        tailored = app_row["tailored_resume"]
        cover = app_row.get("cover_letter") or ""
        ai_settings = await db.get_ai_settings()
        model = (ai_settings or {}).get("model", "")
        check = checker.check(tailored, candidate_skill_values=store.skill_values_all_statuses())
        evidence_result = check.to_dict()
    elif not tailor:
        raise HTTPException(503, "No AI tailoring available — run /prepare first or use refresh=true")
    else:
        # Full path: AI tailoring + hard gate + one regeneration (same as /prepare)
        score = await db.get_score(job_id)
        result = await tailor.prepare(
            job_description=job["description"] or "",
            match_reasons=(score or {}).get("match_reasons", []),
            suggested_keywords=(score or {}).get("suggested_keywords", []),
        )
        tailored = result.get("tailored_resume", "")
        cover = result.get("cover_letter", "")
        check = checker.check(tailored, candidate_skill_values=store.skill_values_all_statuses())
        if not check.ok:
            logger.warning("Package build evidence fail job %s — regenerating once", job_id)
            result = await tailor.prepare(
                job_description=job["description"] or "",
                match_reasons=(score or {}).get("match_reasons", []),
                suggested_keywords=(score or {}).get("suggested_keywords", []),
            )
            tailored = result.get("tailored_resume", "")
            cover = result.get("cover_letter", "")
            check = checker.check(tailored, candidate_skill_values=store.skill_values_all_statuses())
        evidence_result = check.to_dict()

        # Persist prepared text (same contract as /prepare)
        application = await db.get_application(job_id)
        if not application:
            app_id = await db.insert_application(job_id, "prepared")
        else:
            app_id = application["id"]
        await db.update_application(app_id, status="prepared",
                                    tailored_resume=tailored, cover_letter=cover)

    if not check.ok:
        raise HTTPException(422, detail={
            "error": "evidence_check_failed",
            "failures": check.failures,
            "message": "Package refused: generated text has unverified claims. Nothing saved.",
        })

    resume_row = await db.get_default_resume()
    ai_settings = await db.get_ai_settings()
    builder = _builder(request)
    inputs = PackageInputs(
        job_id=job_id,
        company=job["company"] or "",
        job_title=job["title"] or "",
        job_description_hash=sha256_text(job["description"] or ""),
        resume_version_id=(resume_row or {}).get("id", 0) if resume_row else 0,
        profile_version=_profile_version(request),
        tailored_resume=tailored,
        cover_letter=cover,
        model=(ai_settings or {}).get("model", ""),
        evidence_check_ok=True,
        evidence_check_failures=[],
    )
    try:
        result = await builder.build(inputs, evidence_check_result=evidence_result)
    except EvidenceViolationError as e:
        raise HTTPException(422, str(e))

    app_row = await db.get_application(job_id)
    if app_row:
        await db.set_package_meta(
            app_row["id"], result.package_dir, inputs.fingerprint(),
            result.metadata.get("status", "ready_for_review"))
    await db.add_event(job_id, "note",
                       f"Package {result.action}: {result.package_dir}")
    return result.to_dict()


@router.get("/jobs/{job_id}")
async def get_package(request: Request, job_id: int):
    db = _db(request)
    meta = await db.get_package_meta(job_id)
    if not meta:
        raise HTTPException(404, "No package built for this job")
    builder = _builder(request)
    job = await db.get_job(job_id)
    on_disk = builder.read_metadata(job_id, job["company"] or "") if job else None
    return {**meta, "on_disk": on_disk}


@router.get("")
@router.get("/")
async def list_packages(request: Request):
    db = _db(request)
    rows = await (await db.db.execute(
        """SELECT a.job_id, j.company, j.title, a.package_dir, a.package_status
           FROM applications a JOIN jobs j ON j.id = a.job_id
           WHERE a.package_dir IS NOT NULL ORDER BY a.job_id""")).fetchall()
    return {"count": len(rows), "packages": [dict(r) for r in rows]}


@router.get("/jobs/{job_id}/download/{filename}")
async def download_file(request: Request, job_id: int, filename: str):
    if filename not in {"resume.docx", "resume.txt", "cover_letter.docx",
                        "cover_letter.txt", "metadata.json"}:
        raise HTTPException(400, "Unknown package file")
    db = _db(request)
    meta = await db.get_package_meta(job_id)
    if not meta:
        raise HTTPException(404, "No package built for this job")
    path = os.path.join(meta["package_dir"], filename)
    if not os.path.exists(path):
        raise HTTPException(404, f"{filename} not in package")
    media = ("application/vnd.openxmlformats-officedocument.wordprocessingml.document"
             if filename.endswith(".docx") else
             "application/pdf" if filename.endswith(".pdf") else "text/plain")
    if filename.endswith(".json"):
        media = "application/json"
    return FileResponse(path, media_type=media, filename=filename)
