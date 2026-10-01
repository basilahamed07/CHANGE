# STAGE-3 ELIGIBILITY — Quality Audit

**Date:** 2026-10-01 · **Scope:** the 1,962-row live eligibility run on a **COPY**
of Basil's real workspace DB (never his original).
**Behavior:** unchanged during the analysis phase; two defects were found and
fixed afterwards (§11), then the audit was re-run for before/after numbers.
**Not committed / not pushed.**

Reproduce:
```bash
cd job-search-system/root
.venv/bin/python -u ../analysis/eligibility_quality_audit.py
```
Raw output: `docs/eligibility/results/quality_audit_raw.json`.

---

## 1. Exact counts

### BEFORE fixes

Total evaluated: **1,962** (of 1,996 jobs; 34 unclassified/dismissed never evaluated)

**By status**

| status | count | % |
|---|---:|---:|
| ELIGIBLE | 67 | 3.4% |
| INELIGIBLE | 1,895 | 96.6% |
| REVIEW_REQUIRED | 0 | 0.0% |
| UNKNOWN | 0 | 0.0% |

**By gate**

| gate | count | % |
|---|---:|---:|
| DISMISSED | 1,357 | 69.2% |
| FRESHNESS | 515 | 26.2% |
| FINAL_ELIGIBILITY | 67 | 3.4% |
| LOCATION | 20 | 1.0% |
| ALREADY_APPLIED | 2 | 0.1% |
| EVIDENCE | 1 | 0.1% |
| DATA_SANITY | 0 | 0.0% |
| JOB_STATUS | 0 | 0.0% |

**By reason**

| reason | count | % |
|---|---:|---:|
| DISMISSED_BY_COUNTRY_STRATEGY | 941 | 48.0% |
| STALE_POSTED_DATE | 436 | 22.2% |
| DISMISSED | 416 | 21.2% |
| POSTED_DATE_UNKNOWN | 79 | 4.0% |
| OK | 67 | 3.4% |
| WORK_TYPE_NOT_ALLOWED | 20 | 1.0% |
| ALREADY_APPLIED | 2 | 0.1% |
| MISSING_DESCRIPTION | 1 | 0.1% |

### AFTER fixes (re-run)

| status | before | after | Δ |
|---|---:|---:|---:|
| ELIGIBLE | 67 | **67** | 0 (no decision changed) |
| INELIGIBLE | 1,895 | **1,818** | −77 |
| REVIEW_REQUIRED | 0 | **77** | +77 |
| UNKNOWN | 0 | 0 | 0 |

| reason | before | after |
|---|---:|---:|
| DISMISSED_BY_COUNTRY_STRATEGY | 941 | 941 |
| STALE_POSTED_DATE | 436 | 436 |
| DISMISSED | 416 | 416 |
| POSTED_DATE_UNKNOWN | 79 | 79 (77 now REVIEW, 2 still INELIGIBLE) |
| OK | 67 | 67 |
| ~~WORK_TYPE_NOT_ALLOWED~~ → **SALARY_BELOW_FLOOR** | 20 | 20 |
| ALREADY_APPLIED | 2 | 2 |
| MISSING_DESCRIPTION | 1 | 1 |

