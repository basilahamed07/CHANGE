# STAGE-2 CLASSIFY — Known Limitations

Honest list. None of these block the stage; each is recorded so a later session
does not mistake it for coverage.

1. **Live sample shows 0 unknowns — that is a sample artifact, not proof the
   classifier resolves everything.** The discovery sweep applies a region gate,
   so the rows that reached `sample_jobs` are mostly single-country and clean.
   Genuinely ambiguous rows (bare `Remote`, region buckets, unconfigured places)
   are covered by the curated battery + unit tests, not by this sample.

2. **The live pool carries no descriptions**, so the `DESCRIPTION` tier is not
   exercised on live rows — only in the unit suite and curated battery. When
   real ingested descriptions are available, re-run the validation to confirm.

3. **AI fallback is unit-tested with a mock client, not against a live model.**
   No current job in the pool reaches the residue, so the path is not exercised
   end-to-end. The contract is proven (residue-only, validated, rejects
   unconfigured/low-confidence, swallows errors); a live-cost run is deferred to
   avoid spend on a path that is currently a no-op.

4. **`CITY_TO_COUNTRY` is a static table.** It does not yet merge the `cities:`
   lists from `config/countries/*.yaml` at runtime. Extension point exists
   (`classify_job(region_of=…)` + the registry's `classification_terms()`); a
   future change should union the YAML cities into the map so adding a country
   YAML needs zero code edits for city coverage too (Golden Rule 8).

5. **`SOURCE_HINT` (LOW) is still stored as `jobs.location_region`.** Downstream
   consumers that only look at the region string cannot see that the answer was
   a hint rather than evidence. The confidence/source columns now expose this,
   but ELIGIBILITY does not yet branch on them. Tracked as a follow-up, not
   changed here (that is Stage-3 territory).

6. **Multi-location primary = string order, not market priority.** A listing
   reading `United States; Canada; Poland (Remote)` becomes `CA` because the US
   is unconfigured and Canada appears first. `supported_countries` records the
   alternatives; a smarter "prefer the highest-priority configured market" rule
   is possible but not implemented.

7. **`region_of` depends on the country registry at run time.** If the registry
   fails to load, region strings fall back to the ISO code (logged warning),
   which would not match `allowed_regions`. Registry load is treated as reliable
   and tested elsewhere; this is a degraded-mode caveat only.

8. **No HTTP-API E2E for classification.** Verification is at the module +
   scheduler level (the exact code the daily run calls). The router/endpoint
   surface for classification was not re-exercised in this stage; DISCOVER's API
   was verified separately in the Stage-1 work.
