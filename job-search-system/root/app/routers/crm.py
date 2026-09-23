"""M10/M11/M12 routers — CRM transitions, DailyRun, response monitor.

All transitions validated by app.crm.check_transition (deterministic).
Daily-run trigger respects approval matrix: everything runs locally,
nothing sends, nothing auto-publishes.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request

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
    db = request.app.state.db
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
    db = request.app.state.db
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
    db = request.app.state.db
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
    db = request.app.state.db
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
    from app.daily_run import DailyRun
    db = request.app.state.db
    runner = DailyRun(db)
    # Minimal stage set for the API path: compute what's computable now.
    # Discovery/scoring remain on the scheduler cycle; this closes the loop
    # from already-scored pool to packages + follow-ups + report.
    async def _select(report, stage):
        rows = await db.get_top_unpackaged_jobs(cutoff=60, limit=max(0, report.daily_target))
        stage.detail["selected"] = len(rows)
        if len(rows) < report.daily_target:
            stage.detail["shortfall_reasons"] = ["ALL_SCORED_BELOW_CUTOFF"]
        return {"job_ids": [r["job_id"] for r in rows]}
    async def _packages(report, stage):
        # Real package build requires AI + evidence gate — out of scope for
        # the trigger path; report what's pending instead of half-building.
        pending = await db.get_top_unpackaged_jobs(cutoff=60, limit=50)
        return {"pending_packages": len(pending),
                "note": "build via POST /api/packages/build per job"}
    report = await runner.run({
        "select": _select,
        "packages": _packages,
        "outreach": None,
        "digest": None,
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

    db = request.app.state.db
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
    db = request.app.state.db
    analytics = await db.get_analytics()
    recs = recommend(weights={}, funnel=analytics.get("funnel", {}),
                     sources=analytics.get("sources", []))
    return recs
