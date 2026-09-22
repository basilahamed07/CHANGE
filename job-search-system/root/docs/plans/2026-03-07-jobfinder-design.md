# JobFinder - Automated Job Discovery & Application Tool

## Overview

A self-hosted web dashboard for discovering, scoring, and applying to senior engineering jobs. Runs as a Docker container on mmgnas (QNAP NAS), scrapes 8 job sources on a schedule, scores each listing against Luke's resume using the Claude API, and provides tools to generate tailored resumes, cover letters, and application emails.

## Target Roles & Compensation

- Senior/Staff DevOps/Platform Engineer
- Senior/Staff SRE
- AI/ML Infrastructure Engineer
- AI/LLM Engineer
- Engineering Manager / Tech Lead
- Minimum salary: $150k (FTE) or $95/hr (contract)
- Remote only

## Architecture

Single Docker container on mmgnas:
- **FastAPI** backend (API + static file serving)
- **SQLite** database on mounted QNAP volume
- **APScheduler** for scheduled scraping (no external cron)
- **Claude API** for resume scoring, tailoring, and cover letter generation

### Directory Structure

```
jobfinder/
├── Dockerfile
├── docker-compose.yml
├── app/
│   ├── main.py              # FastAPI app + routes
│   ├── config.py            # Settings, API keys, schedule config
│   ├── database.py          # SQLite models + connection
│   ├── scrapers/            # One module per job source
│   │   ├── __init__.py
│   │   ├── base.py          # Base scraper class + JobListing schema
│   │   ├── indeed.py        # Indeed RSS feeds
│   │   ├── remoteok.py      # RemoteOK JSON API
│   │   ├── weworkremotely.py # WWR RSS feeds
│   │   ├── hackernews.py    # HN Who's Hiring thread scraper
│   │   ├── remotive.py      # Remotive API
│   │   ├── usajobs.py       # USAJobs REST API
│   │   ├── linkedin.py      # Google search scrape (site:linkedin.com/jobs)
│   │   └── dice.py          # Google search scrape (site:dice.com/job-detail)
│   ├── matcher.py           # Claude API resume scoring
│   ├── tailoring.py         # Resume tweaking + cover letter generation
│   ├── emailer.py           # Draft/send application emails
│   └── static/              # Frontend HTML/CSS/JS
│       ├── index.html
│       ├── css/
│       │   └── style.css    # Pico CSS base + custom theme
│       └── js/
│           └── app.js
└── data/                    # Mounted volume: SQLite DB + resume files
```

## Job Sources

| Source | Method | Frequency | Notes |
|--------|--------|-----------|-------|
| Indeed | RSS feed parsing | Every 6h | Multiple keyword feeds |
| RemoteOK | JSON API | Every 6h | Free, no auth, remote-only |
| We Work Remotely | RSS feed | Every 6h | Remote-only, good senior roles |
| HackerNews Who's Hiring | HTML scrape | Daily | High quality, often direct-hire |
| Remotive | API | Every 6h | Remote-focused |
| USAJobs | REST API (free key) | Every 12h | Federal/gov roles |
| LinkedIn | Google search scrape | Every 12h | No login, lower rate |
| Dice | Google search scrape | Every 12h | No login, safe approach |

### Scraper Design

Each scraper returns a standard `JobListing` dict:
- title, company, location, salary_min, salary_max, description, url, source, posted_date, application_method (url/email), contact_email (if found)

**Deduplication:** Hash of (title + company + normalized URL). Same job from multiple sources links to one record.

**Rate limiting:** Google-based scrapers use randomized delays (30-90s between requests), rotate user agents. Max ~20 queries per source per run.

## Database Schema

### `jobs`
- id, title, company, location, salary_min, salary_max, description, url, source, posted_date, application_method, contact_email, created_at

### `job_scores`
- job_id, match_score (0-100), match_reasons (JSON array), concerns (JSON array), suggested_keywords (for resume tailoring), scored_at

### `applications`
- job_id, status (interested/tailored/applied/rejected/interviewing), tailored_resume (text), cover_letter (text), email_draft (text), applied_at, notes

### `sources`
- job_id, source_name, source_url (one job can have multiple sources)

## Matching & Scoring

New jobs are queued for scoring after each scrape run. The matcher sends Claude a prompt with:
1. Full parsed resume text
2. Job description
3. Instructions to return JSON: score (0-100), reasons, concerns, keywords to emphasize

**Scoring criteria:**
- Skills overlap (Linux, AWS, K8s, Python, Terraform, etc.)
- Seniority alignment (20+ years, lead/senior roles)
- Salary fit (filters below $150k/$95hr)
- Remote compatibility
- AI/LLM relevance (bonus — key differentiator)

**Batch scoring:** 10 jobs at a time, ~2s delay between API calls. ~50-100 new jobs per cycle costs ~$0.50-1.00 in tokens.

## Resume Tailoring & Cover Letters

Triggered when user clicks "Prepare Application" on a job:

1. **Resume tailoring** — Claude reorders bullet points, adjusts summary to mirror job language, highlights matching keywords. Does NOT fabricate experience.
2. **Cover letter** — ~250 words, confident senior engineer tone. Maps specific accomplishments to job requirements.
3. **Application method detection:**
   - Direct email found: draft email with cover letter body + resume
   - Web form / Easy Apply: open URL, display materials for copy/paste
   - Company careers page: attempt to find HR/hiring email via common patterns (jobs@, careers@, hiring@)

All generated materials saved to `applications` table for editing and reuse.

## Web Dashboard

Single-page vanilla JS app. Polished, clean design using Pico CSS base + custom theme. Inter/system font stack, proper spacing, subtle shadows, smooth transitions, cohesive color palette. Linear.app / Notion aesthetic.

### Views

**1. Job Feed (home)**
- Table/card list sorted by match score (default) or date
- Filters: min score, role type, salary range, source, remote-only toggle
- Search box for keyword filtering
- Color-coded score badges: green (80+), yellow (60-79), gray (<60)
- Quick actions: Save, Dismiss, Prepare Application
- New jobs since last visit highlighted

**2. Job Detail**
- Full job description
- Match analysis panel: score, reasons, concerns
- "Prepare Application" generates tailored resume + cover letter inline
- Editable text areas for tweaking generated materials
- Copy to Clipboard / Open Application URL buttons
- Draft Email button if direct email available
- Status dropdown for pipeline tracking

**3. Dashboard / Stats**
- Total jobs scraped, scored, applied-to
- Jobs by source breakdown
- Average match score trends
- Application pipeline funnel
- Last/next scrape times
- Manual "Scrape Now" button

## Deployment

Docker container on mmgnas:
- Mount `/share/CACHEDEV1_DATA/jobfinder/data` for SQLite DB + resume storage
- Expose on a local port (e.g., 8085)
- Environment variables for Claude API key, USAJobs API key, email settings
- docker-compose.yml for easy start/stop

## Interaction Model

Fully assisted — tool finds, scores, and prepares everything, but user reviews and approves all applications before sending. No auto-apply.
