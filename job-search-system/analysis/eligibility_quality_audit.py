"""Stage-3 ELIGIBILITY quality audit — counts + representative samples.

Read-only analysis over a COPY of Basil's real workspace DB. Runs the shipped
Stage-2 + Stage-3 passes, then dumps exact counts by status/gate/reason and a
wide sample of rejected jobs per reason for manual inspection.

Run:
    cd job-search-system/root
    .venv/bin/python -u ../analysis/eligibility_quality_audit.py
"""
from __future__ import annotations

import asyncio
import json
import shutil
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "root"
sys.path.insert(0, str(ROOT))

from app.country_registry import CountryRegistry             # noqa: E402
from app.database import Database                            # noqa: E402
from app.scheduler import run_eligibility_pass, run_location_classification  # noqa: E402

JS = Path(__file__).resolve().parents[1]
SRC_DB = ROOT / "data" / "users" / "1-basil" / "jobagent.db"
OUT = JS / "docs" / "eligibility" / "results" / "quality_audit_raw.json"

SAMPLES_PER_REASON = 12
MAX_MANUAL = 60


def _copy_db() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="elig_audit_")) / "jobagent.db"
    shutil.copy(SRC_DB, tmp)
    for suffix in ("-wal", "-shm"):
        s = Path(str(SRC_DB) + suffix)
        if s.exists():
            shutil.copy(s, Path(str(tmp) + suffix))
    return tmp


