"""Tests for the second batch of coverage-expansion scrapers (2026-09-23).

Ashby (ATS boards + structured salary), Landing.jobs (EU tech board) and
4dayweek.io (remote / 4-day-week board). Payloads mirror the real API shapes
captured live on 2026-09-23.
"""
import re

import pytest
from app.scrapers.ashby import AshbyScraper
from app.scrapers.base import JobListing
from app.scrapers.fourdayweek import FourDayWeekScraper, _annual_salary
from app.scrapers.landingjobs import LandingJobsScraper, _company_from

# ---------------------------------------------------------------------- Ashby

ASHBY_PAYLOAD = {
    "apiVersion": "1",
    "jobs": [
        {
            "id": "8fb1",
            "title": "Senior Backend Engineer",
            "department": "Engineering",
            "team": "Platform",
            "employmentType": "FullTime",
            "location": "Berlin",
            "isRemote": False,
            "publishedAt": "2026-09-01T10:00:00.000+00:00",
            "jobUrl": "https://jobs.ashbyhq.com/acme/abc-123",
            "descriptionPlain": "Build Python services on Kubernetes.",
            "compensation": {
                "compensationTiers": [
                    {
                        "components": [
                            {
                                "compensationType": "Salary",
                                "interval": "1 YEAR",
                                "minValue": 90000,
                                "maxValue": 120000,
                            },
                            {"compensationType": "EquityCashValue", "minValue": None, "maxValue": None},
                        ]
                    }
                ]
            },
        },
        {
            "id": "def4",
            "title": "Office Manager",
            "location": "Munich",
            "jobUrl": "https://jobs.ashbyhq.com/acme/def-456",
            "descriptionPlain": "Coordinate the Munich office.",
        },
        {
            "id": "ghi7",
            "title": "Backend Developer (Remote)",
            "isRemote": True,
            "location": "",
            "jobUrl": "https://jobs.ashbyhq.com/acme/ghi-789",
            "descriptionPlain": "Fully distributed team.",
        },
    ],
}

ASHBY_ONE = {"scraper_keys": {"ashby_companies": "acme"}}


@pytest.mark.asyncio
async def test_ashby_parse_with_salary(httpx_mock):
    httpx_mock.add_response(url=re.compile(r"https://api\.ashbyhq\.com/posting-api/job-board/acme"), json=ASHBY_PAYLOAD)
    jobs = await AshbyScraper(**ASHBY_ONE).scrape()
    assert len(jobs) == 3
    assert isinstance(jobs[0], JobListing)
    assert jobs[0].source == "ashby"
    assert jobs[0].company == "acme"
    assert jobs[0].salary_min == 90000
    assert jobs[0].salary_max == 120000
    assert jobs[0].posted_date == "2026-09-01"
    assert "Engineering" in jobs[0].tags
    # isRemote with an empty location must still resolve to a usable location
    assert "Remote" in jobs[2].location


@pytest.mark.asyncio
async def test_ashby_search_filter(httpx_mock):
    httpx_mock.add_response(url=re.compile(r"https://api\.ashbyhq\.com/posting-api/job-board/acme"), json=ASHBY_PAYLOAD)
    # "backend engineer" needs BOTH words, so the plain "Backend Developer" is
    # correctly filtered out and only the exact-title job survives.
    jobs = await AshbyScraper(search_terms=["backend engineer"], **ASHBY_ONE).scrape()
    assert len(jobs) == 1
    assert "Backend Engineer" in jobs[0].title


@pytest.mark.asyncio
async def test_ashby_single_word_term_is_title_only(httpx_mock):
    httpx_mock.add_response(url=re.compile(r"https://api\.ashbyhq\.com/posting-api/job-board/acme"), json=ASHBY_PAYLOAD)
    jobs = await AshbyScraper(search_terms=["backend"], **ASHBY_ONE).scrape()
    assert len(jobs) == 2


