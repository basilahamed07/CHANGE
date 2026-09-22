# CareerPulse Enhancements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform CareerPulse from a job discovery tool into a complete application management platform with hiring manager lookup, auto-tracking, company research, salary insights, smart dedup, keyboard shortcuts, CSV export, and daily digest.

**Architecture:** Extend existing FastAPI + SQLite + Vanilla JS stack. New features are additive — new DB tables/columns, new API endpoints, new UI components. Web scraping uses httpx + BeautifulSoup (already dependencies). No new major dependencies except `python-dateutil` for date parsing.

**Tech Stack:** Python 3.12+, FastAPI, aiosqlite, httpx, BeautifulSoup4, PyMuPDF, Vanilla JS SPA

---

## Task 1: Application Notes Timeline

Replace the single `notes` text field on applications with a timestamped timeline of events.

**Files:**
- Modify: `app/database.py`
- Modify: `app/main.py`
- Modify: `app/static/js/app.js`
- Test: `tests/test_database.py`
- Test: `tests/test_api.py`

**Step 1: Add `app_events` table to database**

In `app/database.py`, add to `_create_tables()`:

```sql
CREATE TABLE IF NOT EXISTS app_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (job_id) REFERENCES jobs(id)
);
CREATE INDEX IF NOT EXISTS idx_events_job ON app_events(job_id);
```

Event types: `note`, `status_change`, `prepared`, `email_drafted`, `pdf_downloaded`, `applied`

**Step 2: Add database methods**

```python
async def add_event(self, job_id: int, event_type: str, detail: str = ""):
    now = datetime.now(timezone.utc).isoformat()
    await self.db.execute(
        "INSERT INTO app_events (job_id, event_type, detail, created_at) VALUES (?, ?, ?, ?)",
        (job_id, event_type, detail, now)
    )
    await self.db.commit()

async def get_events(self, job_id: int) -> list[dict]:
    cursor = await self.db.execute(
        "SELECT * FROM app_events WHERE job_id = ? ORDER BY created_at DESC", (job_id,)
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]
```

**Step 3: Write tests**

```python
async def test_add_and_get_events(db):
    job_id = await db.insert_job("Dev", "Co", "Remote", None, None, "desc", "http://x", None, "url", None)
    await db.add_event(job_id, "note", "Looks interesting")
    await db.add_event(job_id, "status_change", "interested -> prepared")
    events = await db.get_events(job_id)
    assert len(events) == 2
    assert events[0]["event_type"] == "status_change"  # DESC order
```

Run: `pytest tests/test_database.py -v -k test_add_and_get_events`

**Step 4: Add events to API**

In `app/main.py`:

- Add `POST /api/jobs/{job_id}/events` — add a note event
- Modify `GET /api/jobs/{job_id}` — include `events` in response
- Modify `POST /api/jobs/{job_id}/application` (status save) — auto-add `status_change` event
- Modify `POST /api/jobs/{job_id}/prepare` — auto-add `prepared` event
- Modify `POST /api/jobs/{job_id}/email` — auto-add `email_drafted` event
- Modify `GET /api/jobs/{job_id}/resume.pdf` and `cover-letter.pdf` — auto-add `pdf_downloaded` event

**Step 5: Update frontend job detail view**

In `app/static/js/app.js`, in `renderJobDetail()`:

- Replace the notes textarea with a timeline component
- Add "Add Note" input + button at top of timeline
- Render events as a vertical timeline with icons per event_type
- Show relative timestamps
- Keep the existing notes field value — migrate it to an event if non-empty

**Step 6: Run all tests, commit**

Run: `pytest tests/ -v`
Commit: `git commit -m "Add application timeline with auto-tracked events"`

---

## Task 2: User Profile / Autofill Data

Store common application form fields for quick copy-paste.

**Files:**
- Modify: `app/database.py`
- Modify: `app/main.py`
- Modify: `app/static/js/app.js`
- Test: `tests/test_database.py`
- Test: `tests/test_api.py`

**Step 1: Add `user_profile` table**

```sql
CREATE TABLE IF NOT EXISTS user_profile (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    full_name TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    location TEXT NOT NULL DEFAULT '',
    linkedin_url TEXT NOT NULL DEFAULT '',
    github_url TEXT NOT NULL DEFAULT '',
    portfolio_url TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);
```

**Step 2: Add database methods**