async def main() -> int:
    db_path = _copy_db()
    db = Database(str(db_path))
    await db.init()
    registry = CountryRegistry(str(ROOT / "config" / "countries")).load()
    await db.update_allowed_regions(registry.enabled_region_names() + ["Remote"])

    await run_location_classification(db, ai_client=None)
    await run_eligibility_pass(db, registry, force=True, limit=5000)

    cur = await db.db.execute(
        "SELECT id, title, company, location, location_region, country_code, "
        "classification_confidence, classification_source, supported_countries, "
        "posted_date, description, apply_url, url, dismissed, strategy_dismissed, "
        "eligibility_status, eligibility_gate, eligibility_reason, "
        "eligibility_evidence, freshness_evidence "
        "FROM jobs WHERE eligibility_status IS NOT NULL")
    rows = [dict(r) for r in await cur.fetchall()]
    total = len(rows)

    by_status = Counter(r["eligibility_status"] for r in rows)
    by_gate = Counter(r["eligibility_gate"] for r in rows)
    by_reason = Counter(r["eligibility_reason"] for r in rows)

    # reason -> {gate: count, status: count, samples: [...]}
    detail = defaultdict(lambda: {"count": 0, "gate": Counter(),
                                  "status": Counter(), "samples": []})
    for r in rows:
        d = detail[r["eligibility_reason"]]
        d["count"] += 1
        d["gate"][r["eligibility_gate"]] += 1
        d["status"][r["eligibility_status"]] += 1
        if len(d["samples"]) < SAMPLES_PER_REASON:
            d["samples"].append({
                "id": r["id"], "title": (r["title"] or "")[:60],
                "company": (r["company"] or "")[:34],
                "location": (r["location"] or "")[:70],
                "region": r["location_region"], "country_code": r["country_code"],
                "confidence": r["classification_confidence"],
                "source": r["classification_source"],
                "supported_countries": r["supported_countries"],
                "posted_date": r["posted_date"],
                "desc_len": len(r["description"] or ""),
                "url": bool(r["url"]), "apply_url": r["apply_url"],
                "dismissed": r["dismissed"],
                "strategy_dismissed": r["strategy_dismissed"],
                "freshness": json.loads(r["freshness_evidence"] or "{}") if r["freshness_evidence"] else None,
                "gate": r["eligibility_gate"],
                "status": r["eligibility_status"],
            })

    # Remote / bucket / multi-location subsets (priority review areas)
    def subset(pred):
        return [r for r in rows if pred(r)]

    remote = subset(lambda r: r["location_region"] in
                    ("GLOBAL", "APAC", "EMEA", "EUROPE", "LATAM", "MENA",
                     "NORTH_AMERICA") or r["country_code"] is None)
    with_supported = subset(lambda r: r["supported_countries"])

    # --- scoreable contract checks -------------------------------------
    scoreable = await db.get_scoreable_jobs(limit=5000)
    scoreable_ids = {j["id"] for j in scoreable}
    leaked_ineligible = [r["id"] for r in rows
                         if r["id"] in scoreable_ids
                         and r["eligibility_status"] != "ELIGIBLE"]
    eligible_missing = [r["id"] for r in rows
                        if r["eligibility_status"] == "ELIGIBLE"
                        and r["id"] not in scoreable_ids]

    # --- Critical Test #3: DATE_UNKNOWN never fresh ---------------------
    cur2 = await db.db.execute(
        "SELECT id, freshness_evidence FROM jobs WHERE eligibility_reason='POSTED_DATE_UNKNOWN'")
    bad_3 = [r[0] for r in await cur2.fetchall()
             if r[1] and json.loads(r[1]).get("state") == "VERIFIED_FRESH"]
    # every DATE_UNKNOWN row must NOT be scoreable either
    du_ids = [r["id"] for r in rows if r["eligibility_reason"] == "POSTED_DATE_UNKNOWN"]
    du_scoreable = [i for i in du_ids if i in scoreable_ids]

    raw = {
        "total_evaluated": total,
        "by_status": dict(by_status),
        "by_gate": dict(by_gate),
        "by_reason": dict(by_reason.most_common()),
        "reason_detail": {k: {"count": v["count"],
                              "gate": dict(v["gate"]),
                              "status": dict(v["status"]),
                              "samples": v["samples"]}
                          for k, v in sorted(detail.items(),
                                             key=lambda kv: -kv[1]["count"])},
        "remote_or_no_country_subset": len(remote),
        "multi_country_subset": len(with_supported),
        "contract": {
            "scoreable_total": len(scoreable_ids),
            "leaked_ineligible_count": len(leaked_ineligible),
            "leaked_ineligible_ids": leaked_ineligible[:20],
            "eligible_missing_from_scoreable": len(eligible_missing),
            "eligible_missing_ids": eligible_missing[:20],
            "date_unknown_wrongly_fresh": len(bad_3),
            "date_unknown_scoreable": len(du_scoreable),
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(raw, indent=2, default=str))

    def pct(n):
        return f"{100.0 * n / total:.1f}%" if total else "0%"

    print("=" * 76)
    print("STAGE-3 ELIGIBILITY QUALITY AUDIT — exact counts")
    print("=" * 76)
    print(f"total evaluated: {total}")
    print("\nBY STATUS")
    for k in ("ELIGIBLE", "INELIGIBLE", "REVIEW_REQUIRED", "UNKNOWN"):
        n = by_status.get(k, 0)
        print(f"  {k:<20}{n:>6}  {pct(n)}")
    print("\nBY GATE")
    for k, n in by_gate.most_common():
        print(f"  {k:<24}{n:>6}  {pct(n)}")
    print("\nBY REASON")
    for k, n in by_reason.most_common():
        print(f"  {k:<34}{n:>6}  {pct(n)}")
    print(f"\nremote/bucket/no-country rows: {len(remote)}")
    print(f"multi-country rows: {len(with_supported)}")
    print("\nCONTRACT CHECKS")
    print(f"  scoreable returned: {raw['contract']['scoreable_total']}")
    print(f"  INELIGIBLE/REVIEW leaked into scoreable: "
          f"{raw['contract']['leaked_ineligible_count']}")
    print(f"  ELIGIBLE missing from scoreable: "
          f"{raw['contract']['eligible_missing_from_scoreable']}")
    print(f"  DATE_UNKNOWN rows wrongly VERIFIED_FRESH: "
          f"{raw['contract']['date_unknown_wrongly_fresh']}")
    print(f"  DATE_UNKNOWN rows in scoreable: "
          f"{raw['contract']['date_unknown_scoreable']}")
    print(f"\nraw → {OUT.relative_to(JS)}")
    await db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
