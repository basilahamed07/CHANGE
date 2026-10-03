"""STAGE-4 SCORE — LIVE validation against real rows (copied DB, never the original).

Default mode is FREE and re-runnable: it makes ZERO AI calls and answers the
questions the hardening was written to fix, using only what is already in the DB.

  1. Stage-3 containment — does any non-ELIGIBLE job carry a score?
  2. Stage-4 input pool   — how many eligible jobs are still unscored?
  3. D1 artifact scan      — are there fabricated `score=0` rows produced by the
                             old batch parser ("Missing from batch response")?
                             `clear_failed_scores()` does NOT clean these up.
  4. Score distribution    — the shape of what the AI actually produced.
  5. Re-score candidates   — score=0 rows that look like transient artifacts.

Optional `--score N` (SPENDS AI CALLS) builds the real matcher from the
workspace's own ai_settings and batch-scores N real jobs, reporting how many
were scored versus skipped. That is the only mode that exercises the new
"omit, never pad" parser against a real model; it is off by default.

Run:
    cd job-search-system/root
    .venv/bin/python -u ../analysis/verify_score_live.py            # free analysis
    .venv/bin/python -u ../analysis/verify_score_live.py --score 5  # spends AI calls
"""
from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sqlite3
import sys
import tempfile
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "root"
sys.path.insert(0, str(ROOT))

# Windows consoles default to cp1252; the report prints non-ASCII (→, —) and
# would die with UnicodeEncodeError *after* doing all the work. Force UTF-8.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

from app.database import Database                              # noqa: E402

JS = Path(__file__).resolve().parents[1]
# Live rows live either in the admin's per-user workspace (after the multi-user
# migration) or, on a deployment that has not been migrated yet, in the original
# root/data/jobagent.db. Point at whichever actually holds jobs — otherwise the
# "live" verification silently runs against an empty DB and reports all zeros.
_WS_DB = ROOT / "data" / "users" / "1-basil" / "jobagent.db"
_LEGACY_DB = ROOT / "data" / "jobagent.db"


def _pick_src_db() -> Path:
    best, best_n = _LEGACY_DB, -1
    for p in (_LEGACY_DB, _WS_DB):
        if not p.exists():
            continue
        try:
            con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
            n = con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
            con.close()
        except sqlite3.Error:
            continue
        if n > best_n:
            best, best_n = p, n
    return best


SRC_DB = _pick_src_db()


def _borrow_from_workspace() -> dict:
    """Read the profile pieces Stage-4 needs from the admin workspace DB.

    This deployment keeps jobs and profile in separate databases, so the job DB
    can have no resume/ai_settings. Read-only; the live file is never modified.
    """
    out: dict = {}
    if not _WS_DB.exists() or _WS_DB == SRC_DB:
        return out
    try:
        con = sqlite3.connect(f"file:{_WS_DB}?mode=ro", uri=True)
    except sqlite3.Error:
        return out
    try:
        row = con.execute(
            "SELECT resume_text FROM resumes WHERE resume_text IS NOT NULL "
            "AND resume_text != '' ORDER BY is_default DESC, id ASC LIMIT 1").fetchone()
        if row:
            out["resume_text"] = row[0]
        row = con.execute(
            "SELECT provider, api_key, model, base_url FROM ai_settings "
            "WHERE provider IS NOT NULL AND provider != '' LIMIT 1").fetchone()
        if row:
            out["ai_settings"] = {"provider": row[0], "api_key": row[1] or "",
                                  "model": row[2] or "", "base_url": row[3] or ""}
    except sqlite3.Error:
        pass
    finally:
        con.close()
    return out
OUT = JS / "docs" / "score" / "results" / "score_summary.json"

# The exact concern string the pre-hardening parser wrote for a job it never
# actually scored. Finding any of these proves D1 fired on real data.
D1_MARKER = "Missing from batch response"

# Concerns that mark a score=0 row as a transient failure rather than a real
# "this job is a terrible fit" verdict (mirrors db.clear_failed_scores).
TRANSIENT_MARKERS = ("unavailable", "unreachable", "Scoring error",
                     "circuit breaker", "rate limit")


def _copy_db() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="score_live_")) / "jobagent.db"
    shutil.copy(SRC_DB, tmp)
    for suffix in ("-wal", "-shm"):
        s = Path(str(SRC_DB) + suffix)
        if s.exists():
            shutil.copy(s, Path(str(tmp) + suffix))
    return tmp


async def _scalar(db: Database, sql: str, params: tuple = ()) -> int:
    cur = await db.db.execute(sql, params)
    row = await cur.fetchone()
    return int(row[0]) if row and row[0] is not None else 0