@pytest.mark.asyncio
async def test_ashby_unknown_board_is_skipped(httpx_mock):
    """A 404 board must be skipped, not abort the whole run."""
    httpx_mock.add_response(
        url=re.compile(r"https://api\.ashbyhq\.com/posting-api/job-board/missing"), status_code=404)
    assert await AshbyScraper(scraper_keys={"ashby_companies": "missing"}).scrape() == []


@pytest.mark.asyncio
async def test_ashby_handles_bad_json(httpx_mock):
    httpx_mock.add_response(
        url=re.compile(r"https://api\.ashbyhq\.com/posting-api/job-board/acme"),
        text="<html>oops</html>")
    assert await AshbyScraper(**ASHBY_ONE).scrape() == []


def test_ashby_salary_ignores_non_annual_and_equity():
    from app.scrapers.ashby import _annual_salary

    assert _annual_salary({"compensationTiers": [{"components": [
        {"compensationType": "Salary", "interval": "1 HOUR", "minValue": 50, "maxValue": 60},
    ]}]}) == (None, None)
    assert _annual_salary(None) == (None, None)
    assert _annual_salary({"compensationTiers": []}) == (None, None)


# --------------------------------------------------------------- Landing.jobs

LANDINGJOBS_PAYLOAD = [
    {
        "id": 1,
        "title": "Senior AI Engineer",
        "url": "https://landing.jobs/at/ki-performance/senior-ai-engineer-2025",
        "locations": [{"city": "Munich", "country_code": "DE"}, {"city": "Lisbon", "country_code": "PT"}],
        "remote": False,
        "role_description": "<div>Build LLM systems.</div>",
        "main_requirements": "Python, PyTorch",
        "nice_to_have": "Rust",
        "tags": ["python", "llm"],
        "gross_salary_low": 50000,
        "gross_salary_high": 65000,
        "published_at": "2026-09-01T09:38:38.127Z",
        "type": "Full-time",
    },
    {
        "id": 2,
        "title": "Brand Marketing Manager",
        "url": "https://landing.jobs/at/brandco/brand-marketing-manager-2025",
        "locations": [],
        "remote": True,
        "role_description": "Own paid acquisition.",
        "tags": [],
        "published_at": "2026-08-01T00:00:00Z",
    },
]


@pytest.mark.asyncio
async def test_landingjobs_parse(httpx_mock):
    httpx_mock.add_response(url=re.compile(r"https://landing\.jobs/api/v1/jobs"), json=LANDINGJOBS_PAYLOAD)
    jobs = await LandingJobsScraper().scrape()
    assert len(jobs) == 2
    assert isinstance(jobs[0], JobListing)
    assert jobs[0].source == "landingjobs"
    # No company field in the API — it must be recovered from the URL path
    assert jobs[0].company == "Ki Performance"
    assert "Munich, DE" in jobs[0].location
    assert jobs[0].salary_min == 50000
    assert jobs[0].posted_date == "2026-09-01"
    # Empty locations + remote=True falls back to a Remote label
    assert jobs[1].location == "Remote"


@pytest.mark.asyncio
async def test_landingjobs_search_filter(httpx_mock):
    httpx_mock.add_response(url=re.compile(r"https://landing\.jobs/api/v1/jobs"), json=LANDINGJOBS_PAYLOAD)
    jobs = await LandingJobsScraper(search_terms=["ai engineer"]).scrape()
    assert len(jobs) == 1
    assert jobs[0].title == "Senior AI Engineer"


@pytest.mark.httpx_mock(can_send_already_matched_responses=True)
@pytest.mark.asyncio
async def test_landingjobs_handles_http_error(httpx_mock):
    """502 is retryable, so the scraper retries then degrades to an empty list."""
    httpx_mock.add_response(url=re.compile(r"https://landing\.jobs/api/v1/jobs"), status_code=502)
    assert await LandingJobsScraper().scrape() == []


def test_landingjobs_company_from_url():
    assert _company_from({}, "https://landing.jobs/at/ki-performance/senior-ai-engineer-2025") == "Ki Performance"
    assert _company_from({}, "https://landing.jobs/jobs/123") == ""
    assert _company_from({"company": "Explicit Co"}, "https://landing.jobs/jobs/1") == "Explicit Co"