```python
async def get_user_profile(self) -> dict | None:
    cursor = await self.db.execute("SELECT * FROM user_profile WHERE id = 1")
    row = await cursor.fetchone()
    return dict(row) if row else None

async def save_user_profile(self, **fields):
    now = datetime.now(timezone.utc).isoformat()
    cols = ["full_name", "email", "phone", "location", "linkedin_url", "github_url", "portfolio_url"]
    values = [fields.get(c, "") for c in cols]
    placeholders = ", ".join("?" for _ in cols)
    col_str = ", ".join(cols)
    update_str = ", ".join(f"{c} = excluded.{c}" for c in cols)
    await self.db.execute(
        f"""INSERT INTO user_profile (id, {col_str}, updated_at)
            VALUES (1, {placeholders}, ?)
            ON CONFLICT(id) DO UPDATE SET {update_str}, updated_at = excluded.updated_at""",
        (*values, now)
    )
    await self.db.commit()
```

**Step 3: Add API endpoints**

```python
@app.get("/api/profile")
async def get_profile():
    profile = await app.state.db.get_user_profile()
    return profile or {"full_name": "", "email": "", "phone": "", "location": "",
                        "linkedin_url": "", "github_url": "", "portfolio_url": ""}

@app.post("/api/profile")
async def update_profile(request: Request):
    body = await request.json()
    await app.state.db.save_user_profile(**body)
    return {"ok": True}
```

**Step 4: Add Settings UI section**

Add a "Your Profile" card to settings (above AI Provider) with labeled inputs for each field and a "Save Profile" button. Each field gets a small copy button next to it for quick clipboard access.

**Step 5: Add profile quick-copy to job detail view**

In the job detail sidebar, add a collapsible "Quick Copy" section showing profile fields with one-click copy buttons. This lets users rapidly fill out application forms.

**Step 6: Tests, commit**

Run: `pytest tests/ -v`
Commit: `git commit -m "Add user profile with quick-copy for application forms"`

---

## Task 3: Hiring Manager Lookup

Search the web for hiring manager contact info when not available in the listing.

**Files:**
- Create: `app/contact_finder.py`
- Modify: `app/main.py`
- Modify: `app/static/js/app.js`
- Modify: `app/database.py`
- Test: `tests/test_contact_finder.py`

**Step 1: Add columns to jobs table**

In `app/database.py`, add migration:

```python
# In _migrate(), add jobs table migrations:
jobs_cursor = await self.db.execute("PRAGMA table_info(jobs)")
jobs_columns = {row[1] for row in await jobs_cursor.fetchall()}
jobs_migrations = {
    "hiring_manager_name": "ALTER TABLE jobs ADD COLUMN hiring_manager_name TEXT",
    "hiring_manager_email": "ALTER TABLE jobs ADD COLUMN hiring_manager_email TEXT",
    "hiring_manager_title": "ALTER TABLE jobs ADD COLUMN hiring_manager_title TEXT",
    "contact_lookup_done": "ALTER TABLE jobs ADD COLUMN contact_lookup_done INTEGER DEFAULT 0",
}
for col, sql in jobs_migrations.items():
    if col not in jobs_columns:
        await self.db.execute(sql)
```

Add method:

```python
async def update_job_contact(self, job_id: int, **fields):
    sets = ", ".join(f"{k} = ?" for k in fields)
    vals = list(fields.values()) + [job_id]
    await self.db.execute(f"UPDATE jobs SET {sets} WHERE id = ?", vals)
    await self.db.commit()
```

**Step 2: Create `app/contact_finder.py`**

