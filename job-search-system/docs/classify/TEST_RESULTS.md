# STAGE-2 CLASSIFY — Test Results

**Run:** 2026-10-01 · `cd job-search-system/root`
Command: `.venv/bin/python -m pytest <files> -q --timeout=60 -p no:cacheprovider`

## Unit suite — `tests/test_classification.py`

```
70 passed in ~4s
```

Coverage map (task §22):

| area | tests |
|---|---|
| country normalization + all 10 aliases | `test_normalize_country_aliases` (parametrized), `test_normalize_rejects_unconfigured` |
| explicit / text / city location | `test_city_only_location`, `test_explicit_country_in_text`, `test_city_map_all_countries` |
| remote variants | `test_remote_country_specific_*`, `test_remote_region_only_*`, `test_remote_worldwide_*`, `test_pure_remote_*` |
| hybrid / onsite | `test_hybrid_keeps_country`, `test_onsite_keyword` |
| multi-location | `test_multi_location_*` |
| region-only / unconfigured | `test_region_only_ambiguity_never_fabricates`, `test_unconfigured_country_is_unknown_not_fabricated` |
| source hint | `test_source_hint_never_overrides_text`, `test_source_hint_fallback_is_low_confidence`, `test_no_hint_no_evidence_is_unknown` |
| description evidence | `test_description_location_evidence`, `test_description_residency_evidence` |
| conflict | `test_conflict_detected_and_recorded_not_applied`, `test_no_conflict_when_agreement` |
| idempotency | `test_classification_is_idempotent` |
| AI fallback (new, +6) | `test_ai_fallback_resolves_residue_country`, `_rejects_unconfigured_country`, `_rejects_low_confidence`, `_handles_garbage_and_errors`, `_not_called_for_empty_evidence`, `test_scheduler_ai_only_for_residue` |
| scheduler integration | `test_scheduler_pass_persists_and_is_idempotent`, `test_classification_metrics_recorded` |
| ELIGIBILITY contract | `test_downstream_eligibility_contract` |
| per-user isolation | `test_multi_user_isolation_of_classification` |

**Critical assertions proven by unit tests:**
- Unknown/ambiguous input → honest `UNKNOWN`, never a fabricated country.
- Source country never overrides explicit text.
- AI is called **only** for deterministic residue (`ai.calls == 1` with one
  Berlin + one unknown job) and rejected answers stay UNKNOWN.
- Deterministic outputs never carry an `AI_*` source.

## Regression — related suites

```
tests/test_location_classifier.py  tests/test_countries.py  tests/test_pipeline.py
tests/test_eligibility.py  tests/test_daily_run.py  tests/test_workspaces.py
tests/test_discovery_upgrade.py  tests/test_scheduler.py  tests/test_database.py
→ 218 passed in 51.5s
```

Earlier broader pass (incl. `test_multiuser_real_scenario`, `test_discovery_expansion`,
`test_adapters`) — **234 passed**.

The ELIGIBILITY suite passing unchanged confirms the downstream contract still
holds: CLASSIFY writes `location_classified` + `location_region` exactly as the
eligibility engine expects.

## Bugs caught and fixed during this stage

1. **`set_classification_metrics` no-op on a fresh DB** — a bare `UPDATE ...
   WHERE id = 1` matched nothing, and the first fix attempt still failed because
   `search_config.updated_at` is `NOT NULL` with no default and was omitted from
   the INSERT. Now a correct UPSERT that supplies `updated_at`. (Caught by
   `test_classification_metrics_recorded`.)
2. **Bare `Remote` skipped description evidence** — returned GLOBAL/UNKNOWN
   before consulting the description, so `"Remote" + "must reside in Germany"`
   never resolved. Now falls through to tier 4. (Caught by
   `test_description_residency_evidence`.)
3. **Dangling `source` column reference** in `get_unclassified_jobs` — jobs has
   no such column; query fixed to select real columns.
