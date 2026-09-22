# NEW PC SETUP — jobagent from zero (Basil)

Read this whole file once before starting. Two lists matter: what comes from git
automatically, and what ONLY you can bring (secrets + personal files). Total setup
time: ~10 minutes.

---

## 1. THE ONE RULE

> **Git gives you the CODE. You bring the SECRETS and the DATA.**
> Nothing personal or secret is in the repo (by design — it's public).

## 2. What transfers automatically via git ✅

| Comes with the clone | Where |
|---|---|
| The entire jobagent app (FastAPI + SPA + extension) | `job-search-system/root/` |
| All 6 country YAMLs + M2 evidence **templates** (all-UNVERIFIED skeletons) | `root/config/countries/`, `root/data/profile/` |
| M6–M8 engines, M3–M5 strategy/discovery/eligibility, all routers | `root/app/` |
| Every test (unit + E2E harness), every milestone report | `root/tests/`, `job-search-system/docs/` |
| Project memory + implementation plan | `PROJECT_MEMORY.md`, `docs/IMPLEMENTATION_PLAN.md` |

## 3. What does NOT transfer — YOU must bring these ⚠️

| Item | Why | Where it lives on the old PC |
|---|---|---|
| **1. OpenRouter API key** | The AI brain. Without it: no AI scoring/tailoring/cover letters. The app still boots — everything deterministic (discovery, hybrid M6 scoring, eligibility) still works. | `root/.env` → `JOBAGENT_OPENROUTER_API_KEY=sk-or-v1-...` (also in DB `ai_settings`) |
| **2. Your resume .docx file** | Source of truth for tailoring. Upload again via the dashboard (it re-runs AI analysis). | Your files — the original `Basil_Ahamed_H_..._Resume.docx` |
| **3. Hunter / Apollo keys (optional, M7)** | Contact research quality. Without them the chain falls back to manual + web search — still works. | `root/.env` (optional) |
| **4. SQLite DB (OPTIONAL — usually skip)** | Your 778-job pool + scores. Fresh start is recommended; old jobs go stale anyway (7-day freshness rule). | `root/data/jobagent.db` (+ `-shm`/`-wal` if present) |
| ~~Evidence templates~~ | ✅ NOW IN GIT (fixed 2026-09-23 — `data/profile/` is versioned; flip your claim statuses to VERIFIED again on the new PC) | — |

**Minimum to be fully productive: your OpenRouter key + your resume .docx. That's it.**

## 4. Step-by-step (new PC)

```bash
# 0. Prerequisites: Python 3.12+, git, and uv (the only installer)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 1. Clone (SSH — your basilahamed07 account)
git clone git@github.com:basilahamed07/CHANGE.git
cd CHANGE/job-search-system/root

# 2. Install dependencies (creates .venv from uv.lock — exact same versions)
uv sync

# 3. Secrets: create .env and paste YOUR OpenRouter key
cp .env.example .env
nano .env   # set JOBAGENT_OPENROUTER_API_KEY=sk-or-v1-...

# 4. Boot it
uv run uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8085
#    → open http://127.0.0.1:8085 — health should show ai_configured: true

# 5. Upload your resume .docx in the UI (Settings → Resume)
#    Re-run AI analysis when quota allows — it stores search_terms/key_skills
#    which the hybrid matcher uses as your target profile.

# 6. Flip your evidence claims to VERIFIED (Settings/evidence or edit
#    data/profile/*.yaml directly: status + source + last_verified).
#    Only VERIFIED claims feed resume generation (fail-closed).
```

## 5. Verify the new PC is fully alive (60 seconds)

```bash
curl -s http://127.0.0.1:8085/api/system/health          # expect "status":"healthy"
curl -s http://127.0.0.1:8085/api/resumes                 # expect your uploaded resume
curl -s http://127.0.0.1:8085/api/countries               # expect count=6
curl -s -X POST http://127.0.0.1:8085/api/matching/score-all   # FREE hybrid scoring

# Unit tests from the same directory (job-search-system/root/):
.venv/bin/python -m pytest tests/ -q   # expect 788 passed
```

Full E2E check (takes ~6 min): `uv run python ../analysis/e2e_module_test.py`
→ writes `docs/E2E_MODULE_TEST_REPORT.md`. **AI-dependent checks will SKIP unless
the OpenRouter quota is available — that is expected, not a failure.**

## 6. Two PCs / syncing between them

- **Daily work:** commit + push code from whichever PC you're on; pull on the other.
- **DB is NOT synced by git (on purpose):** pick ONE machine as the "job pool" PC,
  or manually copy `root/data/jobagent.db` (stop the server first) when you want to
  move the pool. Copying also brings your scores/prepared applications.
- **.env is per-machine:** copy it manually between PCs if you want identical keys
  (never commit it, never paste the key into chat/screenshots).
- **Verify-before-migrate:** on the OLD PC run the verification block in §5 first;
  on the NEW PC run it again. Compare numbers.

## 7. Common new-PC mistakes (avoid these)

1. **Forgetting `uv sync`** → `ModuleNotFoundError: aiosqlite` on boot.
2. **Skipping the resume upload** → "No resume yet" on the dashboard, matcher never initializes.
3. **Leaving evidence claims UNVERIFIED** → generation returns 422 (fail-closed). This is the system protecting you, not a bug.
4. **Expecting the old 778-job pool** → data/ is not in git (by design). Fresh discovery run will rebuild it: Scrape Now, or wait for the 6-hourly scheduler.
5. **`uv run uvicorn app.main:app`** → "Attribute app not found". The entrypoint is `app.main:create_app --factory` (see Dockerfile CMD).
6. **Committing `.env` or `*.docx`** → never. The gitignore blocks them; keep it that way.

---
*Tested end-to-end on the original PC (2026-09-23): fresh `uv sync`, factory boot,
788 unit tests, 137/137 E2E. Report: docs/M8_E2E_TEST_REPORT.md.*
