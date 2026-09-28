"""E2E (live): discovery expansion — new sponsor countries + 11 new adapters.

Runs the REAL discovery orchestrator (app/discovery.run_discovery_cycle) with
the REAL 15 adapters over REAL HTTP against a real temporary SQLite DB,
scoped to the sponsor-heavy countries added in this session:
Canada, Australia, Poland (+ India from the earlier step).

What it proves (Golden Rule #11 — verified through the running system):
  1. run_discovery_cycle ingests REAL jobs into the DB for each new country.
  2. The 9 keyless adapters work against their live APIs (honest telemetry).
  3. The 2 keyed adapters (jooble/adzuna) degrade HONESTLY without keys —
     SOURCE_FAILURE with a clear message, no crash, no bar-lowering.
  4. Every adapter appears in telemetry exactly once per term (registration).
  5. Every ingested job classifies into the target country or Remote
     (the region gate holds on live data).

Usage:
    root/.venv/bin/python analysis/e2e_discovery_expansion.py
Exit code 0 = every check passes.

Outputs:
  analysis/e2e_runs/discovery_expansion_<ts>/telemetry.json
  docs/E2E_DISCOVERY_EXPANSION_REPORT.md
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "root"
sys.path.insert(0, str(ROOT))

from app.adapters import ALL_ADAPTERS                       # noqa: E402
from app.country_registry import CountryRegistry            # noqa: E402
from app.database import Database                           # noqa: E402
from app.discovery import run_discovery_cycle               # noqa: E402
from app.job_adapter import STOP_SOURCE_FAILURE             # noqa: E402
from app.location_classifier import classify_location_rule_based  # noqa: E402

COUNTRIES_UNDER_TEST = ["Canada", "Australia", "Poland", "India",
                        "Singapore", "UAE"]
NEW_SOURCE_NAMES = {
    "jooble", "adzuna", "reed", "arbeitnow", "remotive", "jobicy",
    "weworkremotely", "remoteok", "himalayas", "4dayweek",
    "landingjobs", "recruitee", "mycareersfuture", "wellfound",
    "workingnomads",
}
KEYED_SOURCES = {"jooble", "adzuna", "reed"}
PASSES_PER_COUNTRY = 19   # one search term × 19 adapters, exact fit


class FocusedRegistry:
    """A registry exposing exactly ONE enabled country (the orchestrator only
    calls enabled_countries(); everything else stays in the real YAMLs)."""

    def __init__(self, country):
        self._country = country

    def enabled_countries(self):
        return [self._country]


async def health_probes() -> tuple[dict, list[str]]:
    """Probe every NEW adapter; return (health_by_source, failures)."""
    health, failures = {}, []
    for cls in ALL_ADAPTERS:
        if cls.source_name not in NEW_SOURCE_NAMES:
            continue
        try:
            h = await asyncio.wait_for(cls().health_check(), timeout=30)
        except asyncio.TimeoutError:
            h = {"source": cls.source_name, "ok": False, "error": "health probe timeout"}
        except Exception as e:  # probe must never kill the run
            h = {"source": cls.source_name, "ok": False, "error": str(e)[:120]}
        health[cls.source_name] = h
        expected_ok = cls.source_name not in KEYED_SOURCES
        if expected_ok and not h.get("ok"):
            failures.append(f"{cls.source_name}: {h.get('error') or h.get('status')}")
        print(f"  health {cls.source_name:<16} ok={h.get('ok')} {h.get('error', '')[:70]}")
    return health, failures


async def run_country(db: Database, country) -> dict:
    # Snapshot the job-table high-water mark so the row audit below only
    # examines jobs ingested by THIS cycle (not earlier countries' rows).
    row = await db.db.execute("SELECT COALESCE(MAX(id), 0) FROM jobs")
    max_id_before = (await row.fetchone())[0]

    telemetry = await run_discovery_cycle(
        db, FocusedRegistry(country), ALL_ADAPTERS, max_passes=PASSES_PER_COUNTRY)

    checks: list[tuple[str, bool, str]] = []

    # 1. all 19 adapters ran exactly once (one term budget)
    passes = telemetry["passes"]
    ran = [p["source"] for p in passes]
    checks.append(("all 19 adapters ran", len(passes) == 19 and len(set(ran)) == 19,
                   f"ran={len(passes)}"))
    # 1b. region-hint sources skip other countries honestly (2 of them:
    #     reed→UK, mycareersfuture→Singapore) unless this IS their country.
    hint = {"reed": "UK", "mycareersfuture": "Singapore"}
    for p in passes:
        if p["source"] in hint and p["source"].lower() not in ("",):
            expected_country = hint[p["source"]]
            if country.region != expected_country:
                honest_skip = (p["stop_reason"] == "NO_MORE_RESULTS"
                               and p["found"] == 0
                               and "only" in (p.get("error") or ""))
                checks.append((f"{p['source']} honest skip for {country.region}",
                               honest_skip, f"err={p.get('error', '')[:40]}"))

    # 2. keyed adapters degrade honestly without keys
    for p in passes:
        if p["source"] in KEYED_SOURCES:
            honest = (p["stop_reason"] == STOP_SOURCE_FAILURE
                      and "key" in (p.get("error") or "").lower())
            checks.append((f"keyed {p['source']} honest no-op", honest,
                           f"stop={p['stop_reason']} err={p.get('error', '')[:50]}"))

    # 3. real jobs ingested (keyless sources only)
    keyless_new = sum(p["ingested"] for p in passes if p["source"] not in KEYED_SOURCES)
    checks.append((f"real jobs ingested for {country.region}", keyless_new > 0,
                   f"new={keyless_new}"))

    # 4. region gate on live data: every ingested job classifies to the
    #    country or Remote (audit of what actually landed in the DB)
    row = await db.db.execute(
        """SELECT j.location FROM jobs j JOIN sources s ON s.job_id = j.id
           WHERE j.id > ? AND s.source_name IN ({})""".format(",".join("?" * len(NEW_SOURCE_NAMES))),
        (max_id_before, *NEW_SOURCE_NAMES))
    locations = [r["location"] for r in await row.fetchall()]
    allowed = {country.region, "Remote"}
    offside = [loc for loc in locations
               if classify_location_rule_based(loc or "") not in allowed]
    checks.append(("region gate holds on ingested rows", not offside,
                   f"checked={len(locations)} offside={len(offside)}"
                   + (f" e.g. {offside[:3]}" if offside else "")))

    return {"country": country.region, "telemetry": telemetry,
            "keyless_new": keyless_new, "checks": checks,
            "locations_sample": locations[:10]}


def write_report(results: list[dict], health: dict, health_failures: list[str],
                 run_dir: Path) -> tuple[int, int]:
    total_checks = passed = 0
    lines = ["# E2E DISCOVERY EXPANSION REPORT — live verification",
             "",
             f"**Run:** {datetime.now(timezone.utc).isoformat(timespec='seconds')}  ",
             f"**Countries:** {', '.join(r['country'] for r in results)}  ",
             "**Orchestrator:** real `run_discovery_cycle` · real 15 adapters · "
             "real HTTP · real temp SQLite DB", ""]
    lines += ["## Health probes (new adapters, live)",
              "", "| source | ok | note |", "|---|---|---|"]
    for src, h in health.items():
        lines.append(f"| {src} | {h.get('ok')} | {(h.get('error') or h.get('status') or '')[:80]} |")
    lines.append("")

    for r in results:
        lines += [f"## {r['country']}", "",
                  f"**Real jobs ingested (keyless sources):** {r['keyless_new']}", "",
                  "| check | result | detail |", "|---|---|---|"]
        for name, ok, detail in r["checks"]:
            total_checks += 1
            passed += ok
            lines.append(f"| {name} | {'PASS' if ok else 'FAIL'} | {detail} |")
        lines += ["", "Per-source telemetry:", "",
                  "| source | stop_reason | found | ingested | dupes | error |",
                  "|---|---|---|---|---|---|"]
        for p in r["telemetry"]["passes"]:
            lines.append(f"| {p['source']} | {p['stop_reason']} | {p['found']} | "
                         f"{p['ingested']} | {p['duplicates']} | {(p.get('error') or '')[:60]} |")
        lines.append("")
        if r["locations_sample"]:
            lines += ["Sample locations ingested:", ""]
            lines += [f"- {loc}" for loc in r["locations_sample"]]
            lines.append("")

    if health_failures:
        lines += ["## Health failures (keyless adapters that did NOT answer)",
                  ""] + [f"- {f}" for f in health_failures] + [""]

    verdict = (total_checks == passed and not health_failures)

    # Per-country × source contribution matrix (which sources actually fed
    # each country — the "no missed opportunity" proof Basil asked for).
    sources_order = []
    for r in results:
        for p in r["telemetry"]["passes"]:
            if p["source"] not in sources_order:
                sources_order.append(p["source"])
    ingest_by = {r["country"]: {p["source"]: p["ingested"]
                                for p in r["telemetry"]["passes"]}
                 for r in results}
    lines += ["## Coverage matrix — jobs ingested per source × country", "",
              "| source | " + " | ".join(r["country"] for r in results) + " |",
              "|---|" + "---|" * len(results)]
    for src in sources_order:
        cells = [str(ingest_by[r["country"]].get(src, 0)) for r in results]
        lines.append(f"| {src} | " + " | ".join(cells) + " |")
    lines += ["", "(0 = source ran but found nothing in-country or is keyed-but-unset; "
              "empty pass ≠ missing coverage)", ""]

    lines += ["## Verdict", "",
              f"**{passed}/{total_checks} checks passed, "
              f"{len(health_failures)} keyless health failures** — "
              + ("GREEN ✅" if verdict else "RED ❌"), ""]
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "telemetry.json").write_text(json.dumps(
        {"results": [{k: v for k, v in r.items() if k != "telemetry"} |
                     {"telemetry": r["telemetry"]} for r in results],
         "health": health}, indent=2, default=str))
    report_path = Path(__file__).resolve().parents[1] / "docs" / "E2E_DISCOVERY_EXPANSION_REPORT.md"
    report_path.write_text("\n".join(lines))
    print(f"\nreport → {report_path}")
    return total_checks, passed, verdict


async def main() -> int:
    t0 = time.monotonic()
    registry = CountryRegistry(str(ROOT / "config" / "countries")).load()
    run_dir = (Path(__file__).resolve().parent / "e2e_runs" /
               f"discovery_expansion_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}")
    run_dir.mkdir(parents=True, exist_ok=True)

    print("== Live health probes (new adapters) ==")
    health, health_failures = await health_probes()

    db = Database(str(run_dir / "jobs.db"))
    await db.init()
    await db.update_allowed_regions(COUNTRIES_UNDER_TEST + ["Remote"])

    results = []
    for region in COUNTRIES_UNDER_TEST:
        country = registry.get(region)
        print(f"\n== Discovery cycle: {region} (budget {PASSES_PER_COUNTRY} passes) ==")
        r = await run_country(db, country)
        for name, ok, detail in r["checks"]:
            print(f"  [{'PASS' if ok else 'FAIL'}] {name} — {detail}")
        results.append(r)

    total, passed, verdict = write_report(results, health, health_failures, run_dir)
    row = await db.db.execute("SELECT COUNT(*) FROM jobs")
    all_jobs = (await row.fetchone())[0]
    await db.close()

    print(f"\nDB total jobs after run: {all_jobs}")
    print(f"== {passed}/{total} checks passed — "
          f"{'GREEN' if verdict else 'RED'} in {time.monotonic() - t0:.0f}s ==")
    return 0 if verdict else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
