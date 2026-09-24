# GUIDE — How to use this website (jobagent)

This is the **practical, start-here guide** for the International AI Job Search
System. It covers how to start the server, log in, set yourself up, and run the
whole daily workflow from the browser.

- Deep reference for every feature → [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md)
- What the system can do, honestly → [`docs/CAPABILITIES.md`](docs/CAPABILITIES.md)
- Multi-user design → [`docs/MULTI_USER_PLAN.md`](docs/MULTI_USER_PLAN.md)
- Latest real end-to-end run → [`docs/USER_JOURNEY_E2E_REPORT.md`](docs/USER_JOURNEY_E2E_REPORT.md)
- Build/verification status → [`docs/E2E_RUN_STATUS.md`](docs/E2E_RUN_STATUS.md)

---

## 1. What this website is

One product that takes you from *"I need a job"* to *"a reviewed application
package and an outreach draft are ready"*:

```
discover jobs → normalise → dedupe → verify freshness → check eligibility
   → match/score → research the company & contacts → tailor your resume
   → write a cover letter → build the package → draft outreach
   → track it in a CRM → remind you to follow up → learn from responses
```

Two rules the site will never break:

1. **Nothing is invented.** A resume/cover letter cannot claim a skill, date,
   employer, metric or certification that isn't in your **VERIFIED evidence**.
   The evidence gate blocks it and returns an error instead of saving it.
2. **Nothing is sent.** Outreach is **DRAFT-ONLY**. You review and send it
   yourself.

---

## 2. Start the server

```bash
cd job-search-system/root
.venv/bin/python -m uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8085
```

Then open **http://localhost:8085** (or `http://<server-ip>:8085` if the server
is on another machine).

| Flag | Meaning |
|------|---------|
| `--host 127.0.0.1` | only this machine can reach it (**safest**) |
| `--host 0.0.0.0` | any machine that can route to this host can reach it — see §8 |

Requirements: `.venv` installed (`uv sync`) and a `.env` with at least one AI
key (see §3).

---

## 3. First visit — create the admin account

On a brand-new install the first screen is **Create Admin**. That first account
is always the administrator, and the endpoint refuses forever afterwards.

![flow] `First visit → Create Admin → username + password`
`Every later visit → Sign In → username + password`

Sessions last 7 days. 5 failed logins for the same username lock it for 15
minutes. Changing a password signs every device out.

---

## 4. Log in (every time after that)

1. Open the site → **Sign In**.
2. Enter username + password.
3. You land on the **Dashboard**.

> Everything you see is **your own data**. Another user's jobs, resumes,
> packages, keys and drafts are invisible to you (and enforced by the server,
> not just the UI).

---

## 5. First-time setup (do these in order)

### Step 1 — Add your AI provider (Settings → AI)

- Choose **DeepSeek** (recommended for cost), paste your API key, pick the model
  (e.g. `deepseek-flash`), press **Test**.
- Every user uses **their own key**, billed to them, and the **AI Usage & Cost**
  panel on the Stats page meters only your own spend.

### Step 2 — Upload your resume (Settings → Resume)

- Upload `.docx`, `.pdf`, `.txt`, `.md`, `.doc` or `.rtf` (max 10 MB).
- The AI then does three things automatically:
  1. **Grades it** — ATS score, issues, tips.
  2. **Learns from it** — search terms, job titles, key skills, seniority, summary.
  3. **Pre-fills your profile** — and sets an initial country strategy.
- Your uploaded resume also becomes **VERIFIED evidence** (it is your own
  source-of-truth document), so the generation gate has something to allow.

### Step 3 — Check your evidence (Settings → Evidence)

- You will see claims in four states: `VERIFIED`, `UNVERIFIED`, `DISPUTED`,
  `DO_NOT_USE`. Only `VERIFIED` facts may appear in generated documents.
- Add/confirm real skills, employers, dates, metrics here. If generation later
  fails with `evidence_check_failed`, it means the text claimed something your
  evidence doesn't support — fix it here, then retry.
- **Rescan/backfill** rebuilds VERIFIED claims from your stored resume (costs
  zero AI).

### Step 4 — Choose countries (Settings → Countries & Discovery)

- Toggle the countries you want. **Apply strategy** re-checks the existing pool
  and reverses earlier automatic dismissals if you widen the search.
- **Reload from YAML** picks up newly added country files.
- The same tab has **adapter health** and a **Run discovery** button.

### Step 5 — Fill in remaining settings (optional but recommended)

Search terms / exclude terms, remote-only, allowed regions, scraper schedule,
and any scraper API keys (Adzuna, USAJobs, Hunter, Apollo…). All optional —
discovery works with keyless sources.

---

## 6. Daily use — the whole workflow

### 1) Run the pipeline — Dashboard → **Daily Run**

