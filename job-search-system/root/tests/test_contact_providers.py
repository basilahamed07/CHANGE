"""M7: Company + contact research tests.

Key guarantees: provider fallback (a failing provider never breaks research),
deterministic classification/confidence, cache hits (no re-research), dedup on
select, and provider contract conformance (find() never raises).
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.company_enrichment import (
    COMPANY_CACHE_TTL_DAYS,
    company_cache_fresh,
    extract_ai_clues,
    extract_links,
)
from app.contact_providers import (
    ROLE_HIRING_MANAGER,
    ROLE_OTHER,
    ROLE_RECRUITER,
    ROLE_REFERRER,
    ContactCandidate,
    ContactResearchService,
    HunterProvider,
    ManualResearchProvider,
    WebSearchProvider,
    classify_role,
    default_provider_chain,
    rank_candidates,
    score_confidence,
)


def _job(**kw) -> dict:
    base = dict(id=1, title="Senior AI Engineer", company="Acme AI",
                location="Remote", description="Build LLM products.")
    base.update(kw)
    return base


# ---------------- classification taxonomy (deterministic) ----------------

@pytest.mark.parametrize("title,expected", [
    ("Technical Recruiter", ROLE_RECRUITER),
    ("Talent Acquisition Partner", ROLE_RECRUITER),
    ("Engineering Manager", ROLE_HIRING_MANAGER),
    ("Head of AI", ROLE_HIRING_MANAGER),
    ("VP Engineering", ROLE_HIRING_MANAGER),
    ("Senior Software Engineer", ROLE_REFERRER),
    ("Data Scientist", ROLE_REFERRER),
    ("Accountant", ROLE_OTHER),
    ("", ROLE_OTHER),
])
def test_classify_role_taxonomy(title, expected):
    assert classify_role(title) == expected


# ---------------- confidence scoring ----------------

def test_confidence_prefers_recruiter_with_personal_email():
    good = ContactCandidate(name="Jane Doe", email="jane.doe@acme.com",
                            title="Technical Recruiter", provider="hunter")
    bad = ContactCandidate(name="", email="jobs@acme.com",
                           title="Some Role", provider="web_search")
    s_good = score_confidence(good, "AI Engineer")
    s_bad = score_confidence(bad, "AI Engineer")
    assert s_good > s_bad
    assert 0 <= s_good <= 100 and 0 <= s_bad <= 100


def test_confidence_title_overlap_boost():
    c = ContactCandidate(name="Jane", email="jane@x.com",
                         title="AI Engineer Hiring", provider="hunter")
    with_overlap = score_confidence(c, "AI Engineer")
    without = score_confidence(
        ContactCandidate(name="Jane", email="jane@x.com", title="Sales",
                         provider="hunter"), "AI Engineer")
    assert with_overlap > without


def test_confidence_no_email_penalized():
    no_email = score_confidence(
        ContactCandidate(name="Jane", title="Recruiter", provider="hunter"),
        "AI Engineer")
    with_email = score_confidence(
        ContactCandidate(name="Jane", email="jane@x.com",
                         title="Recruiter", provider="hunter"), "AI Engineer")
    assert no_email < with_email


def test_confidence_deterministic():
    c = ContactCandidate(name="Jane Doe", email="jane@acme.com",
                         title="Recruiter", provider="hunter")
    assert score_confidence(c, "AI Engineer") == score_confidence(c, "AI Engineer")


# ---------------- ranking ----------------

def test_rank_candidates_sorts_by_confidence():
    cands = [
        ContactCandidate(name="A", email="a@x.com", title="Accountant",
                         provider="web_search"),
        ContactCandidate(name="B", email="b.doe@x.com",
                         title="Talent Acquisition", provider="hunter"),
    ]
    ranked = rank_candidates(cands, "AI Engineer")
    assert ranked[0].name == "B"
    assert ranked[0].role_type == ROLE_RECRUITER
    assert ranked[0].why_selected  # rationale filled


# ---------------- provider contract: never raises ----------------

@pytest.mark.asyncio
async def test_provider_failure_returns_empty_not_raise():
    class Boom(HunterProvider):
        async def _find(self, job):
            raise RuntimeError("api exploded")

    boom = Boom(api_key="k")
    assert await boom.find(_job()) == []  # contract: swallowed


@pytest.mark.asyncio
async def test_hunter_unavailable_without_key():
    provider = HunterProvider(api_key="")
    assert provider.available is False
    assert await provider.find(_job()) == []


@pytest.mark.asyncio
async def test_hunter_parses_domain_search(respx_mock):
    import respx
    respx.get("https://api.hunter.io/v2/domain-search").respond(json={
        "data": {"domain": "acme.com", "emails": [
            {"value": "jane@acme.com", "first_name": "Jane",
             "last_name": "Doe", "position": "Technical Recruiter"},
            {"value": "bob@acme.com", "first_name": "Bob",
             "last_name": "Smith", "position": "Engineering Manager"},
        ]}})
    provider = HunterProvider(api_key="test-key")
    found = await provider.find(_job())
    assert len(found) == 2
    assert found[0].email == "jane@acme.com"
    assert found[0].provider == "hunter"


@pytest.mark.asyncio
async def test_manual_provider_surfaces_basils_saved_contacts(tmp_path):
    from app.database import Database
    db = Database(str(tmp_path / "t.db"))
    await db.init()
    await db.create_contact(name="Jane Doe", email="jane@acme.ai",
                            company="Acme AI", role="Technical Recruiter")
    await db.create_contact(name="Bob", email="bob@other.com",
                            company="Other Co", role="Engineer")
    provider = ManualResearchProvider(db)
    found = await provider.find(_job())
    assert len(found) == 1  # only Acme AI contacts
    assert found[0].email == "jane@acme.ai"
    await db.close()


# ---------------- research service: fallback + cache ----------------

class _FakeProvider:
    def __init__(self, name, results=None, available=True):
        self.name = name
        self.results = results or []
        self.available = available
        self.calls = 0

    async def find(self, job):
        self.calls += 1
        if isinstance(self.results, Exception):
            raise self.results
        return list(self.results)


@pytest.mark.asyncio
async def test_research_falls_through_empty_providers(tmp_path):
    from app.database import Database
    db = Database(str(tmp_path / "t.db"))
    await db.init()
    empty = _FakeProvider("empty", [])
    good = _FakeProvider("good", [ContactCandidate(
        name="Jane", email="jane@acme.ai", title="Recruiter", provider="good")])
    service = ContactResearchService(db, [empty, good])
    result = await service.research(_job())
    assert result["provider"] == "good"
    assert result["status"] == "found"
    assert result["candidates"][0]["confidence"] > 0
    await db.close()


@pytest.mark.asyncio
async def test_research_cache_hit_skips_providers(tmp_path):
    from app.database import Database
    db = Database(str(tmp_path / "t.db"))
    await db.init()
    provider = _FakeProvider("p", [ContactCandidate(
        name="Jane", email="jane@acme.ai", title="Recruiter", provider="p")])
    service = ContactResearchService(db, [provider])
    first = await service.research(_job())
    assert first["cache_hit"] is False
    second = await service.research(_job())
    assert second["cache_hit"] is True
    assert provider.calls == 1  # no re-research within TTL
    forced = await service.research(_job(), force=True)
    assert forced["cache_hit"] is False
    assert provider.calls == 2
    await db.close()


@pytest.mark.asyncio
async def test_research_not_found_persists_status(tmp_path):
    from app.database import Database
    db = Database(str(tmp_path / "t.db"))
    await db.init()
    service = ContactResearchService(db, [_FakeProvider("p", [])])
    result = await service.research(_job())
    assert result["status"] == "not_found"
    row = await db.get_contact_research(1)
    assert row["status"] == "not_found"
    await db.close()


@pytest.mark.asyncio
async def test_select_candidate_writes_job_and_dedupes_contacts(tmp_path):
    from app.database import Database
    db = Database(str(tmp_path / "t.db"))
    await db.init()
    jid = await db.insert_job(
        title="AI Engineer", company="Acme AI", location="Remote",
        salary_min=None, salary_max=None, description="d", url="https://x/1",
        posted_date="2026-09-20", application_method="direct", contact_email=None)
    job = await db.get_job(jid)
    provider = _FakeProvider("p", [ContactCandidate(
        name="Jane Doe", email="jane@acme.ai", title="Technical Recruiter",
        company="Acme AI", provider="p")])
    service = ContactResearchService(db, [provider])
    await service.research(job)
    sel = await service.select_candidate(job, 0)
    got = await db.get_job(jid)
    assert got["hiring_manager_email"] == "jane@acme.ai"
    # selecting the same person twice must NOT create a duplicate contact
    await service.select_candidate(job, 0)
    contacts = await db.get_contacts()
    assert sum(1 for c in contacts if c["email"] == "jane@acme.ai") == 1
    assert sel["candidate"]["role_type"] == ROLE_RECRUITER
    await db.close()


@pytest.mark.asyncio
async def test_select_candidate_rejects_bad_index(tmp_path):
    from app.database import Database
    db = Database(str(tmp_path / "t.db"))
    await db.init()
    service = ContactResearchService(db, [_FakeProvider("p", [])])
    with pytest.raises(ValueError):
        await service.select_candidate(_job(), 0)
    await db.close()


def test_default_chain_manual_first_web_last(tmp_path):
    chain = default_provider_chain(object(), web=True)
    assert chain[0].name == "manual"
    assert chain[-1].name == "web_search"


# ---------------- company enrichment ----------------

def test_extract_ai_clues_deterministic():
    text = "We build LLM products with RAG and Computer Vision. LLM again."
    clues = extract_ai_clues(text)
    assert "llm" in clues and "rag" in clues
    assert len(clues) == len(set(clues))


def test_extract_links_finds_careers_and_linkedin():
    html = ('<a href="https://acme.com/careers">Jobs</a> '
            '<a href="https://www.linkedin.com/company/acme-ai">LI</a>')
    links = extract_links(html, "acme")
    assert links["careers_url"] == "https://acme.com/careers"
    assert "linkedin.com/company/acme-ai" in links["linkedin_url"]


def test_extract_links_no_false_positives():
    links = extract_links("<p>no links here</p>", "acme")
    assert links == {"careers_url": "", "linkedin_url": ""}


def test_company_cache_ttl():
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    fresh = {"researched_at": now.isoformat()}
    stale = {"researched_at": (now - timedelta(days=COMPANY_CACHE_TTL_DAYS + 1)).isoformat()}
    garbage = {"researched_at": "not-a-date"}
    assert company_cache_fresh(fresh) is True
    assert company_cache_fresh(stale) is False
    assert company_cache_fresh(garbage) is False


# ---------------- DB persistence ----------------

@pytest.mark.asyncio
async def test_contact_research_db_roundtrip(tmp_path):
    from app.database import Database
    db = Database(str(tmp_path / "t.db"))
    await db.init()
    await db.save_contact_research(7, "Acme", "found", "hunter",
                                   [{"name": "Jane", "confidence": 88}])
    row = await db.get_contact_research(7)
    assert row["company"] == "Acme"
    assert row["candidates"][0]["confidence"] == 88
    # upsert overwrites
    await db.save_contact_research(7, "Acme", "not_found", "none", [])
    row = await db.get_contact_research(7)
    assert row["status"] == "not_found"
    await db.close()
