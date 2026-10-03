# DEFECT BACKLOG — pipeline stages 4 → 10

> Consolidated, prioritised list of every **open** defect found by the stage audits for stages 5–10.
> Each entry cites the stage audit it came from for the full code quote and reasoning. (Stage-4 SCORE's
> defects are already hardened and are tracked separately in `docs/score/SCORE_AUDIT.md`.)
>
> **Status: nothing in this file has been executed or reproduced live.** The environment's command
> classifier refused every `pytest`/script invocation during the audit session. Every item below is a
> *static* finding from reading `file:line`. Treat "confirmed" as "confirmed in source", not "reproduced".
>
> Companions: `docs/STAGE_ROADMAP.md` (status board) · `docs/<stage>/<STAGE>_AUDIT.md` (full analysis).

---

## How to read the severity column

| Level | Meaning |
|---|---|
| **P0 — act now** | Silent data loss, an ungated outward action, or a security hole. Fix before anything else. |
| **P1 — corrupt** | Produces a wrong result a user would act on (wrong job packaged, wrong score kept, wrong report). |
| **P2 — dishonest** | Succeeds while failing, or reports something it did not do. |
| **P3 — hygiene** | Dead code, wrong input, naming, determinism of stored artefacts. |

---

## P0 — act now

> **Status (2026-10-03):** all four P0s are now fixed — **#1** (ungated send, deleted), **#2**
> (reviewed-text overwrite, default inverted), **#3** (hybrid vs AI score, column-ownership split —
> was already in the working tree), **#4** (SSRF, committed `c96e0f7`). **38 defects remain**
> (9 P1 · 5 P2 · 24 P3).

### 1. Ungated SMTP send endpoint — Stage-9 **O1** — ✅ **FIXED (2026-10-03)**
`app/routers/pipeline.py:112-127`
`POST /jobs/{id}/send-email` sent real mail via SMTP with **no** `JOBAGENT_ALLOW_SEND` check and **no**
`approval_required()` call — though `crm.py:182` registers `outreach_send` as high-risk/explicit. The M9
module correctly has no send path; this endpoint was the one that did.
**Fixed by deletion, not gating:** the route, the `send_application_email()` helper, the UI button and
its handler were all removed — jobagent is draft-only, so no sender should exist even dormant.
**Tests:** `test_send_job_email_endpoint_is_removed` (route 404s) and
`test_no_send_email_route_is_registered` (no `send-email` route under any method). Full detail in
`docs/outreach/OUTREACH_AUDIT.md` §O1.

### 2. Default package build overwrites human-reviewed text — Stage-8 **D1** — ✅ **FIXED (2026-10-03)**
`app/routers/packages.py:38,54,61-93`
`refresh` defaulted to `False`, so a plain `POST .../build` took the AI branch and wrote the fresh
generation over the reviewed `tailored_resume`. The flag that preserved reviewed work was opt-in, and its
name was inverted.
**Fixed as recommended:** `POST /build` now packages the **stored reviewed text unchanged at zero AI**;
regeneration requires an explicit `regenerate=true`; `refresh=true` is a legacy alias for the safe path;
a build with no reviewed text is an honest `409`. `metadata.json` gains `generated_by`.
**Tests:** `test_default_build_packages_stored_text_without_ai`,
`test_regenerate_true_overwrites_and_records_provenance`,
`test_default_build_refuses_when_no_reviewed_text` (`tests/test_application_builder.py`, 15 passed). Detail
in `docs/packages/PACKAGES_AUDIT.md` §D1.

### 3. Manual hybrid re-score destroys the AI score permanently — Stage-5 **H1** — ✅ **FIXED (2026-10-03)**
`app/routers/matching.py:32-47`, `app/database.py:1180`, `app/database.py:1731`
`upsert_hybrid_score` was `INSERT OR REPLACE` on `job_scores.job_id UNIQUE`, and `get_scoreable_jobs`
required `js.id IS NULL`. So re-scoring a job with the hybrid engine replaced the AI row **and** removed
the job from every future AI scoring pass — irreversible without clearing the score table.
**Fixed (found already implemented in the working tree; docs were stale):** `job_scores` gained separate
`ai_score` / `hybrid_score` columns (+ a backfilling migration); each engine owns its own columns and
`match_score` mirrors whichever is effective; `get_scoreable_jobs` keys off `js.ai_score IS NULL`.
**Tests:** `tests/test_scoring_ownership.py` — **8 passed**. Detail in `docs/hybrid/HYBRID_AUDIT.md` §H1.

### 4. SSRF-shaped server-side fetch — Stage-7 **R3**
`app/routers/research.py:78-80`, `app/company_enrichment.py:75-92`
`website` is an unvalidated query parameter the server `GET`s with `follow_redirects=True`. Admits
`http://localhost:…`, `http://169.254.169.254/…`, and internal hosts; the response body is parsed back to
the caller through `description`/`careers_url`/`ai_clues`.
**Fix:** allowlist or drop the parameter; refuse private/link-local hosts; re-validate redirect targets.

