"""Phase 4 — role-targeted discovery: per-source query capability,
country/term pairing, per-pass caps, reject counts, and the report endpoint.

All tests are DETERMINISTIC: stub adapters, tmp DBs, no network (the live
coverage is the separate analysis/ sweep + reports).
"""

from __future__ import annotations

import pytest

from app import source_registry as sr
from app.discovery import (
    DEFAULT_ROLE_TERMS,
    MAX_RESULTS_PER_PASS,
    QUERYABLE_SOURCES,
    role_terms_from_config,
    run_discovery_cycle,
)
from app.routers.discovery import _query_overrides

ROLE_TITLES = ["AI Engineer", "LLM Engineer"]


# ---------------------------------------------------------------------------
# Query capability
# ---------------------------------------------------------------------------


def test_queryable_sources_are_real_and_registered():
    """Every queryable name must be an actual adapter + a registry entry."""
    from app.adapters import ALL_ADAPTERS
    adapter_names = {cls.source_name for cls in ALL_ADAPTERS}
    assert QUERYABLE_SOURCES <= adapter_names
    assert QUERYABLE_SOURCES <= set(sr.SOURCES)
    assert "jooble" in QUERYABLE_SOURCES
    assert "greenhouse" not in QUERYABLE_SOURCES  # whole-feed ATS board


def test_role_terms_normalizes_strings_dicts_and_blanks():
    cfg = {"job_titles": ["  AI Engineer ", {"title": "LLM Engineer", "why": "x"},
                          "", None, "AI Engineer", 42]}
    assert role_terms_from_config(cfg) == ["AI Engineer", "LLM Engineer"]
    assert role_terms_from_config({}) == []
    assert role_terms_from_config(None) == []


def test_query_overrides_targets_queryable_sources_with_roles():
    cfg = {"job_titles": ROLE_TITLES, "search_terms": ["devops"]}
    plan = _query_overrides(cfg)

    assert plan["jooble"] == {"queries": ROLE_TITLES, "queryless": False}
    assert plan["reed"] == {"queries": ROLE_TITLES, "queryless": False}
    assert plan["greenhouse"] == {"queries": [], "queryless": True}
    assert plan["remotive"] == {"queries": [], "queryless": True}
    # Fallbacks: board search terms first, then the product defaults.
    assert _query_overrides({"search_terms": ["sre"]})["jooble"]["queries"] == ["sre"]
    assert _query_overrides({})["jooble"]["queries"] == DEFAULT_ROLE_TERMS


# ---------------------------------------------------------------------------
# Country/term pairing (the over-fetch fix)
# ---------------------------------------------------------------------------


class _ListStub:
    """Adapter stub that returns a fixed list of CanonicalJobs."""
    source_name = "himalayas"
    specs: list[tuple] = []
    calls: list[tuple] = []

    def __init__(self, search_terms=None, scraper_keys=None):
        self.search_terms = list(search_terms or [])

    async def search(self, role_terms, country=None):
        from app.job_adapter import AdapterResult, CanonicalJob
        type(self).calls.append((getattr(country, "code", None), list(role_terms)))
        jobs = []
        for i, (title, location) in enumerate(type(self).specs):
            jobs.append(CanonicalJob(
                title=title, company="ProvCo", location=location,
                description="Build RAG systems with Python and LangGraph.",
                url=f"https://stub/{type(self).source_name}/{i}",
                source=self.source_name, posted_date="2026-09-25"))
        return AdapterResult(source=self.source_name, listings=jobs,
                             stop_reason="NO_MORE_RESULTS")

    async def health_check(self):
        return {"source": self.source_name, "ok": True}


@pytest.fixture
def germany_only():
    """A one-country registry (Germany) — real YAMLs untouched."""
    from app.country_registry import CountryRegistry
    registry = CountryRegistry("config/countries").load()

    class _Reg:
        def enabled_countries(self):
            return [registry.get("Germany")]

    return _Reg()


async def _db_with_config(tmp_path, job_titles=None, search_terms=None):
    from app.database import Database
    db = Database(str(tmp_path / "t.db"))
    await db.init()
    await db.update_allowed_regions(["Germany", "Remote"])
    if job_titles is not None or search_terms is not None:
        await db.save_search_config("resume", search_terms or [],
                                    job_titles=job_titles or [])
    return db


@pytest.mark.asyncio
async def test_queryable_runs_per_role_and_queryless_once(tmp_path, germany_only):
    db = await _db_with_config(tmp_path, job_titles=ROLE_TITLES,
                               search_terms=["devops"])

    class QuerylessStub(_ListStub):
        source_name = "himalayas"    # queryless, once per country
        specs = []
        calls = []

    class QueryableStub(_ListStub):
        source_name = "jooble"       # queryable, once per role term
        specs = []
        calls = []

    try:
        await run_discovery_cycle(db, germany_only,
                                  [QuerylessStub, QueryableStub],
                                  max_passes=50, scraper_keys={})
    finally:
        await db.close()

    # The whole feed is fetched exactly once, with ALL role terms for local use.
    assert len(QuerylessStub.calls) == 1
    assert QuerylessStub.calls[0][1] == ROLE_TITLES

    # The queryable source is asked once per role — role-targeted, no cross
    # product with generic search terms.
    assert [term for (_c, terms) in QueryableStub.calls for term in terms] == ROLE_TITLES