One button runs the ordered stages (discover → classify → eligibility → score →
research → select → packages → outreach → report) and shows a shortfall reason
when it can't hit your daily target.

> **Daily target = qualifying application PACKAGES**, not scraped URLs. The
> eligibility bar is never lowered to hit a number.

### 2) See your matches — **Jobs**

Filter/sort by score, search, source, region. Open any job to see its
**hybrid score breakdown** (skills / role / location / visa / recency / semantic),
why it matched, what's missing, and any hard blockers.

### 3) Work a job — Job detail → **Pipeline Actions**

| Action | What it does |
|--------|--------------|
| Re-check eligibility | runs the freshness + eligibility gates again, with reason codes |
| Score | deterministic hybrid score + explanation (free, instant) |
| Research contacts | company enrichment + contact discovery, ranked with confidence |
| Prepare application | **AI tailors your resume** through the evidence gate, writes a cover letter |
| Build package | writes `resume.docx/.txt`, `cover_letter.docx/.txt`, `metadata.json` into your own applications folder |
| Repackage | rebuilds from the **stored** text — **zero AI spend** |
| Create outreach draft | writes a DRAFT (never sends) and refuses to create a duplicate |

Download the package from the same panel; the file list is allow-listed and
path-traversal safe.

### 4) Track it — **Network / Pipeline**

CRM statuses (interested → prepared → applied → interviewing → offered, plus
rejected/withdrawn/closed/ghosted) with an append-only event history. The engine
blocks impossible jumps and stops follow-ups for terminal states. The follow-up
engine surfaces what's due using your configured cadence.

### 5) Review your letters — `PUT`/UI edit

Cover letters are plain text you can edit after generation; edits round-trip and
are stored on the application.

### 6) Learn — **Stats**

Funnel, response rates, source quality, skill gaps, and **AI Usage & Cost**
(spend, calls, tokens, per-model table, budget projection, cache hit-rate).

---

## 7. Multi-user: what happens when you and a friend both log in

**Your data is fully separate.** Each user gets their own workspace:

```
root/data/users/<id>-<username>/
    jobagent.db      their own 46-table database (jobs, apps, CRM, keys…)
    profile/         their own evidence YAMLs
    applications/    their own generated packages
    gmail_drafts/    their own local drafts
```

| Situation | What happens |
|-----------|--------------|
| Same job found by both users | Two rows with two ids, one per pool. Neither user can see the other's. Dedup merges sources *within* a pool, not across users. |
| Same resume uploaded by both | Two independent resumes, two evidence corpora, two separate AI grading runs — each billed to that user's own key. No cross-contamination. |
| Both build a package for the same job | Two packages in two separate folders. No conflict. |
| **Both press "Run discovery" / "Scrape now"** | ⚠️ **Only one runs at a time.** The second gets `already_running` / 409 and must retry after the first finishes. |
| **Both create an outreach draft** | ⚠️ Drafts are separate, but a configured Gmail token is **shared** — so both drafts can land in the **same mailbox**. Leave Gmail unconnected until this is per-user. |
| Changing countries | ⚠️ Country YAMLs are shared, so the enabled set is a **shared default** (each user's actual targeting is per-user). |

Admin can create users, disable/enable them and reset passwords from
**Settings → Users**, and every admin action is audit-logged.

---

## 8. Exposing it beyond one machine — read this first

`--host 0.0.0.0` makes the site reachable from the network. Before doing that
beyond a trusted LAN, know that:

- There is **no HTTPS yet**; the session cookie is set `secure=False`.
- **API keys are stored in plaintext** in each workspace DB (encryption at rest
  is the pending M15e work).
- Put it behind a reverse proxy with TLS, restrict the firewall/security group
  to the addresses that need it, and prefer `127.0.0.1` for local-only use.

---

## 9. Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| "No resume uploaded" when preparing | Upload one in Settings → Resume (and give it a moment to finish grading). |
| Generation returns `evidence_check_failed` | The text claimed something not in your VERIFIED evidence. Open Settings → Evidence, verify the real facts (or re-upload your resume, which verifies them), then retry. |
| Generation returns 502 / a quota message | Provider-side limit or credits. Try **Repackage** (zero AI) or check Stats → AI Usage. |
| Discovery says `already_running` | Another run (yours or another user's) is in progress — wait for it to finish. |
| Jobs page looks empty | Fresh, in-region, complete jobs only. Run discovery, then score, and check your countries/regions. |
| Everything 401s | Your session expired — sign in again. |
| `No countries enabled` on discovery | Pick at least one country in Settings → Countries & Discovery. |

---

## 10. Keys and data — what to back up, what never to commit

**Back up** `root/data/users/<id>-<username>/` — it *is* your data (jobs, pool,
applications, evidence, CRM).

**Never commit**: `.env` (API keys), `data/` (resume text + DB), `*.docx`
resumes, and `analysis/e2e_runs/` (it contains generated resume text).
