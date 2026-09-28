# JOB PORTALS BY COUNTRY — the master source list for discovery

> **What this is:** the researched, maximum-coverage list of hiring portals
> ("top hiring websites") for every target country — Germany, Netherlands,
> Ireland, UK, Singapore, UAE — **plus the newly added India**.
> Researched 2026-09-28 from multiple 2026 job-market guides (liveingermany.de,
> join.com, manatal, gohire, ismartrecruit, resumewriter.sg, whitecarrot,
> cutshort/instahyre comparisons).
>
> **Why it exists:** discovery currently only covers ATS boards (Greenhouse,
> Lever, Ashby, SmartRecruiters) + international scrapers (LinkedIn, Indeed,
> Remotive, etc.). This document is the source-of-truth for **which
> country-native portals matter**, so we can (a) add their search terms, and
> (b) decide which ones deserve a real `JobSourceAdapter` later.

---

## 1. How to read this document

| Column | Meaning |
|---|---|
| **Portal** | The website, with URL |
| **Type** | `general` = all industries · `tech` = IT/software-focused · `gov` = government-run · `expat` = English/foreigner-friendly · `agg` = aggregator |
| **Country focus** | ✅ = country-native portal · 🌍 = international portal widely used there |
| **Sponsor-friendly** | Known to list visa-sponsorship roles for internationals |
| **Adapter status** | `scraped today` = already wired in the app · `YAML terms only` = discovery uses it as a search term (jobs found via other sources) · `future adapter` = candidate for a new `JobSourceAdapter` |

**Golden rule for this list:** a portal is only useful to jobagent if its
listings are either **scrapeable** (public, no login wall) or **reachable
through an adapter**. Login-walled portals (XING, JobStreet, Bayt) are listed
for manual use — mark them clearly.

---

## 2. Germany 🇩🇪

| Portal | URL | Type | Country | Sponsor-friendly | Adapter status |
|---|---|---|---|---|---|
| StepStone | stepstone.de | general | ✅ | partial | YAML terms only |
| XING | xing.com/jobs | general | ✅ | partial | manual (login-walled) |
| Bundesagentur für Arbeit (Arbeitsagentur) | arbeitsagentur.de | gov | ✅ | no | future adapter (public job boerse API) |
| Make it in Germany | make-it-in-germany.com | gov/expat | ✅ | **yes** | manual (curated gov portal) |
| Indeed Germany | de.indeed.com | agg | 🌍 | partial | scraped today (indeed) |
| LinkedIn | linkedin.com/jobs | general | 🌍 | **yes** | scraped today (linkedin) |
| Monster.de | monster.de | general | ✅ | partial | YAML terms only |
| Arbeitnow | arbeitnow.com | tech/expat | ✅ | **yes** | scraped today (arbeitnow) |
| Glassdoor | glassdoor.de | agg | 🌍 | partial | YAML terms only |
| Jobvector | jobvector.com | tech (science/IT) | ✅ | yes | YAML terms only |
|:get-in-IT | get-in-it.de | tech | ✅ | partial | YAML terms only |
| Jobninja | jobninja.com | agg | ✅ | partial | future adapter |
| Hays / Robert Half DE | hays.de | recruiter | ✅ | yes | manual (recruiter-run) |

**Germany notes**
- StepStone is the #1 paid portal; XING is the #1 network (like a German
  LinkedIn) — both need accounts, so jobagent covers them via **search terms**,
  not scraping.
- **Arbeitsagentur** (BA) is the federal employment agency — its Jobbörse has a
  public search; a high-value future adapter.
- **Arbeitnow is already scraped** and is explicitly expat/English-friendly.
- Visa keywords for Germany (already in `config/countries/germany.yaml`):
  Blue Card, work permit, visa sponsorship, relocation support.

---

## 3. Netherlands 🇳🇱