---

## P1 — produces a wrong result

### 5. Evidence gate does not validate personal facts — Stage-8 **D2**
`app/evidence_checker.py:181-185`
Only numbers / similarity / thin-lines / skills are checked. A generated line changing relocation
country (`Singapore` → `Amsterdam`) or flipping visa sponsorship passes — **proven live** in run
`2026-09-24_125119`.
**Fix:** add `_check_personal_facts` covering relocation target, sponsorship stance, willingness, years.
Must match candidate evidence, never the JD. Fail → regenerate once → 422.

### 6. Selection never re-checks eligibility — Stage-6 **S3**
`app/database.py:3750-3752`
`get_top_unpackaged_jobs` filters `dismissed`/`strategy_dismissed` only. A score row survives an
eligibility flip (nothing prunes `job_scores` on eligibility change), so a job that went stale is still
selected and packaged.
**Fix:** add `AND j.eligibility_status = 'ELIGIBLE'`.

### 7. Digest has no eligibility filter — Stage-10 **G4**
`app/digest.py:17`
Same root cause as #6: a job whose eligibility flipped after scoring still satisfies the digest query and
is headlined as a "new match".

### 8. Gmail draft dedup can adopt another job's draft — Stage-9 **O2**
`app/outreach.py:183-199`, `:289-293`
`find_existing_draft` searches the whole mailbox by subject substring and returns `drafts[0]`. Two jobs
sharing a rendered subject ⇒ job B records job A's draft id and **no draft is created for B**, silently.
**Fix:** scope by subject **and** recipient; verify company/job before adopting.

### 9. A transient provider failure is cached as "no contact" for 7 days — Stage-7 **R2**
`app/contact_providers.py:353-363`, `:398-403`
`find()` swallows every exception into `[]`, so a timeout / 429 / bad key is written as
`status="not_found"` and treated as fresh for a week. Six more daily runs "succeed" on the negative.
**Fix:** do not persist a fresh negative when any provider errored.

### 10. `/api/matching/score-all` scores against an empty profile — Stage-5 **H2**
`app/routers/matching.py:68-71`, `app/matching_service.py:94-106`
The router passes a stub state with only `.matcher`; `build_hybrid_matcher_async` reads `evidence_store`
and `country_registry`, both absent ⇒ no verified skills, no corpus, no visa keywords ⇒ every job gets
skills=50 / semantic=50.
**Fix:** pass the real per-user state.

### 11. Provider keys are read from process env, not the workspace — Stage-7 **R1**
`app/contact_providers.py:182`, `:225`
`HunterProvider()` / `ApolloProvider()` take keys from `os.getenv`, ignoring the workspace `scraper_keys`
table. In multi-user deployments every user shares one key or none.
**Fix:** build the chain from workspace settings; env only as the documented fallback.

### 12. The digest is not a run report — Stage-10 **G1**
`app/digest.py:9-61`
It counts new high-scoring **jobs** and never reports packages created, `target_met`, or a shortfall
reason — though `daily_run.py:43-54` exists for exactly that. A run that built 0 packages emails
"jobagent: 12 new matches", a success-shaped message about a failed day.
**Fix:** lead with the outcome (packages vs target + `shortfall_reasons()`); listing becomes secondary.

### 13. The API daily-run executes almost nothing — Stage-6 **S6**
`app/routers/crm.py:188-193`
Only `select` and `packages` are supplied; the other eight stages are `None` →
`status="skipped", reason="not_implemented"` (`daily_run.py:158-161`). And `_packages` builds nothing —
it counts pending rows. So the user-visible "run today" builds no packages and cannot meet its target.

---

## P2 — succeeds while failing / dishonest reporting

### 14. Hardcoded shortfall reason — Stage-6 **S4**
`app/routers/crm.py:179-180` — always reports `ALL_SCORED_BELOW_CUTOFF` when the count is short, whatever
the real cause.

### 15. `refresh=true` silently spends an AI call — Stage-8 **D3**
`app/routers/packages.py:54,61-63` — with no stored text the "no-AI" flag falls through to the AI path.

### 16. Empty digest reported as a config failure — Stage-10 **G5**
`app/digest.py:128-130` + `analytics.py:344-349` — `False` means both "not configured" and "nothing to
report"; the test endpoint always blames settings.

### 17. "New in the last 24h" is discovery time, not freshness — Stage-10 **G3**
`app/digest.py:11,17` — filters `jobs.created_at`; a 45-day-old posting scraped today reads as new.
Relates to Golden Rule 10.