```python
import re
import httpx
from bs4 import BeautifulSoup

async def find_hiring_contact(company: str, job_title: str, location: str = "") -> dict:
    """Search DuckDuckGo for hiring manager contact info.

    Returns: {name: str, email: str, title: str, source: str} or empty dict.

    Strategy:
    1. Search: "hiring manager" {company} {job_title} site:linkedin.com
    2. Search: {company} recruiter email {job_title}
    3. Search: {company} careers contact email
    4. Try company website /careers, /about, /contact pages for emails
    """
    results = {}
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }

    async with httpx.AsyncClient(timeout=15.0, headers=headers, follow_redirects=True) as client:
        # Strategy 1: DuckDuckGo HTML search for LinkedIn profiles
        queries = [
            f'"{company}" hiring manager {job_title} site:linkedin.com',
            f'"{company}" recruiter {job_title} email',
            f'"{company}" careers contact email',
        ]

        for query in queries:
            try:
                resp = await client.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": query},
                )
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    # Extract result snippets for names/emails
                    for result in soup.select(".result__body"):
                        text = result.get_text()
                        emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', text)
                        if emails:
                            results["email"] = emails[0]
                            results["source"] = "web_search"
                            # Try to extract name from surrounding text
                            break
                if results.get("email"):
                    break
            except Exception:
                continue

        # Strategy 2: Try company website directly
        if not results.get("email"):
            company_slug = re.sub(r'[^a-z0-9]', '', company.lower())
            for domain in [f"{company_slug}.com", f"www.{company_slug}.com"]:
                for path in ["/careers", "/jobs", "/contact", "/about"]:
                    try:
                        resp = await client.get(f"https://{domain}{path}")
                        if resp.status_code == 200:
                            emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', resp.text)
                            # Filter out generic emails
                            good = [e for e in emails if not any(
                                g in e.lower() for g in ['noreply', 'no-reply', 'support', 'info@', 'sales@']
                            )]
                            if good:
                                results["email"] = good[0]
                                results["source"] = domain
                                break
                    except Exception:
                        continue
                if results.get("email"):
                    break

    return results
```

**Step 3: Add API endpoint**

```python
@app.post("/api/jobs/{job_id}/find-contact")
async def find_contact(job_id: int):
    from app.contact_finder import find_hiring_contact
    job = await app.state.db.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    result = await find_hiring_contact(
        job["company"], job["title"], job.get("location", "")
    )

    update = {"contact_lookup_done": 1}
    if result.get("email"):
        update["hiring_manager_email"] = result["email"]
    if result.get("name"):
        update["hiring_manager_name"] = result["name"]
    if result.get("title"):
        update["hiring_manager_title"] = result["title"]

    await app.state.db.update_job_contact(job_id, **update)
    return {"ok": True, "contact": result}
```

**Step 4: Update job detail UI**

In the job detail sidebar, add a "Contact Info" section:
- If `hiring_manager_email` exists: show name/email/title with copy buttons
- If `contact_email` exists on the job: show it
- If neither and `contact_lookup_done == 0`: show "Find Contact" button that calls the API
- If lookup done but nothing found: show "No contact found" with "Retry" option
- If email found: enable the "Draft Email" button with the found email

**Step 5: Write tests**

```python
# tests/test_contact_finder.py
import pytest
from unittest.mock import AsyncMock, patch
from app.contact_finder import find_hiring_contact

@pytest.mark.asyncio
async def test_find_contact_from_search():
    mock_html = '<div class="result__body">Contact john@acme.com for positions</div>'
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = AsyncMock()
        mock_resp.status_code = 200
        mock_resp.text = mock_html
        mock_get.return_value = mock_resp
        result = await find_hiring_contact("Acme Corp", "Engineer")
        assert result.get("email") == "john@acme.com"

@pytest.mark.asyncio
async def test_find_contact_no_results():
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = AsyncMock()
        mock_resp.status_code = 200
        mock_resp.text = "<html>nothing here</html>"
        mock_get.return_value = mock_resp
        result = await find_hiring_contact("NoCompany", "NoJob")
        assert result == {} or "email" not in result
```

**Step 6: Run tests, commit**

Run: `pytest tests/ -v`
Commit: `git commit -m "Add hiring manager contact lookup via web search"`

---

## Task 4: Direct Apply Link Extraction

Scrape the actual "Apply" button URL from job listing pages.

**Files:**
- Create: `app/apply_link_finder.py`
- Modify: `app/database.py`
- Modify: `app/main.py`
- Modify: `app/static/js/app.js`
- Test: `tests/test_apply_link.py`

**Step 1: Add `apply_url` column to jobs**

Migration in `_migrate()`:

```python
"apply_url": "ALTER TABLE jobs ADD COLUMN apply_url TEXT",
```

**Step 2: Create `app/apply_link_finder.py`**