async def _analysis(db: Database) -> dict:
    """Everything that needs no AI call."""

    # 1. Stage-3 containment: only ELIGIBLE jobs may hold a score.
    leaked = await _scalar(db, """
        SELECT COUNT(*) FROM job_scores js JOIN jobs j ON j.id = js.job_id
        WHERE j.eligibility_status IS NULL
           OR j.eligibility_status != 'ELIGIBLE'""")

    # 2. Stage-4 input pool (exactly what get_scoreable_jobs returns).
    pool = await _scalar(db, """
        SELECT COUNT(*) FROM jobs j LEFT JOIN job_scores js ON j.id = js.job_id
        WHERE js.id IS NULL AND j.dismissed = 0
          AND j.location_classified = 1 AND j.eligibility_status = 'ELIGIBLE'""")

    eligible_total = await _scalar(db, """
        SELECT COUNT(*) FROM jobs
        WHERE eligibility_status = 'ELIGIBLE' AND dismissed = 0""")

    # 3. D1 artifact scan — fabricated zeros from the old padding parser.
    cur = await db.db.execute(
        "SELECT js.job_id, j.title, j.company, js.concerns "
        "FROM job_scores js JOIN jobs j ON j.id = js.job_id "
        "WHERE js.match_score = 0 AND js.concerns LIKE ? LIMIT 20",
        (f"%{D1_MARKER}%",))
    d1_rows = [dict(r) for r in await cur.fetchall()]
    d1_total = await _scalar(db, """
        SELECT COUNT(*) FROM job_scores
        WHERE match_score = 0 AND concerns LIKE ?""", (f"%{D1_MARKER}%",))

    # 5. Transient zeros — the ones clear_failed_scores() is meant to purge.
    like = " OR ".join(["concerns LIKE ?"] * len(TRANSIENT_MARKERS))
    transient_total = await _scalar(
        db, f"SELECT COUNT(*) FROM job_scores WHERE match_score = 0 AND ({like})",
        tuple(f"%{m}%" for m in TRANSIENT_MARKERS))

    # 4. Distribution of persisted scores.
    cur = await db.db.execute("SELECT match_score FROM job_scores")
    scores = [int(r[0]) for r in await cur.fetchall()]
    buckets = Counter()
    for s in scores:
        lo = (s // 10) * 10
        buckets[f"{lo:02d}-{min(lo + 9, 100):03d}"] += 1

    cur = await db.db.execute(
        "SELECT COUNT(*) FROM job_scores WHERE role_match = 0")
    role_mismatch = int((await cur.fetchone())[0])

    # role_match=false rows that still exceed the cap would be pre-fix rows.
    over_cap = await _scalar(db, """
        SELECT COUNT(*) FROM job_scores
        WHERE role_match = 0 AND match_score > 50""")

    return {
        "stage3_leaked_scores": leaked,
        "stage4_input_pool": pool,
        "eligible_total": eligible_total,
        "already_scored": len(scores),
        "d1_fabricated_zero_total": d1_total,
        "d1_samples": d1_rows,
        "transient_zero_total": transient_total,
        "role_match_false": role_mismatch,
        "role_match_false_over_cap": over_cap,
        "score_buckets": dict(sorted(buckets.items())),
        "score_min": min(scores) if scores else None,
        "score_max": max(scores) if scores else None,
        "score_mean": round(sum(scores) / len(scores), 1) if scores else None,
    }


async def _live_score(db: Database, n: int) -> dict:
    """OPT-IN: score `n` real eligible jobs with the real matcher. Spends AI calls."""
    from app.main import _build_ai_client
    from app.matcher import JobMatcher

    ai_settings = await db.get_ai_settings()
    if not ai_settings:
        ai_settings = _borrow_from_workspace().get("ai_settings")
        if ai_settings:
            print("(no ai_settings in the job DB — borrowed deepseek settings "
                  "from the workspace DB)")
    client = _build_ai_client(ai_settings)
    if client is None:
        # Documented fallback: the DB is authoritative, env is the fallback. The
        # legacy single-user DB carries no ai_settings row, so without this the
        # live score can never run here (it would just report "no client").
        from app.config import get_settings
        client = _build_ai_client(None, get_settings())
        if client is not None:
            print("(no ai_settings in DB — using env provider fallback)")
    if client is None:
        return {"error": "no AI client configured for this workspace"}

    resume_text = ""
    cur = await db.db.execute(
        "SELECT resume_text FROM resumes WHERE resume_text IS NOT NULL "
        "AND resume_text != '' ORDER BY is_default DESC, id ASC LIMIT 1")
    row = await cur.fetchone()
    if row:
        resume_text = row[0]
    if not resume_text:
        cfg = await db.get_search_config()
        resume_text = (cfg or {}).get("resume_text", "") or ""
    if not resume_text:
        # This deployment is split: jobs sit in root/data/jobagent.db, the resume
        # sits in the admin workspace DB. Borrow it from there (read-only).
        borrowed = _borrow_from_workspace().get("resume_text")
        if borrowed:
            resume_text = borrowed
            print("(no resume in the job DB — borrowed the real resume "
                  "from the workspace DB)")
    if not resume_text:
        return {"error": "no resume text in this workspace — Stage-4 cannot score"}

    jobs = await db.get_scoreable_jobs(limit=n)
    if not jobs:
        return {"requested": n, "scored": 0, "skipped": 0,
                "note": "nothing eligible left to score"}

    matcher = JobMatcher(client=client, resume_text=resume_text)
    print(f"scoring {len(jobs)} real jobs via {getattr(client, 'provider', '?')}"
          f"/{getattr(client, 'model', '?')} ...")
    results = await matcher.score_batch(jobs)

    scored_ids = {r["job_id"] for r in results}
    skipped = [j["id"] for j in jobs if j["id"] not in scored_ids]
    return {
        "requested": len(jobs),
        "scored": len(results),
        "skipped": len(skipped),
        "skipped_ids": skipped[:20],
        "scores": [{"job_id": r["job_id"], "score": r["score"],
                    "role_match": r["role_match"]} for r in results],
        "ai_calls": 1,
        "note": ("every job accounted for — nothing was fabricated"
                 if not skipped else
                 f"{len(skipped)} job(s) left unscored for the next cycle "
                 "(correct: omitted, never padded with a score of 0)"),
    }


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--score", type=int, default=0, metavar="N",
                    help="ALSO batch-score N real jobs (SPENDS AI CALLS). "
                         "Default 0 = free analysis only.")
    ap.add_argument("--raw", action="store_true",
                    help="skip the Stage-2/Stage-3 passes and analyse the DB "
                         "exactly as it sits (default: run the deterministic "
                         "gates first so the Stage-4 pool is real)")
    args = ap.parse_args()

    if not SRC_DB.exists():
        print(f"no live DB at {SRC_DB} — skipping live validation")
        return 0

    t0 = time.monotonic()
    db_path = _copy_db()
    print(f"validating on a COPY of {SRC_DB.name} ({db_path})")

    db = Database(str(db_path))
    await db.init()

    summary: dict = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                     "source_db": SRC_DB.name}

    # Stage-3 is the ONLY documented entry to scoring, so a "live" Stage-4 result
    # is only meaningful once Stage-2/3 have actually run. Both are deterministic
    # and cost zero AI calls, so we run them on the COPY (never the original)
    # before measuring the pool. --raw skips this to inspect the DB untouched.
    if not args.raw:
        from app.country_registry import CountryRegistry
        from app.scheduler import run_eligibility_pass, run_location_classification

        registry = CountryRegistry(str(ROOT / "config" / "countries")).load()
        await db.update_allowed_regions(registry.enabled_region_names() + ["Remote"])
        classified = await run_location_classification(db, ai_client=None)
        evaluated = await run_eligibility_pass(db, registry, force=True, limit=5000)
        print(f"Stage-2 classified {classified} newly-unclassified jobs; "
              f"Stage-3 evaluated {evaluated} jobs")
        summary["gates"] = {"classified": classified, "evaluated": evaluated}

    summary["analysis"] = await _analysis(db)
    if args.score:
        summary["live_score"] = await _live_score(db, args.score)

    summary["duration_s"] = round(time.monotonic() - t0, 1)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(summary, indent=2))

    a = summary["analysis"]
    print("\n" + "=" * 74)
    print("STAGE-4 SCORE — LIVE (real workspace rows, copied DB)")
    print("=" * 74)
    print(f"eligible pool: {a['eligible_total']}   "
          f"already scored: {a['already_scored']}   "
          f"awaiting score: {a['stage4_input_pool']}")
    print(f"Stage-3 containment — non-ELIGIBLE rows holding a score: "
          f"{a['stage3_leaked_scores']}  "
          f"({'OK' if a['stage3_leaked_scores'] == 0 else 'LEAK'})")
    print(f"D1 fabricated zeros ('{D1_MARKER}'): {a['d1_fabricated_zero_total']}  "
          f"({'clean' if a['d1_fabricated_zero_total'] == 0 else 'DEFECT SEEN IN DATA'})")
    print(f"transient zeros (clearable): {a['transient_zero_total']}")
    print(f"role_match=false: {a['role_match_false']}  "
          f"of which over the 50 cap: {a['role_match_false_over_cap']}")
    print(f"score range: {a['score_min']}–{a['score_max']}  mean {a['score_mean']}")
    print("distribution:", a["score_buckets"])
    if args.score:
        ls = summary["live_score"]
        print("\n-- live scoring (real AI calls) --")
        print(json.dumps({k: v for k, v in ls.items() if k != "scores"}, indent=2,
                         default=str))
    print(f"\nsummary → {OUT.relative_to(JS)}  ({summary['duration_s']}s)")
    await db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
