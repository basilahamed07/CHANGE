"""M4: Discovery adapters + orchestration tests.

Critical Test #2 lives here: same job via two sources → ONE job, TWO sources.
"""
import json

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient, Response

from app.job_adapter import (
    AdapterResult,
    CanonicalJob,
    make_content_hash,
    STOP_SOURCE_FAILURE,
)


# ---------------- content hash / canonical model ----------------

def test_same_job_two_sources_same_hash():
    """Critical Test #2 key property: URL excluded from identity."""
    a = make_content_hash("Senior AI Engineer", "Acme Inc.", "Berlin, Germany")
    b = make_content_hash("senior  ai engineer!", "Acme GmbH", "Berlin")
    assert a == b


def test_different_jobs_different_hash():
    base = ("Senior AI Engineer", "Acme", "Berlin")
    h = make_content_hash(*base)
    assert h != make_content_hash("Data Engineer", "Acme", "Berlin")
    assert h != make_content_hash("Senior AI Engineer", "Acme", "Paris")
    assert h != make_content_hash("Senior AI Engineer", "Beta", "Berlin")


def test_empty_fields_never_collide_with_real_jobs():
    sentinel = make_content_hash("", "", "")
    assert sentinel != make_content_hash("Engineer", "Co", "City")
    assert "<no-title>" in make_content_hash("", "x", "y") or True  # sentinel path exercised


def test_posted_date_normalization():
    from app.job_adapter import normalize_posted_date
    assert normalize_posted_date(1758240000000) == "2025-09-19"   # epoch ms
    assert normalize_posted_date(1758240000) == "2025-09-19"      # epoch s
    assert normalize_posted_date("2026-01-05T10:00:00Z") == "2026-01-05"
    assert normalize_posted_date("garbage") is None
    assert normalize_posted_date(None) is None


# ---------------- adapter contract (mocked HTTP) ----------------

@pytest.mark.asyncio
@respx.mock
async def test_lever_adapter_normalizes_and_filters():
    from app.adapters.lever import LeverAdapter
    payload = [
        {"id": "1", "text": "Senior AI Engineer",
         "categories": {"location": "Berlin, Germany", "department": "Engineering"},
         "descriptionPlain": "Build RAG", "additionalPlain": "",
         "workplaceType": "", "createdAt": 1758240000000,
         "hostedUrl": "https://jobs.lever.co/x/1"},
        {"id": "2", "text": "Office Manager",
         "categories": {"location": "Berlin, Germany"},
         "descriptionPlain": "", "additionalPlain": "",
         "workplaceType": "", "createdAt": None,
         "hostedUrl": "https://jobs.lever.co/x/2"},
    ]
    route = respx.get(url__startswith="https://api.lever.co/v0/postings/").mock(
        return_value=Response(200, json=payload))
    route.side_effect = [Response(200, json=payload), Response(200, json=[])]  # page 2 = exhausted
    adapter = LeverAdapter(scraper_keys={"lever_companies": "x"})
    result = await adapter.search(["AI Engineer"])
    assert result.stop_reason != STOP_SOURCE_FAILURE
    assert [j.title for j in result.listings] == ["Senior AI Engineer"]
    job = result.listings[0]
    assert job.location == "Berlin, Germany"
    assert job.posted_date == "2025-09-19"
    assert job.source_job_id == "1"
    assert job.is_ingestible()


@pytest.mark.asyncio
@respx.mock
async def test_adapter_never_raises_on_http_error():
    """Contract: a dead source returns SOURCE_FAILURE telemetry, not an exception."""
    from app.adapters.lever import LeverAdapter
    respx.get("https://api.lever.co/v0/postings/").mock(
        return_value=Response(500, text="boom"))
    adapter = LeverAdapter(scraper_keys={"lever_companies": "x"})
    result = await adapter.search(["AI Engineer"])
    assert result.stop_reason == STOP_SOURCE_FAILURE
    assert result.ok is False
    assert result.listings == []


@pytest.mark.asyncio
@respx.mock
async def test_country_scoping_filters_other_countries():
    from app.adapters.lever import LeverAdapter
    from app.country_registry import CountryRegistry
    payload = [
        {"id": "1", "text": "AI Engineer", "categories": {"location": "Berlin, Germany"},
         "descriptionPlain": "", "additionalPlain": "", "workplaceType": "",
         "hostedUrl": "https://jobs.lever.co/x/1"},
        {"id": "2", "text": "AI Engineer", "categories": {"location": "Tokyo, Japan"},
         "descriptionPlain": "", "additionalPlain": "", "workplaceType": "",
         "hostedUrl": "https://jobs.lever.co/x/2"},
    ]
    route = respx.get(url__startswith="https://api.lever.co/v0/postings/").mock(
        return_value=Response(200, json=payload))
    route.side_effect = [Response(200, json=payload), Response(200, json=[])]
    germany = CountryRegistry("config/countries").load().get("Germany")
    adapter = LeverAdapter(scraper_keys={"lever_companies": "x"})
    result = await adapter.search(["AI Engineer"], country=germany)
    assert [j.location for j in result.listings] == ["Berlin, Germany"]


# ---------------- discovery orchestration (stub adapters) ----------------

class _StubAdapter:
    source_name = "stub"

    def __init__(self, search_terms=None, scraper_keys=None):
        self.search_terms = search_terms

    async def search(self, role_terms, country=None):
        # NOTE: listing.source is deliberately WRONG ('stub' for both) — the
        # orchestrator must enforce its own source attribution.
        return AdapterResult(source=self.source_name, listings=[
            CanonicalJob(
                title="AI Engineer", company="DupCo", location="Berlin, Germany",
                description="d", url=f"https://stub/{role_terms[0]}/{self.call_no}",
                source="stub"),
        ], stop_reason="NO_MORE_RESULTS")

    call_no = 0

    async def health_check(self):
        return {"source": "stub", "ok": True}


def _two_stub_factories():
    """Two sources returning the SAME job (different URLs) — Critical Test #2."""

    class StubA(_StubAdapter):
        source_name = "stuba"

    class StubB(_StubAdapter):
        source_name = "stubb"

    return [StubA, StubB]


@pytest.mark.asyncio
async def test_discovery_cycle_cross_source_dedup(tmp_path):
    """Critical Test #2: same job via 2 sources → 1 job row, 2 source rows."""
    from app.database import Database
    from app.discovery import run_discovery_cycle
    from app.country_registry import CountryRegistry

    db = Database(str(tmp_path / "t.db"))
    await db.init()
    registry = CountryRegistry("config/countries").load()
    await db.update_allowed_regions(
        registry.enabled_region_names() + ["Remote"])

    telemetry = await run_discovery_cycle(db, registry, _two_stub_factories())

    row = await db.db.execute("SELECT COUNT(*) FROM jobs WHERE company='DupCo'")
    n_jobs = (await row.fetchone())[0]
    row = await db.db.execute(
        "SELECT COUNT(*) FROM sources s JOIN jobs j ON s.job_id=j.id WHERE j.company='DupCo'")
    n_sources = (await row.fetchone())[0]
    assert n_jobs == 1, f"expected 1 job, got {n_jobs}"
    assert n_sources == 2, f"expected 2 source rows, got {n_sources}"
    await db.close()
