# STAGE-2 CLASSIFY — Audit (before → after)

An honest record of what Stage-2 did before this work, what was actually
broken/missing, and what changed. Only Stage-2 was touched — DISCOVER,
ELIGIBILITY and downstream were not redesigned.

## What existed before

`app/location_classifier.py`:
- `classify_location_rule_based(location)` → a **single region string**
  (`"Germany"`, `"UK"`, `"Remote"`, or `None`).
- `classify_locations_llm(ai_client, locations)` → a **US-centric** batch prompt
  (`US` / `Remote` / country name) returning region strings.
- A `_country_map` merged constants with the registry's `_EXTRA_COUNTRY_TERMS`.
- Rules were US-first: `"Remote"` defaulted to `"Remote"`, and unknown strings
  became `"Unknown"` with no evidence trail.

`app/scheduler.py#run_location_classification` ran:
1. rule pass over unclassified jobs,
2. LLM batch for the leftover ambiguous strings,
3. dismiss everything classified outside the allowed regions.

`app/eligibility.py#EligibilityEngine.check` requires `location_classified = 1`
and reads `job["location_region"]` against `allowed_regions` /
`min_salary_by_region`.

## Gaps found (and closed)

| # | gap | impact | fix |
|---|---|---|---|
| 1 | **No confidence, no source, no reason.** Only a region string was stored. | Could not tell a confidently-mapped city from a guess; audits impossible. | New columns + `Classification` dataclass (country, confidence, source, reason, supported). |
| 2 | **Source country could become the answer.** Ingest-time region gate occasionally stamped the searched country onto jobs whose text said otherwise. | Jobs mis-attributed to the wrong country; eligibility skewed. | `SOURCE_HINT` tier at LOW, text/structured always wins; unit-tested. |
| 3 | **US-centric rules + LLM prompt.** | Non-US countries were second-class; the AI batch answered in region names, not country codes. | Canonical `COUNTRY_ALIASES` for all 10 + bounded, validated country fallback. |
| 4 | **No honest-unknown discipline.** Ambiguous strings fell to `"Unknown"`/`"Remote"` with no signal about why. | Unclear whether a job was genuinely unknown or a classifier miss. | `UNKNOWN` tier with reason; `Unknown` jobs are **kept**, never dismissed. |
| 5 | **Remote collapsed.** All remote jobs became `"Remote"`, losing the country qualifier and the region bucket. | `Remote - India` and `Remote - APAC` looked identical. | Remote parsed into country / region bucket / GLOBAL; work type recorded. |
| 6 | **Conflicts invisible.** Description could contradict the location with nothing recording it. | Silent mis-classification. | `detect_conflict` records and counts disagreements. |
| 7 | **`search_config` row assumption.** `set_classification_metrics`/`update_allowed_regions` on a fresh DB could silently no-op. | Metrics/strategy lost on first run. | Both are UPSERTs; `updated_at` (NOT NULL) supplied on insert. |
| 8 | **Dead `source` column reference** in `get_unclassified_jobs` (jobs has no `source` column). | Would raise on a fresh query path. | Query now selects `id, location, description, country_code`. |

## What was deliberately NOT changed

- **DISCOVER** and its scrapers, concurrency, registry — untouched.
- **ELIGIBILITY** semantics — CLASSIFY still writes `location_classified` and
  `location_region` exactly as before, so the downstream contract is unchanged
  (verified by `test_downstream_eligibility_contract`).
- `classify_location_rule_based` is **retained** and still used by discovery
  ingest as a scrape-time prefilter. The new chain supersedes it for Stage-2.
- Dismiss-outside-regions remains in this pass (pre-existing behavior), but
  `Unknown` is now explicitly preserved so nothing unclassifiable is dropped.

## Verification

- `tests/test_classification.py` — 70 tests (was 64; +6 for the AI fallback).
- Regression: location_classifier, countries, pipeline, eligibility, daily_run,
  workspaces, discovery upgrade, scheduler, database — **218 passed**.
- Live validation over the real discovery sample pool — see
  `LIVE_SAMPLE_RESULTS.md`.
