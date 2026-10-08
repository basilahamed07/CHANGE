# Status and Next Plan - 2026-10-04

## Completed In This Session

### 1. Scrape and Scoring Performance

- Legacy `run_scrape_cycle` now fetches scraper sources concurrently with a bounded semaphore.
- Database insert/dedup still runs sequentially to avoid SQLite write-lock problems.
- New config:
  - `JOBAGENT_SCRAPE_CONCURRENCY`, default `4`
  - `JOBAGENT_PER_SCRAPER_TIMEOUT`, default `60`
- AI scoring batch size changed from `5` to configurable default `20`:
  - `JOBAGENT_SCORE_BATCH_SIZE`, capped at `25`
- Regression coverage added for concurrent scraper execution.

### 2. Resume and Cover Letter Generation Fixed

- Real workspace prepare flow was tested against Basil's job `67`.
- The app previously accepted empty AI output as success. That is now blocked:
  - Tailoring validates that both `tailored_resume` and `cover_letter` are non-empty.
  - One retry is attempted with a stricter prompt.
  - Persistent empty output returns a clear error and saves nothing.
- Evidence checking for prepare now includes the selected/default uploaded resume text as evidence.
  This fixed false 422 failures where valid claims already present in Basil's PDF resume were rejected.
- Real result verified:
  - `POST /api/jobs/67/prepare` returned `200`
  - Tailored resume stored: `4326` chars
  - Cover letter stored: `1540` chars
  - Evidence check: `ok=true`

### 3. Package Build Fixed And Verified

- `POST /api/packages/jobs/67/build` built a real package:
  - `resume.docx`
  - `resume.txt`
  - `cover_letter.docx`
  - `cover_letter.txt`
  - `metadata.json`
- Package evidence check now uses the default uploaded resume text, matching the prepare path.
- Package builder now preserves existing locked files instead of crashing on Windows `PermissionError`.
  This matters when `resume.docx` or `cover_letter.docx` is open in Word/preview.

### 4. Markdown Resume Export Integrated

Research confirmed Junian Markdown Resume uses normal Markdown as the local-first source format and exports PDF/Markdown/HTML/DOCX from the browser.

Implemented in this app:

- New module: `app/markdown_generator.py`
- Direct download endpoints:
  - `GET /api/jobs/{job_id}/resume.md`
  - `GET /api/jobs/{job_id}/cover-letter.md`
- Job detail UI now shows `MD` download buttons next to PDF/DOCX.
- Application packages now include:
  - `resume.md`
  - `cover_letter.md`
- Package download allowlist now permits `.md`.

Real files generated for job `67`:

- `root/data/users/1-basil/applications/0067-net2aspire-llc/resume.md`
- `root/data/users/1-basil/applications/0067-net2aspire-llc/cover_letter.md`

Live endpoint verification:

- `/api/jobs/67/resume.md` -> `200 text/markdown`
- `/api/jobs/67/cover-letter.md` -> `200 text/markdown`

### 5. UI And Browser Verification

- Playwright Chromium was installed locally.
- Logged-in Chromium smoke test verified job `67` renders:
  - `TAILORED RESUME`
  - `COVER LETTER`
  - two prepared textareas
- Screenshot artifact:
  - `root/artifacts/browser-smoke-job67-prepared.png`

### 6. Resume Defaults

- Upload flow now marks the uploaded/analyzed resume as default.
- Basil's current default resume was switched to:
  - `Basil Ahamed H - AI Engineer Resume.pdf`

## Test Results

Focused test runs completed:

- Scrape/scoring/tailoring/resume/evidence regression suite: `125 passed`
- Markdown/package/download integration suite: `30 passed`
- Earlier focused backend suite after tailoring fixes: `80 passed`
- JS syntax check: `node --check app/static/js/views/detail.js` passed
- Python compile checks passed for modified backend modules

## Current Working Real App State

- Server runs at `http://127.0.0.1:8085`.
- Basil workspace has:
  - `565` jobs
  - `103` scored jobs
  - `2` resumes
  - PDF resume is now default
  - Job `67` prepared and packaged

