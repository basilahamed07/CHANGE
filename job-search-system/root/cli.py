"""M13 — `jobagent` CLI over the same service layer as the web UI.

Golden Rule: one service layer. The CLI never talks to the DB differently
than the API does — it reuses Database + the same helpers the routers use.

Usage:
    uv run python cli.py health
    uv run python cli.py daily-run
    uv run python cli.py followups
    uv run python cli.py search "AI Engineer" --min-score 70 --limit 10
    uv run python cli.py prepare JOB_ID
    uv run python cli.py contacts JOB_ID
    uv run python cli.py analytics
    uv run python cli.py status JOB_ID --set interviewing
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from app.database import Database  # noqa: E402
from app.config import Settings  # noqa: E402


def _fmt(obj) -> str:
    return json.dumps(obj, indent=2, default=str)


async def _open_db() -> Database:
    settings = Settings()
    db = Database(settings.db_path)
    await db.init()
    return db


# ------------------------------------------------------------- commands

async def cmd_health(_: argparse.Namespace) -> int:
    db = await _open_db()
    try:
        jobs = await db.get_all_applications()
        stats = await db.get_pipeline_stats()
        print(_fmt({"db": "ok", "applications": len(jobs), "pipeline": stats}))
        return 0
    finally:
        await db.close()


async def cmd_search(args: argparse.Namespace) -> int:
    db = await _open_db()
    try:
        rows = await db.list_jobs(min_score=args.min_score, limit=args.limit,
                                  search=args.query or None)
        out = [{"id": r["id"], "title": r["title"], "company": r["company"],
                "score": r.get("match_score"), "location": r.get("location")}
               for r in rows]
        print(_fmt(out))
        return 0
    finally:
        await db.close()


async def cmd_prepare(args: argparse.Namespace) -> int:
    db = await _open_db()
    try:
        app_row = await db.get_application(args.job_id)
        if not app_row:
            await db.insert_application(args.job_id, "prepared")
        else:
            await db.update_application(app_row["id"], status="prepared")
        await db.add_event(args.job_id, "status_change", "CLI: → prepared")
        print(_fmt({"job_id": args.job_id, "status": "prepared"}))
        return 0
    finally:
        await db.close()


async def cmd_contacts(args: argparse.Namespace) -> int:
    db = await _open_db()
    try:
        from app.routers.research import default_provider_chain  # same chain as API
        from app.contact_providers import ContactResearchService
        job = await db.get_job(args.job_id)
        if not job:
            print(_fmt({"error": "job not found"}))
            return 1
        service = ContactResearchService(db, default_provider_chain(db))
        result = await service.research(args.job_id, job.get("company", ""))
        print(_fmt(result))
        return 0
    finally:
        await db.close()


async def cmd_daily(_: argparse.Namespace) -> int:
    """Daily run status + today's target accounting."""
    db = await _open_db()
    try:
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        state = await db.get_daily_run_state(today)
        packages = await db.count_packages_created_on(today)
        print(_fmt({"run_date": today, "packages_created": packages,
                    "state": state or "not started — run POST /api/daily-run/run"}))
        return 0
    finally:
        await db.close()


async def cmd_followups(_: argparse.Namespace) -> int:
    db = await _open_db()
    try:
        from app.crm import FOLLOW_UP_STOP_STATUSES, compute_follow_up
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        apps = await db.get_all_applications()
        due = []
        for a in apps:
            status = a.get("status", "interested")
            if status in FOLLOW_UP_STOP_STATUSES:
                continue
            reminders = await db.get_reminders_for_job(a["job_id"])
            pending = any(r["status"] == "pending" for r in reminders)
            last = a.get("applied_at") or a.get("updated_at")
            last_dt = datetime.fromisoformat(last) if last else None
            plan = compute_follow_up(a["job_id"], status, last_dt,
                                     pending_reminder=pending, now=now)
            if plan.due:
                due.append({"job_id": a["job_id"], "status": status,
                            "reason": plan.reason})
        print(_fmt({"followups_due": len(due), "items": due}))
        return 0
    finally:
        await db.close()


async def cmd_analytics(_: argparse.Namespace) -> int:
    db = await _open_db()
    try:
        data = await db.get_analytics()
        from app.response_monitor import recommend
        recs = recommend({}, funnel=data.get("funnel", {}),
                         sources=data.get("sources", []))
        print(_fmt({"analytics": data, "recommendations": recs["recommendations"]}))
        return 0
    finally:
        await db.close()


async def cmd_status(args: argparse.Namespace) -> int:
    from app.crm import check_transition
    db = await _open_db()
    try:
        app_row = await db.get_application(args.job_id)
        from_status = (app_row or {}).get("status", "interested")
        result = check_transition(from_status, args.set, actor="human")
        if not result.ok:
            print(_fmt({"ok": False, "reason": result.reason}))
            return 1
        if not app_row:
            await db.insert_application(args.job_id, args.set)
        else:
            await db.update_application(app_row["id"], status=args.set)
        await db.add_event(args.job_id, "status_change",
                           f"CLI: {from_status} → {args.set}")
        print(_fmt({"ok": True, "job_id": args.job_id,
                    "from": from_status, "to": args.set}))
        return 0
    finally:
        await db.close()


def main() -> int:
    p = argparse.ArgumentParser(prog="jobagent",
                                description="jobagent CLI — one service layer with the web UI")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("health").set_defaults(func=cmd_health)
    sp = sub.add_parser("search")
    sp.add_argument("query", nargs="?", default="")
    sp.add_argument("--min-score", type=int, default=None)
    sp.add_argument("--limit", type=int, default=20)
    sp.set_defaults(func=cmd_search)
    pp = sub.add_parser("prepare")
    pp.add_argument("job_id", type=int)
    pp.set_defaults(func=cmd_prepare)
    cp = sub.add_parser("contacts")
    cp.add_argument("job_id", type=int)
    cp.set_defaults(func=cmd_contacts)
    sub.add_parser("daily").set_defaults(func=cmd_daily)
    sub.add_parser("followups").set_defaults(func=cmd_followups)
    sub.add_parser("analytics").set_defaults(func=cmd_analytics)
    stp = sub.add_parser("status")
    stp.add_argument("job_id", type=int)
    stp.add_argument("--set", dest="set", required=True)
    stp.set_defaults(func=cmd_status)

    args = p.parse_args()
    return asyncio.run(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
