# M9 E2E TEST REPORT — Outreach Engine + Gmail Drafts

**Date:** 2026-09-23 (UTC)
**Milestone:** M9 — Outreach engine (audience variants, config-driven sequences) + GmailProvider DRAFT-ONLY
**Method:** `analysis/e2e_module_test.py` section 16g — isolated instance of the real app
(fresh DB, evidence profile seeded from **Basil's real uploaded resume**), every check
exercised through the **live HTTP API** per Golden Rule #11.

**Harness result this run:** **147/147 passed** (137 PASS · 10 SKIP · 0 FAIL)
- The 10 SKIPs remain the pre-existing AI-quota checks. **All 10 M9 checks ran for
  real** — outreach templates are deterministic (no AI quota needed).
- Full-suite unit regression: **805 passed** (788 + 17 new M9 tests).

---

## ✅ CRITICAL TEST #4 — PASSED at three layers

> **Creating outreach twice MUST NOT create a second draft.**

| Layer | Enforcement | Proven by |
|-------|-------------|-----------|
| Service | Dedup-first: `get_outreach(job, audience)` before any creation → returns `already_exists` with the SAME message id | Unit `test_critical_4_double_outreach_single_draft` + E2E via API |
| Database | `UNIQUE(job_id, audience)` — a raw duplicate INSERT raises even if code is bypassed | Unit `test_critical_4_db_unique_constraint_backstop` |
| Provider (Gmail) | `find_existing_draft(subject)` thread lookup before creating; if found → reuse the existing draft id, `create_draft` never called | Unit `test_gmail_thread_dedup_prevents_second_draft` |

E2E live check: second `POST /api/outreach/jobs/{id}/create` → `status: already_exists`,
identical message id, and `GET /api/outreach/jobs/{id}` shows **exactly 1 row**.

## What was verified (10 new checks, all PASS)

| # | Check | Result |
|---|-------|--------|
| 1 | Config: audiences + caps + identity; gmail_connected=false | PASS |
| 2 | Create → draft with rendered subject/body (status=created) | PASS |
| 3 | Message born `drafted` via `local` provider (no token configured) | PASS |
| 4 | Rendered subject carries job title — zero unfilled `{placeholders}` | PASS |
| 5 | **CRITICAL #4:** second create ⇒ already_exists, SAME id | PASS |
| 6 | Exactly ONE outreach row for the job | PASS |
| 7 | Second audience on the same job allowed (dedup is per-audience) | PASS |
| 8 | Follow-up refused before the 6-day wait window | PASS |
| 9 | Unknown audience → 422 | PASS |
| 10 | (unit) DB UNIQUE backstop + gmail-thread dedup + caps matrix | PASS |

## Architecture delivered (M9)

| Piece | File | Notes |
|-------|------|-------|
| Sequences config | `config/outreach_sequences.yaml` | recruiter / hiring_manager / referral / followup — Phase-21 config-over-code; placeholders rendered deterministically |
| Outreach engine | `app/outreach.py` | `OutreachService.create_outreach` (idempotent), `create_followup` (6-day gate), deterministic `_pick_audience` from the contact on file (classify_role reuse), anti-spam caps (12/day, 2/company/day) |
| Gmail provider | `GmailProvider` | REST via httpx (zero new deps); `create_draft` + `find_existing_draft` — **no send method exists**; local-draft fallback when no token, so the pipeline completes without Gmail |
| API | `app/routers/outreach.py` | POST jobs/{id}/create · POST jobs/{id}/followup · GET jobs/{id} · GET messages · GET config |
| DB | `outreach_messages` | UNIQUE(job_id, audience), provider/draft_id/thread_id, FK to jobs |

## Safety model (Golden Rule 6)

1. Every message is born `status='drafted'` — **no send code path exists in M9**.
2. Gmail integration is DRAFT-ONLY: `create_draft`/`find_existing_draft` only; the
   word "send" does not appear in the provider.
3. Sending later (M10 approval flow) will require **JOBAGENT_ALLOW_SEND=true** AND
   per-draft human approval — neither exists today.
4. `gmail_connected` is honestly reported false in the config endpoint; drafts land
   locally so nothing is lost and sync can happen after OAuth is set up.

## Notes

- `JOBAGENT_GMAIL_TOKEN` (OAuth access token) is the only switch needed to make
  drafts land in Basil's real Gmail drafts folder; the local fallback keeps
  everything working until then.
- AI-written message variants (beyond templates) are deliberately deferred —
  templates are deterministic, auditable, and cost zero quota.

**M9 = DONE.** Next: M10 (CRM + follow-up engine + approval matrix).
