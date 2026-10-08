"""The score report — one row per job, plus the facts that make it checkable.

Basil's requirement (2026-10-07): *"that report of all the job scores needs to
have — that was need to check properly."*

The pipeline already stores every score, but nothing ever asserted that the
stored set is *coherent*: you could not tell, without hand-written SQL, whether
an INELIGIBLE job had leaked into SCORE, whether an eligible job had been
silently missed, whether an AI score of 0 was real or the D1 "missing from batch
response" artifact, or whether the free hybrid layer had ever run at all (it had
not — `hybrid_score` was 0 on live data).

This module answers those questions in one place. It is read-only: it never
writes a score, never dismisses a job, and never calls a model.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Coverage / integrity checks
# ---------------------------------------------------------------------------

CHECK_DESCRIPTIONS = {
    "eligibility_containment": (
        "No INELIGIBLE / REVIEW_REQUIRED / dismissed job carries a score "
        "(the Stage-3 SCORE-gate contract)."
    ),
    "eligible_coverage": (
        "Every ELIGIBLE job has a score of some kind (hybrid or AI)."
    ),
    "hybrid_coverage": (
        "Every ELIGIBLE job has a hybrid (free) score. Before 2026-10-07 this "
        "was 0 across the board because the free pass was fed the AI query."
    ),
    "no_fabricated_zeros": (
        "No AI score of exactly 0 — the D1 artifact class, where a job the "
        "model never returned was padded with a fabricated zero."
    ),
    "role_match_cap": (
        "No AI score above the cap while role_match is explicitly false (D3b)."
    ),
}


def _decided_by(row: dict) -> str:
    """Which engine's score is effective for this job."""
    if row.get("ai_score") is not None:
        return "ai"
    if row.get("hybrid_score") is not None:
        return "hybrid"
    return "unscored"


def _json_or(raw, fallback):
    if isinstance(raw, (dict, list)):
        return raw
    if isinstance(raw, str) and raw:
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return fallback
    return fallback


async def build_score_report(db, limit: int | None = None) -> dict:
    """Build the report from stored data only. Read-only, no model calls."""
    from app.matcher import ROLE_MATCH_SCORE_CAP

    cursor = await db.db.execute(
        """SELECT j.id, j.title, j.company, j.location, j.url,
                  j.eligibility_status, j.eligibility_gate, j.eligibility_reason,
                  j.dismissed, j.created_at,
                  js.ai_score, js.hybrid_score, js.match_score, js.role_match,
                  js.hard_blockers, js.component_scores, js.ai_model,
                  js.ai_scored_at, js.hybrid_scored_at
           FROM jobs j
           LEFT JOIN job_scores js ON js.job_id = j.id
           ORDER BY (js.match_score IS NULL) ASC,
                    js.match_score DESC,
                    j.id ASC"""
    )
    jobs = [dict(r) for r in await cursor.fetchall()]
    if limit:
        jobs = jobs[:limit]

    rows = []
    for j in jobs:
        ai, hybrid = j.get("ai_score"), j.get("hybrid_score")
        effective = ai if ai is not None else hybrid
        rows.append({
            "job_id": j["id"],
            "title": j.get("title"),
            "company": j.get("company"),
            "location": j.get("location"),
            "url": j.get("url"),
            "eligibility_status": j.get("eligibility_status"),
            "eligibility_gate": j.get("eligibility_gate"),
            "eligibility_reason": j.get("eligibility_reason"),
            "dismissed": bool(j.get("dismissed")),
            "ai_score": ai,
            "hybrid_score": hybrid,
            "effective_score": effective,
            "decided_by": _decided_by(j),
            "role_match": (None if j.get("role_match") is None
                           else bool(j["role_match"])),
            "ai_model": j.get("ai_model"),
            "hybrid_scored_at": j.get("hybrid_scored_at"),
            "ai_scored_at": j.get("ai_scored_at"),
            "component_scores": _json_or(j.get("component_scores"), {}),
            "hard_blockers": _json_or(j.get("hard_blockers"), []),
        })

    eligible = [r for r in rows if r["eligibility_status"] == "ELIGIBLE"
                and not r["dismissed"]]
    ineligible = [r for r in rows if r["eligibility_status"] != "ELIGIBLE"]

    # --- the checks the report asserts about itself -------------------------
    leaked = [r["job_id"] for r in ineligible if r["decided_by"] != "unscored"]
    eligible_unscored = [r["job_id"] for r in eligible
                         if r["decided_by"] == "unscored"]
    eligible_no_hybrid = [r["job_id"] for r in eligible
                          if r["hybrid_score"] is None]
    fabricated = [r["job_id"] for r in rows if r["ai_score"] == 0]
    capped = [r["job_id"] for r in rows
              if r["role_match"] is False and (r["ai_score"] or 0) > ROLE_MATCH_SCORE_CAP]

    def check(name: str, offenders: list) -> dict:
        return {
            "name": name,
            "ok": not offenders,
            "count": len(offenders),
            "job_ids": offenders[:50],
            "description": CHECK_DESCRIPTIONS[name],
        }

    checks = [
        check("eligibility_containment", leaked),
        check("eligible_coverage", eligible_unscored),
        check("hybrid_coverage", eligible_no_hybrid),
        check("no_fabricated_zeros", fabricated),
        check("role_match_cap", capped),
    ]

    coverage = {
        "jobs_total": len(rows),
        "eligible": len(eligible),
        "ineligible_or_review": len(ineligible),
        "scored_any": sum(1 for r in rows if r["decided_by"] != "unscored"),
        "ai_scored": sum(1 for r in rows if r["ai_score"] is not None),
        "hybrid_scored": sum(1 for r in rows if r["hybrid_score"] is not None),
        "unscored": sum(1 for r in rows if r["decided_by"] == "unscored"),
        "decided_by": {
            "ai": sum(1 for r in rows if r["decided_by"] == "ai"),
            "hybrid": sum(1 for r in rows if r["decided_by"] == "hybrid"),
            "unscored": sum(1 for r in rows if r["decided_by"] == "unscored"),
        },
    }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "coverage": coverage,
        "checks": checks,
        "all_checks_pass": all(c["ok"] for c in checks),
        "jobs": rows,
    }


