"""Discovery expansion tests: new country-scoped + keyed adapters.

Key guarantees:
  1. Every new adapter honors the JobSourceAdapter contract: search() NEVER
     raises, returns AdapterResult with honest stop-reasons.
  2. Country scoping: listings outside the target country are DROPPED.
  3. Keyed adapters (jooble/adzuna) are honest no-ops without keys —
     SOURCE_FAILURE with a clear error, never a crash.
  4. All 15 adapters registered; keyed ones present even without keys.
  5. Legacy scrapers still work unchanged (base.py method param is
     backward-compatible).

External HTTP is mocked with respx (same discipline as test_adapters.py).
"""

from pathlib import Path

import httpx
import pytest
import respx

from app.adapters import ALL_ADAPTERS
from app.adapters.country_facade import CountryScopedAdapter, in_country
from app.country_registry import CountryRegistry
from app.job_adapter import STOP_SOURCE_FAILURE

SEEDS = Path(__file__).resolve().parents[1] / "config" / "countries"

SOURCE_NAMES = {cls.source_name for cls in ALL_ADAPTERS}


def _canada():
    return CountryRegistry(SEEDS).load().get("Canada")


def _germany():
    return CountryRegistry(SEEDS).load().get("Germany")


# ---------------- registry / registration ----------------

def test_adapters_registered_count():
    # Stage-1 upgrade 2026-09-30: 19 → 20 — the audit found builtin.py's
    # scraper existed since M1 but was never wired into discovery; the
    # BuiltinAdapter closes that gap (CA/US tech-city coverage).
    assert len(ALL_ADAPTERS) == 20
    assert {"greenhouse", "lever", "ashby", "smartrecruiters",
            "jooble", "adzuna", "reed", "arbeitnow", "remotive", "jobicy",
            "weworkremotely", "remoteok", "himalayas", "4dayweek",
            "landingjobs", "recruitee", "mycareersfuture", "wellfound",
            "builtin",
            "workingnomads"} == SOURCE_NAMES


# ---------------- shared facade ----------------

def test_in_country_matches_region_name_alias_and_city():
    ca = _canada()
    assert in_country("Toronto, ON, Canada", ca)
    assert in_country("Remote — Vancouver", ca)
    assert in_country("canadian startup, remote", ca)  # alias
    assert not in_country("New York, NY, USA", ca)
    assert not in_country("Sao Paulo, Brazil", ca)


def test_facade_drops_out_of_country_and_never_raises():
    class StubScraper:
        def __init__(self, search_terms=None, scraper_keys=None):
            self.search_terms = list(search_terms or [])

        async def scrape(self):
            from app.scrapers.base import JobListing
            return [
                JobListing(title="AI Engineer", company="Good Co",
                           location="Toronto, Canada", description="",
                           url="https://x.co/1", source="stub"),
                JobListing(title="AI Engineer", company="Bad Co",
                           location="New York, USA", description="",
                           url="https://x.co/2", source="stub"),
            ]

    class StubAdapter(CountryScopedAdapter):
        source_name = "stub"
        scraper_cls = StubScraper

    import asyncio
    result = asyncio.run(StubAdapter().search(["ai"], country=_canada()))
    assert result.ok
    assert len(result.listings) == 1
    assert result.listings[0].company == "Good Co"
    assert result.listings[0].source == "stub"


def test_region_hint_skips_other_countries_honestly():
    """Single-country sources (mycareersfuture→SG, reed→UK) must not waste a
    scrape pass on other countries — honest empty result instead."""
    import asyncio
    sg = CountryRegistry(SEEDS).load().get("Singapore")
    from app.adapters.country_scoped import MyCareersFutureAdapter
    result = asyncio.run(MyCareersFutureAdapter().search(["x"], country=_canada()))
    assert result.stop_reason != STOP_SOURCE_FAILURE   # honest skip, not failure
    assert result.listings == []
    assert "Singapore only" in result.error