| Portal | URL | Type | Country | Sponsor-friendly | Adapter status |
|---|---|---|---|---|---|
| LinkedIn NL | linkedin.com/jobs | general | 🌍 | **yes** | scraped today (linkedin) |
| Indeed NL | nl.indeed.com | agg | 🌍 | partial | scraped today (indeed) |
| Nationale Vacaturebank | nationalevacaturebank.nl | general | ✅ | partial | YAML terms only |
| Monsterboard NL | monsterboard.nl | general | ✅ | partial | YAML terms only |
| Undutchables | undutchables.nl | expat/recruiter | ✅ | **yes** | manual (recruiter-run) |
| IamExpat Jobs | iamexpat.nl/career | expat | ✅ | **yes** | manual |
| Together Abroad | togetherabroad.nl | expat | ✅ | **yes** | manual |
| OfferZen | offerzen.com | tech (reverse marketplace) | ✅ | **yes** | manual (profile-based; companies apply to you) |
| DevITJobs.nl | devitjobs.nl | tech | ✅ | **yes** | future adapter (public-ish listing pages) |
| Join.com | join.com | tech (startups) | ✅ | yes | future adapter |
| Glassdoor NL | glassdoor.com | agg | 🌍 | partial | YAML terms only |
| Werk.nl (UWV) | werk.nl | gov | ✅ | no | manual (Dutch-language, login) |

**Netherlands notes**
- The **30% ruling** and the **highly skilled migrant (HSM) visa** are the two
  sponsorship anchors — search terms should include "highly skilled migrant",
  "30% ruling", "visa sponsorship".
- **OfferZen** is unique: developers create a profile and companies apply to
  them — cannot be scraped, must be used manually.
- English-friendly expat boards (Undutchables, IamExpat) are where
  internationals actually get hired.

---

## 4. Ireland 🇮🇪

| Portal | URL | Type | Country | Sponsor-friendly | Adapter status |
|---|---|---|---|---|---|
| IrishJobs | irishjobs.ie | general | ✅ | **yes** | YAML terms only |
| Jobs.ie | jobs.ie | general | ✅ | partial | YAML terms only |
| Indeed Ireland | ie.indeed.com | agg | 🌍 | partial | scraped today (indeed) |
| LinkedIn Ireland | linkedin.com/jobs | general | 🌍 | **yes** | scraped today (linkedin) |
| Jobbio | jobbio.com | tech | ✅ | yes | future adapter |
| RecruitIreland | recruitireland.com | general | ✅ | partial | YAML terms only |
| CPL / Hays / Morgan McKinley | cpl.ie, morganmckinley.ie | recruiter | ✅ | **yes** | manual (recruiter-run) |
| JobsPlus (gov) | jobsplus.ie | gov | ✅ | no | manual |
| Glassdoor | glassdoor.com | agg | 🌍 | partial | YAML terms only |

**Ireland notes**
- Ireland's **Critical Skills Employment Permit** is the visa anchor — search
  terms: "critical skills", "stamp 1/4 support", "work permit", "relocation".
- Dublin hosts EMEA HQs of nearly every US tech giant → ATS boards (Greenhouse
  / Lever / Ashby) are **unusually productive for Ireland** — keep all 4
  adapters enabled.
- Jobbio powers several companies' own career pages — good future adapter.

---

## 5. United Kingdom 🇬🇧

| Portal | URL | Type | Country | Sponsor-friendly | Adapter status |
|---|---|---|---|---|---|
| Indeed UK | uk.indeed.com | agg | 🌍 | partial | scraped today (indeed) |
| LinkedIn UK | linkedin.com/jobs | general | 🌍 | **yes** | scraped today (linkedin) |
| Reed | reed.co.uk | general | ✅ | **yes** | **future adapter (public API exists!)** |
| Totaljobs | totaljobs.com | general | ✅ | partial | YAML terms only |
| CV-Library | cv-library.co.uk | general | ✅ | partial | **future adapter (public API exists)** |
| Monster UK | monster.co.uk | general | ✅ | partial | YAML terms only |
| Glassdoor UK | glassdoor.com | agg | 🌍 | partial | YAML terms only |
| Technojobs | technojobs.co.uk | tech | ✅ | partial | YAML terms only |
| CWJobs / Dice UK | theitjobboard.co.uk | tech | ✅ | partial | YAML terms only |
| UK Gov Find a Job | findajob.dwp.gov.uk | gov | ✅ | no | **future adapter (public API)** |
| Otta (Welcome to the Jungle) | otta.com | tech/startup | ✅ | yes | future adapter (curated, clean HTML) |
| WorkInStartups | workinstartups.com | startup | ✅ | partial | YAML terms only |

**UK notes**
- The **Skilled Worker visa register of licensed sponsors** (gov.uk) is the
  definitive sponsor list — the UK YAML already has "certificate of
  sponsorship" + "skilled worker visa" keywords; discovery search terms should
  add "licensed sponsor".
- **Reed, CV-Library and Find a Job all expose public APIs** — the three
  highest-value future adapters on this entire page.