# ---------------------------------------------------------------------------
# Human-readable rendering
# ---------------------------------------------------------------------------

def render_markdown(report: dict) -> str:
    """Render the report as Markdown a person can actually read."""
    cov = report["coverage"]
    lines = [
        "# Score Report",
        "",
        f"Generated: `{report['generated_at']}`",
        "",
        "## Coverage",
        "",
        "| Measure | Count |",
        "|---|---|",
        f"| Jobs seen | {cov['jobs_total']} |",
        f"| ELIGIBLE | {cov['eligible']} |",
        f"| INELIGIBLE / REVIEW | {cov['ineligible_or_review']} |",
        f"| Has any score | {cov['scored_any']} |",
        f"| AI-scored | {cov['ai_scored']} |",
        f"| Hybrid-scored (free) | {cov['hybrid_scored']} |",
        f"| Unscored | {cov['unscored']} |",
        "",
        "Which engine decided each score: "
        f"**AI {cov['decided_by']['ai']}** · "
        f"**hybrid {cov['decided_by']['hybrid']}** · "
        f"unscored {cov['decided_by']['unscored']}.",
        "",
        "## Integrity checks",
        "",
        f"**Overall: {'PASS' if report['all_checks_pass'] else 'ATTENTION NEEDED'}**",
        "",
        "| Check | Result | Count |",
        "|---|---|---|",
    ]
    for c in report["checks"]:
        lines.append(f"| `{c['name']}` | {'PASS' if c['ok'] else 'FAIL'} | {c['count']} |")
    lines += ["", "### What each check means", ""]
    for c in report["checks"]:
        lines.append(f"- **`{c['name']}`** — {c['description']}")
        if not c["ok"]:
            ids = ", ".join(str(i) for i in c["job_ids"])
            lines.append(f"  - Offenders ({c['count']}): {ids}")
    lines += [
        "",
        "## Per-job scores",
        "",
        "| Job | Title | Company | Effective | Decided by | AI | Hybrid | "
        "Eligibility | role_match |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in report["jobs"]:
        def num(v):
            return "—" if v is None else str(v)
        title = (r["title"] or "")[:48]
        company = (r["company"] or "")[:24]
        lines.append(
            f"| {r['job_id']} | {title} | {company} | {num(r['effective_score'])} "
            f"| {r['decided_by']} | {num(r['ai_score'])} | {num(r['hybrid_score'])} "
            f"| {r['eligibility_status'] or '—'} | "
            f"{'—' if r['role_match'] is None else r['role_match']} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_score_report(report: dict, root: str | Path) -> dict:
    """Write the Markdown + JSON artifacts. Returns the paths written."""
    root = Path(root)
    docs_dir = root / "docs" / "score"
    results_dir = docs_dir / "results"
    docs_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    stamp = report["generated_at"][:10]
    md_path = docs_dir / f"SCORE_REPORT_{stamp}.md"
    json_path = results_dir / "score_report.json"

    md_path.write_text(render_markdown(report), encoding="utf-8")
    json_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    logger.info("Score report written to %s and %s", md_path, json_path)
    return {"markdown": str(md_path), "json": str(json_path)}