```python
import httpx
from bs4 import BeautifulSoup

APPLY_PATTERNS = [
    # Link text patterns
    "apply now", "apply for this job", "apply for this position",
    "submit application", "apply here", "apply on company",
    "apply on website", "easy apply",
]

async def find_apply_url(job_url: str) -> str | None:
    """Fetch job listing page and find the actual apply link."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }
    try:
        async with httpx.AsyncClient(timeout=15.0, headers=headers, follow_redirects=True) as client:
            resp = await client.get(job_url)
            if resp.status_code != 200:
                return None
            soup = BeautifulSoup(resp.text, "html.parser")

            # Look for apply links/buttons by text content
            for a in soup.find_all("a", href=True):
                text = a.get_text(strip=True).lower()
                if any(p in text for p in APPLY_PATTERNS):
                    href = a["href"]
                    if href.startswith("http"):
                        return href
                    if href.startswith("/"):
                        from urllib.parse import urljoin
                        return urljoin(job_url, href)

            # Look for apply buttons with onclick or data attributes
            for btn in soup.find_all(["button", "a"], class_=lambda c: c and "apply" in str(c).lower()):
                href = btn.get("href") or btn.get("data-url")
                if href and href.startswith("http"):
                    return href
    except Exception:
        pass
    return None
```

**Step 3: Add API endpoint and update job detail**

```python
@app.post("/api/jobs/{job_id}/find-apply-link")
async def find_apply_link(job_id: int):
    from app.apply_link_finder import find_apply_url
    job = await app.state.db.get_job(job_id)
    if not job:
        raise HTTPException(404)
    url = await find_apply_url(job["url"])
    if url:
        await app.state.db.update_job_contact(job_id, apply_url=url)
    return {"ok": True, "apply_url": url}
```

**Step 4: Update job detail UI**

- Show "Apply Now" button linking to `apply_url` if available (prominent, green)
- Show "Find Apply Link" button if no `apply_url` exists
- Fall back to existing "Open Job Listing" link to `url`

**Step 5: Tests, commit**

Run: `pytest tests/ -v`
Commit: `git commit -m "Add direct apply link extraction from job pages"`

---

## Task 5: Smart Deduplication

Flag near-duplicate jobs using fuzzy title/company matching.

**Files:**
- Modify: `app/database.py`
- Modify: `app/main.py`
- Modify: `app/static/js/app.js`
- Test: `tests/test_dedup.py`

**Step 1: Add dedup methods to database**

```python
async def find_similar_jobs(self, title: str, company: str, exclude_id: int = None) -> list[dict]:
    """Find jobs with similar title and same company (fuzzy match)."""
    # Normalize: lowercase, strip whitespace, remove common prefixes/suffixes
    norm_company = company.lower().strip()
    # Search for same company, different listing
    query = """
        SELECT j.id, j.title, j.company, j.url, js.match_score
        FROM jobs j
        LEFT JOIN job_scores js ON j.id = js.job_id
        WHERE LOWER(j.company) LIKE ? AND j.dismissed = 0
    """
    params = [f"%{norm_company}%"]
    if exclude_id:
        query += " AND j.id != ?"
        params.append(exclude_id)
    cursor = await self.db.execute(query, params)
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]
```

**Step 2: Add duplicate detection to job detail endpoint**

In `GET /api/jobs/{job_id}`, add a `similar_jobs` field to the response by calling `find_similar_jobs()`.

**Step 3: Update job detail UI**

If `similar_jobs` has entries, show a "Similar Listings" section below the description with links to the other postings. Include a "Dismiss Duplicates" button that dismisses all but the current one.

**Step 4: Add batch dedup endpoint**

```python
@app.post("/api/jobs/dedup")
async def find_all_duplicates():
    """Scan all jobs for potential duplicates."""
    # Group jobs by normalized company name
    # Within each group, compare titles using simple word overlap
    # Return groups of potential duplicates
```

**Step 5: Tests, commit**

Run: `pytest tests/ -v`
Commit: `git commit -m "Add smart deduplication for similar job listings"`

---

## Task 6: Salary Insights

Use AI to estimate salary when not provided in listing.

**Files:**
- Create: `app/salary_estimator.py`
- Modify: `app/main.py`
- Modify: `app/database.py`
- Modify: `app/static/js/app.js`
- Test: `tests/test_salary.py`

**Step 1: Add salary estimate columns**

Migration:

```python
"salary_estimate_min": "ALTER TABLE jobs ADD COLUMN salary_estimate_min INTEGER",
"salary_estimate_max": "ALTER TABLE jobs ADD COLUMN salary_estimate_max INTEGER",
"salary_confidence": "ALTER TABLE jobs ADD COLUMN salary_confidence TEXT",
```

**Step 2: Create `app/salary_estimator.py`**