- Otta is startup/tech-curated and has clean listing pages.

---

## 6. Singapore 🇸🇬

| Portal | URL | Type | Country | Sponsor-friendly | Adapter status |
|---|---|---|---|---|---|
| MyCareersFuture | mycareersfuture.gov.sg | gov | ✅ | yes (EP rules) | scraped today (mycareersfuture) |
| JobStreet Singapore | sg.jobstreet.com | general | ✅ | partial | YAML terms only |
| LinkedIn SG | linkedin.com/jobs | general | 🌍 | **yes** | scraped today (linkedin) |
| Indeed SG | sg.indeed.com | agg | 🌍 | partial | scraped today (indeed) |
| Glassdoor SG | glassdoor.com | agg | 🌍 | partial | YAML terms only |
| eFinancialCareers SG | efinancialcareers.sg | finance/tech | ✅ | yes | YAML terms only |
| Startup Jobs Asia | startupjobs.asia | startup | ✅ | partial | YAML terms only |
| Tech in Asia Jobs | techinasia.com/jobs | tech/startup | ✅ | partial | future adapter |
| JobTech | jobtech.sg | tech agg | ✅ | partial | YAML terms only |

**Singapore notes**
- The **Employment Pass (EP)** and its salary thresholds are the visa anchor —
  the SG YAML carries "employment pass" style keywords; add "EP eligible",
  "END YeAR" style terms only if seen in real listings.
- **MyCareersFuture is already scraped** — it is the government portal and
  every EP role must be posted there for 14 days first (fair-consideration
  rule) → **this is a structural advantage: SG jobs appear there first**.
- JobStreet is the biggest commercial board but requires login to apply
  (listings are still publicly viewable).

---

## 7. UAE 🇦🇪

| Portal | URL | Type | Country | Sponsor-friendly | Adapter status |
|---|---|---|---|---|---|
| Bayt.com | bayt.com | general | ✅ | **yes** | manual (login-walled; largest MENA board) |
| GulfTalent | gulftalent.com | general | ✅ | **yes** | manual (login-walled) |
| Naukrigulf | naukrigulf.com | general/expat | ✅ | **yes** | YAML terms only |
| Indeed UAE | ae.indeed.com | agg | 🌍 | partial | scraped today (indeed) |
| LinkedIn UAE | linkedin.com/jobs | general | 🌍 | **yes** | scraped today (linkedin) |
| Laimoon | laimoon.com | agg/courses+jobs | ✅ | partial | YAML terms only |
| Monster Gulf | monstergulf.com | general | ✅ | partial | YAML terms only |
| Dubizzle Jobs | dubizzle.com/jobs | general | ✅ | partial | YAML terms only |
| Michael Page / Hays Gulf | michaelpage.ae | recruiter | ✅ | **yes** | manual (recruiter-run) |

**UAE notes**
- In the UAE the **employer sponsors the visa by default** — most skilled jobs
  come with residency; the gate is whether the employer is willing, so
  sponsorship keywords matter less here than "will hire from abroad".
- **Bayt + GulfTalent are the two giants** but both wall their listings behind
  accounts → treat as manual portals; Naukrigulf listings are publicly
  viewable → good future adapter.
- Dubai's free zones (DIC, DIFC, Internet City) cluster tech employers —
  useful `search.extra_terms` additions.

---

## 8. India 🇮🇳 — **NEWLY ADDED to the system**

> India was added as the **7th country** via a new
> `config/countries/india.yaml` (zero code changes — the M3 drop-in design).
> The location classifier **already** mapped Bangalore/Bengaluru, Mumbai,
> Hyderabad, Pune, Chennai, Delhi/NCR, Noida, Gurgaon, Kolkata, Ahmedabad →
> `"India"`, so the moment the YAML exists, strategy/classification/eligibility
> all work.

