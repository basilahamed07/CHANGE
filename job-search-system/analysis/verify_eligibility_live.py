"""STAGE-3 ELIGIBILITY — LIVE validation on real classified rows.

Runs the REAL Stage-2 (`run_location_classification`) then the REAL Stage-3
(`run_eligibility_pass`) over a COPY of Basil's live workspace DB — never the
original — so we validate the gate chain on real discovered jobs (real
locations, real posted dates, real descriptions, real dismissals/applications)
with zero risk to his data.

Per country (target region) it reports: evaluated / eligible / ineligible /
review_required and the top rejection reasons; plus overall metrics written to
docs/eligibility/results/eligibility_summary.json.

Run:
    cd job-search-system/root
    .venv/bin/python -u ../analysis/verify_eligibility_live.py
"""
from __future__ import annotations

import asyncio
import json
import shutil
import sys
import tempfile
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "root"
sys.path.insert(0, str(ROOT))

from app.country_registry import CountryRegistry             # noqa: E402
from app.database import Database                            # noqa: E402
from app.scheduler import run_eligibility_pass, run_location_classification  # noqa: E402

JS = Path(__file__).resolve().parents[1]
SRC_DB = ROOT / "data" / "users" / "1-basil" / "jobagent.db"
OUT = JS / "docs" / "eligibility" / "results" / "eligibility_summary.json"


def _copy_db() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="elig_live_")) / "jobagent.db"
    shutil.copy(SRC_DB, tmp)
    for suffix in ("-wal", "-shm"):
        s = Path(str(SRC_DB) + suffix)
        if s.exists():
            shutil.copy(s, Path(str(tmp) + suffix))
    return tmp


async def main() -> int:
    if not SRC_DB.exists():
        print(f"no live DB at {SRC_DB} — skipping live validation")
        return 0
    t0 = time.monotonic()
    db_path = _copy_db()
    print(f"validating on a COPY of {SRC_DB.name} ({db_path})")

    db = Database(str(db_path))
    await db.init()
    registry = CountryRegistry(str(ROOT / "config" / "countries")).load()
    regions = registry.enabled_region_names() + ["Remote"]
    await db.update_allowed_regions(regions)
    print(f"target regions: {regions}")

    # Run Stage-2 for any not-yet-classified rows, then Stage-3 over the FULL
    # classified pool (force) so dismissed/already-applied rows are represented.
    classified = await run_location_classification(db, ai_client=None)
    print(f"Stage-2 classified {classified} newly-unclassified jobs")

    evaluated = await run_eligibility_pass(db, registry, force=True, limit=5000)
    print(f"Stage-3 evaluated {evaluated} jobs")

    # ---- aggregate ----
    cur = await db.db.execute(
        "SELECT eligibility_status, eligibility_gate, eligibility_reason, "
        "location_region FROM jobs WHERE eligibility_status IS NOT NULL")
    rows = [dict(r) for r in await cur.fetchall()]
    by_status = Counter(r["eligibility_status"] for r in rows)
    by_reason = Counter(r["eligibility_reason"] for r in rows)
    by_gate = Counter(r["eligibility_gate"] for r in rows)

    per_country: dict[str, dict] = {}
    for r in rows:
        c = per_country.setdefault(
            r["location_region"] or "(none)",
            {"evaluated": 0, "ELIGIBLE": 0, "INELIGIBLE": 0,
             "REVIEW_REQUIRED": 0, "UNKNOWN": 0, "reasons": Counter()})
        c["evaluated"] += 1
        c[r["eligibility_status"]] = c.get(r["eligibility_status"], 0) + 1
        c["reasons"][r["eligibility_reason"]] += 1

    for c in per_country.values():
        c["reasons"] = dict(c["reasons"].most_common(5))

    # Representative samples for manual review (task §34).
    async def _samples(where: str, n: int = 4) -> list[dict]:
        c2 = await db.db.execute(
            "SELECT id, title, company, location, location_region, country_code,"
            " posted_date, eligibility_status, eligibility_gate,"
            " eligibility_reason FROM jobs WHERE " + where +
            " LIMIT ?", (n,))
        return [dict(r) for r in await c2.fetchall()]

    samples = {
        "eligible": await _samples("eligibility_status='ELIGIBLE'", 5),
        "stale": await _samples("eligibility_reason='STALE_POSTED_DATE'", 3),
        "unknown_date": await _samples("eligibility_reason='POSTED_DATE_UNKNOWN'", 3),
        "dismissed": await _samples("eligibility_gate='DISMISSED'", 3),
        "already_applied": await _samples("eligibility_reason='ALREADY_APPLIED'", 3),
    }

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_db": SRC_DB.name, "db_copy": str(db_path),
        "target_regions": regions,
        "total_evaluated": len(rows),
        "by_status": dict(by_status),
        "by_gate": dict(by_gate),
        "by_reason": dict(by_reason.most_common(20)),
        "per_country": per_country,
        "samples": samples,
        "duration_s": round(time.monotonic() - t0, 1),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(summary, indent=2))

    # ---- report ----
    print("\n" + "=" * 74)
    print("STAGE-3 ELIGIBILITY — LIVE (real workspace rows, copied DB)")
    print("=" * 74)
    total = len(rows)
    print(f"evaluated={total}  " + "  ".join(
        f"{k}={by_status.get(k, 0)}" for k in
        ("ELIGIBLE", "INELIGIBLE", "REVIEW_REQUIRED", "UNKNOWN")))
    print("\nby gate:", dict(by_gate))
    print("top reasons:", dict(by_reason.most_common(12)))
    print(f"\n{'region':<16}{'eval':>6}{'elig':>7}{'inelig':>8}{'review':>8}"
          "  top reasons")
    for c, d in sorted(per_country.items(), key=lambda kv: -kv[1]["evaluated"]):
        top = ", ".join(f"{r}:{n}" for r, n in list(d["reasons"].items())[:3])
        print(f"{c:<16}{d['evaluated']:>6}{d['ELIGIBLE']:>7}"
              f"{d['INELIGIBLE']:>8}{d['REVIEW_REQUIRED']:>8}  {top}")
    print("\n-- manual review sample --")
    for kind, rows in samples.items():
        for s in rows[:2]:
            print(f"[{kind}] #{s['id']} {str(s['title'])[:30]!r} "
                  f"loc={str(s['location'])[:34]!r} region={s['location_region']} "
                  f"posted={s['posted_date']} -> {s['eligibility_status']}/"
                  f"{s['eligibility_gate']}/{s['eligibility_reason']}")
    print(f"\nsummary → {OUT.relative_to(JS)}  ({summary['duration_s']}s)")
    await db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