@pytest.mark.asyncio
async def test_pass_plan_is_logged_and_bounded(tmp_path, germany_only):
    db = await _db_with_config(tmp_path, job_titles=ROLE_TITLES)

    class QuerylessStub(_ListStub):
        source_name = "himalayas"
        specs = []
        calls = []

    class QueryableStub(_ListStub):
        source_name = "jooble"
        specs = []
        calls = []

    try:
        telemetry = await run_discovery_cycle(
            db, germany_only, [QuerylessStub, QueryableStub],
            max_passes=1, scraper_keys={})
    finally:
        await db.close()

    # 1 queryless + 2 queryable = plan of 3; budget 1 truncates it honestly.
    assert telemetry["planned_passes"] == 3
    assert telemetry["pass_budget"] == 1
    assert telemetry["budget_exhausted"] is True
    assert len(telemetry["passes"]) == 1


# ---------------------------------------------------------------------------
# Reject counts + per-pass cap
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reject_counts_record_role_and_region_gate(tmp_path, germany_only):
    db = await _db_with_config(tmp_path, job_titles=["AI Engineer"])

    class Noise(_ListStub):
        source_name = "himalayas"    # queryless, global
        specs = [
            ("Graphic Designer", "Berlin, Germany"),   # role gate
            ("AI Engineer", "Tokyo, Japan"),           # region gate
            ("AI Engineer", "Berlin, Germany"),        # ingested
        ]
        calls = []

    try:
        telemetry = await run_discovery_cycle(db, germany_only, [Noise],
                                              max_passes=10, scraper_keys={})
    finally:
        await db.close()

    rejects = telemetry["reject_counts"]
    assert rejects["by_role_gate"] == 1
    assert rejects["by_region_gate"] == 1
    assert rejects["not_ingestible"] == 0
    assert rejects["total"] == 2

    pass_rec = next(p for p in telemetry["passes"] if p["source"] == "himalayas")
    assert pass_rec["rejected"] == {"not_ingestible": 0, "role_gate": 1, "region_gate": 1}
    assert pass_rec["ingested"] == 1


@pytest.mark.asyncio
async def test_per_pass_cap_truncates_and_reports(tmp_path, germany_only):
    db = await _db_with_config(tmp_path, job_titles=["AI Engineer"])
    over = MAX_RESULTS_PER_PASS + 25

    class Flood(_ListStub):
        source_name = "remotive"     # queryless, global
        specs = [(f"AI Engineer {i}", "Berlin, Germany") for i in range(over)]
        calls = []

    try:
        telemetry = await run_discovery_cycle(db, germany_only, [Flood],
                                              max_passes=10, scraper_keys={})
    finally:
        await db.close()

    pass_rec = next(p for p in telemetry["passes"] if p["source"] == "remotive")
    assert pass_rec["found"] == over
    assert pass_rec["truncated"] == 25
    assert pass_rec["ingested"] == MAX_RESULTS_PER_PASS
    assert telemetry["truncated"] == 25


# ---------------------------------------------------------------------------
# Report endpoint
# ---------------------------------------------------------------------------


async def test_report_endpoint_shape_without_a_run(client):
    resp = await client.get("/api/discovery/report")
    assert resp.status_code == 200
    data = resp.json()

    for key in ("generated_at", "has_run", "nature", "config", "per_source",
                "pass_budget", "planned_passes", "pass_count", "budget_exhausted",
                "cap", "reject_counts", "dedup", "db"):
        assert key in data, key

    assert data["has_run"] is False
    assert data["pass_count"] == 0
    assert data["cap"]["max_results_per_pass"] == MAX_RESULTS_PER_PASS
    assert data["per_source"]["jooble"]["queryless"] is False
    assert data["per_source"]["greenhouse"]["queryless"] is True
    assert data["nature"]["queryable_sources"] == sorted(QUERYABLE_SOURCES)
    # Every registry source is reported.
    assert set(data["per_source"]) == set(sr.SOURCES)


async def test_report_reflects_the_last_run(client, app):
    from app.run_state import ANON

    slot = app.state.run_registry.slot(ANON)
    slot["discovery_telemetry"] = {
        "pass_budget": 50,
        "planned_passes": 12,
        "budget_exhausted": False,
        "reject_counts": {"by_role_gate": 3, "by_region_gate": 1,
                          "not_ingestible": 2, "duplicates": 4, "total": 6},
        "passes": [
            {"source": "jooble", "term": "AI Engineer", "found": 10,
             "ingested": 2, "duplicates": 4, "truncated": 0,
             "health_status": "PASS", "error": ""},
            {"source": "greenhouse", "term": None, "found": 5,
             "ingested": 1, "duplicates": 0, "truncated": 0,
             "health_status": "PASS", "error": ""},
        ],
    }

    resp = await client.get("/api/discovery/report")
    assert resp.status_code == 200
    data = resp.json()

    assert data["has_run"] is True
    assert data["pass_count"] == 2
    assert data["planned_passes"] == 12
    assert data["pass_budget"] == 50
    assert data["reject_counts"]["total"] == 6
    assert data["per_source"]["jooble"]["passes"] == 1
    assert data["per_source"]["jooble"]["ingested"] == 2
    assert data["per_source"]["greenhouse"]["passes"] == 1
    assert data["dedup"]["total"] == 4
    assert data["dedup"]["by_source"] == {"jooble": 4}