| Portal | URL | Type | Country | Sponsor-friendly | Adapter status |
|---|---|---|---|---|---|
| Naukri | naukri.com | general | ✅ | n/a (domestic) | **#1 portal; login-walled — YAML terms + manual** |
| LinkedIn India | linkedin.com/jobs | general | 🌍 | n/a | scraped today (linkedin) |
| Indeed India | in.indeed.com | agg | 🌍 | n/a | scraped today (indeed) |
| Instahyre | instahyre.com | tech | ✅ | n/a | manual (curated, profile-based) |
| Cutshort | cutshort.io | tech/startup | ✅ | n/a | future adapter (public listing pages) |
| Wellfound | wellfound.com | startup/tech | 🌍 | n/a | scraped today (wellfound) |
| Foundit (Monster India) | foundit.in | general | ✅ | n/a | YAML terms only |
| Hirist | hirist.tech | tech | ✅ | n/a | future adapter |
| Internshala | internshala.com | intern/fresher | ✅ | n/a | YAML terms only (not core target) |
| Shine | shine.com | general | ✅ | n/a | YAML terms only |
| Apna | apna.co | general/blue-collar | ✅ | n/a | YAML terms only (not core target) |
| TimesJobs | timesjobs.com | general | ✅ | n/a | YAML terms only |
| Glassdoor India | glassdoor.com | agg | 🌍 | n/a | YAML terms only |

**India notes**
- No visa concept (domestic market) → the India YAML sets
  `visa.requires_sponsorship: false`, and the hybrid matcher's
  **NO_SPONSORSHIP_STATED hard-blocker must not fire for India** — Indian jobs
  simply don't mention sponsorship. (The visa component is scored, not
  blocked, when `requires_sponsorship` is false.)
- **Naukri is the monster** (the StepStone-of-India) but is login-walled for
  applications and aggressively bot-protected for scraping → keep as search
  term + manual portal, revisit as adapter only with care (ToS).
- **Instahyre / Cutshort / Hirist** are the quality tech boards where AI/ML
  roles actually concentrate; Cutshort + Hirist have publicly viewable
  listings → **best future adapters for India**.
- Wellfound already covers the Indian startup scene (it's in the scrapers
  today).
- Cities wired into the YAML: Bengaluru, Bangalore, Mumbai, Hyderabad, Pune,
  Chennai, Delhi, New Delhi, Noida, Gurgaon, Gurugram, Kolkata, Ahmedabad —
  matching `location_classifier.py` exactly.

---

## 9. Cross-country: portals that work everywhere

| Portal | Covers | Adapter status |
|---|---|---|
| LinkedIn | all 7 countries | scraped today |
| Indeed (per-country domains) | all 7 countries | scraped today |
| Glassdoor | all 7 countries | YAML terms only |
| Wellfound (startups) | all 7 (strong in India/UK/NL) | scraped today |
| RemoteOK / WeWorkRemotely / Remotive / Himalayas | remote roles for any country | scraped today |
| Greenhouse / Lever / Ashby / SmartRecruiters | company ATS boards in every country | scraped today |

---

## 10. Recommended `search.extra_terms` per country (copy into YAMLs)

These feed M4 discovery (countries × terms × adapters) — they bias search
toward sponsor-friendly listings:

```yaml
# germany.yaml
search:
  extra_terms: [english, visa sponsorship, blue card, relocation support]

# netherlands.yaml
search:
  extra_terms: [english, highly skilled migrant, 30% ruling, visa sponsorship]

# ireland.yaml
search:
  extra_terms: [critical skills permit, visa sponsorship, relocation]

# uk.yaml
search:
  extra_terms: [skilled worker visa, certificate of sponsorship, licensed sponsor]

# singapore.yaml
search:
  extra_terms: [employment pass, EP eligible, relocation]

# uae.yaml
search:
  extra_terms: [dubai internet city, DIFC, relocation package]

# india.yaml
search:
  extra_terms: [AI engineer, machine learning engineer, generative AI, LLM, python]

# canada.yaml  (ADDED 2026-09-28 — sponsor-heavy)
search:
  extra_terms: [AI engineer, machine learning engineer, LLM engineer, python developer]

# australia.yaml  (ADDED 2026-09-28 — sponsor-heavy)
search:
  extra_terms: [AI engineer, machine learning engineer, LLM engineer, python developer]

# poland.yaml  (ADDED 2026-09-28 — relocation-friendly EU hub)
search:
  extra_terms: [AI engineer, machine learning engineer, LLM engineer, python developer]
```

---

## 11. Future-adapter priority list (highest value first)

| # | Portal | Country | Why | Difficulty |
|---|---|---|---|---|
| 1 | **Reed** | UK | Official public API (job listings, free key) | LOW — clean REST |
| 2 | **CV-Library** | UK | Public API documented for partners | LOW-MED |
| 3 | **Find a Job (DWP)** | UK | Government open-data API | LOW |
| 4 | **Arbeitsagentur Jobbörse** | Germany | Federal board, public search/API | MED |
| 5 | **Cutshort** | India | Public listing pages, tech-concentrated | MED |
| 6 | **Hirist** | India | Public listings, AI/ML heavy | MED |
| 7 | **DevITJobs.nl** | NL | Viewable listings, sponsor-heavy | MED |
| 8 | **Jobbio** | Ireland | Powers many company pages | MED |
| 9 | **Naukrigulf** | UAE | Public listings | MED-HIGH (bot protection) |
| 10 | **Tech in Asia** | Singapore | Public listings | MED-HIGH |