```python
SALARY_PROMPT = """Based on this job listing, estimate the annual salary range in USD.

Job Title: {title}
Company: {company}
Location: {location}
Description (first 500 chars): {description}

Respond with JSON only:
{{"min": 80000, "max": 120000, "confidence": "medium", "reasoning": "brief explanation"}}

Confidence levels: "high" (salary mentioned or very standard role), "medium" (good comparables), "low" (unusual role or limited info)
If you truly cannot estimate, return: {{"min": 0, "max": 0, "confidence": "none", "reasoning": "why"}}
"""

async def estimate_salary(client, job: dict) -> dict:
    prompt = SALARY_PROMPT.format(
        title=job.get("title", ""),
        company=job.get("company", ""),
        location=job.get("location", ""),
        description=(job.get("description", "") or "")[:500],
    )
    from app.ai_client import parse_json_response
    raw = await client.chat(prompt, max_tokens=200)
    return parse_json_response(raw)
```

**Step 3: Add API endpoint**

```python
@app.post("/api/jobs/{job_id}/estimate-salary")
async def estimate_salary_endpoint(job_id: int):
    from app.salary_estimator import estimate_salary
    job = await app.state.db.get_job(job_id)
    if not job:
        raise HTTPException(404)
    if not app.state.ai_client:
        raise HTTPException(503, "No AI provider configured")
    # Skip if salary already known
    if job.get("salary_min") and job.get("salary_max"):
        return {"ok": True, "already_known": True, "min": job["salary_min"], "max": job["salary_max"]}
    result = await estimate_salary(app.state.ai_client, job)
    if result.get("min"):
        await app.state.db.update_job_contact(job_id,
            salary_estimate_min=result["min"],
            salary_estimate_max=result["max"],
            salary_confidence=result.get("confidence", "low"),
        )
    return {"ok": True, **result}
```

**Step 4: Update UI**

- In job cards and detail view: if no `salary_min/max` but `salary_estimate_min/max` exists, show estimated range with a "~" prefix and confidence indicator
- In job detail: "Estimate Salary" button if no salary data at all
- Color code confidence: green (high), amber (medium), gray (low)

**Step 5: Tests, commit**

Run: `pytest tests/ -v`
Commit: `git commit -m "Add AI-powered salary estimation for jobs without listed pay"`

---

## Task 7: Company Research Cards

Auto-fetch basic company info for the job detail view.

**Files:**
- Create: `app/company_research.py`
- Modify: `app/database.py`
- Modify: `app/main.py`
- Modify: `app/static/js/app.js`
- Test: `tests/test_company_research.py`

**Step 1: Add `companies` table**

```sql
CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    normalized_name TEXT UNIQUE NOT NULL,
    website TEXT,
    description TEXT,
    size TEXT,
    industry TEXT,
    glassdoor_rating REAL,
    updated_at TEXT NOT NULL
);
```

**Step 2: Create `app/company_research.py`**

```python
async def research_company(company_name: str) -> dict:
    """Fetch company info via DuckDuckGo Instant Answer API and web scraping."""
    import httpx
    from bs4 import BeautifulSoup

    info = {"name": company_name}
    headers = {"User-Agent": "Mozilla/5.0 ..."}

    async with httpx.AsyncClient(timeout=15.0, headers=headers, follow_redirects=True) as client:
        # DuckDuckGo Instant Answer API (no key needed)
        try:
            resp = await client.get("https://api.duckduckgo.com/", params={
                "q": company_name, "format": "json", "no_html": "1"
            })
            data = resp.json()
            if data.get("Abstract"):
                info["description"] = data["Abstract"][:500]
            if data.get("Image"):
                info["logo_url"] = data["Image"]
            if data.get("AbstractURL"):
                info["website"] = data["AbstractURL"]
        except Exception:
            pass

        # Try to find Glassdoor rating via search
        try:
            resp = await client.get("https://html.duckduckgo.com/html/",
                params={"q": f"{company_name} glassdoor rating"})
            if resp.status_code == 200:
                text = resp.text
                import re
                rating_match = re.search(r'(\d\.\d)\s*(?:out of 5|/5|stars)', text)
                if rating_match:
                    info["glassdoor_rating"] = float(rating_match.group(1))
        except Exception:
            pass

    return info
```

**Step 3: Add DB methods and API**