@respx.mock
def test_reed_uk_happy_path_and_honest_no_key():
    from app.adapters.reed import ReedAdapter

    # Without a key: honest no-op
    import asyncio
    no_key = asyncio.run(ReedAdapter().search(["ai"], country=_germany()))
    # Germany gets the region-hint skip BEFORE the key check:
    assert no_key.listings == [] and "UK only" in no_key.error

    uk = CountryRegistry(SEEDS).load().get("UK")
    no_key_uk = asyncio.run(ReedAdapter().search(["ai"], country=uk))
    assert no_key_uk.stop_reason == STOP_SOURCE_FAILURE
    assert "key" in no_key_uk.error.lower()

    # With a key: live-shaped happy path
    route = respx.get("https://www.reed.co.uk/api/1.0/search").mock(
        return_value=httpx.Response(200, json={"results": [
            {"jobId": 1, "employerName": "Revolut", "jobTitle": "AI Engineer",
             "locationName": "London", "minimumSalary": 70000,
             "maximumSalary": 95000, "currency": "GBP",
             "date": "2026-09-27", "jobUrl": "https://www.reed.co.uk/jobs/1",
             "jobDescription": "llm"},
            {"jobId": 2, "employerName": "Leak Co", "jobTitle": "AI Engineer",
             "locationName": "New York", "jobUrl": "https://www.reed.co.uk/jobs/2",
             "jobDescription": "nope"},
        ], "totalResults": 2}))
    adapter = ReedAdapter(scraper_keys={"reed": {"api_key": "k"}})
    result = asyncio.run(adapter.search(["AI Engineer"], country=uk))
    assert route.called
    assert result.ok
    assert len(result.listings) == 1                    # NY leak dropped
    assert result.listings[0].company == "Revolut"
    assert result.listings[0].salary_currency == "GBP"


def test_facade_crash_becomes_source_failure():
    class BoomScraper:
        def __init__(self, search_terms=None, scraper_keys=None):
            self.search_terms = []

        async def scrape(self):
            raise RuntimeError("boom")

    class BoomAdapter(CountryScopedAdapter):
        source_name = "boom"
        scraper_cls = BoomScraper

    import asyncio
    result = asyncio.run(BoomAdapter().search(["x"], country=None))
    assert result.stop_reason == STOP_SOURCE_FAILURE
    assert "boom" in result.error


# ---------------- keyed adapters: honest no-op without keys ----------------

def test_jooble_without_key_is_source_failure_with_clear_error():
    import asyncio
    result = asyncio.run(
        __import__("app.adapters.jooble", fromlist=["JoobleAdapter"])
        .JoobleAdapter().search(["ai"], country=_canada()))
    assert result.stop_reason == STOP_SOURCE_FAILURE
    assert "key" in result.error.lower()
    assert result.listings == []


def test_adzuna_without_keys_is_source_failure_with_clear_error():
    import asyncio
    result = asyncio.run(
        __import__("app.adapters.adzuna", fromlist=["AdzunaAdapter"])
        .AdzunaAdapter().search(["ai"], country=_germany()))
    assert result.stop_reason == STOP_SOURCE_FAILURE
    assert "key" in result.error.lower()


def test_jooble_health_without_key_reports_not_ok():
    import asyncio
    health = asyncio.run(
        __import__("app.adapters.jooble", fromlist=["JoobleAdapter"])
        .JoobleAdapter().health_check())
    assert health["ok"] is False
    assert "key" in health["error"].lower()


# ---------------- keyed adapters: happy paths (mocked) ----------------

@respx.mock
def test_jooble_search_ca_happy_path():
    from app.adapters.jooble import JoobleAdapter

    route = respx.post("https://api.jooble.org/api/test-key").mock(
        return_value=httpx.Response(200, json={
            "jobs": [
                {"title": "Senior AI Engineer", "company": "Shopify",
                 "location": "Toronto, Canada", "snippet": "LLM work",
                 "link": "https://jooble.org/x/1", "id": "1",
                 "updated": "2026-09-27"},
                {"title": "ML Engineer", "company": "TD Bank",
                 "location": "Vancouver, Canada", "snippet": "torch",
                 "link": "https://jooble.org/x/2", "id": "2"},
                # cross-border leak that must be dropped:
                {"title": "AI Engineer", "company": "Leak Co",
                 "location": "New York, USA", "snippet": "nope",
                 "link": "https://jooble.org/x/3", "id": "3"},
            ],
            "totalCount": 3,
        }))

    adapter = JoobleAdapter(scraper_keys={"jooble": {"api_key": "test-key"}})
    import asyncio
    result = asyncio.run(adapter.search(["AI Engineer"], country=_canada()))
    assert route.called
    assert result.ok
    assert len(result.listings) == 2          # NY leak dropped
    assert {j.company for j in result.listings} == {"Shopify", "TD Bank"}
    assert all(j.source == "jooble" for j in result.listings)


