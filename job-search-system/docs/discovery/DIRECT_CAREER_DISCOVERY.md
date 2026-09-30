# DIRECT COMPANY CAREER DISCOVERY — app/company_careers.py (2026-09-30)

The system must not depend on job boards alone. This layer discovers jobs
straight from companies' own careers pages through the SANCTIONED structured
path — schema.org **JobPosting JSON-LD** (the same data Google reads). No
CAPTCHA evasion, no stealth browsers, no fragile HTML heuristics.

## Flow (task §10)

```
Company domain (scraper key 'career_companies', comma-separated)
   │
   ▼
resolve career page: /careers · /jobs · /company/careers · /about/careers
                      careers.<domain> · jobs.<domain>
   │
   ▼
detect_ats(career_url)          ← app/ats_detect.py
   ├── ATS host → REPORT + route to the existing ATS adapter
   │             (single parsing path — never re-parsed here)
   └── own domain → fetch page → extract_job_postings()
            ├── JSON-LD JobPosting found → CanonicalJob
            └── none → honest skip (health status, no fabrication)
```

## Normalization (task §16)

Every posting maps into the EXISTING `CanonicalJob`: title, company
(hiringOrganization.name), location (jobLocation address → "City, Country" /
applicantLocationRequirements for remote), salary min/max/currency,
employmentType, datePosted, apply URL (directApply → url → @id → page).
A posting with NO datePosted stays `posted_date=None` — never "today"
(M5 freshness then treats it as DATE_UNKNOWN, Critical Test #3 path).

## Idempotency + caching (task §25/§31)

* Same fingerprint inputs ⇒ same dedup hash ⇒ no duplicate rows.
* Company metadata cached in the `companies` table: `careers_url`,
  `careers_ats` (detected provider), `careers_checked_at` — the same company
  is not re-probed every run.
* `MAX_COMPANIES_PER_PASS = 25` bounds a pass.

## Configuration

Settings → scraper keys → `career_companies`: `openai.com,stripe.com,deeplearning.ai`
(without the key the adapter is an honest no-op with a clear error, same
discipline as jooble/adzuna/reed).

## Tests (all deterministic — tests/test_discovery_upgrade.py)

* fixture HTML: JobPosting + non-JobPosting + malformed blob + @graph flattening
* full field mapping (salary, location, employment type, apply URL)
* dedupe-by-URL · non-JobPosting → None · missing title → None
* **unknown date stays None (never fabricated)**
* candidate URL shape · ATS-hosted companies are skipped (routing contract)