Job `67` package folder:

```text
root/data/users/1-basil/applications/0067-net2aspire-llc/
```

Files:

- `resume.docx`
- `resume.md`
- `resume.txt`
- `cover_letter.docx`
- `cover_letter.md`
- `cover_letter.txt`
- `metadata.json`

## New Achievements

- Real prepare path is no longer theoretical: it generated, stored, passed evidence, and rendered in browser.
- Markdown resume export is now product-integrated, not a manual side file.
- Scrape source fetching is parallelized.
- AI scoring now batches up to 20 jobs per LLM call.
- Evidence gate remains fail-closed but now uses the uploaded resume as source truth during prepare/package.
- Package writing is safer on Windows when generated documents are open.

## Next Plan

### P0 - Commit And Stabilize Current Work

1. Review the working tree and remove accidental/private generated artifacts from Git tracking decisions.
2. Run a larger backend regression suite.
3. Commit the current performance + prepare + Markdown export work.

### P1 - Make Daily Run Truly Useful

1. Wire all 10 stages into `/api/daily-run/run`.
2. Ensure packages are actually built during daily run, not only counted.
3. Make shortfall reasons honest:
   - no eligible jobs
   - AI unavailable/quota
   - evidence gate failed
   - research/contact unavailable
   - below score cutoff

### P1 - Finish Remaining Stage Hardening

1. Selection must re-check `eligibility_status='ELIGIBLE'`.
2. Hybrid score route must use the real per-user AI/evidence/profile state.
3. Digest must report packages vs target, not only scraped job counts.
4. Research/contact providers must use workspace keys and avoid caching transient failures as permanent negatives.
5. Outreach draft dedup must be scoped by job and recipient.

### P2 - Better Resume Quality

1. Improve Markdown resume layout further for Junian preview.
2. Add a "Preview Markdown Resume" action or modal.
3. Add optional export of a `junian_resume.md` source optimized for one-page ATS layout.
4. Add tests that guard against mojibake characters in exported resume files.

### P2 - E2E Automation

1. Add an E2E that logs in, prepares a job, downloads `resume.md`, and confirms non-empty Markdown.
2. Add package E2E that confirms package folder includes DOCX, TXT, MD, and metadata.
3. Re-run the full user-journey harness with normal budgets.

## 7. ATS Resume Pipeline (same session, later)

Goal: Markdown becomes the **source of truth**, and PDF/DOCX/MD all derive from
it — the flow the hand-written `resume_junian_markdown.md` implied but which
nothing produced automatically.

### What the flow is now

```
1. TAILOR     AI -> structured resume_json (basics/experience/skills/education)
              + tailored_resume (plain text)   EvidenceChecker fail-closed -> 422
                   ↓
2. EMIT MD    app/ats_resume.py -> resume.md          ← THE SOURCE
                   ↓
3. RENDER     app/html_renderer.py  (MD -> HTML, dependency-free)
              app/pdf_renderer.py   (Chromium -> PDF, text fallback)
              app/docx_generator.py (DOCX)
                   ↓
4. PACKAGE    resume.md / .pdf / .docx / .txt (+ cover letter) + allowlist + UI
```

### New files

| File | Purpose |
|---|---|
| `app/ats_resume.py` | Structured schema + ATS Markdown renderer + plain-text flatten. Single entry point `build_resume_markdown()`. |
| `app/ats_template/ats.css` | **Self-written** single-column ATS stylesheet (no third-party code, no licence question). |
| `app/html_renderer.py` | Markdown subset -> HTML. Dependency-free; every value HTML-escaped (JD is untrusted). |
| `app/pdf_renderer.py` | HTML -> PDF via shared headless Chromium, with the PyMuPDF generator as fallback. |
| `tests/test_ats_resume.py` | 29 tests. |
| `tests/test_pdf_renderer.py` | 11 tests, incl. real Chromium renders. |

