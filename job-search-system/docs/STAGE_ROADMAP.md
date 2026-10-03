# STAGE ROADMAP — pipeline stages 4 → 10

> **What this file is:** the master tracker for hardening the remaining pipeline stages.
> Stages 1–3 were hardened one at a time; this is the plan and status board for 4–10.
> Each stage gets its own `docs/<stage>/` folder — this file links to them.
>
> **Source of the stage list:** `app/daily_run.py:29` (`STAGES`) — the canonical order.
> When this file and the code disagree, the code wins.

---

## Why

The pipeline is ten ordered stages. Stages 1–3 (DISCOVER, CLASSIFY, ELIGIBILITY) were each
audited, hardened, unit-tested, live-verified against a copy of the real DB, and documented in
their own `docs/` folder. Stages 4–10 have never had that treatment — they work, but their
contracts are implicit and their failure modes are not all pinned by tests.

**Outcome:** every stage has an explicit, tested, documented contract, so the whole flow is
auditable and failures stay honest instead of silent.

---

## Status board

| # | Stage | Code | Audit | Harden | Tests | Live-verify | Docs | Status |
|---|-------|------|-------|--------|-------|-------------|------|--------|
| 1 | DISCOVER | `app/discovery.py`, `app/source_registry.py` | ✅ | ✅ | ✅ | ✅ | `docs/discovery/` (10 files) | **DONE** · committed `18575d6`, `af31874` |
| 2 | CLASSIFY | `app/classification.py` | ✅ | ✅ | ✅ 70 tests | ✅ | `docs/classify/` (6 files) | **DONE** · committed `1a5483d` |
| 3 | ELIGIBILITY | `app/eligibility.py` | ✅ | ✅ | ✅ 33 tests | ✅ | `docs/eligibility/` (7 files) | **DONE** · *uncommitted* |
| 4 | SCORE (AI) | `app/matcher.py`, `app/main.py:458` | ✅ | ✅ | ✅ 23 tests | ✅ | `docs/score/` (6 files) | **DONE** · 23 tests green, live-verified, real AI call (3/3 scored) · *uncommitted* |
| 5 | HYBRID_SCORE | `app/hybrid_matcher.py`, `app/matching_service.py` | ✅ | ⬜ | ⬜ | ⬜ | `docs/hybrid/HYBRID_AUDIT.md` | audit done — 8 defects (H1–H8); **H1 fixed** (ownership split, verified); rest not started |
| 6 | SELECT | `app/daily_run.py:189` | ✅ | ⬜ | ⬜ | ⬜ | `docs/select/SELECT_AUDIT.md` | audit done — 6 defects (S1–S6); hardening not started |
| 7 | RESEARCH | `app/company_enrichment.py`, `app/contact_providers.py` | ✅ | ⬜ | ⬜ | ⬜ | `docs/research/RESEARCH_AUDIT.md` | audit done — 8 defects (R1–R8); hardening not started |
| 8 | PACKAGES | `app/application_builder.py`, `app/evidence_checker.py` | ✅ | ⬜ | ⬜ | ⬜ | `docs/packages/PACKAGES_AUDIT.md` | audit done — **D1/D3/D4 fixed**; **D2 open** (personal-facts guard); rest not started |
| 9 | OUTREACH | `app/outreach.py` | ✅ | ⬜ | ⬜ | ⬜ | `docs/outreach/OUTREACH_AUDIT.md` | audit done — 10 defects (O1–O10); **O1 fixed** 2026-10-03 (send deleted); rest not started |
| 10 | DIGEST | `app/digest.py` | ✅ | ⬜ | ⬜ | ⬜ | `docs/digest/DIGEST_AUDIT.md` | audit done — 8 defects (G1–G8); hardening not started |

