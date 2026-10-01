# STAGE-2 CLASSIFY — Overview

**Status:** COMPLETE (deterministic chain) + bounded AI residue fallback —
E2E/live verified per Golden Rule #11 on 2026-10-01.

Stage-2 CLASSIFY answers exactly one question:

> **Where is this job?** — country, region, city, work type, and *how sure are
> we*, with machine-readable evidence.

It deliberately does **not** decide whether the candidate may work there.
That is Stage-3 EVIDENCE/ELIGIBILITY. CLASSIFY records a country + confidence;
ELIGIBILITY consumes it. Keeping the two apart is what lets an unknown
location stay honestly unknown instead of being silently guessed or dropped.

## Where it sits in the pipeline

```
RESUME → DISCOVER → [CLASSIFY] → SCORE → HYBRID → SELECT → …ELIGIBILITY…
```

CLASSIFY runs as the scheduler pass `app/scheduler.py#run_location_classification`,
invoked by the daily run and by `apply_country_strategy`. It reads every job
with `location_classified = 0`, writes a classification, and marks it
classified so the same job is never re-classified (idempotent).

## What changed (before → after)

| | Before | After |
|---|---|---|
| Output | one region string (`"Germany"` / `"Remote"` / `"Unknown"`) | country code + name + region + city + work type **+ confidence + source + reason + supported countries** |
| Priority | US-centric rules, then a US-centric LLM batch | explicit priority chain (see `CLASSIFICATION_RULES.md`) |
| Source country | could become the answer | **HINT ONLY** — recorded at LOW confidence, never overrides text |
| Remote | collapsed to `"Remote"` | `Remote - India` → IN; `Remote - APAC` → region APAC; `Remote Worldwide` → GLOBAL; bare `Remote` → honest UNKNOWN/GLOBAL |
| Evidence | none persisted | confidence, source, reason, conflict persisted per job |
| Countries | 10 via registry terms merged into a US map | canonical `COUNTRY_ALIASES` for all 10 + city map + region buckets |
| AI | ambiguous residue → US-centric region prompt | **bounded, validated** country fallback — residue only, unconfigured/low-confidence answers rejected |

## Modules

| file | role |
|---|---|
| `app/classification.py` | **the Stage-2 core** — `classify_job`, `classify_job_ai`, `detect_conflict`, `normalize_country_code`, alias/city/region tables |
| `app/scheduler.py#run_location_classification` | drives the pass, persists rows, tracks metrics, dismisses out-of-region |
| `app/database.py` | jobs columns `country_code`, `classification_confidence`, `classification_source`, `classification_reason`, `supported_countries`; `search_config.classification_metrics`; `set_job_classifications_batch`, `set_classification_metrics` |
| `app/location_classifier.py` | **legacy** — `classify_location_rule_based` still used by discovery ingest as a scrape-time prefilter; `classify_locations_llm` retained but no longer on the Stage-2 path |

## Data written per job

| column | example | meaning |
|---|---|---|
| `location_region` | `Germany` / `UK` / `APAC` / `Unknown` | region string the rest of the pipeline already understands |
| `country_code` | `DE` / `GB` / `NULL` | ISO-2 **of configured countries only**, or NULL |
| `classification_confidence` | `HIGH` / `MEDIUM` / `LOW` / `UNKNOWN` | evidence strength |
| `classification_source` | `CITY_MAP` / `TEXT_LOCATION` / `SOURCE_HINT` / `AI_FALLBACK` / … | which tier answered |
| `classification_reason` | `city 'berlin' → DE` | human audit string (conflicts appended) |
| `supported_countries` | `["SG","GB"]` | multi-location listings |

## Docs map

- `CLASSIFICATION_RULES.md` — the priority chain, confidence, aliases, cities, regions, conflicts.
- `CLASSIFY_AUDIT.md` — what the old classifier did, and the specific gaps closed.
- `TEST_RESULTS.md` — unit + regression results.
- `LIVE_SAMPLE_RESULTS.md` — classification of the real discovery sample pool.
- `KNOWN_LIMITATIONS.md` — honest gaps.
- `results/classification_summary.json` — machine-readable run output.