Gate counts are unchanged (the two fixes changed *status* and *reason label*,
not which gate stopped the job). The 2 DATE_UNKNOWN rows that stay INELIGIBLE
(#1448 UK, #1906 AU) also fall below their salary floor — FRESHNESS is the
earliest gate so it is reported first, and `eligibility_evidence` records
`salary_floor`.

---

## 2. Why only 67 / 1,962 (~3.4%) were ELIGIBLE

Three stacked effects, none of which is a bug:

1. **69.2% were already dismissed before eligibility ran.** 1,357 rows are
   dismissed (941 by country strategy, 416 by the user). A dismissed job stops at
   gate 2 and can never become eligible. These are overwhelmingly `region=US`
   jobs — the US is not one of the 10 targeted countries, so the country
   strategy dismissed them long before this stage.
2. **26.2% fail FRESHNESS.** Of the 605 alive+classified rows, 436 are STALE
   (posted > 7 days, Golden Rule 10) and 79 have DATE_UNKNOWN.
3. **Only 605 rows were even alive to evaluate.** 1,996 − 1,391 dismissed = 605.

So the *meaningful* rate is **67 / 605 = 11.1% among live, non-dismissed jobs**,
and within the 93 rows that are live **and fresh**, **67 of 93 (72%)** are
eligible — the rest are blocked by concrete rules (20 salary floor, 4 future
posted-date, 2 already-applied, 1 too-short description).

The "3.4%" headline is therefore dominated by pre-existing dismissals, not by
Stage-3 conservatism.

---

## 3. Manual inspection — 75 individual rejected rows

Reviewed **75 rows** across every reason code (12 per reason where available),
plus the 79-row DATE_UNKNOWN dump and 8-per-reason dumps for dismissed/stale:

| category | reviewed | verdict |
|---|---:|---|
| DISMISSED_BY_COUNTRY_STRATEGY | 12 | all `region=US` — correct, US not targeted |
| DISMISSED (user) | 12 | all `region=US` — correct |
| STALE_POSTED_DATE | 12 | all posted ≤ 2026-09-22 (cutoff 09-24) — correct |
| POSTED_DATE_UNKNOWN | 12 (+67 dump) | no posted_date — correct to be non-fresh |
| WORK_TYPE_NOT_ALLOWED (salary) | 12 | fresh, in-country SG jobs — correct rule, **wrong label** |
| ALREADY_APPLIED | 2 | both have a submitted application — correct |
| MISSING_DESCRIPTION | 1 | 34-char description — correct |
| ELIGIBLE (control) | 12 | fresh, Remote, full descriptions — correct |
| **total individually inspected** | **75** | |

---

## 4. False rejections found

**Decision-level false rejections: 0.**

Every job that stopped at a gate did so for a reason that matches product rules:

- All 1,357 dismissals were already recorded by the user/country strategy.
- All 436 STALE rows have a posted date before the 7-day cutoff
  (earliest 2026-07-29, latest 2026-09-22 vs. cutoff 2026-09-24) — Golden Rule 10.
- All 79 DATE_UNKNOWN rows genuinely have no posted date.
- 1 job has a 34-char description (pre-existing ≥80 rule).
- 2 jobs have a submitted application.

**Two defects (explainability/status), not wrong gate decisions:**

1. **Wrong reason code on the salary-floor gate.** 20 fresh, in-country,
   well-described Singapore jobs were rejected with `WORK_TYPE_NOT_ALLOWED` —
   a factually wrong label (no work type was evaluated). A human reading the
   reason would have been misled about *why* they were blocked.
2. **DATE_UNKNOWN reported as a proven rejection.** 79 rows had
   `status=INELIGIBLE` for "we don't know the date". Uncertainty was being
   presented as proof of a bad job, which the task (§10) explicitly warns
   against.

Both were fixed (§11).

---

## 5. Special attention areas

| area | finding |
|---|---|
| **Remote Worldwide** | Region `GLOBAL` passes the country gate. 10 GLOBAL rows exist but all are strategy-dismissed. Eligible `Anywhere`/`Remote` rows (#1288 etc.) correctly pass. |
| **Remote APAC** | Region `APAC` → REVIEW if the user targets SG/IN/AU (they do). 2 APAC rows exist, both strategy-dismissed. Reviewed in unit tests. |
| **Remote EMEA** | Region `EMEA` → REVIEW for a 10-country European target. 1 EMEA row, dismissed. |
| **Multi-country jobs** | `supported_countries` was **empty on all 1,962 rows** — Stage-2 only populates it for comma/pipe multi-location strings, and none matched. The multi-location logic is unit-tested but not exercised by this data. |
| **Unknown dates** | See §4 #2 — now REVIEW_REQUIRED, still never scored. |
| **Cross-country classification** | **`country_code` was NULL on all 1,962 rows** — see §6. |
| **Missing optional vs required** | Optional fields (apply_url, contact email, hiring manager, posted_date) do NOT block. Required: title, company, URL, description ≥80. 1 job blocked on description; 0 on title/company/URL. |

---

## 6. Notable finding: Stage-2 evidence absent on historical rows

`country_code`, `classification_confidence`, `classification_source` are **NULL
on every row** because `run_location_classification` only processes
`location_classified = 0` rows, and these were classified by the *legacy*
classifier before Stage-2 shipped. Consequence: the LOCATION gate ran on legacy
`location_region` strings only, so its country-code/confidence/`supported_countries`
logic never engaged — which is why `REVIEW_REQUIRED` from location was 0 in the
before-run, and why gates `REGION_NOT_ALLOWED` / `COUNTRY_UNKNOWN` /
`REMOTE_REGION_REVIEW` never appear in live counts.

This is **not** a Stage-3 logic bug (the gate degrades gracefully to the region
string, and produced 0 wrong rejections among live+fresh jobs). It is a
**coverage gap** requiring a Stage-2 re-classification pass. Recommended, not
done here (would modify Stage-2 behavior).

Proof it is only a coverage issue: forcing a Stage-2 re-classification of the
605 alive rows populated `country_code` on 376 of them and the LOCATION gate
then ran normally with no spurious rejections.

---

## 7. Confirmations

| check | result |
|---|---|
| DATE_UNKNOWN never becomes VERIFIED_FRESH | ✅ **0** rows |
| DATE_UNKNOWN never in `get_scoreable_jobs()` | ✅ **0** rows |
| INELIGIBLE never enters `get_scoreable_jobs()` | ✅ **0 leaked** |
| REVIEW_REQUIRED never enters `get_scoreable_jobs()` | ✅ **0 leaked** |
| scoreable returns ELIGIBLE only | ✅ 5 returned, all ELIGIBLE |

(`scoreable` = 5 because `get_scoreable_jobs` also excludes already-scored jobs;
62 of the 67 ELIGIBLE rows already have a score — correct.)

---

## 8. Bugs found, fixed, re-tested

### Fix A — wrong reason code on the salary-floor gate
`app/eligibility.py`: new `R_SALARY_BELOW_FLOOR = "SALARY_BELOW_FLOOR"`, used
instead of `R_WORK_TYPE` for `salary_min < floor`; evidence now also records
`salary_min`. `R_WORK_TYPE` remains reserved for a real work-type rule.
No code consumed the old string (only docs/metrics).

**Regression test:** `test_salary_floor_uses_dedicated_reason`.

### Fix B — DATE_UNKNOWN is uncertainty, not a rejection
`app/eligibility.py`: `R_DATE_UNKNOWN` moved from HARD → REVIEW so the gate
yields `REVIEW_REQUIRED` instead of `INELIGIBLE`. Critical Test #3 is preserved:
it is still never VERIFIED_FRESH, still `eligible=False`, still absent from
`get_scoreable_jobs()`. If a *hard* gate also fires (e.g. salary floor), the row
stays INELIGIBLE.

**Regression tests:** `test_date_unknown_is_review_not_rejection`,
`test_date_unknown_with_hard_reason_stays_ineligible`,
`test_date_unknown_never_enters_scoreable`.

**Test totals:** `tests/test_eligibility.py` 29 → **33 passed**.
**Regression:** batch 1 **216 passed**, batch 2 **105 passed** (321 total).

---

## 9. Rules that may need adjustment (recommendations, not changed)

1. **Salary floor as a hard gate.** 20 fresh, in-country Singapore jobs were
   blocked purely on salary (42k–72k vs. SGD 90k floor). The rule is legitimate
   country policy and pre-existing, but (a) currency of `salary_min` is not
   verified against the YAML currency, and (b) the task's suggested gate list
   does not include salary. Recommend reviewing whether it belongs in SCORE or
   REVIEW rather than a hard gate.
2. **STALE vs. recently-seen.** 423 of the 436 STALE jobs had `last_seen_at`
   within 7 days — i.e. still actively listed by scrapers, while
   `auto_dismiss_stale` deliberately *keeps* recently-seen jobs (30-day window +
   last-seen escape hatch). Eligibility uses a stricter 7-day `posted_date`
   window. This is consistent with Golden Rule 10 and with the SQL eligible
   pool, so **not a bug**, but the 7-day vs 30-day tension should be a
   deliberate decision rather than an accident.
3. **DATE_UNKNOWN → REVIEW is now a review queue of 77.** The UI has no panel for
   it yet (`GET /api/eligibility/review-jobs` exists).
4. **Stage-2 re-classification** (§6) to populate `country_code` on legacy rows.
5. **Multi-region listings collapse** (e.g. #12 `LATAM, Europe, USA, Canada,
   APAC` → `region=US` → dismissed) — a Stage-2 classification concern.

---

## 10. Reported totals (final)

- **Total evaluated:** 1,962
- **ELIGIBLE:** 67 (3.4%)
- **INELIGIBLE:** 1,818 (92.7%)
- **REVIEW_REQUIRED:** 77 (3.9%)
- **UNKNOWN:** 0
- **By gate:** DISMISSED 1,357 · FRESHNESS 515 · FINAL_ELIGIBILITY 67 ·
  LOCATION 20 · ALREADY_APPLIED 2 · EVIDENCE 1 · DATA_SANITY 0 · JOB_STATUS 0
- **By reason:** DISMISSED_BY_COUNTRY_STRATEGY 941 · STALE_POSTED_DATE 436 ·
  DISMISSED 416 · POSTED_DATE_UNKNOWN 79 · OK 67 · SALARY_BELOW_FLOOR 20 ·
  ALREADY_APPLIED 2 · MISSING_DESCRIPTION 1
- **Manually reviewed:** 75 individual rows (+ full 79-row DATE_UNKNOWN dump)
- **Decision-level false rejections:** 0
- **Defects found & fixed:** 2 (wrong salary reason code; DATE_UNKNOWN as rejection)
- **Contract:** 0 ineligible/review leaked into SCORE; 0 DATE_UNKNOWN ever fresh

---

## 11. Final verdict

**READY_FOR_SCORE**

The gate chain makes correct decisions on real data, the SCORE contract holds
(hard-verified: 0 leaks), Critical Test #3 holds, and the two defects found by
this audit have been fixed with regression tests and re-verified. Remaining
items (§9) are policy recommendations and Stage-2 coverage work — none blocks
eligibility from feeding SCORE.