> **Where this stands (2026-10-03, after execution):** Stage-4 SCORE is **DONE and proven** — 23 unit
> tests green, full backend suite **1171 passed / 0 failed**, live-verified on a copy of the real DB
> (pool 26 eligible, `stage3_leaked_scores=0`), and a real end-to-end AI call scored 3/3 eligible jobs
> with nothing fabricated. **All four P0 defects are now fixed** (see the list below). Stages 5–10 are
> otherwise **audited only** — 38 defects remain open, and none of those stages has been hardened or
> tested against its own contract. See `docs/DEFECT_BACKLOG.md` for the consolidated, prioritised defect list and
> `docs/STAGE_TEST_RESULTS.md` for the execution log.
>
> **The three audit findings that change behaviour for a user today:**
> 1. ~~**Stage-9 O1** — `POST /jobs/{id}/send-email` sends real mail over SMTP with **no** approval
>    gate (`app/routers/pipeline.py:112`). The only ungated send path in the app.~~ ✅ **FIXED
>    2026-10-03** — the endpoint, its helper, and the UI send button were deleted; jobagent is
>    draft-only. Guards: `test_send_job_email_endpoint_is_removed`,
>    `test_no_send_email_route_is_registered`.
> 2. ~~**Stage-5 H1** — a manual hybrid re-score **permanently destroys** the AI score for that job
>    (the job is then excluded from `get_scoreable_jobs`, so it can never be re-scored).~~ ✅ **FIXED**
>    — score column-ownership split (`ai_score` vs `hybrid_score`); `get_scoreable_jobs` keys off
>    `ai_score IS NULL`. `tests/test_scoring_ownership.py` 8 passed.
> 3. ~~**Stage-8 D1** — a default `POST /api/packages/jobs/{id}/build` overwrites human-reviewed resume
>    text with a fresh AI generation.~~ ✅ **FIXED** — build defaults to the stored reviewed text at zero
>    AI; regeneration requires explicit `regenerate=true`; `metadata.json` records `generated_by`.

**Phase 0 — ✅ COMPLETE (2026-10-03):** `analysis/resume_ai_eval.py` ran with **3/3 AI calls** against
the real resume (DeepSeek): ATS 90/100, best-fit role *Agentic AI Engineer*. Findings:
`docs/RESUME_AI_EVAL.md`.

---

## Per-stage document set

Each `docs/<stage>/` folder gets this set — the convention established by `docs/classify/` and
`docs/eligibility/`:

| File | Contents |
|------|----------|
| `<STAGE>_OVERVIEW.md` | what the stage is, its contract, inputs → outputs |
| `<STAGE>_AUDIT.md` | what the code actually did before hardening; defects found |
| `<RULES>.md` | the explicit decision/gate/selection rules |
| `TEST_RESULTS.md` | unit-test inventory and counts |
| `LIVE_SAMPLE_RESULTS.md` | results of the live-verify run on real data |
| `KNOWN_LIMITATIONS.md` | honest limits, unfixed issues, recommendations |
| `results/<stage>_summary.json` | machine-readable summary from the live-verify script |

Stage-specific additions are allowed — `docs/eligibility/` adds `QUALITY_AUDIT.md`, and
`docs/discovery/` carries ten files including per-source matrices.

---

## Per-stage work (what hardening means here)

Same six-step sequence for every stage:

1. **Audit** — read the real code; record what it does vs what it claims; list defects.
2. **Harden** — make the contract explicit: one documented entry point returning a machine-readable
   result; persist decision + reason + evidence; add metrics to `search_config`; zero LLM where
   determinism is required; fail honestly.
3. **Tests** — `tests/test_<stage>.py`, ~20–35 tests, one regression test per defect found.
4. **Live verify** — `analysis/verify_<stage>_live.py`, run against a **copy** of Basil's real DB
   (never the live file), printing per-item results and writing a JSON summary.
5. **Docs** — the folder above.
6. **Memory + commit** — update `PROJECT_MEMORY.md`, then commit.

### Stage 4 — SCORE (AI)
`app/matcher.py` (`JobMatcher:179`, `BATCH_SCORING_PROMPT:95`), `app/main.py#_score_unscored:458`,
`app/ai_client.py`, `app/ai_usage.py`.
Confirm the Stage-3 gate is the only entry to scoring; persist score provenance (model, prompt
version, attempts, source); prove an unrecoverable AI failure writes **no** score row.
*Watch item:* `country_code` is NULL on ~1,962 legacy rows, so Stage-3's LOCATION gate never
engaged on live data — Stage-4's input pool is wider than intended until Stage-2 re-runs.

