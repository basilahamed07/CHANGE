# STAGE-2 CLASSIFY — Live Sample Results

Validation of the **shipped** `app.classification.classify_job` (+ `detect_conflict`)
against the real jobs captured by the all-countries DISCOVER sweep
(`docs/discovery/results/countries/*.json#sample_jobs`) — i.e. rows pulled from
live boards, not synthetic fixtures.

**Run:** 2026-10-01
```bash
cd job-search-system/root
.venv/bin/python -u ../analysis/verify_classification_live.py
```
Machine-readable output: `docs/classify/results/classification_summary.json`.

> The sweep artifacts do **not** carry descriptions, so the `DESCRIPTION` tier is
> exercised by the curated battery + unit suite rather than the live rows. The
> live rows exercise `TEXT_LOCATION` / `CITY_MAP` / multi-location / remote /
> region-only / `SOURCE_HINT`. `AI_FALLBACK` is `0` by construction (the chain is
> deterministic and no AI client is passed).

## 1. Curated priority-chain battery — 16/16 PASS

Runs the shipped module in-process on the documented examples: structured
country, `UK`/`UAE` aliases, city map, multi-location primary+supported, remote
country/region/worldwide, bare-remote + residency, description evidence,
source-hint LOW, unconfigured place → hint, source-never-overrides-text, honest
unknown, hybrid work type. All expected `(country, region, source)` tuples match.

## 2. Per-country live sample classification

| country | tested | same | other | unknown | remote | hybrid | AI | conflicts |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| AE | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 0 |
| AU | 6 | 4 | 2 | 0 | 0 | 0 | 0 | 0 |
| CA | 12 | 12 | 0 | 0 | 9 | 0 | 0 | 0 |
| DE | 12 | 9 | 3 | 0 | 3 | 0 | 0 | 0 |
| GB | 12 | 12 | 0 | 0 | 1 | 1 | 0 | 0 |
| IE | 12 | 5 | 7 | 0 | 3 | 1 | 0 | 0 |
| IN | 12 | 12 | 0 | 0 | 0 | 0 | 0 | 0 |
| NL | 12 | 3 | 9 | 0 | 0 | 0 | 0 | 0 |
| PL | 12 | 6 | 6 | 0 | 5 | 0 | 0 | 0 |
| SG | 12 | 12 | 0 | 0 | 0 | 0 | 0 | 0 |
| **total** | **104** | **77** | **27** | **0** | **21** | **2** | **0** | **0** |

- **104/104 rows classified** — zero honest-UNKNOWN among this high-quality
  sample. Every answer is `HIGH` confidence via `TEXT_LOCATION`/`CITY_MAP`,
  which is the expected profile of rows that survived the discovery region gate.
- **27 rows classified to a country other than the one searched** — these are
  the interesting ones (below), and they prove source-country is a hint, not
  ground truth.

## 3. Suspicious `search_country != classified_country` samples

All 27 are **legitimate** — the job's own location text names a different
configured country, and the classifier correctly follows the text:

| searched | classified | location | source |
|---|---|---|---|
| AU | AE | `Dubai` | CITY_MAP |
| AU | AE | `Abu Dhabi, UAE` | TEXT_LOCATION |
| DE | CA | `Canada` / `United States; Canada; Poland (Remote)` | TEXT_LOCATION |
| IE | GB | `United Kingdom (Remote)` / `London, UK` | TEXT_LOCATION |
| NL | IN | `Bengaluru, Karnataka` / `Hyderabad, Telangana` | CITY_MAP |
| PL | NL | `Amsterdam, Netherlands` / `Utrecht, …` | TEXT_LOCATION |
| PL | IN | `Mumbai, Maharashtra` / `Bengaluru, Karnataka` | CITY_MAP |

Examples of why this is correct:
- A listing returned by the **Ireland** search that literally reads
  `United Kingdom (Remote)` is a UK job surfaced by a nearby search — GB, not IE.
- Jobs returned by the **NL/PL** searches reading `Bengaluru, Karnataka` are
  India roles from global boards — IN, not NL/PL.
- `United States; Canada; Poland (Remote)` is a multi-location listing; primary
  is the first configured country (`CA`), with `PL` in `supported_countries`.

No case required a fabricated country — the classifier never guessed beyond the
configured set.

## 4. What this proves

- The priority chain resolves real, messy, multi-country location strings
  deterministically with HIGH confidence and zero AI.
- Source country never leaks into the answer when text disagrees (the rule most
  at risk of silent mis-attribution).
- Remote qualifiers survive: 21 `REMOTE` + 2 `HYBRID` rows kept their country or
  region bucket instead of collapsing to a bare `"Remote"`.