### Integration decision: junian/markdown-resume

Repo inspected (Nuxt 3 + Vue 3 SPA, **AGPL-3.0**, everything client-side — its
PDF export is browser print-to-PDF, and there is no importable function). Three
options were considered; **Option A** chosen: serve-render from Markdown with a
self-written stylesheet. Consequences:

- No Node runtime at build or serve time.
- No AGPL obligation — the stylesheet is original.
- `= yaml =|---` front-matter is supported (`front_matter=True`) but **opt-in**,
  because which keys that editor honours could not be verified.
- Option B (self-hosting their SPA as a `Resume Editor` page) stays open later:
  the MD already round-trips.

### Changes to existing files

- `app/tailoring.py` — prompt now asks for `resume_json`; `resume_json` added to
  every result; `max_tokens` 8000 -> 12000; a real `TAILORING_RETRY_INSTRUCTION`
  (the old one never asked for `resume_json`).
- `app/database.py` — `applications.resume_json` column (migration + allowlist).
- `app/routers/tailoring.py` — `/prepare` persists `resume_json`; `/resume.md`
  and `/resume.pdf` prefer the structured form.
- `app/application_builder.py` — `resume_json` input; writes `resume.md` from
  structure, `resume.pdf`, `cover_letter.pdf`; fingerprint includes `resume_json`
  so legacy packages rebuild once to gain them.
- `app/routers/packages.py` — PDFs in the download allowlist; correct media types.
- `app/markdown_generator.py` — `generate_resume_markdown()` **removed**; it was
  the superseded duplicate renderer. Cover letter export kept.
- `app/static/js/views/detail.js` — package panel lists every file in the
  package instead of only `resume.docx`.

### Two bugs found and fixed while building this

1. **Structured-vs-text confusion.** `coerce_resume_json()` wrapped loose text in
   `{"summary_text": ...}`, which `is_structured()` accepted — so a text-only AI
   response would have rendered a **summary-only resume**, silently losing every
   section. Now `coerce_resume_json()` returns `""` unless the payload is a real
   structure (`basics` + at least one section), and `build_resume_markdown()`
   falls back to the full plain text. Regression test
   `test_text_only_ai_response_never_loses_sections`.
2. **The evidence gate did not cover the structure.** The gate checked
   `tailored_resume`, but the MD/PDF/DOCX render *from* `resume_json` — a claim
   present only in the structure would have shipped unverified (Golden Rule 5).
   Both `/prepare` and the package build now gate **every form** via
   `text_forms_for_evidence_check()`. Integration test
   `test_prepare_rejects_a_structure_with_unverified_claims` proves a 422 and
   that nothing is saved.

### Verification (executed)

- Full backend suite: **1341 passed, 0 failed** (`-n auto`, 2m54s).
- Real job-67 stored text (4326 chars, legacy, non-structured) rendered through
  the new path: `renderer=chromium`, 55,632 bytes, **2 pages, 4,293 extractable
  chars** — comparable to the old PyMuPDF output (4,320) with proper pagination
  and a real text layer.
- `node --check app/static/js/views/detail.js` passes.
- Frontend vitest **still not run** — `app/static/node_modules` is absent.

## Package Lock Bug — Found via Job 67, Now Fixed

The locked `resume.docx` above was **not** a harmless skip. Investigating it
turned up a real defect in `ApplicationBuilder`:

- `_write_*_preserve_locked()` caught `PermissionError` and preserved the file,
  but the caller appended the filename to `written` **unconditionally**, so
  `metadata.json` advertised a file that was stale on disk.
- It then wrote the **new** fingerprint. Since the build is idempotent by
  fingerprint, every later build returned `noop` — the stale artifact could
  **never** be refreshed, silently and permanently.

Fix: the write helpers return `bool`, `_record()` routes each name to `written`
or `skipped`, and `inputs_fingerprint` is persisted as `new_fp if not skipped
else old_fp`. A skipped file therefore forces a rebuild on the next call, and a
warning lists what stayed locked.

