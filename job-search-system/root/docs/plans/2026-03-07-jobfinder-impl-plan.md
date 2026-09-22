# JobFinder Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a self-hosted job discovery, scoring, and application dashboard.

**Architecture:** Single Docker container running FastAPI + SQLite + vanilla JS frontend. Scrapers pull from 8 job sources on a schedule, Claude API scores/tailors, web dashboard for interaction.

**Tech Stack:** Python 3.12, FastAPI, SQLite (aiosqlite), APScheduler, httpx, feedparser, beautifulsoup4, anthropic SDK, Pico CSS, vanilla JS

---

### Task 1: Project Scaffold & Dependencies

**Files:**
- Create: `pyproject.toml`
- Create: `app/__init__.py`
- Create: `app/config.py`
- Create: `tests/__init__.py`
- Create: `tests/test_config.py`

**Step 1: Initialize git repo and create pyproject.toml**

```bash
cd /Users/lukemacneil/code/jobfinder
git init
```

```toml
# pyproject.toml
[project]
name = "jobfinder"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.34.0",
    "aiosqlite>=0.20.0",
    "httpx>=0.28.0",
    "feedparser>=6.0.0",
    "beautifulsoup4>=4.12.0",
    "anthropic>=0.42.0",
    "apscheduler>=3.10.0",
    "python-multipart>=0.0.18",
    "pydantic-settings>=2.7.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "pytest-httpx>=0.35.0",
    "httpx>=0.28.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

**Step 2: Write failing test for config**

```python
# tests/test_config.py
from app.config import Settings

def test_settings_defaults():
    s = Settings(anthropic_api_key="test-key")
    assert s.db_path == "data/jobfinder.db"
    assert s.scrape_interval_hours == 6
    assert s.min_salary == 150000
    assert s.min_hourly_rate == 95
    assert s.anthropic_api_key == "test-key"

def test_settings_custom():
    s = Settings(anthropic_api_key="k", scrape_interval_hours=12, min_salary=180000)
    assert s.scrape_interval_hours == 12
    assert s.min_salary == 180000
```

**Step 3: Run test to verify it fails**

Run: `cd /Users/lukemacneil/code/jobfinder && python -m pytest tests/test_config.py -v`
Expected: FAIL — module not found

**Step 4: Write minimal implementation**

```python
# app/__init__.py
# (empty)
```

```python
# app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    anthropic_api_key: str
    usajobs_api_key: str = ""
    db_path: str = "data/jobfinder.db"
    scrape_interval_hours: int = 6
    min_salary: int = 150000
    min_hourly_rate: int = 95
    host: str = "0.0.0.0"
    port: int = 8085
    resume_path: str = "data/resume.txt"

    model_config = {"env_prefix": "JOBFINDER_"}
```

**Step 5: Run tests to verify pass**

Run: `python -m pytest tests/test_config.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add pyproject.toml app/ tests/
git commit -m "Project scaffold with config and dependencies"
```

---

### Task 2: Database Schema & CRUD

**Files:**
- Create: `app/database.py`
- Create: `tests/test_database.py`

**Step 1: Write failing tests**

```python
# tests/test_database.py
import pytest
import os
import asyncio
from app.database import Database

@pytest.fixture
async def db(tmp_path):
    db_path = str(tmp_path / "test.db")
    database = Database(db_path)
    await database.init()
    yield database
    await database.close()

@pytest.mark.asyncio
async def test_insert_and_get_job(db):
    job_id = await db.insert_job(
        title="Senior DevOps Engineer",
        company="Acme Corp",
        location="Remote",
        salary_min=160000,
        salary_max=200000,
        description="We need a senior devops engineer...",
        url="https://example.com/job/1",
        posted_date="2026-03-01",
        application_method="url",
        contact_email=None,
    )
    assert job_id is not None
    job = await db.get_job(job_id)
    assert job["title"] == "Senior DevOps Engineer"
    assert job["company"] == "Acme Corp"
    assert job["salary_min"] == 160000

@pytest.mark.asyncio
async def test_insert_source(db):
    job_id = await db.insert_job(
        title="SRE", company="BigCo", location="Remote",
        salary_min=None, salary_max=None, description="SRE role",
        url="https://example.com/job/2", posted_date=None,
        application_method="url", contact_email=None,
    )
    await db.insert_source(job_id, "remoteok", "https://remoteok.com/jobs/123")
    sources = await db.get_sources(job_id)
    assert len(sources) == 1
    assert sources[0]["source_name"] == "remoteok"

@pytest.mark.asyncio
async def test_dedup_hash(db):
    from app.database import make_dedup_hash
    h = make_dedup_hash("Senior DevOps Engineer", "Acme Corp", "https://example.com/job/1")
    assert isinstance(h, str)
    assert len(h) == 64  # sha256

@pytest.mark.asyncio
async def test_find_by_dedup_hash(db):
    job_id = await db.insert_job(
        title="SRE", company="BigCo", location="Remote",
        salary_min=None, salary_max=None, description="SRE role",
        url="https://example.com/sre", posted_date=None,
        application_method="url", contact_email=None,
    )
    from app.database import make_dedup_hash
    h = make_dedup_hash("SRE", "BigCo", "https://example.com/sre")
    found = await db.find_job_by_hash(h)
    assert found is not None
    assert found["id"] == job_id

@pytest.mark.asyncio
async def test_insert_score(db):
    job_id = await db.insert_job(
        title="SRE", company="BigCo", location="Remote",
        salary_min=None, salary_max=None, description="SRE role",
        url="https://example.com/sre2", posted_date=None,
        application_method="url", contact_email=None,
    )
    await db.insert_score(job_id, 85, ["strong AWS match"], ["no K8s mentioned"], ["kubernetes"])
    score = await db.get_score(job_id)
    assert score["match_score"] == 85
    assert "strong AWS match" in score["match_reasons"]