# ------------------------------------------------------------------ 4dayweek

FOURDAYWEEK_PAYLOAD = {
    "total": 3,
    "page": 1,
    "has_more": False,
    "jobs": [
        {
            "id": "01a0",
            "title": "Staff AI Engineer",
            "slug": "staff-ai-engineer-at-capital-one-abc",
            "company_name": "Capital One",
            "work_arrangement": "remote",
            "locations": [{"country": "United States", "continent": "North America", "is_primary": True}],
            "posted": 1790137782,
            "inserted": "2026-09-23T04:29:42.400039Z",
            "schedule_type": "4_day_week",
            "salary": "$70k - $87k",
            "salary_lower": 7000000,
            "salary_upper": 8700000,
            "salary_currency": "USD",
            "salary_period": "year",
            "category": "engineering",
            "level": "senior",
            "is_expired": False,
        },
        {
            "id": "exp",
            "title": "Expired AI Role",
            "slug": "expired-ai-role",
            "company_name": "Ghost Co",
            "is_expired": True,
            "locations": [],
        },
    ],
}


@pytest.mark.asyncio
async def test_fourdayweek_parse(httpx_mock):
    httpx_mock.add_response(url=re.compile(r"https://4dayweek\.io/api/jobs"), json=FOURDAYWEEK_PAYLOAD)
    jobs = await FourDayWeekScraper().scrape()
    assert len(jobs) == 1  # expired listing dropped
    assert isinstance(jobs[0], JobListing)
    assert jobs[0].source == "4dayweek"
    assert jobs[0].company == "Capital One"
    assert jobs[0].url == "https://4dayweek.io/job/staff-ai-engineer-at-capital-one-abc"
    assert "United States" in jobs[0].location
    # cents/year -> annual dollars
    assert jobs[0].salary_min == 70000
    assert jobs[0].salary_max == 87000
    assert jobs[0].posted_date is not None


@pytest.mark.asyncio
async def test_fourdayweek_search_filter(httpx_mock):
    httpx_mock.add_response(url=re.compile(r"https://4dayweek\.io/api/jobs"), json=FOURDAYWEEK_PAYLOAD)
    jobs = await FourDayWeekScraper(search_terms=["ai engineer"]).scrape()
    assert len(jobs) == 1
    assert "AI Engineer" in jobs[0].title


@pytest.mark.asyncio
async def test_fourdayweek_handles_bad_json(httpx_mock):
    httpx_mock.add_response(url=re.compile(r"https://4dayweek\.io/api/jobs"), text="not json")
    assert await FourDayWeekScraper().scrape() == []


@pytest.mark.parametrize(
    "payload,expected",
    [
        ({"salary_lower": 7000000, "salary_upper": 8700000, "salary_period": "year"}, (70000, 87000)),
        ({"salary_lower": 5000, "salary_upper": 6000, "salary_period": "hour"}, (104000, 124800)),
        ({"salary_lower": 800000, "salary_upper": 900000, "salary_period": "month"}, (96000, 108000)),
        ({"salary_lower": 200000, "salary_upper": 250000, "salary_period": "week"}, (104000, 130000)),
        ({"salary_lower": 0, "salary_upper": 0}, (None, None)),
        ({}, (None, None)),
    ],
)
def test_fourdayweek_salary_conversion(payload, expected):
    assert _annual_salary(payload) == expected


# ------------------------------------------------------------- registration

def test_all_new_sources_are_registered():
    """Guard against the WeWorkRemotely bug (implemented but never registered)."""
    from app.scrapers import ALL_SCRAPERS

    names = {s.source_name for s in ALL_SCRAPERS}
    for required in ("ashby", "landingjobs", "4dayweek", "weworkremotely",
                     "workingnomads", "recruitee", "mycareersfuture"):
        assert required in names, f"{required} is not registered in ALL_SCRAPERS"