```python
async def get_company(self, name: str) -> dict | None:
    normalized = name.lower().strip()
    cursor = await self.db.execute(
        "SELECT * FROM companies WHERE normalized_name = ?", (normalized,))
    row = await cursor.fetchone()
    return dict(row) if row else None

async def save_company(self, **fields):
    # Upsert by normalized_name
    ...
```

API endpoint: `GET /api/companies/{name}` — returns cached or fetches fresh.

**Step 4: Update job detail UI**

Show a "Company" card in the sidebar with:
- Company description (first 2-3 sentences)
- Size / Industry (if available)
- Glassdoor rating (star visualization)
- Website link
- "Research Company" button if no data cached

**Step 5: Tests, commit**

Run: `pytest tests/ -v`
Commit: `git commit -m "Add company research cards with auto-fetched info"`

---

## Task 8: Job Freshness Alerts

Flag jobs by age to help prioritize fresh listings.

**Files:**
- Modify: `app/static/js/app.js`
- Modify: `app/static/css/style.css`

**Step 1: Add freshness logic to frontend**

This is purely a UI enhancement — no backend changes needed. The `posted_date` and `created_at` fields already exist.

In `createJobCard()` and `renderJobDetail()`:

```javascript
function getFreshness(job) {
    const date = job.posted_date || job.created_at;
    if (!date) return null;
    const days = Math.floor((Date.now() - new Date(date)) / 86400000);
    if (days <= 1) return { label: "Fresh", class: "freshness-hot", days };
    if (days <= 3) return { label: "New", class: "freshness-new", days };
    if (days <= 7) return { label: `${days}d ago`, class: "freshness-recent", days };
    if (days <= 14) return { label: `${days}d ago`, class: "freshness-aging", days };
    if (days <= 30) return { label: `${days}d ago`, class: "freshness-old", days };
    return { label: "Stale", class: "freshness-stale", days };
}
```

**Step 2: Add CSS classes**

```css
.freshness-hot { color: #22c55e; font-weight: 600; }
.freshness-new { color: #3b82f6; }
.freshness-recent { color: var(--text-secondary); }
.freshness-aging { color: #f59e0b; }
.freshness-old { color: #ef4444; }
.freshness-stale { color: #ef4444; text-decoration: line-through; opacity: 0.7; }
```

**Step 3: Add freshness badge to job cards**

Show a small freshness indicator next to the date on each job card. For "Stale" jobs (30+ days), show a warning tooltip: "This listing may be expired."

**Step 4: Add freshness sort option**

Add "Freshest" as a sort option in the feed filter bar. Map to `ORDER BY j.posted_date DESC NULLS LAST` (new backend sort).

In `app/database.py` `list_jobs()`:

```python
elif sort_by == "date":
    query += " ORDER BY j.created_at DESC"
elif sort_by == "freshest":
    query += " ORDER BY COALESCE(j.posted_date, j.created_at) DESC"
```

**Step 5: Commit**

Run: `pytest tests/ -v`
Commit: `git commit -m "Add job freshness indicators and staleness warnings"`

---

## Task 9: One-Click Apply Tracker

Auto-update application status based on user actions.

**Files:**
- Modify: `app/main.py`
- Modify: `app/static/js/app.js`

**Step 1: Auto-track in backend**

Already partially done in Task 1 (events). This task adds:

- When user downloads PDF: if status is "prepared" or "interested", auto-update to "prepared"
- Add an "I Applied" button to the job detail that sets status to "applied" and records `applied_at` timestamp
- When status changes to "applied", auto-set `applied_at = now()`

**Step 2: Add "Mark as Applied" prominent button**

In job detail, add a large green "Mark as Applied" button that:
1. Sets status to "applied"
2. Sets `applied_at` to current timestamp
3. Adds a timeline event
4. Shows a celebratory toast

**Step 3: Add `applied_at` tracking**

In `update_application()`, if status changes to "applied" and `applied_at` is not set, auto-set it.

**Step 4: Show applied date in job cards**

If `app_status == "applied"`, show "Applied X days ago" on the card.

**Step 5: Commit**

Run: `pytest tests/ -v`
Commit: `git commit -m "Add one-click apply tracking with auto status updates"`

---

## Task 10: Export to Spreadsheet

CSV export of the job pipeline.

**Files:**
- Modify: `app/main.py`
- Modify: `app/static/js/app.js`

**Step 1: Add CSV export endpoint**

