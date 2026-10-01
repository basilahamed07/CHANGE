# STAGE-3 ELIGIBILITY — Gate Rules

`app/eligibility.py` implements one explicit ordered gate chain. HARD reasons
stop the job (INELIGIBLE); REVIEW reasons route it to human review
(REVIEW_REQUIRED, never auto-scored). The reported `gate`/`reason` is the one
from the **earliest gate** in the documented order.

## Gate order

| # | gate | question | outcome |
|---|---|---|---|
| 1 | `DATA_SANITY` | identity + actionable link present? | missing title/company → INELIGIBLE; missing/invalid URL → REVIEW |
| 2 | `DISMISSED` | user or strategy dismissed? | INELIGIBLE |
| 3 | `ALREADY_APPLIED` | a submitted application exists? | INELIGIBLE |
| 4 | `JOB_STATUS` | positive closed/expired evidence? | INELIGIBLE |
| 5 | `FRESHNESS` | posted within the window? | STALE/DATE_UNKNOWN → INELIGIBLE |
| 6 | `LOCATION` | classified country/region targeted? | not targeted → INELIGIBLE; unknown/low-confidence → REVIEW |
| 7 | `EVIDENCE` | required description present? | INELIGIBLE |
| 8 | `FINAL_ELIGIBILITY` | nothing stopped it | ELIGIBLE |

## Statuses

| status | meaning | enters SCORE? |
|---|---|---|
| `ELIGIBLE` | all gates passed | yes |
| `INELIGIBLE` | a hard gate stopped it | no |
| `REVIEW_REQUIRED` | uncertainty a human must resolve | no (see `GET /api/eligibility/review-jobs`) |
| `UNKNOWN` | could not be evaluated at all | no |

## Reason codes

Existing codes are preserved (analytics depends on the strings); new codes are
added for the new gates.

| reason | gate | kind |
|---|---|---|
| `MISSING_TITLE` / `MISSING_COMPANY` | DATA_SANITY | hard |
| `INVALID_APPLY_URL` | DATA_SANITY | review |
| `DISMISSED` / `DISMISSED_BY_COUNTRY_STRATEGY` | DISMISSED | hard |
| `ALREADY_APPLIED` | ALREADY_APPLIED | hard |
| `JOB_CLOSED` | JOB_STATUS | hard |
| `STALE_POSTED_DATE` | FRESHNESS | hard |
| `POSTED_DATE_UNKNOWN` | FRESHNESS | **review** (§10 — uncertainty, not proof) |
| `LOCATION_NOT_CLASSIFIED` / `REGION_NOT_ALLOWED` / `WORK_TYPE_NOT_ALLOWED` / `SALARY_BELOW_FLOOR` | LOCATION | hard |
| `COUNTRY_UNKNOWN` / `REMOTE_REGION_REVIEW` / `LOCATION_LOW_CONFIDENCE` | LOCATION | review |
| `MISSING_DESCRIPTION` | EVIDENCE | hard |
| `OK` | FINAL_ELIGIBILITY | — |

## Dismissed gate

`dismissed=1` → INELIGIBLE. `strategy_dismissed=1` is reported separately
(`DISMISSED_BY_COUNTRY_STRATEGY`) because strategy dismissals are reversible
(`restore_strategy_dismissed_jobs`). A dismissed job is never automatically
re-admitted; only an explicit user restore clears it.

## Already-applied gate

An application whose status is in {applied, interviewing, offered, accepted,
declined, rejected, withdrawn, closed, ghosted} → INELIGIBLE `ALREADY_APPLIED`.
`interested` (saved) and `prepared` (package built, not sent) deliberately do
NOT block — a saved job should stay eligible and a prepared package is not a
submission. Identity is the canonical `job_id` (dedup already merges the same
opportunity across sources), not title/company string matching. Different
positions at the same company are different jobs → not blocked.

## Job-status gate

Closure is only ever asserted from positive evidence: `job_status ∈ {closed,
expired, inactive, filled, removed}`, `is_closed`, or a `closing_date` that has
passed. A scraper returning `NO_RESULTS` or a network failure is **not** closure
and never sets these fields.

## Freshness gate

Reuses `app/freshness.assess_freshness` (window = 7 days, Golden Rule 10).
`VERIFIED_FRESH` passes; `STALE` → INELIGIBLE `STALE_POSTED_DATE`;
`DATE_UNKNOWN` → **REVIEW_REQUIRED** `POSTED_DATE_UNKNOWN` (Critical Test #3 —
never promoted to fresh, never eligible, never scored). The status is REVIEW
rather than INELIGIBLE because "we don't know the date" is uncertainty, not
proof of a bad job (task §10). If a *hard* gate also fires (e.g. below the
salary floor) the row stays INELIGIBLE.

## Location / country gate (consumes Stage-2)

ELIGIBILITY never re-classifies. It reads `location_region`, `country_code`,
`classification_confidence`, `classification_source`, `supported_countries`.

1. region in allowed regions → pass; country_code in allowed countries → pass.
2. otherwise, any `supported_countries` entry targeted (multi-location) → pass.
3. region in a bucket {APAC, EMEA, EUROPE, LATAM, MENA, NORTH_AMERICA}:
   REVIEW (`REMOTE_REGION_REVIEW`) if the user targets a country inside that
   bucket, else INELIGIBLE `REGION_NOT_ALLOWED`.
4. region in {GLOBAL, WORLDWIDE, ANYWHERE, REMOTE} → pass (worldwide remote).
5. region unknown / unset → REVIEW `COUNTRY_UNKNOWN` (never fabricate a country).
6. region configured but not targeted with LOW confidence / `SOURCE_HINT` →
   REVIEW `LOCATION_LOW_CONFIDENCE`; with HIGH confidence → INELIGIBLE
   `REGION_NOT_ALLOWED`.

Salary floor (country config) is a policy gate applied regardless of match:
`salary_min` below the region's floor → INELIGIBLE `SALARY_BELOW_FLOOR`
(fixed 2026-10-01 — it previously reported the misleading
`WORK_TYPE_NOT_ALLOWED`; see `QUALITY_AUDIT.md`).

## Evidence gate

Required: a description of ≥ 80 chars (`MISSING_DESCRIPTION`, existing rule).
Identity/URL are covered by DATA_SANITY. Missing fields are never fabricated.

## What ELIGIBILITY deliberately does NOT do

- **No relevance scoring** — no skill/experience/title/similarity logic.
- **No work-authorization/visa verdict** — the user's right-to-work is not
  inferred; visa/sponsorship conflicts remain SCORE/hybrid hard-blockers.
- **No experience hard-gates** unless an explicit product rule exists.
- **No AI** — every gate is deterministic (Golden Rule 4).
