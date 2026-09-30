"""Stage-1 discovery upgrade — LIVE smoke test + report generator (all 10 countries).

For every enabled country, runs the REAL discovery orchestrator (the exact
code the server runs) over live HTTP with the full registered adapter set,
then emits the machine-readable Stage-1 reports:

    docs/discovery/results/discovery_summary.json     ← global summary
    docs/discovery/results/country_coverage.json      ← per-country buckets
    docs/discovery/results/source_health.json         ← per-pass health records
    docs/discovery/results/countries/<CODE>.json      ← bounded per-country sample
    docs/discovery/SOURCE_HEALTH.md                   ← generated from the JSON
    docs/discovery/COUNTRY_SOURCE_MATRIX.md           ← generated from the JSON

Honesty rules (task §38/§51): all counts come from runtime output; keyed
sources without credentials report CONFIGURATION_REQUIRED; a crashed country
is recorded, never silently skipped. NO credentials are written to reports.

Run (server may be running or not — this drives the orchestrator in-process):
    cd job-search-system/root
    setsid nohup .venv/bin/python -u ../analysis/discovery_upgrade_smoke.py \
        > /tmp/discovery_upgrade_smoke.log 2>&1 < /dev/null &
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

from app.adapters import ALL_ADAPTERS                        # noqa: E402
from app.country_registry import CountryRegistry             # noqa: E402
from app.database import Database                            # noqa: E402
from app.discovery import run_discovery_cycle                # noqa: E402
from app import source_registry as sr                        # noqa: E402
from app.location_classifier import classify_location_rule_based  # noqa: E402
from app.routers.discovery import _env_scraper_keys          # noqa: E402

DOCS = Path(__file__).resolve().parents[1] / "docs" / "discovery"
RESULTS = DOCS / "results"
COUNTRIES_DIR = RESULTS / "countries"
SAMPLE_SIZE = 12          # jobs per country sample (bounded, task §43)
PASSES_PER_COUNTRY = len(ALL_ADAPTERS)   # one term × all adapters

KEYED_SOURCES = {"jooble", "adzuna", "reed"}

# Sources to re-verify after the builtin.com JSON-LD fixes (entity-encoded
# type + @graph-wrapped JobPosting). Set to [] for a full 10-country sweep.
REVERIFY_SOURCES: list[str] = []


class FocusedRegistry:
    """Expose exactly ONE enabled country per sweep (real YAMLs untouched)."""

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


def sample_job(db, job_id: int) -> dict | None:
    """One bounded, secret-free sample record for the country report."""

    async def _fetch():
        row = await db.db.execute(
            """SELECT j.id, j.title, j.company, j.location, j.posted_date,
                      j.url, j.canonical_source, j.source_types, j.created_at
               FROM jobs j WHERE j.id = ?""", (job_id,))
        r = await row.fetchone()
        return dict(r) if r else None

    try:
        return asyncio.get_event_loop().run_until_complete(_fetch())
    except RuntimeError:
        return asyncio.new_event_loop().run_until_complete(_fetch())


async def main() -> int:
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    RESULTS.mkdir(parents=True, exist_ok=True)
    COUNTRIES_DIR.mkdir(parents=True, exist_ok=True)

    registry = CountryRegistry(str(ROOT / "config" / "countries")).load()
    enabled = {c.code: c for c in registry.enabled_countries()}
    codes = sorted(enabled)
    print("=" * 78)
    print(f"STAGE-1 DISCOVERY UPGRADE SMOKE — {len(codes)} countries, LIVE")
    print("=" * 78)

    # Fresh throwaway DB — a smoke test must not disturb Basil's real pool.
    db_path = ROOT / "data" / f"discovery_smoke_{int(time.time())}.db"
    db = Database(str(db_path))
    await db.init()
    await db.update_allowed_regions(
        registry.enabled_region_names() + ["Remote"])

    keys = await db.get_scraper_keys()
    env = load_env_file(ROOT / ".env")
    adapters = ALL_ADAPTERS
    if REVERIFY_SOURCES:
        adapters = [cls for cls in ALL_ADAPTERS
                    if cls.source_name in set(REVERIFY_SOURCES)]
        print(f"REVERIFY mode: only {sorted(REVERIFY_SOURCES)}")
    for name, entry in _env_scraper_keys().items():
        keys.setdefault(name, entry)
    # env-file fallback (the router reads os.environ; in-process we read .env)
    if env.get("JOBAGENT_JOOBLE_API_KEY"):
        keys.setdefault("jooble", {"api_key": env["JOBAGENT_JOOBLE_API_KEY"], "email": ""})
    if env.get("JOBAGENT_ADZUNA_APP_KEY"):
        keys.setdefault("adzuna", {"api_key": env["JOBAGENT_ADZUNA_APP_KEY"], "email": ""})
        keys.setdefault("adzuna-id", {"api_key": env.get("JOBAGENT_ADZUNA_APP_ID", ""), "email": ""})
    if env.get("JOBAGENT_REED_API_KEY"):
        keys.setdefault("reed", {"api_key": env["JOBAGENT_REED_API_KEY"], "email": ""})
    print(f"keys present: {sorted(k for k, v in keys.items() if v)}")

    terms = ["AI Engineer", "Machine Learning Engineer"]
    all_countries = []
    all_health: list[dict] = []
    t0 = time.monotonic()

    for code in codes:
        country = enabled[code]
        print(f"\n── {code} ({country.region}) ─────────────────────────")
        try:
            telemetry = await run_discovery_cycle(
                db, FocusedRegistry(country), adapters,
                max_passes=len(adapters), scraper_keys=keys)
        except Exception as e:
            telemetry = {"passes": [], "source_health": [],
                         "new_jobs": 0, "duplicates_seen": 0,
                         "crashed": str(e)[:200]}
            print(f"  CRASHED: {str(e)[:120]}")

        health = telemetry.get("source_health", [])
        all_health.extend(health)
        passes = telemetry.get("passes", [])

        # sample of this country's ingested jobs (bounded)
        row = await db.db.execute(
            """SELECT j.id, j.title, j.company, j.location, j.posted_date,
                      j.url, j.canonical_source, j.source_types
               FROM jobs j
               ORDER BY j.id DESC LIMIT ?""", (SAMPLE_SIZE,))
        sample = [dict(r) for r in await row.fetchall()]

        statuses = {}
        for h in health:
            statuses[h["status"]] = statuses.get(h["status"], 0) + 1
        by_source = {p["source"]: {"found": p.get("found", 0),
                                   "ingested": p.get("ingested", 0),
                                   "status": p.get("health_status",
                                                   p.get("stop_reason", ""))}
                     for p in passes}

        country_rec = {
            "code": code,
            "region": country.region,
            "sources_attempted": len(health),
            "raw_jobs": sum(h["raw_jobs"] for h in health),
            "unique_jobs": sum(h["valid_jobs"] for h in health),
            "duplicates": sum(h["duplicates"] for h in health),
            "new_jobs_total_pool": telemetry.get("new_jobs", 0),
            "by_status": statuses,
            "by_source": by_source,
            "coverage_buckets": sr.coverage_summary(code),
            "coverage_status": sr.coverage_status(code),
            "duration_s": telemetry.get("duration_s"),
            "crashed": telemetry.get("crashed"),
        }
        all_countries.append(country_rec)
        print(f"  sources={len(health)} raw={country_rec['raw_jobs']} "
              f"unique={country_rec['unique_jobs']} status={statuses}")

        country_payload = {
            **country_rec,
            "generated_at": started,
            "search_terms": terms,
            "sample_jobs": [
                {k: job.get(k) for k in
                 ("id", "title", "company", "location", "posted_date", "url",
                  "canonical_source", "source_types")}
                for job in sample],
        }
        (COUNTRIES_DIR / f"{code}.json").write_text(
            json.dumps(country_payload, indent=2, default=str))

    duration = round(time.monotonic() - t0, 1)

    # ---------------- machine-readable reports ----------------
    global_summary = {
        "generated_at": started,
        "countries": codes,
        "adapters": [cls.source_name for cls in adapters],
        "registry_sources": sr.to_dict(),
        "totals": {
            "sources_attempted": sum(c["sources_attempted"] for c in all_countries),
            "sources_successful": sum(
                c["by_status"].get("PASS", 0) for c in all_countries),
            "raw_jobs": sum(c["raw_jobs"] for c in all_countries),
            "unique_jobs": sum(c["unique_jobs"] for c in all_countries),
            "duplicates_removed": sum(c["duplicates"] for c in all_countries),
            "duration_s": duration,
        },
        "by_status": sr._count_by_status(
            [sr.SourceRunHealth(**{"country": h["country"], "source": h["source"],
                                   "source_type": h.get("source_type", ""),
                                   "raw_jobs": h.get("raw_jobs", 0),
                                   "parsed_jobs": h.get("parsed_jobs", 0),
                                   "valid_jobs": h.get("valid_jobs", 0),
                                   "duplicates": h.get("duplicates", 0),
                                   "errors": h.get("errors", ""),
                                   "status": h.get("status", ""),
                                   "duration_ms": h.get("duration_ms", 0)})
             for h in all_health]),
    }
    (RESULTS / "discovery_summary.json").write_text(
        json.dumps(global_summary, indent=2, default=str))
    (RESULTS / "country_coverage.json").write_text(json.dumps(
        {"generated_at": started,
         "countries": all_countries,
         "category_counts_global": sr.category_counts()}, indent=2, default=str))
    (RESULTS / "source_health.json").write_text(json.dumps(
        {"generated_at": started, "runs": all_health}, indent=2, default=str))
    (RESULTS / "ats_coverage.json").write_text(json.dumps(
        {"generated_at": started,
         "rules": ats_rules_summary(),
         "adapters": [cls.source_name for cls in adapters]}, indent=2))

    # ---------------- generated Markdown ----------------
    write_source_health_md(global_summary, all_countries)
    write_country_matrix_md(all_countries)

    print("\n" + "=" * 78)
    print(f"DONE in {duration}s — reports in docs/discovery/")
    print(f"by_status: {global_summary['by_status']}")
    for c in all_countries:
        print(f"  {c['code']}: raw={c['raw_jobs']} unique={c['unique_jobs']} "
              f"{c['coverage_status']}")
    print("=" * 78)

    await db.close()
    db_path.unlink(missing_ok=True)
    return 0


def ats_rules_summary() -> list[dict]:
    from app.ats_detect import rules_summary
    return rules_summary()


def write_source_health_md(summary: dict, countries: list[dict]) -> None:
    lines = [
        "# SOURCE HEALTH — Stage-1 discovery upgrade (generated)",
        "",
        f"Generated: {summary['generated_at']} · countries: "
        f"{', '.join(summary['countries'])}",
        "",
        "## Status counts (all passes, all countries)",
        "",
        "```text",
    ]
    for status, n in summary["by_status"].items():
        lines.append(f"{status:<24}{n}")
    lines += ["```", "", "## Per-country", "",
              "| Country | Attempted | PASS | NO_RESULTS | CONFIG_REQUIRED | FAILED | RATE_LIMITED | N/A |",
              "|---|---|---|---|---|---|---|---|"]
    for c in countries:
        b = c["by_status"]
        lines.append(
            f"| {c['code']} | {c['sources_attempted']} "
            f"| {b.get('PASS', 0)} | {b.get('NO_RESULTS', 0)} "
            f"| {b.get('CONFIGURATION_REQUIRED', 0)} | {b.get('FAILED', 0)} "
            f"| {b.get('RATE_LIMITED', 0)} | {b.get('NOT_APPLICABLE', 0)} |")
    lines += ["", "## Slow sources (top durations, all countries)", ""]
    # read raw runs for durations
    runs_file = RESULTS / "source_health.json"
    if runs_file.exists():
        runs = json.loads(runs_file.read_text())["runs"]
        slow = sorted(runs, key=lambda r: -r.get("duration_ms", 0))[:10]
        lines += ["| Source | Country | Duration (s) | Status |",
                  "|---|---|---|---|"]
        for r in slow:
            lines.append(f"| {r['source']} | {r['country']} "
                         f"| {round(r.get('duration_ms', 0) / 1000, 1)} "
                         f"| {r.get('status', '')} |")
    (DOCS / "SOURCE_HEALTH.md").write_text("\n".join(lines) + "\n")


def write_country_matrix_md(countries: list[dict]) -> None:
    lines = [
        "# COUNTRY SOURCE MATRIX — Stage-1 discovery upgrade (generated)",
        "",
        "Coverage buckets per country from the source registry; job counts",
        "from the live smoke run (see results/country_coverage.json).",
        "",
        "| Country | Status | ATS | Local | Global | Tech/Startup | Gov | Remote | Aggregator | Sources attempted | Unique jobs |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for c in countries:
        b = c["coverage_buckets"]
        lines.append(
            f"| {c['code']} | {c['coverage_status']} "
            f"| {b.get('ATS', 0)} | {b.get('LOCAL', 0)} | {b.get('GLOBAL', 0)} "
            f"| {b.get('TECH_STARTUP', 0)} | {b.get('GOVERNMENT', 0)} "
            f"| {b.get('REMOTE', 0)} | {b.get('AGGREGATOR', 0)} "
            f"| {c['sources_attempted']} | {c['unique_jobs']} |")
    (DOCS / "COUNTRY_SOURCE_MATRIX.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