### 18. Stage-9 is not wired to anything that runs — Stage-9 **O5**
`OutreachService` is constructed only in the router and tests; the pipeline passes `outreach: None`.

---

## P3 — hygiene / determinism

| # | Defect | Location | Stage |
|---|---|---|---|
| 19 | `select_candidates` is dead code; real selection is an inline router closure | `daily_run.py:189` vs `routers/crm.py:176` | 6 **S1** |
| 20 | No tie-break in selection ⇒ different sets across runs on tied scores | `database.py:3753` | 6 **S2** |
| 21 | Score cutoff duplicated as literal `60`, ignoring `DailyRun.score_cutoff` | `routers/crm.py:177,185` | 6 **S5** |
| 22 | Async embedding RAG provider is dead code — always local TF-IDF | `hybrid_matcher.py:329` (0 callers) | 5 **H3** |
| 23 | Skills component measures candidate-skill coverage, not requirement match | `hybrid_matcher.py:188-213` | 5 **H4** |
| 24 | Partial weight sets silently renormalised with injected defaults | `hybrid_matcher.py:453-459` | 5 **H5** |
| 25 | `role_match=True` when no target titles are declared | `hybrid_matcher.py:104,222` | 5 **H6** |
| 26 | Stored reason lists are set-iteration-ordered ⇒ non-deterministic | `matching_service.py:41-57` | 5 **H7** |
| 27 | Scheduler scores into the global DB, not a workspace | `main.py:286` | 5 **H8** (N3) |
| 28 | Contacts with no email are re-created on every selection | `contact_providers.py:378-390` | 7 **R5** |
| 29 | Wrong domain guess cached 30 days as "complete" | `company_enrichment.py:33-35,89-90` | 7 **R4** |
| 30 | `classify_role` fed a name / an email address | `contact_providers.py:130`, `outreach.py:237` | 7 **R6**, 9 **O6** |
| 31 | `base_by_provider` parameter is never passed | `contact_providers.py:86-96,131` | 7 **R7** |
| 32 | New `httpx.AsyncClient` per provider call (no reuse/retry) | `contact_providers.py:199,231` | 7 **R8** |
| 33 | `OutreachService` default re-opens the env-token path | `outreach.py:213` | 9 **O3** |
| 34 | `force_audience=False` silently discards an explicit audience | `outreach.py:248,259` | 9 **O7** |
| 35 | Raw RFC2822 message built by f-string, no CRLF sanitisation | `outreach.py:163-167` | 9 **O8** |
| 36 | Follow-up wait measured only from the first outreach | `outreach.py:312-322` | 9 **O9** |
| 37 | Rendered content has no length/control-char guard | `outreach.py:102-121` | 9 **O10** |
| 38 | Scale: daily cap is a rolling 24h window, named "per day" | `outreach.py:217-223` | 9 **O4** |
| 39 | Schedule values other than `"daily"` silently mean weekly | `digest.py:123-124` | 10 **G6** |
| 40 | No tie-break on the digest top-20 cut | `digest.py:18-19` | 10 **G7** |
| 41 | Parsed `match_reasons` discarded before render | `digest.py:25-27,53-60` | 10 **G8** |
| 42 | No `generated_by` provenance in package metadata | `application_builder.py:149-170` | 8 **D4** |

---

## What holds — verified, so hardening does not need to prove it again

- **Stage-4 gate:** only `ELIGIBLE` + classified + unscored jobs reach scoring (`database.py:1731`).
- **Stage-5:** zero LLM anywhere in the hybrid path; blocker cap applied consistently.
- **Stage-6:** Critical Test #4 — one outreach per `(job, audience)` — is enforced at **two** layers
  (service check + DB `UNIQUE`, `database.py:568`).
- **Stage-7:** the provider chain genuinely never raises; role/confidence/ranking are pure Python;
  no-key operation works via manual + web.
- **Stage-8:** the 422 evidence gate fires **before** `builder.build`; download uses a literal 5-name
  allowlist; fingerprint no-op works.
- **Stage-9:** `app/outreach.py` has no send path (the send lives in `pipeline.py` — defect #1).
- **Stage-10:** HTML output is correctly escaped; SMTP fails soft when unconfigured.

---

## Ordering recommendation

Fix in this order — each step is independent of the ones below it:

1. **#1, #4** — the send endpoint and the SSRF fetch. Both are outward-facing; both are small.
2. **#2, #5, #3** — the three silent-destruction bugs (reviewed text, personal facts, AI score).
3. **#6, #7** — eligibility re-check in select and digest; one query change each, removes a whole class.
4. **#8, #9** — outreach draft mislink and the cached-negative research.
5. **#12, #13** — make the daily run and its report honest before adding new stages.
6. **P2, then P3** — reporting honesty, then hygiene.

Every item needs a regression test. The stage audits already name the test for each.