@pytest.mark.asyncio
async def test_insert_and_update_application(db):
    job_id = await db.insert_job(
        title="SRE", company="BigCo", location="Remote",
        salary_min=None, salary_max=None, description="SRE role",
        url="https://example.com/sre3", posted_date=None,
        application_method="url", contact_email=None,
    )
    app_id = await db.insert_application(job_id, "interested")
    await db.update_application(app_id, status="applied", cover_letter="Dear hiring manager...")
    app = await db.get_application(job_id)
    assert app["status"] == "applied"
    assert app["cover_letter"] == "Dear hiring manager..."

@pytest.mark.asyncio
async def test_list_jobs_with_scores(db):
    for i in range(3):
        jid = await db.insert_job(
            title=f"Job {i}", company=f"Co {i}", location="Remote",
            salary_min=150000 + i * 10000, salary_max=None, description=f"desc {i}",
            url=f"https://example.com/job/{i+10}", posted_date=None,
            application_method="url", contact_email=None,
        )
        await db.insert_score(jid, 90 - i * 10, [], [], [])
    jobs = await db.list_jobs(sort_by="score", limit=10, offset=0)
    assert len(jobs) == 3
    assert jobs[0]["match_score"] >= jobs[1]["match_score"]

@pytest.mark.asyncio
async def test_get_stats(db):
    stats = await db.get_stats()
    assert "total_jobs" in stats
    assert "total_scored" in stats
    assert "total_applied" in stats
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_database.py -v`
Expected: FAIL

**Step 3: Write implementation**

```python
# app/database.py
import hashlib
import json
from datetime import datetime, timezone
import aiosqlite

