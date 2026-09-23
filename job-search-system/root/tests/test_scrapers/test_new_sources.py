"""Tests for the coverage-expansion scrapers added 2026-09-23.

Working Nomads (keyless JSON), Recruitee (EU ATS boards), MyCareersFuture
(Singapore government board), plus a regression test that WeWorkRemotely is
actually registered (it was implemented but orphaned for months).
"""
import re

import pytest
from app.scrapers.base import JobListing
from app.scrapers.mycareersfuture import MyCareersFutureScraper
from app.scrapers.recruitee import RecruiteeScraper
from app.scrapers.workingnomads import WorkingNomadsScraper

# ------------------------------------------------------------ Working Nomads

WORKINGNOMADS_PAYLOAD = [
    {
        "url": "https://www.workingnomads.com/job/go/1885527/",
        "title": "Senior Back-end Engineer",
        "description": "<p>Build APIs with Python and Kubernetes.</p>",
        "company_name": "Lemon.io",
        "category_name": "Development",
        "tags": "back-end,golang,python,kubernetes",
        "location": "EU, US, Canada, UK",
        "pub_date": "2026-09-23T06:49:46-04:00",
    },
    {
        "url": "https://www.workingnomads.com/job/go/1878435/",
        "title": "Graphic Designer",
        "description": "<p>Posters and brochures with Figma.</p>",
        "company_name": "DesignCo",
        "category_name": "Design",
        "tags": "figma,photoshop",
        "location": "Worldwide",
        "pub_date": "2026-09-20T10:00:00-04:00",
    },
]


@pytest.mark.asyncio
async def test_workingnomads_parse(httpx_mock):
    httpx_mock.add_response(
        url=re.compile(r"https://www\.workingnomads\.com/api/exposed_jobs"), json=WORKINGNOMADS_PAYLOAD)
    jobs = await WorkingNomadsScraper().scrape()
    assert len(jobs) == 2
    assert isinstance(jobs[0], JobListing)
    assert jobs[0].source == "workingnomads"
    assert jobs[0].company == "Lemon.io"
    assert jobs[0].location == "EU, US, Canada, UK"
    assert "python" in jobs[0].tags
    assert jobs[0].posted_date == "2026-09-23T06:49:46-04:00"


@pytest.mark.asyncio
async def test_workingnomads_search_filter(httpx_mock):
    httpx_mock.add_response(
        url=re.compile(r"https://www\.workingnomads\.com/api/exposed_jobs"), json=WORKINGNOMADS_PAYLOAD)
    jobs = await WorkingNomadsScraper(search_terms=["backend engineer"]).scrape()
    assert len(jobs) == 1
    assert "Back-end" in jobs[0].title


@pytest.mark.asyncio
async def test_workingnomads_handles_bad_json(httpx_mock):
    """A non-JSON body must degrade to an empty result, not raise."""
    httpx_mock.add_response(
        url=re.compile(r"https://www\.workingnomads\.com/api/exposed_jobs"),
        text="<html>maintenance</html>")
    jobs = await WorkingNomadsScraper().scrape()
    assert jobs == []


@pytest.mark.httpx_mock(can_send_already_matched_responses=True)
@pytest.mark.asyncio
async def test_workingnomads_handles_http_error(httpx_mock):
    httpx_mock.add_response(
        url=re.compile(r"https://www\.workingnomads\.com/api/exposed_jobs"), status_code=503)
    assert await WorkingNomadsScraper().scrape() == []


# ---------------------------------------------------------------- Recruitee

RECRUITEE_PAYLOAD = {
    "offers": [
        {
            "title": "Python Software Engineer - AI team",
            "company_name": "Channable",
            "city": "Utrecht",
            "state_name": "Utrecht",
            "country": "Netherlands",
            "careers_url": "https://jobs.channable.com/o/python-ai",
            "description": "<p>Work on ML pipelines with Python.</p>",
            "department": "Engineering",
            "tags": ["python", "ml"],
            "published_at": "2026-09-18 12:55:59 UTC",
            "remote": False,
        },
        {
            "title": "Customer Success Manager",
            "company_name": "Channable",
            "city": "Utrecht",
            "country": "Netherlands",
            "careers_url": "https://jobs.channable.com/o/csm",
            "description": "<p>Support customers.</p>",
            "department": "Sales",
            "tags": [],
            "remote": False,
        },
    ]
}


@pytest.mark.asyncio
async def test_recruitee_parse(httpx_mock):
    httpx_mock.add_response(
        url=re.compile(r"https://channable\.recruitee\.com/api/offers"), json=RECRUITEE_PAYLOAD)
    jobs = await RecruiteeScraper(scraper_keys={"recruitee_companies": "channable"}).scrape()
    assert len(jobs) == 2
    assert jobs[0].source == "recruitee"
    assert jobs[0].company == "Channable"
    assert jobs[0].location == "Utrecht, Utrecht, Netherlands"
    assert jobs[0].url == "https://jobs.channable.com/o/python-ai"
    assert "python" in jobs[0].tags


@pytest.mark.asyncio
async def test_recruitee_search_filter(httpx_mock):
    httpx_mock.add_response(
        url=re.compile(r"https://channable\.recruitee\.com/api/offers"), json=RECRUITEE_PAYLOAD)
    jobs = await RecruiteeScraper(
        search_terms=["python engineer"],
        scraper_keys={"recruitee_companies": "channable"}).scrape()
    assert len(jobs) == 1
    assert "Python" in jobs[0].title


