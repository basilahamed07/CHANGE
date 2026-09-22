# FEATURE MATRIX

Comparison of all five reference repositories against the features required by the
master build prompt. Legend: ✅ full support · 🟡 partial/related · ❌ absent.
"Decision" = what the final system in `root/` will do (KEEP = reuse CareerPulse,
EXTEND = build on CareerPulse base, PORT = adapt MIT-licensed code,
NEW = build from scratch, CONCEPT = idea only, source unlicensed).

| Feature | CareerPulse | Job Search Agent | Job App Pipeline | Apply Pilot | AI Job Search | Final System Decision |
|---|---|---|---|---|---|---|
| Job discovery | ✅ 17 sources | ✅ LinkedIn/Wellfound/JSearch | ✅ single URL | ❌ | ✅ ATS APIs + guest APIs | **EXTEND** — CareerPulse scheduler + adapters, ATS-first priority |
| ATS APIs | 🟡 Greenhouse only | ❌ | 🟡 reads ATS URLs | ❌ | ✅ 22 platforms | **PORT** Greenhouse/Lever/Ashby/SmartRecruiters from ai-job-search |
| Career-page discovery | ❌ | 🟡 generic_scraper | 🟡 JSON-LD | ❌ | 🟡 Firecrawl platform search | **NEW** — adapter slot + JSON-LD extraction (MIT port) |
| LinkedIn discovery | 🟡 via Google search | 🟡 Playwright (ToS risk) | ❌ | ❌ | 🟡 guest API only | **PORT** guest-API approach only; no authenticated scraping |
| Job deduplication | ✅ SHA-256 title+company+URL | 🟡 DB-level | ❌ | ❌ | 🟡 queue CSV | **EXTEND** — multi-signal: source ID, canonical URL, content hash, fuzzy title similarity, repost detection |
| Date verification | 🟡 last_seen_at freshness | 🟡 posted dates | ❌ | ❌ | 🟡 _parse_posted_date | **NEW** — VERIFIED_FRESH/STALE/DATE_UNKNOWN + posted-date evidence |
| Resume parsing | ✅ PDF/TXT/MD analyzer | ✅ PDF/DOCX processor | ✅ DOCX master | 🟡 bullet library | 🟡 cv_full.md | **KEEP** — CareerPulse analyzer, extended to evidence store |
| Candidate evidence store | ❌ profile rows, no status | ❌ | 🟡 master resume as truth | 🟡 bullet library | 🟡 CV as source of truth | **NEW** — evidence YAML w/ VERIFIED/UNVERIFIED/DISPUTED/DO_NOT_USE |
| ATS scoring | 🟡 inside LLM match | ✅ TF-IDF deterministic | ❌ | ❌ | ✅ rules+disqualifiers | **NEW** — deterministic TF-IDF (concept) + rules layer feeding hybrid score |
| Semantic matching | 🟡 embeddings for similarity | ✅ RAG retrieval | ❌ | ❌ | 🟡 LLM review pass | **EXTEND** — CareerPulse embeddings.py → evidence-collection retrieval |
| RAG | ❌ (similarity only) | ✅ ChromaDB | ❌ | ❌ | ❌ | **NEW** — provider-agnostic embedding abstraction (ChromaDB-compatible) |
| LLM matching | ✅ single-score matcher | ✅ agent scoring | ❌ | ✅ JD assessor | 🟡 LLM review only | **REPLACE** — multi-component weighted score; LLM supplies components, math stays in Python |
| Hard disqualifiers | 🟡 region/clearance filters | ❌ | ❌ | ❌ | ✅ disqualifier list | **PORT** — disqualifier framework → EligibilityEngine reason codes |
| Country filtering | 🟡 coarse regions | 🟡 location strings | ❌ | ❌ | 🟡 config.yml location | **NEW** — country YAML engine (Phase 5) |
| Visa/sponsorship detection | 🟡 hide visa-required toggle | ❌ | ❌ | ❌ | 🟡 text mentions | **NEW** — visa/sponsorship keyword engine per country |
| Company research | ✅ company_research.py | ❌ | ❌ | 🟡 JD-derived | ❌ | **KEEP+EXTEND** — cache per company, add careers/LinkedIn URLs + AI clues |
| Recruiter discovery | 🟡 contact_finder (web) | ❌ | ✅ Hunter/Apollo | 🟡 outreach strategy | ❌ | **PORT** — generalize into ContactProvider interface |
| Hiring-manager discovery | 🟡 generic contact | ❌ | 🟡 title classification | 🟡 assumed | ❌ | **NEW** — relationship taxonomy + confidence model |
| Referral discovery | 🟡 contacts CRM | ❌ | 🟡 dept head in search | 🟡 referral track | ❌ | **NEW** — POTENTIAL_REFERRAL relationship type |
| Email discovery | 🟡 via web search | ❌ | ✅ Hunter/Apollo verified | ❌ | ❌ | **PORT** — ContactProvider + email_status/confidence |
| Resume tailoring | ✅ tailoring.py + DOCX/PDF | ✅ Claude rewrite | ✅ reorder/rephrase only | ✅ bullet selection | ✅ keyword-matched, no fabrication | **EXTEND** — CareerPulse tailoring bound to evidence store |
| Anti-hallucination | ❌ | 🟡 "keep authentic" prompt | ✅ number-diff + similarity floor | 🟡 verifier prompts | ✅ no-fabrication rule | **PORT** — fabrication check → EvidenceChecker (hard gate, not warning) |
| Cover letter | ✅ cover_letter.py | ✅ | ❌ | ✅ framework+verifier | ✅ | **KEEP** — CareerPulse, evidence-bound |
| LinkedIn outreach | ❌ | ✅ connection/InMail drafts | ❌ | ✅ multi-track | ❌ | **PORT** — apply-pilot track model, config-driven |
| Cold email | 🟡 emailer (SMTP) | ✅ email drafts | ✅ Gmail draft | ✅ | ❌ | **PORT** — Gmail draft primary; SMTP optional |
| Gmail drafts | ❌ | ❌ | ✅ draft-only + dedup | ❌ | ❌ | **PORT** — GmailProvider interface; DRAFT-ONLY default; dedup by subject+thread |
| Application tracker | ✅ applications + app_events | ✅ SQLite statuses | 🟡 Google Sheet | 🟡 APPLICATIONS/ dir | 🟡 CSV queue | **KEEP** — CareerPulse CRM, extend status set (Phase 23) |
| Follow-up reminders | ✅ follow_up.py + reminders | ❌ | ❌ | 🟡 escalation tiers | ❌ | **EXTEND** — config-driven sequences, stop-on-terminal-state |
| Response tracking | 🟡 manual log endpoint | ✅ feedback command | ❌ | ❌ | 🟡 tracker CSVs | **NEW** — email classifier + low-confidence→REVIEW |
| Analytics | ✅ analytics.py + response rates | 🟡 dashboard text | ❌ | ❌ | ✅ effectiveness tracker | **EXTEND** — funnel, country/role/source breakdowns (Phase 30) |
| Feedback loop | 🟡 predictor (history-based) | ✅ response→matching | ❌ | ❌ | ✅ monthly recommendations | **NEW+CONCEPT** — recommendations for human review, no auto weight-rewrite |
| Scheduling | ✅ APScheduler, 8 jobs | ❌ | ❌ | ❌ | 🟡 manual runs | **KEEP** — per-country independent scheduled jobs |
| Dashboard | ✅ vanilla JS SPA | ❌ CLI only | ❌ | ❌ | 🟡 static dashboard | **KEEP+EXTEND** — add Kanban + Job Detail + Countries pages |
| REST API | ✅ 12 routers, OpenAPI | ❌ | ❌ | ❌ | ❌ | **KEEP** — add endpoints per Phase 32 |
| CLI | ❌ | ✅ Typer+Rich | ✅ argparse | ❌ | 🟡 scripts | **NEW** — `jobagent` CLI over the SAME service layer |
| Testing | ✅ 1,248 tests | 🟡 few | ❌ | ❌ | ✅ unit tests for scripts | **KEEP+EXTEND** — incl. 4 critical tests from Phase 38 |
| Authentication | ❌ (localhost trust) | ❌ | ❌ OAuth for Google | ❌ | ❌ | **NEW** — OAuth for Gmail/Sheets; optional app token |
| Logging | ✅ structured | 🟡 | 🟡 | ❌ | 🟡 | **KEEP** — structured logs, secrets masked |
| Retry handling | ✅ base scraper backoff | ✅ retry.py | 🟡 | 🟡 orchestrator retries | 🟡 | **KEEP** — backoff everywhere incl. providers |
| Multi-pass search self-correction | ❌ | ❌ | ❌ | ❌ | 🟡 multi-agent search | **NEW** — expand-until-target with stop reasons |
| Daily target (packages ≠ URLs) | 🟡 queue | 🟡 top-N | ❌ | ❌ | 🟡 queue CSV | **NEW** — qualifying-package targetting with shortfall reporting |
| Cost control | 🟡 Ollama option | ✅ local embeddings | ✅ cents-per-run | ✅ flat plan | ✅ Python-first doctrine | **NEW** — token/credit metering + caching + eligibility-first LLM gating |
| Human approval gates | ✅ queue approval | ❌ | 🟡 review drafts | 🟡 review outputs | 🟡 review resumes | **EXTEND** — approval matrix per Phase 34 |
| Observability (run_id etc.) | 🟡 progress endpoints | ❌ | 🟡 run printout | ❌ | ❌ | **NEW** — search_runs/generation_runs with provider errors + LLM cost |

## Score summary (feature coverage of required list)

| Repo | Full | Partial | Absent |
|---|---|---|---|
| CareerPulse | 18 | 15 | 8 |
| ai-job-search | 9 | 12 | 20 |
| job_search_agent | 8 | 7 | 26 |
| job-application-pipeline | 7 | 6 | 28 |
| apply-pilot | 4 | 8 | 29 |

CareerPulse wins on breadth and is the only full web product → confirms it as the base.
No single repo covers the required feature list → targeted porting + a NEW layer
(evidence, country, eligibility, hybrid matching, contacts, response monitor) is required.