```python
@app.get("/api/export/csv")
async def export_csv(
    min_score: int | None = Query(None),
    status: str | None = Query(None),
):
    import csv
    import io

    jobs = await app.state.db.list_jobs(sort_by="score", limit=10000)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Title", "Company", "Location", "Score", "Status",
        "Salary Min", "Salary Max", "URL", "Posted Date",
        "Contact Email", "Applied At", "Source"
    ])

    for job in jobs:
        if status and job.get("app_status") != status:
            continue
        if min_score and (job.get("match_score") or 0) < min_score:
            continue
        sources = await app.state.db.get_sources(job["id"])
        source_names = ", ".join(s["source_name"] for s in sources)
        app_row = await app.state.db.get_application(job["id"])
        writer.writerow([
            job["title"], job["company"], job.get("location", ""),
            job.get("match_score", ""), app_row["status"] if app_row else "",
            job.get("salary_min", ""), job.get("salary_max", ""),
            job["url"], job.get("posted_date", ""),
            job.get("contact_email", ""), app_row.get("applied_at", "") if app_row else "",
            source_names,
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="careerpulse-export.csv"'},
    )
```

**Step 2: Add export button to dashboard**

Add an "Export CSV" button next to the Scrape/Score buttons on the dashboard. Clicking it downloads the file via `window.location = '/api/export/csv'`.

**Step 3: Commit**

Run: `pytest tests/ -v`
Commit: `git commit -m "Add CSV export for job pipeline data"`

---

## Task 11: Daily Digest Email

Generate a summary of new high-scoring jobs for self-emailing.

**Files:**
- Create: `app/digest.py`
- Modify: `app/main.py`
- Modify: `app/static/js/app.js`
- Modify: `app/database.py`
- Test: `tests/test_digest.py`

**Step 1: Create `app/digest.py`**

```python
async def generate_digest(db, min_score: int = 60, hours: int = 24) -> dict:
    """Generate a digest of new high-scoring jobs from the last N hours."""
    from datetime import datetime, timezone, timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

    cursor = await db.db.execute("""
        SELECT j.*, js.match_score, js.match_reasons
        FROM jobs j
        JOIN job_scores js ON j.id = js.job_id
        WHERE js.match_score >= ? AND j.created_at >= ? AND j.dismissed = 0
        ORDER BY js.match_score DESC
        LIMIT 20
    """, (min_score, cutoff))
    rows = await cursor.fetchall()
    jobs = [dict(r) for r in rows]

    # Format as email-ready HTML and plain text
    subject = f"CareerPulse: {len(jobs)} new matches"

    plain = f"CareerPulse Daily Digest - {len(jobs)} new job matches\n\n"
    for j in jobs:
        plain += f"[{j.get('match_score', '?')}/100] {j['title']} at {j['company']}\n"
        plain += f"  {j.get('location', 'Unknown location')}\n"
        plain += f"  {j['url']}\n\n"

    return {
        "subject": subject,
        "body": plain,
        "job_count": len(jobs),
        "jobs": jobs,
    }
```

**Step 2: Add API endpoint**

```python
@app.get("/api/digest")
async def get_digest(
    min_score: int = Query(60),
    hours: int = Query(24),
):
    from app.digest import generate_digest
    return await generate_digest(app.state.db, min_score, hours)
```

**Step 3: Add digest view to dashboard**

Add a "Daily Digest" section at the bottom of the dashboard showing the digest content. Include a "Copy Digest" button to copy the plain text to clipboard (for pasting into email client).

Optionally add a "Preview Digest" link in the nav or dashboard.

**Step 4: Tests, commit**

```python
async def test_generate_digest(db):
    job_id = await db.insert_job("Dev", "Co", "Remote", None, None, "desc", "http://x", None, "url", None)
    await db.insert_score(job_id, 85, ["good fit"], ["none"], ["python"])
    from app.digest import generate_digest
    result = await generate_digest(db, min_score=60, hours=24)
    assert result["job_count"] == 1
    assert "Dev" in result["body"]
```

Run: `pytest tests/ -v`
Commit: `git commit -m "Add daily digest summary of new high-scoring jobs"`

---

## Task 12: Keyboard Shortcuts

Add global keyboard shortcuts for power users.

**Files:**
- Modify: `app/static/js/app.js`
- Modify: `app/static/css/style.css`

**Step 1: Add keyboard handler**