@pytest.mark.asyncio
async def test_recruitee_404_board_is_skipped(httpx_mock):
    """Unknown boards 404 — the scraper must continue, not fail."""
    httpx_mock.add_response(
        url=re.compile(r"https://nope\.recruitee\.com/api/offers"), status_code=404)
    httpx_mock.add_response(
        url=re.compile(r"https://channable\.recruitee\.com/api/offers"), json=RECRUITEE_PAYLOAD)
    jobs = await RecruiteeScraper(
        scraper_keys={"recruitee_companies": ["nope", "channable"]}).scrape()
    assert len(jobs) == 2


@pytest.mark.asyncio
async def test_recruitee_falls_back_to_slug_url(httpx_mock):
    payload = {"offers": [{"title": "AI Engineer", "slug": "ai-engineer",
                           "description": "x", "remote": True}]}
    httpx_mock.add_response(
        url=re.compile(r"https://acme\.recruitee\.com/api/offers"), json=payload)
    jobs = await RecruiteeScraper(scraper_keys={"recruitee_companies": "acme"}).scrape()
    assert jobs[0].url == "https://acme.recruitee.com/o/ai-engineer"
    assert jobs[0].location == "Remote"


# ---------------------------------------------------------- MyCareersFuture

MCF_PAYLOAD = {
    "results": [
        {
            "uuid": "39eba041c1378ea9",
            "title": "AI Engineer",
            "description": "<p>Build RAG systems with Python.</p>",
            "postedCompany": {"name": "ACME PTE. LTD."},
            "address": {"overseasCountry": None, "street": "CECIL STREET"},
            "salary": {"minimum": 6500, "maximum": 9500,
                       "type": {"id": 4, "salaryType": "Monthly"}},
            "employmentTypes": [{"id": 7, "employmentType": "Permanent"}],
            "skills": [{"skill": "Python"}, {"skill": "Machine Learning"}],
            "metadata": {"newPostingDate": "2026-09-09"},
        },
        {
            "uuid": "aaaa1111",
            "title": "Retail Assistant",
            "description": "<p>Serve customers.</p>",
            "postedCompany": {"name": "SHOP PTE. LTD."},
            "address": {},
            "salary": {},
            "skills": [],
            "metadata": {"newPostingDate": "2026-09-01"},
        },
    ],
    "total": 2,
}


@pytest.mark.httpx_mock(can_send_already_matched_responses=True)
@pytest.mark.asyncio
async def test_mycareersfuture_parse_and_annualize_salary(httpx_mock):
    """No explicit terms → default terms drive the query, no local filtering."""
    httpx_mock.add_response(
        url=re.compile(r"https://api\.mycareersfuture\.gov\.sg/v2/jobs"), json=MCF_PAYLOAD)
    jobs = await MyCareersFutureScraper().scrape()
    # 6 default terms × 1 page each, deduped by uuid
    assert len(jobs) == 2
    ai = next(j for j in jobs if j.title == "AI Engineer")
    assert ai.source == "mycareersfuture"
    assert ai.company == "ACME PTE. LTD."
    assert ai.location == "Singapore"
    # Monthly SGD 6500-9500 → annual 78000-114000
    assert ai.salary_min == 78000
    assert ai.salary_max == 114000
    assert ai.url == "https://www.mycareersfuture.gov.sg/job/39eba041c1378ea9"
    assert ai.posted_date == "2026-09-09"
    assert "Python" in ai.tags


@pytest.mark.asyncio
async def test_mycareersfuture_search_filter(httpx_mock):
    httpx_mock.add_response(
        url=re.compile(r"https://api\.mycareersfuture\.gov\.sg/v2/jobs"), json=MCF_PAYLOAD)
    jobs = await MyCareersFutureScraper(search_terms=["ai engineer"]).scrape()
    assert len(jobs) == 1
    assert jobs[0].title == "AI Engineer"


@pytest.mark.httpx_mock(can_send_already_matched_responses=True)
@pytest.mark.asyncio
async def test_mycareersfuture_handles_error(httpx_mock):
    httpx_mock.add_response(
        url=re.compile(r"https://api\.mycareersfuture\.gov\.sg/v2/jobs"), status_code=500)
    assert await MyCareersFutureScraper(search_terms=["ai"]).scrape() == []


def test_mycareersfuture_salary_edge_cases():
    """Zero/None/missing salary must not produce bogus annual figures."""
    assert MyCareersFutureScraper._annual_salary(None) == (None, None)
    assert MyCareersFutureScraper._annual_salary({}) == (None, None)
    assert MyCareersFutureScraper._annual_salary({"minimum": 0, "maximum": 0}) == (None, None)
    assert MyCareersFutureScraper._annual_salary({"minimum": 5000}) == (60000, None)


# ------------------------------------------------- registration regression

def test_all_new_sources_registered():
    """New scrapers must actually be wired into ALL_SCRAPERS."""
    from app.scrapers import ALL_SCRAPERS
    from app.scrapers.mycareersfuture import MyCareersFutureScraper
    from app.scrapers.recruitee import RecruiteeScraper
    from app.scrapers.workingnomads import WorkingNomadsScraper
    from app.scrapers.weworkremotely import WeWorkRemotelyScraper

    registered = set(ALL_SCRAPERS)
    for cls in (WorkingNomadsScraper, RecruiteeScraper,
                MyCareersFutureScraper, WeWorkRemotelyScraper):
        assert cls in registered, f"{cls.__name__} is not in ALL_SCRAPERS"


def test_scraper_registry_has_unique_source_names():
    from app.scrapers import ALL_SCRAPERS
    names = [cls.source_name for cls in ALL_SCRAPERS]
    assert len(names) == len(set(names)), f"duplicate source_name in {names}"
