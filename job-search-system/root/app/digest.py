import json
import logging
from datetime import datetime, timezone, timedelta
from html import escape

logger = logging.getLogger(__name__)


async def daily_outcome(db) -> dict:
    """Today's package outcome: what was built against the target (Golden Rule 7).

    The digest is a DAILY REPORT, so it has to lead with the day's result. A run
    that built nothing must never be emailed as a success (defect G1).
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    state = {}
    try:
        state = await db.get_daily_run_state(today) or {}
    except Exception:            # pragma: no cover — pre-daily-run DBs
        logger.debug("no daily run state for %s", today, exc_info=True)
    target = state.get("daily_target") or 5
    created = state.get("packages_created")
    if created is None:
        try:
            created = await db.count_packages_created_on(today)
        except Exception:        # pragma: no cover — defensive
            created = 0
    met = (created or 0) >= target
    reasons = []
    if not met:
        reasons = [r for r in (state.get("shortfall_reasons") or [])
                   if r != "TARGET_REACHED"]
        if not state:
            reasons = ["NO_RUN_TODAY"]      # nothing reported: say so, don't guess
        elif not reasons:
            reasons = ["NO_ELIGIBLE_JOBS"]  # vocabulary default, never a blank
    return {
        "run_date": today,
        "daily_target": target,
        "packages_created": created or 0,
        "target_met": met,
        "shortfall_reasons": reasons,
    }


def _digest_subject(outcome: dict, job_count: int) -> str:
    """Lead with the outcome — never with a bare job count."""
    head = (f"{outcome['packages_created']}/{outcome['daily_target']} packages")
    if outcome["target_met"]:
        return f"jobagent: target met — {head} · {job_count} new " \
               f"match{'es' if job_count != 1 else ''}"
    reasons = ", ".join(outcome["shortfall_reasons"]) or "unreported"
    return f"jobagent: {head} — {reasons} · {job_count} new " \
           f"match{'es' if job_count != 1 else ''}"


async def generate_digest(db, min_score: int = 60, hours: int = 24) -> dict:
    """Digest of new, ELIGIBLE, high-scoring jobs — led by today's outcome.

    Two defects fixed here:

    * **G4** the query never re-checked eligibility, so a job whose gate had
      since flipped could still be headlined as a "new match" (the same root
      cause as S3 in SELECT).
    * **G1** the digest reported a *job count* and never packages-vs-target or a
      shortfall reason, so a day that built nothing was emailed as
      "jobagent: 12 new matches" — a success-shaped message about a failed day.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

    cursor = await db.db.execute("""
        SELECT j.*, js.match_score, js.match_reasons
        FROM jobs j
        JOIN job_scores js ON j.id = js.job_id
        WHERE js.match_score >= ? AND j.created_at >= ? AND j.dismissed = 0
          AND j.eligibility_status = 'ELIGIBLE'
        ORDER BY js.match_score DESC, j.id ASC
        LIMIT 20
    """, (min_score, cutoff))
    rows = await cursor.fetchall()
    jobs = []
    for row in rows:
        d = dict(row)
        if d.get("match_reasons"):
            d["match_reasons"] = json.loads(d["match_reasons"])
        jobs.append(d)

    outcome = await daily_outcome(db)
    subject = _digest_subject(outcome, len(jobs))

    plain = "jobagent Daily Digest\n"
    plain += (f"Run {outcome['run_date']}: {outcome['packages_created']}/"
              f"{outcome['daily_target']} packages built — "
              f"{'TARGET MET' if outcome['target_met'] else 'TARGET MISSED'}\n")
    if not outcome["target_met"]:
        plain += f"Shortfall: {', '.join(outcome['shortfall_reasons'])}\n"
    plain += f"\n{len(jobs)} new job match{'es' if len(jobs) != 1 else ''} " \
             f"in the last {hours} hours\n\n"

    for j in jobs:
        score = j.get("match_score", "?")
        plain += f"[{score}/100] {j['title']} at {j['company']}\n"
        loc = j.get("location", "")
        if loc:
            plain += f"  Location: {loc}\n"
        sal_min = j.get("salary_min")
        sal_max = j.get("salary_max")
        if sal_min and sal_max:
            plain += f"  Salary: ${sal_min:,} - ${sal_max:,}\n"
        plain += f"  {j['url']}\n\n"

    html = _render_html_digest(jobs, hours, outcome)

    return {
        "subject": subject,
        "body": plain,
        "html": html,
        "job_count": len(jobs),
        "outcome": outcome,
        "jobs": [{
            "id": j["id"],
            "title": j["title"],
            "company": j["company"],
            "location": j.get("location", ""),
            "match_score": j.get("match_score"),
            "url": j["url"],
        } for j in jobs],
    }


