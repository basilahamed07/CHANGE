"""STAGE-2 CLASSIFY — LIVE validation against the real discovery sample pool.

Runs the REAL `app.classification.classify_job` (+ `detect_conflict`) over the
real jobs captured by the all-countries discovery sweep
(`docs/discovery/results/countries/*.json#sample_jobs`) — the exact rows the
DISCOVER stage pulled from live boards. Sources are real; descriptions are not
carried in the sweep artifact (the classifier's DESCRIPTION tier is covered by
the unit suite), so this script validates the tiers the live rows CAN exercise:
TEXT_LOCATION / CITY_MAP / multi-location / remote / region-only / SOURCE_HINT.

Per country it reports: jobs tested, same-country, other-country, unknown,
remote/hybrid/onsite, AI-fallback (0 by construction — the chain is
deterministic) and any suspicious `search_country != classified_country` rows.

Also runs a curated priority-chain battery IN-PROCESS to prove the documented
rules live (these are the same assertions as tests/test_classification.py, run
here against the shipped module, not a copy).

Run:
    cd job-search-system/root
    .venv/bin/python -u ../analysis/verify_classification_live.py

Outputs:
    docs/classify/results/classification_summary.json
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "root"
sys.path.insert(0, str(ROOT))

from app.classification import classify_job, detect_conflict  # noqa: E402
from app.config import get_settings                          # noqa: E402
from app.country_registry import CountryRegistry             # noqa: E402

JS = Path(__file__).resolve().parents[1]
COUNTRIES_DIR = JS / "docs" / "discovery" / "results" / "countries"
OUT = JS / "docs" / "classify" / "results" / "classification_summary.json"


def _region_of_factory(registry: CountryRegistry):
    code_to_region = {c.code: c.region for c in registry.countries.values()}

    def _region_of(code: str) -> str:
        return code_to_region.get(code) or code

    return _region_of


# --- curated priority-chain battery (runs the shipped module in-process) ----
CURATED = [
    # (label, job, expected country_code, expected region, expected source)
    ("structured country field",
     {"location": "Berlin", "country_code": "DE"}, "DE", "Germany", "STRUCTURED_COUNTRY"),
    ("text location UK alias",
     {"location": "UK"}, "GB", "UK", "TEXT_LOCATION"),
    ("text location UAE alias",
     {"location": "UAE"}, "AE", "UAE", "TEXT_LOCATION"),
    ("city map Berlin",
     {"location": "Berlin"}, "DE", "Germany", "CITY_MAP"),
    ("multi-location primary",
     {"location": "Singapore / London / New York"}, "SG", "Singapore", "TEXT_LOCATION"),
    ("remote explicit country",
     {"location": "Remote - India"}, "IN", "India", "TEXT_LOCATION"),
    ("remote region APAC",
     {"location": "Remote - APAC"}, None, "APAC", "TEXT_LOCATION"),
    ("remote region EMEA",
     {"location": "Remote (EMEA)"}, None, "EMEA", "TEXT_LOCATION"),
    ("remote worldwide",
     {"location": "Remote Worldwide"}, None, "GLOBAL", "TEXT_LOCATION"),
    ("remote bare with residency",
     {"location": "Remote", "description": "Candidates must reside in Germany."},
     "DE", "Germany", "DESCRIPTION"),
    ("description location evidence",
     {"location": "", "description": "Location: Dublin, Ireland - hybrid role"},
     "IE", "Ireland", "DESCRIPTION"),
    ("source hint LOW only",
     {"location": "Nowhereville", "search_country": "SG"},
     "SG", "Singapore", "SOURCE_HINT"),
    ("unconfigured place falls back to source hint (LOW)",
     {"location": "Kuala Lumpur", "search_country": "SG", "description": ""},
     "SG", "Singapore", "SOURCE_HINT"),
    ("source hint never overrides explicit text",
     {"location": "Dublin", "search_country": "SG"},
     "IE", "Ireland", "CITY_MAP"),
    ("honest unknown without any signal",
     {"location": "Nowhereville"}, None, "UNKNOWN", "UNKNOWN"),
    ("hybrid London work type",
     {"location": "London (Hybrid)"}, "GB", "UK", "CITY_MAP"),
]


def run_curated(region_of) -> list[dict]:
    out = []
    for label, job, exp_cc, exp_region, exp_src in CURATED:
        r = classify_job(job, region_of=region_of)
        ok = (r.country_code == exp_cc and r.region == exp_region
              and r.classification_source == exp_src)
        out.append({
            "label": label, "ok": ok,
            "expected": {"country_code": exp_cc, "region": exp_region,
                         "source": exp_src},
            "got": {"country_code": r.country_code, "region": r.region,
                    "source": r.classification_source,
                    "confidence": r.classification_confidence,
                    "work_type": r.remote_type},
        })
    return out


def run_country_samples(region_of) -> dict:
    results = []
    for path in sorted(COUNTRIES_DIR.glob("*.json")):
        data = json.loads(path.read_text())
        code = data.get("code")
        region = data.get("region")
        samples = data.get("sample_jobs") or []
        stats = {
            "code": code, "region": region, "tested": 0,
            "same_country": 0, "other_country": 0, "unknown": 0,
            "remote": 0, "hybrid": 0, "onsite": 0,
            "ai_fallback": 0, "conflicts": 0,
            "by_source": {}, "by_confidence": {},
            "suspicious": [],
        }
        for s in samples:
            stats["tested"] += 1
            job = {"location": s.get("location") or "",
                   "description": s.get("description") or "",
                   "search_country": code, "country_code": None}
            r = classify_job(job, region_of=region_of)
            conflict = detect_conflict(job, r)
            if r.country_code is None:
                stats["unknown"] += 1
            elif r.country_code == code:
                stats["same_country"] += 1
            else:
                stats["other_country"] += 1
                stats["suspicious"].append({
                    "id": s.get("id"), "title": (s.get("title") or "")[:50],
                    "location": job["location"][:60],
                    "search_country": code, "classified_country": r.country_code,
                    "source": r.classification_source,
                    "reason": r.classification_reason,
                })
            if r.remote_type == "REMOTE":
                stats["remote"] += 1
            elif r.remote_type == "HYBRID":
                stats["hybrid"] += 1
            elif r.remote_type == "ONSITE":
                stats["onsite"] += 1
            if r.classification_source == "AI_FALLBACK":
                stats["ai_fallback"] += 1
            if conflict:
                stats["conflicts"] += 1
            stats["by_source"][r.classification_source] = \
                stats["by_source"].get(r.classification_source, 0) + 1
            stats["by_confidence"][r.classification_confidence] = \
                stats["by_confidence"].get(r.classification_confidence, 0) + 1
        results.append(stats)
    return {"countries": results}


def main() -> int:
    registry = CountryRegistry(get_settings().countries_dir).load()
    region_of = _region_of_factory(registry)

    print("=" * 78)
    print("STAGE-2 CLASSIFY — LIVE VALIDATION (real discovery sample pool)")
    print("=" * 78)

    curated = run_curated(region_of)
    c_pass = sum(1 for c in curated if c["ok"])
    print(f"\ncurated priority-chain battery: {c_pass}/{len(curated)} PASS")
    for c in curated:
        if not c["ok"]:
            print(f"  FAIL {c['label']}: expected {c['expected']} got {c['got']}")

    live = run_country_samples(region_of)
    print("\nper-country live sample classification:")
    hdr = f"  {'ctry':<4} {'tested':>6} {'same':>5} {'other':>5} {'unk':>4} " \
          f"{'remote':>7} {'hybr':>5} {'AI':>3} {'conf':>5}"
    print(hdr)
    totals = {"tested": 0, "same_country": 0, "other_country": 0, "unknown": 0,
              "remote": 0, "hybrid": 0, "onsite": 0, "ai_fallback": 0, "conflicts": 0}
    for s in live["countries"]:
        print(f"  {s['code']:<4} {s['tested']:>6} {s['same_country']:>5} "
              f"{s['other_country']:>5} {s['unknown']:>4} {s['remote']:>7} "
              f"{s['hybrid']:>5} {s['ai_fallback']:>3} {s['conflicts']:>5}")
        for k in totals:
            totals[k] += s.get(k, 0)

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_pool": "docs/discovery/results/countries/*.json#sample_jobs",
        "note": ("sweep artifacts carry no description, so the DESCRIPTION tier "
                 "is exercised by the curated battery + unit suite, not the live "
                 "rows. AI_FALLBACK is 0 by construction (deterministic chain, "
                 "ai_client=None)."),
        "curated": {"passed": c_pass, "total": len(curated), "cases": curated},
        "live": {**live, "totals": totals},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(summary, indent=2))
    print(f"\ntotals: {totals}")
    print(f"curated {c_pass}/{len(curated)}; live rows classified "
          f"{totals['tested'] - totals['unknown']}/{totals['tested']} "
          f"({totals['unknown']} honest UNKNOWN)")
    print(f"summary → {OUT.relative_to(JS)}")
    print("=" * 78)
    return 0 if c_pass == len(curated) else 1


if __name__ == "__main__":
    raise SystemExit(main())
