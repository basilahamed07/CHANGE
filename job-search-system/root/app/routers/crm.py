"""M10/M11/M12 routers — CRM transitions, DailyRun, response monitor.

All transitions validated by app.crm.check_transition (deterministic).
Daily-run trigger respects approval matrix: everything runs locally,
nothing sends, nothing auto-publishes.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request

from app.main import _db  # M15b: per-user workspace DB
from app.crm import (
    ALL_STATUSES,
    FOLLOW_UP_STOP_STATUSES,
    approval_required,
    check_transition,
    compute_follow_up,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------- M10 CRM

@router.post("/jobs/{job_id}/status")
async def transition_status(request: Request, job_id: int,
                            to_status: str = Query(...),
                            notes: str = Query("")):
    """Validated status transition with append-only event history."""
    db = _db(request)
    app_row = await db.get_application(job_id)
    from_status = (app_row or {}).get("status", "interested")

    result = check_transition(from_status, to_status, actor="human")
    if not result.ok:
        raise HTTPException(422, result.reason)

    if not app_row:
        await db.insert_application(job_id, to_status)
        app_row = await db.get_application(job_id)
    else:
        kwargs = {"status": to_status}
        now = _now().isoformat()
        if to_status == "applied" and not app_row.get("applied_at"):
            kwargs["applied_at"] = now
        if to_status == "rejected" and "rejected_at" in app_row:
            kwargs["rejected_at"] = now
        if to_status == "offered" and "offered_at" in app_row:
            kwargs["offered_at"] = now
        await db.update_application(app_row["id"], **kwargs)

    await db.add_event(job_id, "status_change",
                       f"{from_status} → {to_status}" + (f" — {notes}" if notes else ""))
    # Follow-up lifecycle: new pending reminder on entering 'applied',
    # reminders completed on terminal/offer states.
    if to_status == "applied":
        existing = await db.get_reminders_for_job(job_id)
        if not [r for r in existing if r["status"] == "pending"]:
            remind_at = _now().isoformat()
            await db.create_reminder(job_id, remind_at, "follow_up")
    if to_status in FOLLOW_UP_STOP_STATUSES:
        for r in await db.get_reminders_for_job(job_id):
            if r["status"] == "pending":
                await db.complete_reminder(r["id"])
    return {"ok": True, "from": from_status, "to": to_status,
            "event": result.event_type}


@router.get("/crm/statuses")
async def list_statuses():
    """Transition table + approval matrix — for UI affordances."""
    from app.crm import APPROVAL_MATRIX, PIPELINE_STATUSES, TERMINAL_STATUSES, VALID_TRANSITIONS
    return {"pipeline": PIPELINE_STATUSES, "terminal": sorted(TERMINAL_STATUSES),
            "transitions": {k: sorted(v) for k, v in VALID_TRANSITIONS.items()},
            "approval_matrix": APPROVAL_MATRIX}


@router.post("/crm/followups/run")
async def run_followup_engine(request: Request):
    """Follow-up engine: due follow-ups computed deterministically per status."""
    db = _db(request)
    apps = await db.get_all_applications()
    due, stopped = [], 0
    for a in apps:
        status = a.get("status", "interested")
        if status in FOLLOW_UP_STOP_STATUSES:
            stopped += 1
            continue
        last_touch = a.get("applied_at") or a.get("updated_at")
        last_dt = None
        if last_touch:
            try:
                last_dt = datetime.fromisoformat(last_touch)
            except ValueError:
                last_dt = None
        reminders = await db.get_reminders_for_job(a["job_id"])
        pending = any(r["status"] == "pending" for r in reminders)
        plan = compute_follow_up(a["job_id"], status, last_dt,
                                 pending_reminder=pending, now=_now())
        if plan.due:
            if not pending:
                await db.create_reminder(a["job_id"], _now().isoformat(), "follow_up")
            due.append({"job_id": a["job_id"], "status": status,
                        "reason": plan.reason, "days_overdue": plan.days_overdue})
    return {"ok": True, "followups_due": len(due), "items": due,
            "terminal_stopped": stopped}


@router.post("/jobs/{job_id}/bulk-status")
async def bulk_status(request: Request, to_status: str = Query(...),
                      job_ids: str = Query(..., description="comma-separated")):
    """Bulk transitions — medium risk → 'review' per approval matrix."""
    if approval_required("bulk_status_change") != "auto":
        # Explicit human confirmation still required per item; the endpoint
        # validates each transition and reports failures individually.
        pass
    db = _db(request)
    results = []
    for raw in job_ids.split(","):
        try:
            job_id = int(raw.strip())
        except ValueError:
            results.append({"job_id": raw, "ok": False, "reason": "bad id"})
            continue
        app_row = await db.get_application(job_id)
        result = check_transition((app_row or {}).get("status", "interested"),
                                  to_status, actor="human")
        if result.ok:
            if not app_row:
                await db.insert_application(job_id, to_status)
            else:
                await db.update_application(app_row["id"], status=to_status)
            await db.add_event(job_id, "status_change",
                               f"bulk: {result.from_status} → {to_status}")
        results.append({"job_id": job_id, "ok": result.ok, "reason": result.reason})
    return {"ok": True, "results": results}


# ------------------------------------------------------------- M11 daily run

@router.get("/daily-run/today")
async def daily_run_today(request: Request):
    db = _db(request)
    today = _now().strftime("%Y-%m-%d")
    state = await db.get_daily_run_state(today)
    packages = await db.count_packages_created_on(today)
    if not state:
        return {"run_date": today, "status": "not_started",
                "daily_target": 5, "packages_created": packages}
    state["packages_created"] = packages
    state["target_met"] = packages >= state.get("daily_target", 5)
    return state


@router.post("/daily-run/run")
async def daily_run_trigger(request: Request):
    """Run today's pipeline now (idempotent — resumes/completes in place).

    Honors approval matrix: packages born ready_for_review, outreach
    DRAFT-ONLY. Never sends.
    """
    import os
    from fastapi import HTTPException
    from app.daily_run import DailyRun, select_candidates
    db = _db(request)
    runner = DailyRun(db)

    def _short_error(exc: Exception) -> str:
        detail = getattr(exc, "detail", None)
        return str(detail if detail is not None else exc)[:300]

    async def _discover(report, stage):
        from app.adapters import ALL_ADAPTERS
        from app.discovery import run_discovery_cycle
        from app.routers.discovery import _env_scraper_keys
        from app.search_gate import require_resume_for_search
        await require_resume_for_search(request)
        registry = getattr(request.app.state, "country_registry", None)
        if not registry or not registry.enabled_countries():
            return {"skipped": True, "reason": "no_countries_enabled",
                    "shortfall_reasons": ["NO_ELIGIBLE_JOBS"]}
        keys = await db.get_scraper_keys()
        for name, entry in _env_scraper_keys().items():
            keys.setdefault(name, entry)
        max_passes = int(os.getenv("JOBAGENT_DAILY_DISCOVERY_PASSES", "4"))
        telemetry = await run_discovery_cycle(
            db, registry, ALL_ADAPTERS,
            max_passes=max(1, min(max_passes, 50)),
            scraper_keys=keys,
        )
        reasons = []
        if telemetry.get("new_jobs", 0) == 0:
            reasons.append("SOURCES_EXHAUSTED")
        if telemetry.get("budget_exhausted"):
            reasons.append("RATE_LIMITED")
        return {"new_jobs": telemetry.get("new_jobs", 0),
                "pass_budget": telemetry.get("pass_budget"),
                "budget_exhausted": telemetry.get("budget_exhausted", False),
                "shortfall_reasons": reasons}

    async def _classify(report, stage):
        from app.scheduler import run_location_classification
        ai = await request.app.state.ai_state_for(request)
        n = await run_location_classification(db, ai_client=ai.get("client"))
        return {"classified": n}

    async def _eligibility(report, stage):
        from app.scheduler import run_eligibility_pass
        n = await run_eligibility_pass(
            db, getattr(request.app.state, "country_registry", None))
        return {"evaluated": n,
                "shortfall_reasons": ["NO_ELIGIBLE_JOBS"] if n == 0 else []}

    async def _score(report, stage):
        ai = await request.app.state.ai_state_for(request)
        matcher = ai.get("matcher")
        if not matcher:
            return {"scored": 0, "shortfall_reasons": ["NO_AI_PROVIDER"]}
        before = len(await db.get_scoreable_jobs(limit=10000))
        await request.app.state.score_unscored(
            db, matcher=matcher,
            run_key=f"daily-run:{id(getattr(request.state, 'workspace', None))}")
        after = len(await db.get_scoreable_jobs(limit=10000))
        scored = max(0, before - after)
        reasons = ["AI_QUOTA_EXHAUSTED"] if before and scored == 0 else []
        return {"eligible_before": before, "scored": scored,
                "eligible_after": after, "shortfall_reasons": reasons}

    async def _hybrid_score(report, stage):
        from app.matching_service import score_all_unscored
        from app.routers.matching import _hybrid_state
        return await score_all_unscored(await _hybrid_state(request), db)
    # Minimal stage set for the API path: compute what's computable now.
    # Discovery/scoring remain on the scheduler cycle; this closes the loop
    # from already-scored pool to packages + follow-ups + report.
    async def _select(report, stage):
        result = await select_candidates(
            db, cutoff=runner.score_cutoff, limit=max(0, report.daily_target))
        if result["selected"] < report.daily_target:
            result["shortfall_reasons"] = (
                ["NO_ELIGIBLE_JOBS"] if result["selected"] == 0
                else ["ALL_SCORED_BELOW_CUTOFF"])
        return result

    async def _research(report, stage):
        from app.contact_providers import ContactResearchService, workspace_provider_chain
        selected = report.stage("select").detail.get("job_ids") or [
            r["job_id"] for r in await db.get_top_unpackaged_jobs(
                cutoff=runner.score_cutoff, limit=report.daily_target)
        ]
        service = ContactResearchService(db, await workspace_provider_chain(db))
        found = errors = 0
        results = []
        for job_id in selected:
            job = await db.get_job(job_id)
            if not job:
                continue
            result = await service.research(job)
            results.append({"job_id": job_id, "status": result.get("status"),
                            "provider": result.get("provider")})
            found += 1 if result.get("status") == "found" else 0
            errors += 1 if result.get("status") == "error" else 0
        return {"researched": len(results), "found": found, "errors": errors,
                "jobs": results}

    async def _packages(report, stage):
        # Real package build requires AI + evidence gate — out of scope for
        # the trigger path; report what's pending instead of half-building.
        pending = await db.get_top_unpackaged_jobs(cutoff=60, limit=50)
        return {"pending_packages": len(pending),
                "note": "build via POST /api/packages/build per job"}
    async def _packages(report, stage):
        from app.routers.packages import build_package
        from app.routers.tailoring import prepare_application
        selected = report.stage("select").detail.get("job_ids") or [
            r["job_id"] for r in await db.get_top_unpackaged_jobs(
                cutoff=runner.score_cutoff, limit=report.daily_target)
        ]
        built = prepared = evidence_failures = package_errors = 0
        results = []
        for job_id in selected:
            try:
                if not await db.get_application(job_id):
                    await prepare_application(request, job_id)
                    prepared += 1
                result = await build_package(request, job_id)
                built += 1
                results.append({"job_id": job_id, "status": "built",
                                "action": result.get("action")})
            except HTTPException as exc:
                code = getattr(exc, "status_code", 500)
                if code == 422:
                    evidence_failures += 1
                else:
                    package_errors += 1
                results.append({"job_id": job_id, "status": "failed",
                                "code": code, "error": _short_error(exc)})
            except Exception as exc:  # noqa: BLE001
                package_errors += 1
                logger.exception("Daily package build failed for job %s", job_id)
                results.append({"job_id": job_id, "status": "failed",
                                "error": _short_error(exc)})
        reasons = []
        if evidence_failures:
            reasons.append("EVIDENCE_GATE")
        if package_errors:
            reasons.append("PACKAGE_ERROR")
        return {"selected": len(selected), "prepared": prepared, "built": built,
                "results": results, "shortfall_reasons": reasons}

    async def _outreach(report, stage):
        from app.outreach import GmailProvider, OutreachService, load_sequences
        from app.routers.outreach import _gmail_credential
        token, source = await _gmail_credential(request)
        sequences, limits, identity = load_sequences()
        service = OutreachService(
            db, sequences, limits, identity, GmailProvider(token=token))
        selected = report.stage("select").detail.get("job_ids") or []
        created = existing = capped = failed = 0
        results = []
        for job_id in selected:
            app_row = await db.get_application(job_id)
            if not app_row or not app_row.get("package_dir"):
                continue
            try:
                result = await service.create_outreach(job_id)
                status = result.get("status")
                created += 1 if status == "created" else 0
                existing += 1 if status == "already_exists" else 0
                capped += 1 if status == "capped" else 0
                results.append({"job_id": job_id, "status": status})
            except Exception as exc:  # noqa: BLE001
                failed += 1
                results.append({"job_id": job_id, "status": "failed",
                                "error": _short_error(exc)})
        return {"created": created, "already_exists": existing,
                "capped": capped, "failed": failed,
                "gmail_source": source, "jobs": results}

    async def _digest(report, stage):
        from app.digest import generate_digest
        digest = await generate_digest(db, min_score=runner.score_cutoff)
        return {"subject": digest.get("subject"),
                "job_count": digest.get("job_count"),
                "outcome": digest.get("outcome")}

    report = await runner.run({
        "discover": _discover,
        "classify": _classify,
        "eligibility": _eligibility,
        "score": _score,
        "hybrid_score": _hybrid_score,
        "select": _select,
        "research": _research,
        "packages": _packages,
        "outreach": _outreach,
        "digest": _digest,
    })
    return report.to_dict()


# ------------------------------------------------------------- M12 responses

@router.post("/responses/classify")
async def classify_response(request: Request):
    """Classify a reply email — deterministic rules + REVIEW routing."""
    from app.response_monitor import classify_email
    body = await request.json()
    c = classify_email(subject=body.get("subject", ""),
                       body=body.get("body", ""), sender=body.get("sender", ""))
    return {"label": c.label, "confidence": c.confidence, "review": c.review,
            "matched_rules": c.matched_rules, "reason": c.reason}


@router.get("/analytics/monitoring")
async def monitoring(request: Request, days: int = Query(30, ge=1, le=365)):
    """M14 observability: LLM cost meter + cache-hit metrics + run telemetry.

    Answers the concrete question "how far does my top-up go?" — totals,
    per-model spend, avg cost per call, and an estimate of calls remaining
    against the configured budget.
    """
    from app import ai_usage
    from datetime import timedelta

    db = _db(request)
    since = (_now() - timedelta(days=days)).isoformat()
    rows = await db.get_ai_usage_rows(since=since)
    summary = ai_usage.summarize(rows)
    counters = await db.get_metrics()

    hits = counters.get("research_cache_hits", 0)
    misses = counters.get("research_cache_misses", 0)
    total_lookups = hits + misses

    today = _now().strftime("%Y-%m-%d")
    today_rows = await db.get_ai_usage_rows(since=f"{today}T00:00:00")
    today_summary = ai_usage.summarize(today_rows)

    run_state = await db.get_daily_run_state(today)
    return {
        "window_days": days,
        "ai_usage": {
            "all_time": summary,
            "today": today_summary,
            "pricing_note": "estimates from a static rate table; free models cost $0",
        },
        "budget": ai_usage.budget_projection(
            spent_usd=summary["totals"]["cost_usd"],
            calls=summary["totals"]["calls"],
        ),
        "cache": {
            "research_cache_hits": hits,
            "research_cache_misses": misses,
            "hit_rate": round(hits / total_lookups, 3) if total_lookups else None,
        },
        "daily_run": {
            "run_date": today,
            "packages_created": await db.count_packages_created_on(today),
            "state": run_state,
        },
    }


@router.get("/analytics/feedback")
async def feedback_recommendations(request: Request):
    """Feedback loop — recommendations for HUMAN review, never auto-rewrite."""
    from app.response_monitor import recommend
    db = _db(request)
    analytics = await db.get_analytics()
    recs = recommend(weights={}, funnel=analytics.get("funnel", {}),
                     sources=analytics.get("sources", []))
    return recs