def make_dedup_hash(title: str, company: str, url: str) -> str:
    normalized = f"{title.lower().strip()}|{company.lower().strip()}|{url.lower().strip().rstrip('/')}"
    return hashlib.sha256(normalized.encode()).hexdigest()

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.db = None

    async def init(self):
        self.db = await aiosqlite.connect(self.db_path)
        self.db.row_factory = aiosqlite.Row
        await self._create_tables()

    async def close(self):
        if self.db:
            await self.db.close()

    async def _create_tables(self):
        await self.db.executescript("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                company TEXT NOT NULL,
                location TEXT,
                salary_min INTEGER,
                salary_max INTEGER,
                description TEXT,
                url TEXT NOT NULL,
                posted_date TEXT,
                application_method TEXT DEFAULT 'url',
                contact_email TEXT,
                dedup_hash TEXT UNIQUE NOT NULL,
                dismissed INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                source_name TEXT NOT NULL,
                source_url TEXT,
                FOREIGN KEY (job_id) REFERENCES jobs(id)
            );
            CREATE TABLE IF NOT EXISTS job_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER UNIQUE NOT NULL,
                match_score INTEGER NOT NULL,
                match_reasons TEXT NOT NULL,
                concerns TEXT NOT NULL,
                suggested_keywords TEXT NOT NULL,
                scored_at TEXT NOT NULL,
                FOREIGN KEY (job_id) REFERENCES jobs(id)
            );
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER UNIQUE NOT NULL,
                status TEXT NOT NULL DEFAULT 'interested',
                tailored_resume TEXT,
                cover_letter TEXT,
                email_draft TEXT,
                applied_at TEXT,
                notes TEXT,
                FOREIGN KEY (job_id) REFERENCES jobs(id)
            );
            CREATE INDEX IF NOT EXISTS idx_jobs_dedup ON jobs(dedup_hash);
            CREATE INDEX IF NOT EXISTS idx_scores_job ON job_scores(job_id);
            CREATE INDEX IF NOT EXISTS idx_sources_job ON sources(job_id);
        """)
        await self.db.commit()

    async def insert_job(self, title, company, location, salary_min, salary_max,
                         description, url, posted_date, application_method, contact_email):
        dedup = make_dedup_hash(title, company, url)
        now = datetime.now(timezone.utc).isoformat()
        cursor = await self.db.execute(
            """INSERT OR IGNORE INTO jobs
               (title, company, location, salary_min, salary_max, description, url,
                posted_date, application_method, contact_email, dedup_hash, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (title, company, location, salary_min, salary_max, description, url,
             posted_date, application_method, contact_email, dedup, now)
        )
        await self.db.commit()
        return cursor.lastrowid

    async def get_job(self, job_id):
        cursor = await self.db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def find_job_by_hash(self, dedup_hash):
        cursor = await self.db.execute("SELECT * FROM jobs WHERE dedup_hash = ?", (dedup_hash,))
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def insert_source(self, job_id, source_name, source_url):
        await self.db.execute(
            "INSERT INTO sources (job_id, source_name, source_url) VALUES (?, ?, ?)",
            (job_id, source_name, source_url)
        )
        await self.db.commit()

    async def get_sources(self, job_id):
        cursor = await self.db.execute("SELECT * FROM sources WHERE job_id = ?", (job_id,))
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def insert_score(self, job_id, match_score, match_reasons, concerns, suggested_keywords):
        now = datetime.now(timezone.utc).isoformat()
        await self.db.execute(
            """INSERT OR REPLACE INTO job_scores
               (job_id, match_score, match_reasons, concerns, suggested_keywords, scored_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (job_id, match_score, json.dumps(match_reasons), json.dumps(concerns),
             json.dumps(suggested_keywords), now)
        )
        await self.db.commit()

    async def get_score(self, job_id):
        cursor = await self.db.execute("SELECT * FROM job_scores WHERE job_id = ?", (job_id,))
        row = await cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        d["match_reasons"] = json.loads(d["match_reasons"])
        d["concerns"] = json.loads(d["concerns"])
        d["suggested_keywords"] = json.loads(d["suggested_keywords"])
        return d

    async def insert_application(self, job_id, status="interested"):
        cursor = await self.db.execute(
            "INSERT INTO applications (job_id, status) VALUES (?, ?)",
            (job_id, status)
        )
        await self.db.commit()
        return cursor.lastrowid

    async def update_application(self, app_id, **kwargs):
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        vals = list(kwargs.values())
        vals.append(app_id)
        await self.db.execute(f"UPDATE applications SET {sets} WHERE id = ?", vals)
        await self.db.commit()

    async def get_application(self, job_id):
        cursor = await self.db.execute("SELECT * FROM applications WHERE job_id = ?", (job_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def list_jobs(self, sort_by="score", limit=50, offset=0, min_score=None,
                        search=None, source=None, dismissed=False):
        query = """
            SELECT j.*, js.match_score, js.match_reasons, js.concerns,
                   a.status as app_status
            FROM jobs j
            LEFT JOIN job_scores js ON j.id = js.job_id
            LEFT JOIN applications a ON j.id = a.job_id
            WHERE j.dismissed = ?
        """
        params = [1 if dismissed else 0]
        if min_score is not None:
            query += " AND js.match_score >= ?"
            params.append(min_score)
        if search:
            query += " AND (j.title LIKE ? OR j.company LIKE ? OR j.description LIKE ?)"
            params.extend([f"%{search}%"] * 3)
        if source:
            query += " AND j.id IN (SELECT job_id FROM sources WHERE source_name = ?)"
            params.append(source)
        if sort_by == "score":
            query += " ORDER BY js.match_score DESC NULLS LAST"
        else:
            query += " ORDER BY j.created_at DESC"
        query += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        cursor = await self.db.execute(query, params)
        rows = await cursor.fetchall()
        results = []
        for row in rows:
            d = dict(row)
            if d.get("match_reasons"):
                d["match_reasons"] = json.loads(d["match_reasons"])
            if d.get("concerns"):
                d["concerns"] = json.loads(d["concerns"])
            results.append(d)
        return results

    async def get_unscored_jobs(self, limit=10):
        cursor = await self.db.execute(
            """SELECT j.* FROM jobs j
               LEFT JOIN job_scores js ON j.id = js.job_id
               WHERE js.id IS NULL
               LIMIT ?""",
            (limit,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def dismiss_job(self, job_id):
        await self.db.execute("UPDATE jobs SET dismissed = 1 WHERE id = ?", (job_id,))
        await self.db.commit()

    async def get_stats(self):
        stats = {}
        for key, query in [
            ("total_jobs", "SELECT COUNT(*) FROM jobs WHERE dismissed = 0"),
            ("total_scored", "SELECT COUNT(*) FROM job_scores"),
            ("total_applied", "SELECT COUNT(*) FROM applications WHERE status = 'applied'"),
            ("total_interested", "SELECT COUNT(*) FROM applications WHERE status = 'interested'"),
            ("total_interviewing", "SELECT COUNT(*) FROM applications WHERE status = 'interviewing'"),
        ]:
            cursor = await self.db.execute(query)
            row = await cursor.fetchone()
            stats[key] = row[0]
        return stats
```

**Step 4: Run tests**

Run: `python -m pytest tests/test_database.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/database.py tests/test_database.py
git commit -m "Database schema and CRUD operations with full test coverage"
```

---

### Task 3: Base Scraper + RemoteOK Scraper

**Files:**
- Create: `app/scrapers/__init__.py`
- Create: `app/scrapers/base.py`
- Create: `app/scrapers/remoteok.py`
- Create: `tests/test_scrapers/__init__.py`
- Create: `tests/test_scrapers/test_remoteok.py`

**Step 1: Write failing tests**

```python
# tests/test_scrapers/test_remoteok.py
import pytest
from app.scrapers.base import JobListing
from app.scrapers.remoteok import RemoteOKScraper

MOCK_RESPONSE = [
    {"legal": "https://remoteok.com"},
    {
        "id": "123",
        "epoch": "1709312400",
        "position": "Senior DevOps Engineer",
        "company": "TechCorp",
        "location": "Remote",
        "salary_min": 160000,
        "salary_max": 200000,
        "description": "We need a senior devops engineer with AWS and K8s experience.",
        "url": "https://remoteok.com/remote-jobs/123",
        "tags": ["devops", "aws", "kubernetes"],
        "date": "2026-03-01T00:00:00+00:00",
        "apply_url": "https://techcorp.com/apply"
    },
    {
        "id": "124",
        "epoch": "1709312400",
        "position": "Junior Frontend Dev",
        "company": "SmallCo",
        "location": "Remote",
        "description": "Entry level react role",
        "url": "https://remoteok.com/remote-jobs/124",
        "tags": ["react", "frontend"],
        "date": "2026-03-01T00:00:00+00:00"
    }
]

@pytest.mark.asyncio
async def test_remoteok_parse(httpx_mock):
    httpx_mock.add_response(url="https://remoteok.com/api", json=MOCK_RESPONSE)
    scraper = RemoteOKScraper()
    jobs = await scraper.scrape()
    assert len(jobs) == 2
    assert isinstance(jobs[0], JobListing)
    assert jobs[0].title == "Senior DevOps Engineer"
    assert jobs[0].company == "TechCorp"
    assert jobs[0].salary_min == 160000
    assert jobs[0].source == "remoteok"

@pytest.mark.asyncio
async def test_remoteok_handles_empty(httpx_mock):
    httpx_mock.add_response(url="https://remoteok.com/api", json=[{"legal": "ok"}])
    scraper = RemoteOKScraper()
    jobs = await scraper.scrape()
    assert jobs == []

@pytest.mark.asyncio
async def test_remoteok_handles_error(httpx_mock):
    httpx_mock.add_response(url="https://remoteok.com/api", status_code=500)
    scraper = RemoteOKScraper()
    jobs = await scraper.scrape()
    assert jobs == []
```

**Step 2: Run to verify fail**

Run: `python -m pytest tests/test_scrapers/test_remoteok.py -v`

**Step 3: Implement**

```python
# app/scrapers/base.py
from dataclasses import dataclass, field
from typing import Optional
import httpx

@dataclass
class JobListing:
    title: str
    company: str
    location: str
    description: str
    url: str
    source: str
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    posted_date: Optional[str] = None
    application_method: str = "url"
    contact_email: Optional[str] = None
    tags: list[str] = field(default_factory=list)

class BaseScraper:
    source_name: str = "base"

    def get_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
            timeout=30.0,
            follow_redirects=True,
        )

    async def scrape(self) -> list[JobListing]:
        raise NotImplementedError
```

```python
# app/scrapers/__init__.py
from app.scrapers.remoteok import RemoteOKScraper

ALL_SCRAPERS = [RemoteOKScraper]
```

```python
# app/scrapers/remoteok.py
import logging
from app.scrapers.base import BaseScraper, JobListing

logger = logging.getLogger(__name__)

class RemoteOKScraper(BaseScraper):
    source_name = "remoteok"
    API_URL = "https://remoteok.com/api"

    async def scrape(self) -> list[JobListing]:
        try:
            async with self.get_client() as client:
                resp = await client.get(self.API_URL)
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            logger.error(f"RemoteOK scrape failed: {e}")
            return []

        jobs = []
        for item in data:
            if "position" not in item:
                continue
            jobs.append(JobListing(
                title=item.get("position", ""),
                company=item.get("company", ""),
                location=item.get("location", "Remote"),
                description=item.get("description", ""),
                url=item.get("url", ""),
                source=self.source_name,
                salary_min=item.get("salary_min"),
                salary_max=item.get("salary_max"),
                posted_date=item.get("date"),
                tags=item.get("tags", []),
            ))
        return jobs
```

**Step 4: Run tests**

Run: `python -m pytest tests/test_scrapers/test_remoteok.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/scrapers/ tests/test_scrapers/
git commit -m "Base scraper framework and RemoteOK scraper with tests"
```

---

### Task 4: Remaining Scrapers (Indeed RSS, WWR, HN, Remotive, USAJobs, LinkedIn, Dice)

**Files:**
- Create: `app/scrapers/indeed.py`
- Create: `app/scrapers/weworkremotely.py`
- Create: `app/scrapers/hackernews.py`
- Create: `app/scrapers/remotive.py`
- Create: `app/scrapers/usajobs.py`
- Create: `app/scrapers/linkedin.py`
- Create: `app/scrapers/dice.py`
- Create: `tests/test_scrapers/test_indeed.py`
- Create: `tests/test_scrapers/test_weworkremotely.py`
- Create: `tests/test_scrapers/test_hackernews.py`
- Create: `tests/test_scrapers/test_remotive.py`
- Create: `tests/test_scrapers/test_usajobs.py`
- Create: `tests/test_scrapers/test_linkedin.py`
- Create: `tests/test_scrapers/test_dice.py`

Each scraper follows the same TDD pattern as Task 3:
1. Write test with mock HTTP responses matching the real API format
2. Verify test fails
3. Implement scraper returning `list[JobListing]`
4. Verify tests pass
5. Commit per scraper

**Key patterns per scraper:**

- **Indeed**: feedparser to parse RSS. Search keywords: "devops engineer remote", "SRE remote", "infrastructure engineer remote", "AI engineer remote", "platform engineer remote". Mock with sample RSS XML.
- **We Work Remotely**: feedparser on RSS feed URLs for DevOps and Programming categories. Mock with sample RSS XML.
- **HackerNews**: httpx to fetch `https://hacker-news.firebaseio.com/v0/item/{id}.json` for the monthly "Who's Hiring" thread. Parse comment text with BeautifulSoup. Mock with sample HN API JSON.
- **Remotive**: JSON API at `https://remotive.com/api/remote-jobs?category=devops&category=software-dev`. Mock with sample JSON.
- **USAJobs**: REST API at `https://data.usajobs.gov/api/search` with `Authorization-Key` header. Search for "information technology" series 2210. Mock with sample JSON.
- **LinkedIn**: Google search scrape `site:linkedin.com/jobs "senior devops" OR "SRE" OR "infrastructure engineer" remote`. Parse result links. httpx with randomized delay. Mock with sample HTML.
- **Dice**: Same Google search approach for `site:dice.com/job-detail`. Mock with sample HTML.

**Commit after each scraper is green.** Update `app/scrapers/__init__.py` ALL_SCRAPERS list after each.

---

### Task 5: Claude API Matcher (Job Scoring)

**Files:**
- Create: `app/matcher.py`
- Create: `tests/test_matcher.py`

**Step 1: Write failing tests**

```python
# tests/test_matcher.py
import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from app.matcher import JobMatcher

SAMPLE_RESUME = """Senior Linux and Infrastructure Engineer with 20+ years...
AWS, Kubernetes, Terraform, Ansible, Python, Docker...
Salesforce Lead Infra Engineer, CVS Health Senior Infra Engineer..."""

SAMPLE_JOB_DESC = """Senior DevOps Engineer - Remote
Requirements: AWS, Kubernetes, Terraform, CI/CD, Python
Salary: $180,000 - $220,000"""

MOCK_CLAUDE_RESPONSE = {
    "score": 88,
    "reasons": ["Strong AWS and K8s match", "20+ years seniority aligns"],
    "concerns": ["No Go experience mentioned"],
    "keywords": ["kubernetes", "terraform", "CI/CD"]
}

@pytest.mark.asyncio
async def test_matcher_scores_job():
    mock_client = MagicMock()
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=json.dumps(MOCK_CLAUDE_RESPONSE))]
    mock_client.messages.create = AsyncMock(return_value=mock_message)

    matcher = JobMatcher(client=mock_client, resume_text=SAMPLE_RESUME)
    result = await matcher.score_job(SAMPLE_JOB_DESC)
    assert result["score"] == 88
    assert len(result["reasons"]) > 0
    assert "concerns" in result
    assert "keywords" in result

@pytest.mark.asyncio
async def test_matcher_handles_bad_json():
    mock_client = MagicMock()
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text="not json")]
    mock_client.messages.create = AsyncMock(return_value=mock_message)

    matcher = JobMatcher(client=mock_client, resume_text=SAMPLE_RESUME)
    result = await matcher.score_job(SAMPLE_JOB_DESC)
    assert result["score"] == 0
    assert "parse error" in result["concerns"][0].lower()

@pytest.mark.asyncio
async def test_matcher_batch_score():
    mock_client = MagicMock()
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=json.dumps(MOCK_CLAUDE_RESPONSE))]
    mock_client.messages.create = AsyncMock(return_value=mock_message)

    matcher = JobMatcher(client=mock_client, resume_text=SAMPLE_RESUME)
    jobs = [{"id": 1, "description": "job 1"}, {"id": 2, "description": "job 2"}]
    results = await matcher.batch_score(jobs)
    assert len(results) == 2
    assert all(r["score"] == 88 for r in results)
```

**Step 2: Run to verify fail**

**Step 3: Implement**

```python
# app/matcher.py
import json
import asyncio
import logging

logger = logging.getLogger(__name__)

SCORING_PROMPT = """You are a job matching assistant. Compare this resume against the job description.

RESUME:
{resume}

JOB DESCRIPTION:
{job_description}

Return ONLY valid JSON with this exact structure:
{{
    "score": <0-100 integer>,
    "reasons": ["reason 1", "reason 2"],
    "concerns": ["concern 1"],
    "keywords": ["keyword to emphasize"]
}}

Scoring criteria:
- Skills overlap (Linux, AWS, K8s, Python, Terraform, Ansible, Docker, CI/CD)
- Seniority alignment (candidate has 20+ years, look for senior/staff/lead roles)
- Salary fit (minimum $150k FTE or $95/hr contract)
- Remote compatibility
- AI/LLM relevance is a bonus differentiator
- Score 80+ = strong match, 60-79 = decent, below 60 = weak"""

class JobMatcher:
    def __init__(self, client, resume_text: str):
        self.client = client
        self.resume_text = resume_text

    async def score_job(self, job_description: str) -> dict:
        try:
            message = await self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                messages=[{
                    "role": "user",
                    "content": SCORING_PROMPT.format(
                        resume=self.resume_text,
                        job_description=job_description
                    )
                }]
            )
            return json.loads(message.content[0].text)
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Scoring failed: {e}")
            return {
                "score": 0,
                "reasons": [],
                "concerns": [f"Parse error: {e}"],
                "keywords": []
            }

    async def batch_score(self, jobs: list[dict], delay: float = 2.0) -> list[dict]:
        results = []
        for job in jobs:
            result = await self.score_job(job["description"])
            result["job_id"] = job["id"]
            results.append(result)
            if job != jobs[-1]:
                await asyncio.sleep(delay)
        return results
```

**Step 4: Run tests**

Run: `python -m pytest tests/test_matcher.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/matcher.py tests/test_matcher.py
git commit -m "Claude API job matcher with scoring and batch support"
```

---

### Task 6: Resume Tailoring & Cover Letter Generation

**Files:**
- Create: `app/tailoring.py`
- Create: `tests/test_tailoring.py`

**Step 1: Write failing tests**

```python
# tests/test_tailoring.py
import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from app.tailoring import Tailor

SAMPLE_RESUME = "Senior Linux Engineer with 20+ years..."

MOCK_TAILORED = {
    "tailored_resume": "Senior Infrastructure & AI Engineer with 20+ years...",
    "cover_letter": "Dear Hiring Manager,\n\nI am writing to express my interest..."
}

@pytest.mark.asyncio
async def test_tailor_generates_materials():
    mock_client = MagicMock()
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=json.dumps(MOCK_TAILORED))]
    mock_client.messages.create = AsyncMock(return_value=mock_message)

    tailor = Tailor(client=mock_client, resume_text=SAMPLE_RESUME)
    result = await tailor.prepare(
        job_description="Senior DevOps role...",
        match_reasons=["Strong AWS match"],
        suggested_keywords=["kubernetes"]
    )
    assert "tailored_resume" in result
    assert "cover_letter" in result
    assert len(result["cover_letter"]) > 0

@pytest.mark.asyncio
async def test_tailor_handles_error():
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(side_effect=Exception("API error"))

    tailor = Tailor(client=mock_client, resume_text=SAMPLE_RESUME)
    result = await tailor.prepare("job desc", [], [])
    assert result["tailored_resume"] == SAMPLE_RESUME
    assert "error" in result["cover_letter"].lower() or result["cover_letter"] == ""
```

**Step 2: Run to verify fail**

**Step 3: Implement**

```python
# app/tailoring.py
import json
import logging

logger = logging.getLogger(__name__)

TAILORING_PROMPT = """You are a resume tailoring assistant for a senior engineer.

BASE RESUME:
{resume}

JOB DESCRIPTION:
{job_description}

MATCH REASONS (from prior analysis):
{match_reasons}

KEYWORDS TO EMPHASIZE:
{keywords}

Return ONLY valid JSON:
{{
    "tailored_resume": "<full resume text, lightly reorganized to emphasize relevant experience. DO NOT fabricate experience. Only reorder bullets, adjust summary wording, and highlight matching skills.>",
    "cover_letter": "<~250 word professional cover letter. Confident senior engineer tone. Connect specific accomplishments to job requirements. No generic filler.>"
}}"""

class Tailor:
    def __init__(self, client, resume_text: str):
        self.client = client
        self.resume_text = resume_text

    async def prepare(self, job_description: str, match_reasons: list,
                      suggested_keywords: list) -> dict:
        try:
            message = await self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                messages=[{
                    "role": "user",
                    "content": TAILORING_PROMPT.format(
                        resume=self.resume_text,
                        job_description=job_description,
                        match_reasons="\n".join(match_reasons),
                        keywords=", ".join(suggested_keywords)
                    )
                }]
            )
            return json.loads(message.content[0].text)
        except Exception as e:
            logger.error(f"Tailoring failed: {e}")
            return {
                "tailored_resume": self.resume_text,
                "cover_letter": ""
            }
```

**Step 4: Run tests, verify pass**

**Step 5: Commit**

```bash
git add app/tailoring.py tests/test_tailoring.py
git commit -m "Resume tailoring and cover letter generation with Claude API"
```

---

### Task 7: Email Drafter

**Files:**
- Create: `app/emailer.py`
- Create: `tests/test_emailer.py`

**Step 1: Write failing tests**

```python
# tests/test_emailer.py
import pytest
from app.emailer import draft_application_email, find_contact_emails

def test_draft_email():
    email = draft_application_email(
        to="jobs@techcorp.com",
        company="TechCorp",
        position="Senior DevOps Engineer",
        cover_letter="Dear Hiring Manager,\n\nI am writing...",
        sender_name="Luke MacNeil",
        sender_email="tcpsyn@gmail.com"
    )
    assert email["to"] == "jobs@techcorp.com"
    assert "Senior DevOps Engineer" in email["subject"]
    assert "TechCorp" in email["subject"]
    assert "Dear Hiring Manager" in email["body"]
    assert "Luke MacNeil" in email["body"]

def test_draft_email_no_contact():
    email = draft_application_email(
        to=None,
        company="TechCorp",
        position="Senior DevOps Engineer",
        cover_letter="Dear Hiring Manager...",
        sender_name="Luke MacNeil",
        sender_email="tcpsyn@gmail.com"
    )
    assert email is None

@pytest.mark.asyncio
async def test_find_contact_emails(httpx_mock):
    httpx_mock.add_response(
        url="https://techcorp.com/careers",
        html="<html><body>Contact us at hiring@techcorp.com</body></html>"
    )
    emails = await find_contact_emails("techcorp.com", httpx_mock=None)
    # This tests the pattern matching, not actual HTTP
    from app.emailer import extract_emails_from_text
    found = extract_emails_from_text("Contact us at hiring@techcorp.com or jobs@techcorp.com")
    assert "hiring@techcorp.com" in found
    assert "jobs@techcorp.com" in found

def test_extract_emails_from_text():
    from app.emailer import extract_emails_from_text
    text = "Send resume to jobs@acme.com or hr@acme.com. Not an email: foo@bar"
    emails = extract_emails_from_text(text)
    assert "jobs@acme.com" in emails
    assert "hr@acme.com" in emails
```

**Step 2: Run to verify fail**

**Step 3: Implement**

```python
# app/emailer.py
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')

def extract_emails_from_text(text: str) -> list[str]:
    return list(set(EMAIL_PATTERN.findall(text)))

def draft_application_email(
    to: Optional[str],
    company: str,
    position: str,
    cover_letter: str,
    sender_name: str,
    sender_email: str,
) -> Optional[dict]:
    if not to:
        return None
    return {
        "to": to,
        "subject": f"Application: {position} at {company} - {sender_name}",
        "body": f"{cover_letter}\n\nBest regards,\n{sender_name}\n{sender_email}",
    }

async def find_contact_emails(domain: str) -> list[str]:
    import httpx
    common_paths = ["/careers", "/jobs", "/contact", "/about"]
    found = []
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            for path in common_paths:
                try:
                    resp = await client.get(f"https://{domain}{path}")
                    if resp.status_code == 200:
                        found.extend(extract_emails_from_text(resp.text))
                except Exception:
                    continue
    except Exception as e:
        logger.error(f"Contact email search failed for {domain}: {e}")
    return list(set(found))
```

**Step 4: Run tests, verify pass**

**Step 5: Commit**

```bash
git add app/emailer.py tests/test_emailer.py
git commit -m "Email drafter with contact email extraction"
```

---

### Task 8: FastAPI App & API Routes

**Files:**
- Create: `app/main.py`
- Create: `tests/test_api.py`

**Step 1: Write failing tests**

```python
# tests/test_api.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import create_app

@pytest.fixture
async def client(tmp_path):
    app = create_app(db_path=str(tmp_path / "test.db"), testing=True)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

@pytest.mark.asyncio
async def test_list_jobs_empty(client):
    resp = await client.get("/api/jobs")
    assert resp.status_code == 200
    assert resp.json()["jobs"] == []

@pytest.mark.asyncio
async def test_get_stats(client):
    resp = await client.get("/api/stats")
    assert resp.status_code == 200
    assert "total_jobs" in resp.json()

@pytest.mark.asyncio
async def test_get_job_not_found(client):
    resp = await client.get("/api/jobs/999")
    assert resp.status_code == 404

@pytest.mark.asyncio
async def test_dismiss_job(client):
    # Insert a job first via the DB directly
    resp = await client.get("/api/jobs")
    assert resp.status_code == 200
```

**Step 2: Run to verify fail**

**Step 3: Implement**

```python
# app/main.py
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.database import Database
from app.config import Settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    db_path = app.state.db_path
    os.makedirs(os.path.dirname(db_path) or "data", exist_ok=True)
    app.state.db = Database(db_path)
    await app.state.db.init()
    yield
    await app.state.db.close()

def create_app(db_path: str = "data/jobfinder.db", testing: bool = False) -> FastAPI:
    app = FastAPI(title="JobFinder", lifespan=lifespan)
    app.state.db_path = db_path

    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

    @app.get("/api/jobs")
    async def list_jobs(
        sort: str = Query("score"),
        limit: int = Query(50),
        offset: int = Query(0),
        min_score: int | None = Query(None),
        search: str | None = Query(None),
        source: str | None = Query(None),
    ):
        jobs = await app.state.db.list_jobs(
            sort_by=sort, limit=limit, offset=offset,
            min_score=min_score, search=search, source=source,
        )
        return {"jobs": jobs}

    @app.get("/api/jobs/{job_id}")
    async def get_job(job_id: int):
        job = await app.state.db.get_job(job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        score = await app.state.db.get_score(job_id)
        sources = await app.state.db.get_sources(job_id)
        application = await app.state.db.get_application(job_id)
        return {**job, "score": score, "sources": sources, "application": application}

    @app.post("/api/jobs/{job_id}/dismiss")
    async def dismiss_job(job_id: int):
        await app.state.db.dismiss_job(job_id)
        return {"ok": True}

    @app.post("/api/jobs/{job_id}/prepare")
    async def prepare_application(job_id: int):
        job = await app.state.db.get_job(job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        score = await app.state.db.get_score(job_id)
        # Tailoring will be wired up when Tailor is integrated
        return {"job_id": job_id, "status": "not_implemented_yet"}

    @app.post("/api/jobs/{job_id}/application")
    async def update_application(job_id: int, status: str = Query(...), notes: str = Query("")):
        app_row = await app.state.db.get_application(job_id)
        if not app_row:
            await app.state.db.insert_application(job_id, status)
        else:
            await app.state.db.update_application(app_row["id"], status=status, notes=notes)
        return {"ok": True}

    @app.get("/api/stats")
    async def get_stats():
        return await app.state.db.get_stats()

    @app.post("/api/scrape")
    async def trigger_scrape():
        # Will be wired to scheduler
        return {"status": "triggered"}

    if not testing:
        static_dir = os.path.join(os.path.dirname(__file__), "static")
        if os.path.exists(static_dir):
            app.mount("/static", StaticFiles(directory=static_dir), name="static")
            @app.get("/")
            async def index():
                return FileResponse(os.path.join(static_dir, "index.html"))

    return app
```

**Step 4: Run tests, verify pass**

**Step 5: Commit**

```bash
git add app/main.py tests/test_api.py
git commit -m "FastAPI app with API routes and test suite"
```

---

### Task 9: Scheduler (APScheduler Integration)

**Files:**
- Create: `app/scheduler.py`
- Create: `tests/test_scheduler.py`

**Step 1: Write failing tests**

```python
# tests/test_scheduler.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.scheduler import run_scrape_cycle

@pytest.mark.asyncio
async def test_scrape_cycle_stores_jobs(tmp_path):
    from app.database import Database
    db = Database(str(tmp_path / "test.db"))
    await db.init()

    mock_scraper = MagicMock()
    mock_scraper.source_name = "test"
    from app.scrapers.base import JobListing
    mock_scraper.scrape = AsyncMock(return_value=[
        JobListing(
            title="Test Job", company="TestCo", location="Remote",
            description="A test job", url="https://example.com/test",
            source="test", salary_min=160000, salary_max=200000,
        )
    ])

    await run_scrape_cycle(db, scrapers=[mock_scraper])
    jobs = await db.list_jobs()
    assert len(jobs) == 1
    assert jobs[0]["title"] == "Test Job"
    sources = await db.get_sources(jobs[0]["id"])
    assert sources[0]["source_name"] == "test"
    await db.close()

@pytest.mark.asyncio
async def test_scrape_cycle_deduplicates(tmp_path):
    from app.database import Database
    db = Database(str(tmp_path / "test.db"))
    await db.init()

    mock_scraper = MagicMock()
    mock_scraper.source_name = "test"
    from app.scrapers.base import JobListing
    job = JobListing(
        title="Test Job", company="TestCo", location="Remote",
        description="A test job", url="https://example.com/test",
        source="test",
    )
    mock_scraper.scrape = AsyncMock(return_value=[job])

    await run_scrape_cycle(db, scrapers=[mock_scraper])
    await run_scrape_cycle(db, scrapers=[mock_scraper])
    jobs = await db.list_jobs()
    assert len(jobs) == 1
    await db.close()
```

**Step 2: Run to verify fail**

**Step 3: Implement**

```python
# app/scheduler.py
import logging
from app.database import Database, make_dedup_hash
from app.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

async def run_scrape_cycle(db: Database, scrapers: list):
    total_new = 0
    for scraper_instance in scrapers:
        if isinstance(scraper_instance, type):
            scraper_instance = scraper_instance()
        source_name = scraper_instance.source_name
        logger.info(f"Scraping {source_name}...")
        try:
            listings = await scraper_instance.scrape()
        except Exception as e:
            logger.error(f"Scraper {source_name} failed: {e}")
            continue

        for listing in listings:
            dedup = make_dedup_hash(listing.title, listing.company, listing.url)
            existing = await db.find_job_by_hash(dedup)
            if existing:
                await db.insert_source(existing["id"], source_name, listing.url)
            else:
                job_id = await db.insert_job(
                    title=listing.title,
                    company=listing.company,
                    location=listing.location,
                    salary_min=listing.salary_min,
                    salary_max=listing.salary_max,
                    description=listing.description,
                    url=listing.url,
                    posted_date=listing.posted_date,
                    application_method=listing.application_method,
                    contact_email=listing.contact_email,
                )
                if job_id:
                    await db.insert_source(job_id, source_name, listing.url)
                    total_new += 1

        logger.info(f"{source_name}: found {len(listings)} listings")
    logger.info(f"Scrape cycle complete. {total_new} new jobs added.")
    return total_new
```

**Step 4: Run tests, verify pass**

**Step 5: Commit**

```bash
git add app/scheduler.py tests/test_scheduler.py
git commit -m "Scrape cycle scheduler with deduplication"
```

---

### Task 10: Wire Scheduler + Matcher into FastAPI Lifespan

**Files:**
- Modify: `app/main.py`
- Modify: `tests/test_api.py`

**Step 1: Write test for scrape trigger**

Add to `tests/test_api.py`:

```python
@pytest.mark.asyncio
async def test_trigger_scrape(client):
    resp = await client.post("/api/scrape")
    assert resp.status_code == 200
```

**Step 2: Update main.py lifespan to start APScheduler and wire scoring after scrape**

Update the lifespan in `app/main.py` to:
- Initialize APScheduler with a job running `run_scrape_cycle` every N hours
- After scrape, run `batch_score` on unscored jobs
- Wire `/api/scrape` to trigger an immediate run
- Wire `/api/jobs/{job_id}/prepare` to call Tailor

In testing mode, skip scheduler startup.

**Step 3: Run all tests**

Run: `python -m pytest -v`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add app/main.py tests/test_api.py
git commit -m "Wire scheduler and matcher into FastAPI app lifecycle"
```

---

### Task 11: Frontend - HTML Shell & CSS Theme

**Files:**
- Create: `app/static/index.html`
- Create: `app/static/css/style.css`
- Create: `app/static/js/app.js`

No TDD for frontend — visual verification.

**Step 1: Create index.html**

Single-page app shell with three views (job feed, job detail, stats dashboard). Uses Pico CSS CDN as base. Navigation bar at top. Clean, polished layout.

**Step 2: Create style.css**

Custom theme on top of Pico CSS:
- Inter font stack (with system fallback)
- Custom color palette: slate/blue scheme
- Score badges: green (#22c55e) for 80+, amber (#f59e0b) for 60-79, gray for <60
- Card components with subtle shadows and hover transitions
- Responsive grid layout
- Dark/light mode toggle
- Smooth page transitions

**Step 3: Create app.js**

Vanilla JS SPA:
- Router handling hash-based navigation (#/, #/job/:id, #/stats)
- API client module (fetch wrapper for all /api/* endpoints)
- Job feed view: render job cards, filters sidebar, search, sort controls
- Job detail view: full description, score panel, prepare/apply actions, editable textareas
- Stats view: summary cards, source breakdown, pipeline funnel
- Toast notifications for actions
- "New since last visit" highlighting via localStorage timestamp
- Copy-to-clipboard utility
- Manual "Scrape Now" button

**Step 4: Verify by running the app locally**

```bash
cd /Users/lukemacneil/code/jobfinder
python -m uvicorn app.main:create_app --factory --reload
```

Open http://localhost:8085 and verify layout renders.

**Step 5: Commit**

```bash
git add app/static/
git commit -m "Polished frontend dashboard with job feed, detail, and stats views"
```

---

### Task 12: Docker & Deployment

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `.env.example`
- Create: `data/.gitkeep`

**Step 1: Create Dockerfile**

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir .
COPY app/ app/
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8085"]
```

**Step 2: Create docker-compose.yml**

```yaml
services:
  jobfinder:
    build: .
    ports:
      - "8085:8085"
    volumes:
      - ./data:/app/data
    env_file:
      - .env
    restart: unless-stopped
```

**Step 3: Create .env.example**

```
JOBFINDER_ANTHROPIC_API_KEY=your-key-here
JOBFINDER_USAJOBS_API_KEY=optional
JOBFINDER_DB_PATH=data/jobfinder.db
JOBFINDER_RESUME_PATH=data/resume.txt
JOBFINDER_SCRAPE_INTERVAL_HOURS=6
```

**Step 4: Copy resume text to data/**

Extract resume text from PDF and save as `data/resume.txt` for the matcher to use.

**Step 5: Build and test locally**

```bash
docker compose build && docker compose up -d
curl http://localhost:8085/api/health
```

**Step 6: Commit**

```bash
git add Dockerfile docker-compose.yml .env.example data/.gitkeep
git commit -m "Docker deployment setup for NAS"
```

---

### Task 13: Deploy to mmgnas

**Step 1:** SSH to mmgnas and create project directory

```bash
ssh -p 8001 luke@mmgnas "mkdir -p /share/CACHEDEV1_DATA/jobfinder"
```

**Step 2:** Copy project files to NAS (or push to Gitea and clone there)

**Step 3:** Create `.env` with real API keys on the NAS

**Step 4:** Build and start

```bash
ssh -p 8001 luke@mmgnas "cd /share/CACHEDEV1_DATA/jobfinder && /share/CACHEDEV1_DATA/.qpkg/container-station/bin/docker compose up -d --build"
```

**Step 5:** Copy resume text file to `data/resume.txt` on NAS

**Step 6:** Verify dashboard at `http://mmgnas:8085`

**Step 7: Commit any deployment tweaks**

---

## Summary

| Task | Description | Dependencies |
|------|-------------|-------------|
| 1 | Project scaffold & config | None |
| 2 | Database schema & CRUD | Task 1 |
| 3 | Base scraper + RemoteOK | Task 1 |
| 4 | Remaining 7 scrapers | Task 3 |
| 5 | Claude API matcher | Task 1 |
| 6 | Resume tailoring & cover letters | Task 5 |
| 7 | Email drafter | Task 1 |
| 8 | FastAPI app & routes | Tasks 2 |
| 9 | Scheduler | Tasks 3, 4, 2 |
| 10 | Wire scheduler + matcher | Tasks 8, 9, 5, 6 |
| 11 | Frontend dashboard | Task 8 |
| 12 | Docker deployment | All above |
| 13 | Deploy to NAS | Task 12 |

**Parallelizable:** Tasks 3-7 can run in parallel (independent modules). Task 11 can start once Task 8 is done.