@respx.mock
def test_adzuna_search_uses_country_market_code():
    from app.adapters.adzuna import AdzunaAdapter

    route = respx.get(url__startswith="https://api.adzuna.com/v1/api/jobs/in/search/").mock(
        return_value=httpx.Response(200, json={"results": [
            {"title": "AI Engineer", "company": {"display_name": "TCS"},
             "location": {"display_name": "Bengaluru, Karnataka, India"},
             "redirect_url": "https://adzuna.in/x/1",
             "description": "genai role", "created": "2026-09-26",
             "salary_min": 1800000, "salary_max": 3000000},
        ]}))

    adapter = AdzunaAdapter(scraper_keys={
        "adzuna": {"api_key": "k"}, "adzuna-id": {"api_key": "id"}})
    india = CountryRegistry(SEEDS).load().get("India")
    import asyncio
    result = asyncio.run(adapter.search(["AI Engineer"], country=india))
    assert route.called
    assert result.ok
    assert len(result.listings) == 1
    assert result.listings[0].company == "TCS"
    assert result.listings[0].salary_min == 1800000


@respx.mock
def test_adzuna_unknown_market_is_honest_skip():
    from app.adapters.adzuna import AdzunaAdapter

    adapter = AdzunaAdapter(scraper_keys={
        "adzuna": {"api_key": "k"}, "adzuna-id": {"api_key": "id"}})
    # Country whose region has no Adzuna market:
    country = type("C", (), {"region": "Atlantis", "name": "Atlantis",
                             "aliases": [], "cities": []})()
    import asyncio
    result = asyncio.run(adapter.search(["x"], country=country))
    assert result.stop_reason == "NO_MORE_RESULTS"
    assert result.listings == []


# ---------------- country-scoped adapters over real scrapers (mocked) ----------------

@respx.mock
def test_arbeitnow_adapter_scopes_to_germany():
    from app.adapters.country_scoped import ArbeitnowAdapter

    respx.get("https://www.arbeitnow.com/api/job-board-api").mock(
        return_value=httpx.Response(200, json={"data": [
            {"title": "Senior AI Engineer", "company_name": "Berlin GmbH",
             "location": "Berlin, Germany", "description": "pytorch",
             "url": "https://arbeitnow.com/1", "tags": ["python"],
             "slug": "a"},
            {"title": "Nurse", "company_name": "Clinic",
             "location": "Toronto, Canada", "description": "care",
             "url": "https://arbeitnow.com/2", "tags": [], "slug": "b"},
        ]}))

    adapter = ArbeitnowAdapter(search_terms=["AI"])
    import asyncio
    result = asyncio.run(adapter.search(["AI Engineer"], country=_germany()))
    assert result.ok
    assert len(result.listings) == 1           # Canada listing dropped
    assert result.listings[0].company == "Berlin GmbH"


@respx.mock
def test_remotive_adapter_scopes_to_canada():
    from app.adapters.country_scoped import RemotiveAdapter

    respx.get("https://remotive.com/api/remote-jobs").mock(
        return_value=httpx.Response(200, json={"jobs": [
            {"title": "ML Engineer", "company_name": "Co A",
             "candidate_required_location": "Canada",
             "description": "x", "url": "https://remotive.com/1",
             "publication_date": "2026-09-25"},
            {"title": "ML Engineer", "company_name": "Co B",
             "candidate_required_location": "USA Only",
             "description": "x", "url": "https://remotive.com/2",
             "publication_date": "2026-09-25"},
        ]}))

    adapter = RemotiveAdapter(search_terms=["ML"])
    import asyncio
    result = asyncio.run(adapter.search(["ML Engineer"], country=_canada()))
    assert result.ok
    assert len(result.listings) == 1
    assert result.listings[0].company == "Co A"


@respx.mock
def test_recruitee_adapter_scopes_to_netherlands():
    from app.adapters.country_scoped import RecruiteeAdapter

    respx.get("https://bunq.recruitee.com/api/offers/").mock(
        return_value=httpx.Response(200, json={"offers": [
            {"title": "AI Engineer", "company_name": "bunq",
             "city": "Amsterdam", "country": "Netherlands",
             "careers_url": "https://bunq.recruitee.com/o/x",
             "description": "fintech ai"},
        ]}))

    adapter = RecruiteeAdapter(search_terms=["AI"],
                               scraper_keys={"recruitee_companies": ["bunq"]})
    nl = CountryRegistry(SEEDS).load().get("Netherlands")
    import asyncio
    result = asyncio.run(adapter.search(["AI Engineer"], country=nl))
    assert result.ok
    assert len(result.listings) == 1
    assert result.listings[0].location == "Amsterdam, Netherlands"


# ---------------- legacy scraper backward compatibility ----------------

def test_rate_limited_get_still_gets_by_default():
    """The base.py method= extension must not change default GET behavior."""
    from app.scrapers.base import BaseScraper

    s = BaseScraper()
    assert hasattr(s, "rate_limited_get")
    import inspect
    sig = inspect.signature(s.rate_limited_get)
    assert "method" not in sig.parameters  # kwargs passthrough, not a param