def _render_html_digest(jobs: list[dict], hours: int,
                         outcome: dict | None = None) -> str:
    count = len(jobs)
    rows = ""
    for j in jobs:
        score = j.get("match_score", "?")
        title = escape(j.get("title", ""))
        company = escape(j.get("company", ""))
        location = escape(j.get("location", ""))
        url = escape(j.get("url", ""))
        salary = ""
        if j.get("salary_min") and j.get("salary_max"):
            salary = f"${j['salary_min']:,} - ${j['salary_max']:,}"

        score_color = "#22c55e" if score >= 80 else "#eab308" if score >= 60 else "#ef4444"

        rows += f"""
        <tr style="border-bottom:1px solid #e5e7eb">
          <td style="padding:12px 8px;text-align:center">
            <span style="background:{score_color};color:#fff;padding:4px 8px;border-radius:4px;font-weight:bold">{score}</span>
          </td>
          <td style="padding:12px 8px">
            <a href="{url}" style="color:#2563eb;text-decoration:none;font-weight:600">{title}</a><br>
            <span style="color:#6b7280">{company}</span>
            {f'<br><span style="color:#9ca3af;font-size:0.875em">{location}</span>' if location else ''}
            {f'<br><span style="color:#059669;font-size:0.875em">{salary}</span>' if salary else ''}
          </td>
        </tr>"""

    banner = ""
    if outcome:
        met = bool(outcome.get("target_met"))
        color = "#16a34a" if met else "#dc2626"
        status = "TARGET MET" if met else "TARGET MISSED"
        reasons = "" if met else " — " + escape(
            ", ".join(outcome.get("shortfall_reasons") or []))
        banner = (
            f'<div style="background:{color};color:#fff;padding:10px 14px;'
            f'border-radius:6px;font-weight:600;margin:10px 0 6px">'
            f'{escape(str(outcome.get("run_date", "")))}: '
            f'{outcome.get("packages_created", 0)}/{outcome.get("daily_target", 5)} '
            f'packages built — {status}{reasons}</div>'
        )

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:600px;margin:0 auto;padding:20px;color:#1f2937">
  <h2 style="color:#2563eb;margin-bottom:4px">jobagent Digest</h2>
  {banner}
  <p style="color:#6b7280;margin-top:0">{count} new match{'es' if count != 1 else ''} in the last {hours} hours</p>
  <table style="width:100%;border-collapse:collapse">
    <thead>
      <tr style="border-bottom:2px solid #e5e7eb">
        <th style="padding:8px;text-align:center;width:60px">Score</th>
        <th style="padding:8px;text-align:left">Job</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
  {f'<p style="color:#9ca3af;font-size:0.875em;margin-top:24px">Sent by jobagent</p>' if count else '<p style="color:#6b7280">No new matches found. Check back later!</p>'}
</body>
</html>"""


async def send_digest(db) -> bool:
    """Generate and send digest email using saved email settings."""
    from app.emailer import send_email

    settings = await db.get_email_settings()
    if not settings or not settings.get("digest_enabled"):
        return False
    if not settings.get("smtp_host") or not settings.get("to_address"):
        logger.warning("Digest enabled but SMTP host or to_address not configured")
        return False

    schedule = settings.get("digest_schedule", "daily")
    hours = 24 if schedule == "daily" else 168
    min_score = settings.get("digest_min_score", 60)

    digest = await generate_digest(db, min_score=min_score, hours=hours)
    if digest["job_count"] == 0:
        logger.info("No jobs for digest, skipping email")
        return False

    to_address = settings["to_address"]
    success = await send_email(
        settings,
        to=to_address,
        subject=digest["subject"],
        body_text=digest["body"],
        body_html=digest["html"],
    )
    if success:
        logger.info(f"Digest sent to {to_address}: {digest['job_count']} jobs")
    return success
