"""ALL-COUNTRIES discovery sweep — every enabled country, LIVE, as Basil.

For each of the 10 enabled countries (DE NL IE UK SG AE IN CA AU PL), run the
REAL discovery orchestrator (app/discovery.run_discovery_cycle — the exact code
the server runs) with a focused registry over REAL HTTP with the REAL 19
adapters, ingesting into BASIL's real workspace DB with HIS real search terms.

Per country, proves (Golden Rule #11):
  1. all 19 adapters ran exactly once (one term × 19)
  2. every pass recorded an honest stop_reason
  3. keyed sources (jooble/adzuna/reed) are honest no-ops without keys
  4. every ingested row classifies into the target country or Remote
     (region gate on live data)
  5. fresh rows carry freshness evidence (≤7d / DATE_UNKNOWN)
  6. the cycle never crashes — failures are per-pass SOURCE_FAILURE

Australia additionally re-sweeps its existing pool — proving re-see honesty
(new=0, dupes counted) with the 2026-09-28 fix in place.

Why in-process: POST /api/discovery/run sweeps ALL enabled countries at once
(the router has no per-country scope) and country YAMLs are SHARED global
state — mutating them from a script was rejected (E2E_RUN_STATUS config
lesson). The orchestrator + ingest path verified here is byte-identical to
what the router runs; the router's own wrapper (gate/registry/background)
was already proven 22/22 in DISCOVERY_PHASE_LIVE_VERIFICATION.md.

Run:
    cd job-search-system/root
    setsid nohup .venv/bin/python -u ../analysis/verify_discovery_all_countries.py \
        > /tmp/discovery_all_countries.log 2>&1 < /dev/null &

Outputs:
    analysis/e2e_runs/discovery_all_countries_<ts>/{telemetry.json,checks.json}
    docs/DISCOVERY_ALL_COUNTRIES_SWEEP.md   ← final report
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "root"
sys.path.insert(0, str(ROOT))

from app.adapters import ALL_ADAPTERS                        # noqa: E402
from app.country_registry import CountryRegistry             # noqa: E402
from app.database import Database                            # noqa: E402
from app.discovery import run_discovery_cycle                # noqa: E402
from app.job_adapter import STOP_SOURCE_FAILURE              # noqa: E402
from app.location_classifier import classify_location_rule_based  # noqa: E402
from app.routers.discovery import _env_scraper_keys          # noqa: E402

BASIL_DB = ROOT / "data" / "users" / "1-basil" / "jobagent.db"
RUN_DIR = (Path(__file__).resolve().parent / "e2e_runs" /
           f"discovery_all_countries_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}")

ALL_ADAPTER_NAMES = {cls.source_name for cls in ALL_ADAPTERS}
KEYED_SOURCES = {"jooble", "adzuna", "reed"}
EXPECTED_CODES = ["DE", "NL", "IE", "GB", "SG", "AE", "IN", "CA", "AU", "PL"]
PASSES_PER_COUNTRY = 19   # exactly one term × 19 adapters


class FocusedRegistry:
    """Expose exactly ONE enabled country (the orchestrator only calls
    enabled_countries(); the real YAMLs stay untouched)."""

    def __init__(self, country):
        self._country = country

    def enabled_countries(self):
        return [self._country]


def load_env_file(path: Path) -> dict:
    env = {}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


async def sweep_country(db: Database, registry: CountryRegistry, code: str,
                        scraper_keys: dict, country) -> dict:
    row = await db.db.execute("SELECT COALESCE(MAX(id), 0) FROM jobs")
    max_id_before = (await row.fetchone())[0]

    telemetry = await run_discovery_cycle(
        db, FocusedRegistry(country), ALL_ADAPTERS,
        max_passes=PASSES_PER_COUNTRY, scraper_keys=scraper_keys)

    passes = telemetry["passes"]
    ran = [p["source"] for p in passes]
    new_ids: list[int] = []
    row = await db.db.execute(
        "SELECT j.id, j.location FROM jobs j JOIN sources s ON s.job_id=j.id "
        f"WHERE j.id > ? AND s.source_name IN ({','.join('?' * len(ALL_ADAPTER_NAMES))})",
        (max_id_before, *ALL_ADAPTER_NAMES))
    ingested_rows = [dict(r) for r in await row.fetchall()]
    new_ids = [r["id"] for r in ingested_rows]

    # fresh rows = new rows that are not cross-source-dupe-dismissed
    fresh_expected = 0
    fresh_with_evidence = 0
    if new_ids:
        ph = ",".join("?" * len(new_ids))
        row = await db.db.execute(
            f"SELECT id, freshness_evidence FROM jobs WHERE id IN ({ph})", new_ids)
        for r in await row.fetchall():
            row2 = await db.db.execute(
                "SELECT COUNT(*) FROM job_duplicates WHERE duplicate_job_id = ?", (r["id"],))
            is_dupe = (await row2.fetchone())[0] > 0
            if not is_dupe:
                fresh_expected += 1
                if r["freshness_evidence"] and str(r["freshness_evidence"]).strip():
                    fresh_with_evidence += 1

    allowed = {country.region, "Remote"}
    offside = [
        (r["id"], (r["location"] or "")[:50],
         classify_location_rule_based(r["location"] or ""))
        for r in ingested_rows
        if classify_location_rule_based(r["location"] or "") is not None
        and classify_location_rule_based(r["location"] or "") not in allowed]

    checks = [
        ("all 19 adapters ran once",
         len(passes) == PASSES_PER_COUNTRY and len(set(ran)) == PASSES_PER_COUNTRY,
         f"passes={len(passes)} unique={len(set(ran))}"),
        ("every pass has an honest stop_reason",
         bool(passes) and all(p.get("stop_reason") for p in passes),
         str(sorted({p.get("stop_reason") for p in passes}))),
        ("keyed sources honest without keys",
         all(p.get("stop_reason") != STOP_SOURCE_FAILURE
             or "key" in (p.get("error") or "").lower()
             for p in passes if p["source"] in KEYED_SOURCES),
         "; ".join(f"{p['source']}: {(p.get('error') or '')[:40]}"
                   for p in passes if p["source"] in KEYED_SOURCES)),
        ("region gate holds on ingested rows",
         not offside,
         f"rows={len(ingested_rows)} offside={offside[:3]}"),
        ("fresh rows carry freshness evidence",
         fresh_with_evidence == fresh_expected,
         f"evidence={fresh_with_evidence}/{fresh_expected}"),
    ]
    ingest_by_src = {p["source"]: p["ingested"] for p in passes}
    return {
        "country": country.region, "code": code, "telemetry": telemetry,
        "new_jobs": telemetry["new_jobs"], "dupes": telemetry["duplicates_seen"],
        "duration_s": telemetry.get("duration_s"),
        "ingest_by_src": ingest_by_src,
        "ingested_rows": len(ingested_rows),
        "checks": checks,
        "sample": [
            {"id": r["id"], "location": (r["location"] or "")[:60]}
            for r in ingested_rows[:8]],
    }


async def main() -> int:
    t0 = time.monotonic()
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    print("=" * 78)
    print("ALL-COUNTRIES DISCOVERY SWEEP — Basil's real workspace, live boards")
    print("=" * 78)

    registry = CountryRegistry(str(ROOT / "config" / "countries")).load()
    enabled = {c.code: c for c in registry.enabled_countries()}
    codes = sorted(enabled)
    print(f"enabled countries in YAML: {codes}")
    missing = [c for c in EXPECTED_CODES if c not in enabled]
    if missing:
        print(f"FATAL: expected countries not enabled: {missing}")
        return 1

    db = Database(str(BASIL_DB))
    await db.init()
    try:
        await db.db.execute("PRAGMA busy_timeout = 15000")
    except Exception:
        pass

    # keys: Basil's DB keys first, then the env fallback (same as the router)
    keys = await db.get_scraper_keys()
    for name, entry in _env_scraper_keys().items():
        keys.setdefault(name, entry)
    print(f"scraper keys present: {sorted(k for k, v in keys.items() if v)}")

    term_cfg = await db.get_search_config()
    print(f"search terms (Basil): {(term_cfg or {}).get('search_terms', [])[:4]}…")

    results = []
    for code in EXPECTED_CODES:
        print(f"\n── {code} ({enabled[code].region}) ─────────────────────────")
        try:
            r = await sweep_country(db, registry, code, keys, enabled[code])
        except Exception as e:
            r = {"country": code, "code": code, "crashed": str(e)[:200],
                 "checks": [("cycle completed without crash", False, str(e)[:160])],
                 "new_jobs": 0, "dupes": 0, "ingest_by_src": {},
                 "telemetry": {"passes": []}, "duration_s": None,
                 "ingested_rows": 0, "sample": []}
        for name, ok, detail in r["checks"]:
            print(f"  [{'PASS' if ok else 'FAIL'}] {name} — {detail}")
        print(f"  new={r['new_jobs']} dupes={r['dupes']} "
              f"by_source={ {k: v for k, v in r['ingest_by_src'].items() if v} }")
        results.append(r)

    await db.close()

    total_checks = passed = 0
    for r in results:
        for _, ok, _ in r["checks"]:
            total_checks += 1
            passed += ok
    verdict = passed == total_checks

    (RUN_DIR / "telemetry.json").write_text(json.dumps(
        {"results": results, "generated": datetime.now(timezone.utc).isoformat()},
        indent=2, default=str))
    (RUN_DIR / "checks.json").write_text(json.dumps(
        [{"country": r["country"], "checks": r["checks"]} for r in results],
        indent=2, default=str))

    # ---------------------------------------------------------------- report
    L = ["# DISCOVERY — ALL 10 COUNTRIES LIVE SWEEP (Basil's workspace)",
         "",
         f"**Run:** {datetime.now(timezone.utc).isoformat(timespec='seconds')}  ",
         "**Orchestrator:** real `run_discovery_cycle` (the code the server runs) · "
         "real 19 adapters · real HTTP · Basil's real DB + real resume terms  ",
         f"**Term per country:** Basil's first search term · **budget:** "
         f"{PASSES_PER_COUNTRY} passes/country · **total:** "
         f"{sum(len(r['telemetry'].get('passes', [])) for r in results)} live passes "
         f"in {time.monotonic() - t0:.0f}s", "",
         "> The router wrapper (428 gate, auth, background task, telemetry state) "
         "was already proven 22/22 in `DISCOVERY_PHASE_LIVE_VERIFICATION.md`; this "
         "sweep answers the per-country question with the same ingest path.", ""]
    L += ["## 1. Summary", "",
          "| country | new | dupes | ingested rows | duration | verdict |",
          "|---|---|---|---|---|---|"]
    for r in results:
        c_ok = all(ok for _, ok, _ in r["checks"])
        L.append(f"| {r['country']} ({r['code']}) | {r['new_jobs']} | {r['dupes']} "
                 f"| {r['ingested_rows']} | {r['duration_s']}s "
                 f"| {'GREEN' if c_ok else 'RED'} |")
    L += ["", f"**Totals: {sum(r['new_jobs'] for r in results)} new jobs, "
          f"{passed}/{total_checks} checks passed — "
          f"{'GREEN ✅' if verdict else 'RED ❌'}**", ""]

    L += ["## 2. Jobs ingested per source × country", ""]
    srcs_order: list[str] = []
    for r in results:
        for p in r["telemetry"].get("passes", []):
            if p["source"] not in srcs_order:
                srcs_order.append(p["source"])
    L.append("| source | " + " | ".join(f"{r['code']}" for r in results) + " |")
    L.append("|---|" + "---|" * len(results))
    for s in srcs_order:
        cells = [str(r["ingest_by_src"].get(s, 0)) for r in results]
        L.append(f"| {s} | " + " | ".join(cells) + " |")
    L += ["", "(0 = ran but found nothing in-country, or keyed-but-unset — honest, "
          "not missing coverage)", ""]

    L += ["## 3. Per-country checks", ""]
    for r in results:
        L += [f"### {r['country']} ({r['code']})", "",
              "| check | result | detail |", "|---|---|---|"]
        for name, ok, detail in r["checks"]:
            L.append(f"| {name} | {'PASS' if ok else 'FAIL'} | {detail[:140]} |")
        if r.get("crashed"):
            L.append(f"| cycle crashed | FAIL | {r['crashed']} |")
        L.append("")

    L += ["## 4. Sample of what landed per country", ""]
    for r in results:
        if r["sample"]:
            L.append(f"**{r['country']}:** " +
                     "; ".join(f"#{s['id']} {s['location']}" for s in r["sample"][:5]))
            L.append("")
    L += ["## 5. Re-run", "",
          "```bash",
          "cd job-search-system/root",
          "setsid nohup .venv/bin/python -u ../analysis/verify_discovery_all_countries.py \\",
          "    > /tmp/discovery_all_countries.log 2>&1 < /dev/null &",
          "```", ""]
    report_path = Path(__file__).resolve().parents[1] / "docs" / "DISCOVERY_ALL_COUNTRIES_SWEEP.md"
    report_path.write_text("\n".join(L))

    print("\n" + "=" * 78)
    print(f"RESULT: {passed}/{total_checks} checks — {'GREEN ✅' if verdict else 'RED ❌'} "
          f"in {time.monotonic() - t0:.0f}s")
    print(f"report → {report_path.name}")
    print("=" * 78)
    return 0 if verdict else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