> **Adapter rule (Golden Rule 9):** each of these becomes a
> `JobSourceAdapter` in `app/adapters/` + one line in `adapters/__init__.py`.
> Nothing else in the system changes.

---

## 12. What was DONE

**Session 1 (2026-09-28, earlier):**
1. ✅ This document created (`docs/JOB_PORTALS_BY_COUNTRY.md`).
2. ✅ **India added as the 7th country**: `root/config/countries/india.yaml`.
3. ✅ Docs server verified serving this file on port **8090**.

**Session 2 (2026-09-28, later) — IMPLEMENTATION + E2E GREEN:**
4. ✅ **Canada, Australia, Poland added** (sponsor-heavy trio):
   `canada.yaml` (LMIA + Global Talent Stream keywords), `australia.yaml`
   (482/186 employer-sponsored keywords), `poland.yaml` (relocation-package
   keywords). **10 countries total.**
5. ✅ **11 new discovery adapters registered** (4 → 15 in `ALL_ADAPTERS`):
   - **Jooble** (keyed — ONE API, localized boards in all 10 countries;
     the highest-leverage keyed source on this page)
   - **Adzuna** (keyed — per-country API markets: de/nl/ie/gb/in/ca/au/pl/ae/sg)
   - **9 country-scoped ports of existing keyless scrapers** via a shared
     `CountryScopedAdapter` facade: arbeitnow, remotive, jobicy,
     weworkremotely, remoteok, himalayas, 4dayweek, landingjobs, recruitee.
6. ✅ **E2E verified live** (`analysis/e2e_discovery_expansion.py`, report:
   `docs/E2E_DISCOVERY_EXPANSION_REPORT.md`): real orchestrator + real 15
   adapters + real HTTP → **49 real jobs ingested** (Canada 22, India 19,
   Poland 6, Australia 2); all 9 keyless sources healthy live; keyed sources
   degrade honestly without keys; region gate holds on every ingested row.
   **20/20 checks GREEN.**
7. ✅ BaseScraper `rate_limited_get` extended with optional `method="POST"`
   (backward-compatible) for Jooble; pagination-overlap dedup added in the
   facade + jooble/adzuna adapters; `JOBAGENT_JOOBLE_API_KEY` /
   `JOBAGENT_ADZUNA_APP_KEY` / `JOBAGENT_ADZUNA_APP_ID` env fallbacks wired
   into the discovery router (DB keys from Settings UI always win).
8. ✅ Settings UI: Jooble API Key field added next to Adzuna/JSearch.
9. ✅ Tests: +14 adapter/facade unit tests (`tests/test_discovery_expansion.py`,
   respx-mocked), country suite updated to 10; full suite green
   (874 non-scraper + 137 scraper + 184 frontend).
10. ⬜ **You supply the keys** (see §13) — Jooble first (one key, all countries).
11. ⬜ Future adapters from §11 (Reed UK is still the best next candidate).

---

## 13. API KEYS NEEDED (action list for Basil)

| Priority | Service | Get key at | Env var(s) | Unlocks |
|---|---|---|---|---|
| **1** | **Jooble** | https://jooble.org/api (free, email form) | `JOBAGENT_JOOBLE_API_KEY` | Localized discovery in **all 10 countries** from one key |
| **2** | **Adzuna** | https://developer.adzuna.com (free tier) | `JOBAGENT_ADZUNA_APP_KEY` + `JOBAGENT_ADZUNA_APP_ID` | Per-country markets (10 markets) |
| — | Hunter (contacts, optional) | hunter.io | `JOBAGENT_HUNTER_API_KEY` | Email discovery (M7, already wired) |
| — | Apollo (contacts, optional) | apollo.io | `JOBAGENT_APOLLO_API_KEY` | Contact discovery (M7, already wired) |

Paste into `root/.env` (then restart) **or** Settings → Scraper API Keys in
the UI. Without them everything still runs — the keyed adapters just report
an honest no-op in discovery telemetry.