```javascript
const SHORTCUTS = {
    'j': { desc: 'Next job', action: () => navigateJob(1) },
    'k': { desc: 'Previous job', action: () => navigateJob(-1) },
    'o': { desc: 'Open job listing', action: openCurrentJob },
    'd': { desc: 'Dismiss job', action: dismissCurrentJob },
    'p': { desc: 'Prepare application', action: prepareCurrentJob },
    'a': { desc: 'Mark as applied', action: applyCurrentJob },
    's': { desc: 'Scrape now', action: handleScrape },
    '/': { desc: 'Focus search', action: focusSearch },
    '?': { desc: 'Show shortcuts', action: toggleShortcutsHelp },
    'Escape': { desc: 'Close / Go back', action: goBack },
};

document.addEventListener('keydown', (e) => {
    // Skip if user is typing in an input/textarea
    if (['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)) return;

    const shortcut = SHORTCUTS[e.key];
    if (shortcut) {
        e.preventDefault();
        shortcut.action();
    }
});
```

**Step 2: Add job navigation tracking**

Track `currentJobIndex` in the feed view. `j`/`k` moves focus between job cards with a visual indicator. `Enter` on a focused card opens the detail view.

```javascript
let focusedJobIndex = -1;

function navigateJob(delta) {
    const cards = document.querySelectorAll('.job-card');
    if (!cards.length) return;
    focusedJobIndex = Math.max(0, Math.min(cards.length - 1, focusedJobIndex + delta));
    cards.forEach(c => c.classList.remove('job-card-focused'));
    cards[focusedJobIndex].classList.add('job-card-focused');
    cards[focusedJobIndex].scrollIntoView({ block: 'nearest' });
}
```

**Step 3: Add CSS for focused card**

```css
.job-card-focused {
    outline: 2px solid var(--accent);
    outline-offset: -2px;
}
```

**Step 4: Add shortcuts help modal**

When `?` is pressed, show a modal/overlay listing all shortcuts in a clean grid.

```javascript
function toggleShortcutsHelp() {
    let modal = document.getElementById('shortcuts-modal');
    if (modal) { modal.remove(); return; }
    // Create modal with shortcut list
    modal = document.createElement('div');
    modal.id = 'shortcuts-modal';
    modal.innerHTML = `
        <div class="modal-overlay" onclick="this.parentElement.remove()">
            <div class="modal-content" onclick="event.stopPropagation()">
                <h2>Keyboard Shortcuts</h2>
                <div class="shortcuts-grid">
                    ${Object.entries(SHORTCUTS).map(([key, {desc}]) =>
                        `<div class="shortcut-key"><kbd>${key}</kbd></div><div>${desc}</div>`
                    ).join('')}
                </div>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
}
```

**Step 5: Add modal and kbd CSS**

```css
.modal-overlay {
    position: fixed; inset: 0; background: rgba(0,0,0,0.5);
    display: flex; align-items: center; justify-content: center; z-index: 200;
}
.modal-content {
    background: var(--bg-surface); border-radius: var(--radius);
    padding: 24px; max-width: 400px; width: 90%;
}
.shortcuts-grid { display: grid; grid-template-columns: auto 1fr; gap: 8px 16px; }
kbd {
    background: var(--bg-surface-secondary); border: 1px solid var(--border);
    border-radius: 4px; padding: 2px 8px; font-family: monospace; font-size: 0.875rem;
}
```

**Step 6: Commit**

Commit: `git commit -m "Add keyboard shortcuts for power-user navigation"`

---

## Task Dependency Order

Tasks are mostly independent but recommended order:

1. **Task 1: Application Timeline** — foundation for event tracking (Tasks 3, 4, 9 depend on this)
2. **Task 2: User Profile** — standalone
3. **Task 8: Job Freshness** — standalone, quick win
4. **Task 12: Keyboard Shortcuts** — standalone, quick win
5. **Task 10: CSV Export** — standalone, quick win
6. **Task 5: Smart Dedup** — standalone
7. **Task 3: Hiring Manager Lookup** — uses event tracking from Task 1
8. **Task 4: Direct Apply Links** — uses event tracking from Task 1
9. **Task 9: One-Click Apply** — uses event tracking from Task 1
10. **Task 6: Salary Insights** — requires AI client
11. **Task 7: Company Research** — standalone but larger
12. **Task 11: Daily Digest** — standalone

---

## Final Steps

After all tasks:
1. Run full test suite: `pytest tests/ -v`
2. Update README.md with new features
3. Update API section in README with new endpoints
4. Commit documentation
5. Push to GitHub