Job 67's package was then rebuilt with the lock cleared. `resume.docx` is now
38,986 bytes and its 36 paragraphs match the `resume.pdf` text exactly.

Regression: `tests/test_application_builder.py::test_locked_file_does_not_freeze_the_package`.

### One thing that looked like a bug and wasn't

The rebuilt DOCX showed `Programming &amp; ML`. `_DocumentBuilder` already runs
`HTMLParser(convert_charrefs=True)`, so `&amp;` in `word/document.xml` is the
*correct* OOXML encoding of `&` — the inspection script was at fault. A
redundant `html.unescape()` was added and then **reverted**: decoding twice
would corrupt literal text such as `&amp;amp;`.

## Verification (after the lock fix)

- Full backend suite: **1353 passed, 0 failed** (`-n 4`, 2m43s).
- Job-67 package rebuilt; `resume.docx` 38,986 B, `resume.pdf` 2 pages,
  both carrying the same content as `resume.md`.

## Where the templated resume comes from (provenance)

- `app/ats_template/junian.css` — **Junian's**, copied verbatim from
  `junian/markdown-resume`. That project is AGPL-3.0, so the licence applies to
  that file.
- Everything else in the pipeline is ours: `html_renderer.py` (Markdown→HTML,
  `#resume-preview`, the runtime font/size/colour layer modelled on their
  `utils/css.ts` + `constants/default.ts`), `html_docx.py`, `pdf_renderer.py`,
  `_group_header()`, and `ats.css` (kept only as a fallback).

The *look* is Junian's template. The *pipeline* that renders `resume.md` into
that look is ours.

## The UI download already serves the template (verified, no change)

Job detail → **Tailored Resume** card exposes three tiles, wired in
`app/static/js/views/detail.js` (`renderPreparedSection`):

| Tile | Endpoint | Output |
|------|----------|--------|
| PDF | `/api/jobs/{id}/resume.pdf` | Junian template, A4 + Verdana |
| DOCX | `/api/jobs/{id}/resume.docx` | Same Markdown → Word (editable) |
| MD | `/api/jobs/{id}/resume.md` | `resume.md`, the source of truth |

Every endpoint re-renders fresh from the database
(`application.resume_json or tailored_resume` → `build_resume_markdown`), so
these downloads are independent of the package folder on disk. The Chrome
extension's *Download Resume* action calls the same PDF URL.

Verified by running the exact endpoint code path for job 67:
`renderer=chromium`, 42,998 B, **8.28 × 11.71 in (A4)**, fonts `Verdana` +
`Verdana-Bold`, 2 pages, 5,049 extractable characters, 0 doubled separators.
Evidence: `artifacts/_verify-ui-resume.pdf`.

**Decision (Basil):** keep the three separate buttons. A combined
"Download all" ZIP was considered and declined — no endpoint or UI change was
made.

**Package PDF — RESOLVED 2026-10-07.** `data/users/1-basil/applications/0067-.../resume.pdf`
was the old Letter/Calibri render because Acrobat held the file open, so the
build skipped it and dropped it from `metadata["files"]` (the lock fix working as
designed). Acrobat was closed (never force-killed), the file became writable, and
`artifacts/live_tailor_job67.py` was re-run with `SKIP_AI=1`. Verified afterwards:
**43,316 B · 2 pages · 8.28 × 11.71 in (A4) · fonts `Verdana` + `Verdana-Bold` ·
4,530 extractable chars · 0 doubled pipes**, and `resume.pdf` is back in
`metadata["files"]`. Content equality: DOCX matches `resume.md` at **570/570 word
tokens**; PDF matches at 570/570 modulo hyphenation line-breaks
(`optimisa-/tion.`, `au-/ditable`, etc.). Every package file is now 12:02 or
later except `resume_junian_markdown.md`, a scratch copy.

## Known Notes

- `artifacts/` contains browser smoke screenshots and should normally stay untracked unless intentionally archived.
- The two `.bat` files in the parent directory remain unrelated/untracked.
