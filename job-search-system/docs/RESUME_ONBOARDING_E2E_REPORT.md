# RESUME-DRIVEN ONBOARDING — LIVE E2E TEST REPORT

> **What this proves:** a brand-new user logs in first, cannot search without a
> resume, uploads one, the AI extracts the *job-role keywords* from that exact
> resume, those keywords are confirmed/saved, and only then is search allowed.

- **Test script:** `analysis/verify_resume_onboarding_live.py`
- **Server:** real `uvicorn app.main:create_app --factory`, **auth ON, `testing=False`**
- **Bind:** `0.0.0.0:8085` (LAN IP `172.31.7.58` during the run)
- **AI provider:** `deepseek` (live, billed) — the throwaway user is given the
  admin's provider/key so the extractor runs for real
- **Result:** **26 / 26 checks passed, 0 failed**
- **Date:** 2026-09-27

---

## 1. The user under test

| | |
|---|---|
| Username | `resumeflowdemo` |
| Password | `resumeflow-pass-123` |
| Role | `user` (non-admin) |
| How created | `SystemStore.create_user(...)`, exactly like the admin "create user" API |
| Workspace | `data/users/<id>-resumeflowdemo/` (own 46-table DB + `profile/` + `applications/`) |
| Disposable? | Yes — **removed at the end of the run** (workspace dir + `system.db` rows) |

The run is fully self-contained: it creates the user, then deletes it, so it can
be re-run repeatedly without littering the system.

## 2. The resume uploaded

A fictional but realistic **Senior AI / RAG engineer** resume, stored inline in
the script (`RESUME_TEXT`). It is chosen so the extracted keywords are
attributable to *this* document:

```
PRIYA NAIR
priya.nair@example.com | +49 170 0000000 | Berlin, Germany | linkedin.com/in/priyanair

SUMMARY
Senior AI engineer with 7 years building retrieval-augmented generation systems,
LLM applications and agentic workflows in production.

TECHNICAL SKILLS
Python, LangChain, LlamaIndex, RAG pipelines, vector databases (Pinecone, pgvector),
prompt engineering, OpenAI API, DeepSeek, FastAPI, Kubernetes, MLOps.

EXPERIENCE
Lead Generative AI Engineer, VectorWorks GmbH (2021-present)
- Architected a RAG assistant over 4M documents; cut hallucination rate by 62%.
- Built an agentic AI workflow platform used by 30 internal teams.

Machine Learning Engineer, DataForge (2018-2021)
- Deployed LLM-powered document search serving 12k daily users.

EDUCATION
M.Sc. Computer Science, TU Berlin
```

Uploaded as `priya_nair_resume.txt` via `POST /api/resume/upload`.

## 3. What the test does (step by step)

1. **Anonymous visit** — confirm the session is unauthenticated and protected
   endpoints 401 (login must come first; the resume wizard never opens here).
2. **Login** as the throwaway user.
3. **Gate: no resume** — `POST /api/scrape` and `POST /api/discovery/run` must be
   **blocked** with a clear "upload a resume" message.
4. **Upload the resume** — the real AI runs `analyze_resume` +
   `parse_resume_to_profile`, returning search terms / job titles / key skills.
5. **Persistence** — the extracted terms must be stored in the user's
   `search_config`.
6. **Confirm/edit** — `POST /api/search-config/keywords` must save an edited term.
7. **Gate lifts** — once a resume exists, scrape (202) and discovery (200) are
   allowed again.
8. **Isolation sanity** — the new user has their own empty job pool.
9. **Cleanup** — remove the user and workspace.

## 4. Observed output (verbatim)