### Stage 5 — HYBRID_SCORE
`app/hybrid_matcher.py`, `app/matching_service.py`.
Pin the 6 weights and their normalization; assert hybrid **never overwrites** a good AI score;
prove zero LLM on the path; prove the pool is never left unscored when AI is down.

### Stage 6 — SELECT
`app/daily_run.py#select_candidates:189`.
Deterministic selection with a documented tie-break; already-packaged jobs excluded by fingerprint;
target counts **qualifying packages**, not jobs (Golden Rule 7); idempotent across runs.

### Stage 7 — RESEARCH
`app/company_enrichment.py`, `app/contact_providers.py`, `app/routers/research.py`.
Confirm the Manual → Hunter → Apollo → WebSearch chain never raises; persist why a contact was
chosen; verify the 7-day cache TTL is honest; no paid key still yields a usable (possibly empty) result.

### Stage 8 — PACKAGES  ← carries two **known live defects**
`app/application_builder.py`, `app/routers/packages.py`, `app/evidence_checker.py`.
- **Defect 1:** `POST /api/packages/jobs/{id}/build` re-generates and overwrites the text a human
  reviewed; `refresh=true` is the zero-AI path, so the flag reads backwards. Fix: build defaults to
  the stored reviewed text; regeneration requires explicit `regenerate=true`.
- **Defect 2:** the evidence gate did not catch a rewritten **personal fact** (relocation country
  changed, and visa sponsorship flipped `welcomed` → `required` between two runs). Fix: add a
  personal-facts guard (relocation target, visa sponsorship, willingness, years) that must match the
  candidate's evidence, not the JD. Fail → regenerate once → 422.
- Record `generated_by: "stored" | "regenerated"` in `metadata.json`.

### Stage 9 — OUTREACH
`app/outreach.py`, `app/routers/outreach.py`, `config/outreach_sequences.yaml`.
Confirm no send method exists anywhere; verify the three dedup layers (Critical Test #4); verify caps
(12/day, 2/company/day) and the 6-day follow-up wait; persist why a draft was refused.

### Stage 10 — DIGEST
`app/digest.py`, `app/routers/analytics.py`.
A run that produced zero packages must report the shortfall reason (`daily_run.py:44` vocabulary),
never success. SMTP stays optional and honest when unconfigured.

---

## Verification (per stage — all four must pass)

```powershell
cd D:\personal_project\CHANGE\CHANGE\job-search-system\root

uv run pytest tests/test_<stage>.py -q                          # 1. stage unit tests
uv run python ../analysis/verify_<stage>_live.py                # 2. live verify (DB copy)
uv run pytest tests/test_classification.py tests/test_eligibility.py -q   # 3. regression
uv run pytest -q --timeout=300                                  # 4. full backend suite
```

**Golden Rule #11:** unit tests passing is not done. A stage is done when it is proven through the
running product, its live-verify is green on real data, and the full suite passes.

---

## Carry-in items

1. **Stage-3 is uncommitted** — decide whether to commit 1–3 before Stage-4 lands.
2. **`country_code` NULL gap** — ~1,962 legacy rows never reclassified (Stage-2 only reclassifies
   `location_classified=0`). Widens Stage-4's pool. Resolve before or during Stage-4.
3. **Doc drift** — `docs/AGENT_CONTEXT.md` §2 says "21 scrapers + 15 ATS adapters"; the registry
   (`app/source_registry.py:98`) holds 20 entries. Code wins; fix the doc.
4. **Phase-0 blocked** — `JOBAGENT_DEEPSEEK_API_KEY` must be in `root/.env`.

## Related docs

`docs/AGENT_CONTEXT.md` (read first) · `PROJECT_MEMORY.md` · `docs/NEXT_5_PLAN.md` (the separate
N2–N5 multi-user queue, not this roadmap) · `docs/DAILY_RUN_GUIDE.md` (stage deep-dive) ·
`docs/E2E_RUN_STATUS.md` (live status board)
