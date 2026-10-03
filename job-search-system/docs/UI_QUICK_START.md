# UI QUICK START

This is the practical click-by-click guide for using jobagent from the browser.

## 1. Start And Log In

From PowerShell:

```powershell
cd D:\personal_project\CHANGE\CHANGE\job-search-system\root
uv run uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8085
```

Open:

```text
http://127.0.0.1:8085
```

First ever visit:

1. The app shows **Create Admin**.
2. Enter a username and password.
3. Submit. That first account becomes the admin.

Later visits:

1. The app shows **Sign In**.
2. Enter the username and password you created.
3. You land in your own workspace.

## 2. Required First Setup

Do these before running jobs:

1. Go to **Settings -> AI**.
2. Add your AI provider/key, for example DeepSeek.
3. Press **Test**.
4. Go to **Settings -> Resume**.
5. Upload your resume `.docx`, `.pdf`, `.txt`, or `.md`.
6. Wait for analysis to finish.

After upload, the app automatically:

- extracts your resume text,
- grades the resume,
- creates search terms,
- stores the resume as your default resume,
- seeds verified evidence used by the tailoring gate.

Without a resume, discovery/search is blocked on purpose.

## 3. Run The Pipeline

Use **Dashboard -> Run Daily Run**.

That now runs the full 10-stage pipeline:

```text
discover -> classify -> eligibility -> score -> hybrid_score -> select -> research -> packages -> outreach -> digest
```

Important: it may still produce `0/5 packages` if there are no eligible jobs, no high enough score, AI quota is exhausted, or discovery is rate-limited. That is expected; the app reports the real reason instead of pretending success.

## 4. Where To Find The Tailored Resume

There are two places.

### In The UI

1. Go to **Jobs**.
2. Open a job.
3. In **Pipeline Actions**, click **Prepare application**.
4. The app creates the tailored resume and cover letter.
5. Then click **Build package**.
6. Download:
   - `resume.docx`
   - `resume.txt`
   - `cover_letter.docx`
   - `cover_letter.txt`

If you only prepared but did not build the package yet, the tailored text exists in the application record and the job download buttons can return:

```text
/api/jobs/{job_id}/resume.docx
/api/jobs/{job_id}/resume.pdf
```

### On Disk

Built packages are stored inside your workspace applications folder:

```text
job-search-system/root/data/users/<user-id>-<username>/applications/
```

Each built job package contains files like:

```text
resume.docx
resume.txt
cover_letter.docx
cover_letter.txt
metadata.json
```

For old legacy/admin data, packages may also be under:

```text
job-search-system/root/data/applications/
```

## 5. Normal Daily Use

Recommended workflow:

1. Log in.
2. Check **Settings -> AI** key is working.
3. Check **Settings -> Resume** has your default resume.
4. Check **Countries / Discovery** targets.
5. Click **Run Daily Run**.
6. Open **Jobs** and review scored jobs.
7. For a good job, click **Prepare application**.
8. Review the tailored resume and cover letter.
9. Click **Build package**.
10. Download the package.
11. Click **Create outreach draft** if you want a draft email.
12. You manually send after review. The app does not auto-send.

## 6. Is It Workable Now?

Yes, the app is workable now for the main flow:

- login,
- per-user workspace,
- resume upload,
- AI resume analysis,
- discovery,
- classification,
- eligibility,
- scoring,
- daily run,
- tailored resume and cover letter generation,
- package building,
- draft-only outreach,
- CRM tracking,
- analytics.

The backend test suite passed: **1280 passed**.

The focused real-server E2E passed: **9/9 scenarios, 67/67 checks**, including the daily-run route.

## 7. What To Watch

- AI calls need a valid provider key and quota.
- Some job sources need scraper API keys; sources without keys skip honestly.
- The app prepares packages and drafts, but it never sends emails automatically.
- If daily run says `NO_ELIGIBLE_JOBS`, open Jobs/Settings and check country strategy, eligibility, scores, and discovery results.
- If package build fails with an evidence error, go to **Settings -> Evidence**, rescan/backfill from your resume, then try Prepare again.