```
--- anonymous visitor ---
PASS  anonymous session is not authenticated   <- {'needs_bootstrap': False, 'authenticated': False, 'user': None}
PASS  anonymous /api/search-config is blocked (401)   <- HTTP 401

--- login ---
PASS  POST /api/auth/login succeeds   <- HTTP 200
PASS  session identifies the new user   <- {'id': 5, 'username': 'resumeflowdemo', 'role': 'user'}
PASS  workspace is created on the first authenticated request   <- HTTP 200
PASS  per-user workspace exists on disk   <- .../data/users/5-resumeflowdemo
        (AI provider for this user: deepseek)

--- GATE: search before any resume ---
PASS  new user has no resume text yet   <- terms=[]
PASS  POST /api/scrape is BLOCKED without a resume (428)   <- HTTP 428 {"detail":"Upload a resume first — jobagent needs it to know which roles to search for."}
PASS  the block message tells the user to upload a resume   <- {"detail":"Upload a resume first — jobagent needs it to know which roles to search for."}
PASS  POST /api/discovery/run is BLOCKED without a resume (428)   <- HTTP 428 {"detail":"Upload a resume first — jobagent needs it to know which roles to search for."}

--- STAGE: upload resume (resume-first onboarding step) ---
PASS  POST /api/resume/upload succeeds   <- HTTP 200
PASS  AI extracted search terms from the resume   <- 12: ['Generative AI Engineer', 'AI Engineer', 'Machine Learning Engineer', 'LLM Engineer', 'Senior AI Engineer', 'Lead AI Engineer', 'Applied AI Engineer', 'MLOps Engineer']
PASS  AI extracted job titles   <- 10
PASS  AI extracted key skills   <- 15: ['Python', 'RAG pipelines', 'LLM applications', 'Agentic AI workflows', 'LangChain', 'LlamaIndex', 'Vector databases (Pi', 'Prompt engineering']
PASS  extracted keywords reflect the resume's AI/LLM/RAG focus   <- terms=['Generative AI Engineer', 'AI Engineer', 'Machine Learning Engineer', 'LLM Engineer', 'Senior AI Engineer', 'Lead AI Engineer']
PASS  extracted search terms are persisted to search config   <- 12 terms
PASS  persisted terms match the upload response   <- cfg=[... 12 terms ...]

--- STAGE: confirm/edit keywords ---
PASS  POST /api/search-config/keywords saves   <- HTTP 200
PASS  the user's edited search term is persisted   <- [..., 'Staff RAG Engineer']

--- GATE: search after the resume ---
PASS  re-uploading the same resume stays OK   <- HTTP 200
PASS  POST /api/scrape is ALLOWED once a resume exists (202)   <- HTTP 202 {"task_id":"...","status":"started"}
PASS  POST /api/discovery/run is ALLOWED once a resume exists   <- HTTP 200 {"status":"discovery_started","passes":1,"countries":["DE","IE","NL","SG","AE","GB"]}
PASS  discovery reports the enabled countries it will search   <- countries DE/IE/NL/SG/AE/GB
PASS  empty keyword save is rejected (400)   <- HTTP 400
PASS  the new user has their own job pool   <- HTTP 200

--- cleanup: removing the throwaway user ---
PASS  throwaway user + workspace removed   <- remaining users: ['basil', 'fawaz']

==============================================================================
RESULT: 26/26 checks passed, 0 failed
==============================================================================
```

### 4.1 What the AI actually extracted from Priya's resume

| Kind | Values (from the run) |
|---|---|
| **Search terms (12)** | Generative AI Engineer · AI Engineer · Machine Learning Engineer · LLM Engineer · Senior AI Engineer · Lead AI Engineer · Applied AI Engineer · MLOps Engineer · AI Solutions Architect · NLP Engineer · AI Platform Engineer · Staff AI Engineer |
| **Job titles** | 10 suggestions, each with a "why" rationale |
| **Key skills (15)** | Python · RAG pipelines · LLM applications · Agentic AI workflows · LangChain · LlamaIndex · Vector databases (Pinecone, pgvector) · Prompt engineering · … |
| **After the user edit** | `Staff RAG Engineer` added and persisted, proving the confirm/edit step works |

## 5. Test coverage summary

| Suite | Result |
|---|---|
| Live onboarding E2E (this report) | **26/26 checks · 0 fail** |
| Frontend unit tests (`npx vitest run`) | **184 passed** (incl. `auth-gate-onboarding.test.js`) |
| Backend targeted regression | **106 passed** (`test_api`, `test_scrape_robust`, `test_resume_grading`, `test_resume_autofill`, `test_profile_save_validation`, `test_email_digest`, `test_workspaces`) |
| New backend tests | `test_workspaces.py::test_search_blocked_until_a_resume_exists`, `::test_keyword_confirm_screen_saves_and_is_isolated` |

## 6. How to re-run

```bash
# 1. start the server (0.0.0.0 for LAN access)
cd job-search-system/root
setsid nohup .venv/bin/python -m uvicorn app.main:create_app --factory \
    --host 0.0.0.0 --port 8085 > /tmp/jobagent_server.log 2>&1 &

# 2. run the live onboarding E2E (creates + deletes its own throwaway user)
.venv/bin/python ../analysis/verify_resume_onboarding_live.py
```

The script honors `JOBAGENT_BASE_URL` (defaults to `http://127.0.0.1:8085`).
It uses the real DeepSeek key (billed) for the two resume-analysis calls.

## 7. Product changes this run verifies

| Area | Change |
|---|---|
| Gate | `app/search_gate.py` — `require_resume_for_search()` (428 when no resume) |
| Routes | `routers/scraping.py`, `routers/discovery.py` apply the gate |
| DB | `update_search_keywords()`, `has_usable_resume()` |
| API | `POST /api/search-config/keywords` |
| UI | Onboarding reordered to **Resume (required) → AI → Keywords (confirm/edit) → Done** |

## 8. Known limits / notes

- The live run **starts** a discovery cycle and a scrape, then cancels the
  scrape; it does **not** wait for the full network sweep (bounded by design).
- The gate is intentionally **skipped** on the legacy single-user / no-workspace
  path so the pre-multi-user test suite is unaffected. Real authenticated users
  always have a workspace, so they are always gated.
- Re-uploading a resume re-runs the analysis and overwrites the search terms
  (including any manual edit) — expected, since a new resume means new targets.
