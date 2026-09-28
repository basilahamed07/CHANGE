# USER PROCESS — every single step, from zero to a sent application

> **What this is:** the step-by-step operating manual for jobagent — what you do
> first, what happens when you upload your resume, and every action in order.
> For feature-level reference see `USER_GUIDE.md`; for the quick start see `GUIDE.md`.

---

## STAGE 0 — Start the system (one-time per machine)

| # | Step | Where | What happens |
|---|------|-------|--------------|
| 0.1 | Install once | `root/` | `uv sync` creates `.venv`; copy `.env.example` → `.env` |
| 0.2 | Start the server | terminal | `.venv/bin/python -m uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8085` |
| 0.3 | Open the site | browser | `http://<server-ip>:8085` |

---

## STAGE 1 — First visit: create the admin (60 seconds)

| # | Step | Screen | What happens |
|---|------|--------|--------------|
| 1.1 | Create Admin screen appears | `/` | Because no user exists yet, the app shows **Create Admin** |
| 1.2 | Pick username + password | form | Password ≥ 8 chars. This first account = **admin** |
| 1.3 | Submit | form | `POST /api/auth/bootstrap` — this endpoint **locks itself forever** after the first user |

Every later visit shows **Sign In** instead. Sessions last 7 days; 5 failed
logins lock a username for 15 minutes.

---

## STAGE 2 — Log in (every time)

| # | Step | What happens |
|---|------|--------------|
| 2.1 | Open the site → Sign In | form posts to `/api/auth/login` |
| 2.2 | Enter username + password | scrypt verify; session cookie `jobagent_session` (7-day) |
| 2.3 | Land on Dashboard | **your own workspace is created on first request**: `data/users/<id>-<username>/` with its own DB, profile, applications |

> From here on, everything you see and do is inside **your own workspace**.

---

## STAGE 3 — Resume upload (the required first data step)

> The gate: **you cannot run scrape or discovery until a resume exists**
> (`search_gate.py` → HTTP 428 "Upload a resume first…").

| # | You do | What the system does |
|---|--------|----------------------|
| 3.1 | Settings → Resume → choose file (`.docx/.pdf/.txt/.md`, ≤10 MB) | `POST /api/resume/upload`; text extracted (python-docx for .docx) |
| 3.2 | Press upload | AI runs `analyze_resume` + `parse_resume_to_profile` with **your** provider/key |
| 3.3 | Wait a few seconds | Three results land: **(a)** ATS **grade** + tips; **(b)** **search terms / job titles / key skills** extracted from *your* resume → saved to your `search_config`; **(c)** your **profile tables** pre-filled |
| 3.4 | Resume stored | becomes your **VERIFIED evidence** source-of-truth + the resume used for tailoring |
| 3.5 | (optional) Confirm/edit keywords | Settings → search terms; empty saves are rejected (400); re-uploading a new resume re-runs the analysis and overwrites edited terms |
| 3.6 | **Gate lifts** | `POST /api/scrape` now returns 202, discovery runs return 200 |

---

## STAGE 4 — One-time setup (do in this order)

| # | Step | Where | Notes |
|---|------|-------|-------|
| 4.1 | Add AI provider + key | Settings → AI | DeepSeek recommended; press **Test**; per-user key, per-user cost meter |
| 4.2 | Check evidence | Settings → Evidence | only **VERIFIED** claims may appear in generated docs; "Rescan" backfills from your resume (free) |
| 4.3 | Choose countries | Settings → Countries & Discovery | toggle, then **Apply strategy**; disabled countries dismiss matching jobs (reversible) |
| 4.4 | (optional) scraper keys, exclude terms, remote-only, schedule | Settings | all optional — keyless sources work |

---

## STAGE 5 — Daily loop

| # | You do | Where | What happens |
|---|--------|-------|--------------|
| 5.1 | **Run Daily Run** | Dashboard | ordered stages discover → classify → eligibility → score → research → select → packages → outreach → report; shortfall reasons are honest, the eligibility bar is never lowered |
| 5.2 | Or run pieces | Dashboard | **Run discovery** (bounded `?passes=1..24`), **Scrape now**, **Score** |
| 5.3 | Browse matches | Jobs | filter by score/region/source; open a job for the hybrid breakdown (skills/role/location/visa/recency/semantic + hard blockers) |
| 5.4 | Work a job | Job detail → Pipeline Actions | Re-check eligibility → Score → Research contacts → **Prepare application** (AI tailors resume + cover letter through the evidence gate) → **Build package** |
| 5.5 | Review the package | Job detail | `resume.docx/.txt`, `cover_letter.docx/.txt`, `metadata.json`; **Repackage** rebuilds from stored text with **zero AI**; download is allow-listed |
| 5.6 | Create outreach draft | Job detail | **DRAFT-ONLY** (never sends); duplicate creation refused (`already_exists`) |
| 5.7 | Track it | Pipeline/CRM | interested → prepared → applied → interviewing → offered (+ rejected/withdrawn/closed/ghosted); impossible jumps blocked, terminal states stop follow-ups |
| 5.8 | Follow up | Network | **Draft-due-follow-ups** uses your cadence; response classifier flags no-replies for review |
| 5.9 | Learn | Stats | funnel, response rates, skill gaps, **AI Usage & Cost** (spend, calls, per-model, budget) |

---

## STAGE 6 — Sending (the only manual step, by design)

1. Open the Gmail draft (or `gmail_drafts/` local fallback if no token).
2. Read it. Edit if you want.
3. **You press Send** — the system never does (Golden Rule #6).

---

## STAGE 7 — Admin extras (admin account only)

| Action | Where | Note |
|--------|-------|------|
| Create / disable / reset users | Settings → Users | audit-logged to `admin_actions` |
| Read all docs | the docs file server (see `DOCS_SERVER.md`) | same session auth as the app |

---

## The whole flow in one line

```
start server → create admin → log in → UPLOAD RESUME (gate!) → AI provider →
countries → Daily Run → open job → prepare → build package → outreach draft →
track in CRM → YOU send the draft
```
