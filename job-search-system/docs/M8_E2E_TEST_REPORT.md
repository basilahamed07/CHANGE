# M8 E2E TEST REPORT — Application Package Generation

**Date:** 2026-09-23 (UTC)
**Milestone:** M8 — Application Builder (evidence-gated tailoring + DOCX-first package, Phase-19 layout)
**Method:** `analysis/e2e_module_test.py` section 16f — isolated instance of the real app
(fresh DB, evidence profile seeded from **Basil's real uploaded resume**), every check
exercised through the **live HTTP API** per Golden Rule #11.

**Harness result this run:** **137/137 passed** (127 PASS · 10 SKIP · 0 FAIL)
- The 10 SKIPs remain the pre-existing AI-quota checks (OpenRouter free tier, resets
  00:00 UTC). **All 8 M8 checks ran for real** — the refresh path packages stored
  text with zero AI, which is exactly the quota-dead scenario it was built for.
- Full-suite unit regression: **788 passed** (776 + 12 new M8 tests).

---

## What was verified (8 new checks, all PASS)

| # | Check | Result |
|---|-------|--------|
| 1 | `POST /api/packages/jobs/{id}/build?refresh=true` — stored text passes the evidence gate and packages (action=rebuilt) | PASS |
| 2 | **IDEMPOTENT:** identical inputs ⇒ action=noop, same fingerprint, files NOT rewritten | PASS |
| 3 | Package row + on-disk metadata: status=ready_for_review, hashes present, 4 files | PASS |
| 4 | `resume.docx` downloads — real OOXML (PK zip header), 37,587 bytes | PASS |
| 5 | `metadata.json` downloads | PASS |
| 6 | Unknown file (`evil.exe`) rejected with 400 | PASS |
| 7 | `GET /api/packages` lists the built job | PASS |
| 8 | Untouched job → 404 on package read | PASS |

## Package layout (Phase-19)

```
data/applications/0001-acme-ai/
    resume.docx          ← DOCX-first (what Basil actually sends)
    cover_letter.docx    ← only when a cover letter exists
    resume.txt           ← plain text for review + hashing
    cover_letter.txt
    metadata.json        ← schema jobagent-package/1
```

`metadata.json` audit trail: input fingerprint (sha256 over ALL generation inputs),
content hashes (JD, tailored resume, cover letter), resume_version_id, evidence
profile version, model used, full evidence-check result, `status: ready_for_review`.

## Guarantees delivered

| Guarantee | How it works |
|-----------|--------------|
| **Idempotency** (plan: unchanged inputs ⇒ no rewrite) | `PackageInputs.fingerprint()` = sha256 over job, JD hash, resume version, profile version, output hashes, model. Same fingerprint ⇒ `noop`, zero file writes (byte-compared in unit test) |
| **Evidence gate is the last line** (Rule 5) | Build REFUSES (`422`/`EvidenceViolationError`) any text failing EvidenceChecker — unverified claims can never materialize into a .docx. Unit test: nothing lands on disk on refusal |
| **Human review before anything ships** (Rule 6) | Every package is born `ready_for_review`; status only moves via explicit human action |
| **Quota-proof** | `refresh=true` repackages STORED tailored text with zero AI — verified live in a quota-dead run |
| **Security** | Download allowlist (5 filenames only); path traversal impossible |

## Bugs found and fixed in this session

1. **Corrupt-metadata path reported `built` instead of `rebuilt`** — meta existence
   must be captured before attempting parse; fixed and unit-covered.
2. **Test-harness issues:** FK constraint (package-meta test needed a real job row)
   and a fail-closed 503 in the API test (test app lacked a seeded evidence store —
   the product behaved correctly; the test now seeds a real store + checker).

## Definition-of-done evidence

- Unit: 12 tests in `tests/test_application_builder.py` — fingerprint sensitivity
  (4 distinct changes ⇒ 4 fingerprints), byte-level idempotency, rebuild-on-change,
  metadata audit trail, no-cover-letter case, evidence-violation refusal, corrupt
  metadata recovery, DB round-trip, API flow incl. honest 503.
- E2E: section 16f — real app, real HTTP, real DB, real filesystem, evidence gate
  live. DOCX verified as actual OOXML by magic bytes.
- Deterministic (Rule 4): packaging is pure Python + templates; zero LLM.

**M8 = DONE.** Next: M9 (outreach engine + Gmail DRAFTS — Critical Test #4 lives there).
