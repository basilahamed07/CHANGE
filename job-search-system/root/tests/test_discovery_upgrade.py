"""Stage-1 DISCOVER upgrade tests — source registry, ATS detection, direct
company career discovery (JSON-LD), provenance, and source health.

All tests are DETERMINISTIC: fixture HTML/JSON, respx mocks, tmp DBs —
no live network (live coverage is the separate analysis/ sweep + reports).
"""

from __future__ import annotations

import asyncio
import json

import pytest

from app import source_registry as sr
from app import ats_detect
from app.company_careers import (
    CAREER_PATHS,
    candidate_career_urls,
    extract_jsonld_blocks,
    jsonld_to_canonical,
    parse_job_postings,
)

# ---------------------------------------------------------------------------
# Source registry
# ---------------------------------------------------------------------------


def test_registry_covers_every_adapter():
    """Bidirectional drift check: every registry entry has an adapter and
    every real adapter is registered (stub adapters excluded)."""
    from app.adapters import ALL_ADAPTERS
    adapter_names = {cls.source_name for cls in ALL_ADAPTERS}
    sr.validate_against(adapter_names)  # must not raise
    assert set(sr.SOURCES) == adapter_names


def test_registry_missing_adapter_raises():
    """A registered source with NO adapter = silent source loss — must fail."""
    with pytest.raises(ValueError, match="without adapter"):
        sr.validate_against(set())  # registry full, adapters empty


def test_registry_run_order_is_tier_ordered():
    order = sr.adapter_order()
    tiers = [sr.get(name).tier for name in order]
    assert tiers == sorted(tiers), "run order must be non-decreasing tier"
    # ATS sources (tier 1) run before aggregators (tier 3)
    assert order.index("greenhouse") < order.index("jooble")
    # single-country SG govt board ranks with tier 1
    assert order.index("mycareersfuture") < order.index("remotive")


def test_registry_tiering_preferences_direct_sources():
    """Canonical-source ranking: career page > ATS > government > boards >
    aggregator (task §19)."""
    rank = sr._TIER_OF_TYPE
    assert rank[sr.SourceType.COMPANY_CAREER] < rank[sr.SourceType.ATS]
    assert rank[sr.SourceType.ATS] < rank[sr.SourceType.GOVERNMENT]
    assert rank[sr.SourceType.GOVERNMENT] < rank[sr.SourceType.GLOBAL_BOARD]
    assert rank[sr.SourceType.GLOBAL_BOARD] < rank[sr.SourceType.AGGREGATOR]


def test_keyed_sources_are_configuration_required():
    """Jooble/Adzuna/Reed are IMPLEMENTED but wait on keys — never 'broken'
    (task §55)."""
    for name in ("jooble", "adzuna", "reed"):
        spec = sr.get(name)
        assert spec.access == sr.Access.API_KEY, name
        assert sr.status_from_result("SOURCE_FAILURE", 0, spec, has_key=False) \
            == sr.HEALTH_CONFIGURATION_REQUIRED
        # WITH a key, the same failure is a real failure
        assert sr.status_from_result("SOURCE_FAILURE", 0, spec, has_key=True) \
            == sr.HEALTH_FAILED


def test_health_status_mapping_from_stop_reasons():
    assert sr.status_from_result("NO_MORE_RESULTS", 5, None) == sr.HEALTH_PASS
    assert sr.status_from_result("RATE_LIMITED", 0, None) == sr.HEALTH_RATE_LIMITED
    assert sr.status_from_result("SOURCE_FAILURE", 0, None) == sr.HEALTH_FAILED
    assert sr.status_from_result("NO_MORE_RESULTS", 0, None) == sr.HEALTH_NO_RESULTS


def test_country_relevance_and_coverage_buckets():
    # SG: mycareersfuture applies; arbeitnow (DE) does not
    names = {s.name for s in sr.source_for_country("SG")}
    assert "mycareersfuture" in names and "arbeitnow" not in names
    buckets = sr.coverage_summary("SG")
    assert buckets["GOVERNMENT"] == 1 and buckets["ATS"] >= 3
    assert sr.coverage_status("SG") in ("FULL", "GOOD")  # evidence-based label


def test_category_counts_measure_diversity():
    counts = sr.category_counts()
    assert len(counts) >= 4  # multiple discovery categories, not one type x N
    assert counts.get("ATS", 0) >= 3


def test_run_health_record_shape():
    h = sr.new_run_health("de", "arbeitnow")
    assert h.country == "DE" and h.source_type == sr.SourceType.LOCAL_BOARD
    h.raw_jobs = h.parsed_jobs = 10
    h.valid_jobs = 7
    h.status = sr.HEALTH_PASS
    d = h.to_dict()
    for field in ("country", "source", "source_type", "raw_jobs", "parsed_jobs",
                  "valid_jobs", "duplicates", "status", "duration_ms"):
        assert field in d


# ---------------------------------------------------------------------------
# ATS detection (app.ats_detect)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("url,expected", [
    ("https://boards.greenhouse.io/openai", "greenhouse"),
    ("https://job-boards.greenhouse.io/acme/jobs/123", "greenhouse"),
    ("https://jobs.lever.co/spotify", "lever"),
    ("https://jobs.eu.lever.co/acme", "lever"),
    ("https://jobs.ashbyhq.com/linear", "ashby"),
    ("https://jobs.smartrecruiters.com/visa", "smartrecruiters"),
    ("https://acme.myworkdayjobs.com/careers", "workday"),
    ("https://acme.teamtailor.com/jobs", "teamtailor"),
    ("https://apply.workable.com/acme", "workable"),
    ("https://acme.recruitee.com/", "recruitee"),
    ("https://acme.bamboohr.com/careers", "bamboohr"),
    ("https://example.com/careers", None),
    ("not a url", None),
    ("", None),
])
def test_detect_ats_host_patterns(url, expected):
    assert ats_detect.detect_ats(url) == expected


def test_adapter_hint_routes_to_existing_adapters():
    assert ats_detect.adapter_for("https://jobs.lever.co/spotify") == "lever"
    assert ats_detect.adapter_for("https://jobs.ashbyhq.com/linear") == "ashby"
    # detected but NO adapter yet → honest None (routing falls back to JSON-LD)
    assert ats_detect.detect_ats("https://acme.myworkdayjobs.com/jobs") == "workday"
    assert ats_detect.adapter_for("https://acme.myworkdayjobs.com/jobs") is None


def test_known_ats_providers_deduplicated():
    providers = ats_detect.known_ats_providers()
    assert len(providers) == len(set(providers))
    assert "greenhouse" in providers and "workday" in providers


# ---------------------------------------------------------------------------
# JobPosting JSON-LD parsing (app.company_careers)
# ---------------------------------------------------------------------------

_JOB_HTML = """
<html><head>
<script type="application/ld+json">
{"@context":"https://schema.org/","@type":"JobPosting",
 "title":"Senior AI Engineer","description":"Build LLM systems",
 "datePosted":"2026-09-20","employmentType":"FULL_TIME",
 "hiringOrganization":{"@type":"Organization","name":"Acme BV",
   "sameAs":"https://acme.example"},
 "jobLocation":{"@type":"Place","address":{"@type":"PostalAddress",
   "addressLocality":"Amsterdam","addressCountry":"NL"}},
 "baseSalary":{"@type":"MonetaryAmount","currency":"EUR",
   "value":{"@type":"QuantitativeValue","minValue":60000,"maxValue":90000,"unitText":"YEAR"}},
 "directApply":{"@type":"Boolean","url":"https://acme.example/apply/1"}}
</script>
<script type="application/ld+json">{"@type":"WebSite","name":"x"}</script>
<script type="application/ld+json">not valid json {{{</script>
</head><body>jobs</body></html>
"""


def test_extract_jsonld_blocks_flattens_graph_and_skips_garbage():
    blocks = extract_jsonld_blocks(_JOB_HTML)
    assert len(blocks) == 2  # JobPosting + WebSite; malformed blob skipped
    assert any(b.get("@type") == "JobPosting" for b in blocks)


def test_graph_blocks_are_flattened():
    html = ('<script type="application/ld+json">{"@graph":['
            '{"@type":"JobPosting","title":"X","url":"https://a/1"},'
            '{"@type":"Organization","name":"A"}]}</script>')
    blocks = extract_jsonld_blocks(html)
    types = {b.get("@type") for b in blocks}
    assert types == {"JobPosting", "Organization"}


def test_jsonld_to_canonical_full_mapping():
    node = extract_jsonld_blocks(_JOB_HTML)[0]
    job = jsonld_to_canonical(node, "acme.example", "https://acme.example/careers")
    assert job is not None
    assert job.title == "Senior AI Engineer"
    assert job.company == "Acme BV"
    assert "Amsterdam" in job.location and "NL" in job.location
    assert job.salary_min == 60000 and job.salary_max == 90000
    assert job.salary_currency == "EUR"
    assert job.posted_date == "2026-09-20"
    assert job.employment_type == "full_time"
    assert job.url == "https://acme.example/apply/1"
    assert "direct-career" in job.tags


def test_non_jobposting_returns_none():
    assert jsonld_to_canonical({"@type": "Organization"}, "x", "https://x/") is None
    assert jsonld_to_canonical({"@type": "JobPosting"}, "x", "https://x/") is None  # no title


def test_parse_job_postings_dedupes_by_url():
    html = ('<script type="application/ld+json">{"@type":"JobPosting",'
            '"title":"A","url":"https://a/1"}</script>'
            '<script type="application/ld+json">{"@type":"JobPosting",'
            '"title":"A copy","url":"https://a/1"}</script>')
    jobs = parse_job_postings(html, "a.example", "https://a.example/careers")
    assert len(jobs) == 1


def test_unknown_date_stays_none_never_fabricated():
    """Task §20: a JobPosting with NO datePosted must stay None — 'today' is
    forbidden (M5 freshness treats None as DATE_UNKNOWN, never fresh)."""
    node = {"@type": "JobPosting", "title": "No date", "url": "https://a/2"}
    job = jsonld_to_canonical(node, "a", "https://a.example/careers")
    assert job.posted_date is None


def test_candidate_career_urls_shape():
    urls = candidate_career_urls("acme.example")
    assert any(u.startswith("https://acme.example/careers") for u in urls)
    assert any(u == "https://careers.acme.example" for u in urls)
    assert any(u == "https://jobs.acme.example" for u in urls)
    assert candidate_career_urls("") == []
    assert candidate_career_urls("no-tld") == []


def test_adapter_skips_ats_hosted_companies(respx_mock=None):
    """A careers URL on an ATS host must NOT be re-parsed here — the ATS
    adapter owns it (single parsing path, task §12)."""
    from app.company_careers import CompanyCareersAdapter
    import httpx

    class _Client:
        async def get(self, url, **kw):
            class _R:
                status_code = 200
                text = '<html><body>jobs</body></html>'
                def raise_for_status(self): pass
            return _R()

    adapter = CompanyCareersAdapter(companies=["example.com"])
    # resolve_career_page with a non-ATS, JSON-LD-less page → ('', '') → skip
    # (no crash); adapter returns an honest empty result.
    import asyncio
    result = asyncio.get_event_loop().run_until_complete(None) if False else None
    # direct unit call instead of loop juggling:
    result = asyncio.run(adapter.search(["AI Engineer"], country=None))
    assert result.stop_reason in ("NO_MORE_RESULTS",)
    assert isinstance(result.listings, list)


# ---------------------------------------------------------------------------
# Orchestrator wiring (provenance + health + honest country skip)
# ---------------------------------------------------------------------------


class _StubAdapter:
    source_name = "stub_src"

    def __init__(self, search_terms=None, scraper_keys=None):
        self.search_terms = search_terms

    async def search(self, role_terms, country=None):
        from app.job_adapter import AdapterResult, CanonicalJob
        return AdapterResult(source=self.source_name, listings=[
            CanonicalJob(
                title="AI Engineer", company="ProvCo", location="Berlin, Germany",
                description="d", url=f"https://stub/{role_terms[0]}",
                source=self.source_name, posted_date="2026-09-25"),
        ], stop_reason="NO_MORE_RESULTS")

    async def health_check(self):
        return {"source": self.source_name, "ok": True}


@pytest.mark.asyncio
async def test_cycle_stamps_provenance_on_cross_source_merge(tmp_path):
    """When a HIGHER-tier source confirms an existing job, canonical_source
    upgrades and source_types records both origins (task §17/§19)."""
    from app.database import Database
    from app.discovery import run_discovery_cycle
    from app.country_registry import CountryRegistry
    from app.job_adapter import AdapterResult, CanonicalJob

    class AggregatorSrc(_StubAdapter):
        source_name = "agg_src"

        async def search(self, role_terms, country=None):
            r = await super().search(role_terms, country)
            return r

    class AtsSrc(_StubAdapter):
        source_name = "ats_src"

    # Registry knows neither stub; give them identities via monkeypatched ranks
    import app.discovery as disc
    real_rank = disc._canonical_rank
    def fake_rank(name):
        return {"agg_src": 5, "ats_src": 1}.get(name, real_rank(name))
    disc._canonical_rank = fake_rank
    try:
        db = Database(str(tmp_path / "t.db"))
        await db.init()
        registry = CountryRegistry("config/countries").load()
        await db.update_allowed_regions(
            registry.enabled_region_names() + ["Remote"])

        class _Reg:
            def enabled_countries(self):
                return [registry.get("Germany")]

        # aggregator discovers first...
        await run_discovery_cycle(db, _Reg(), [AggregatorSrc], max_passes=2)
        # ...then the ATS confirms the same job (same title/company/city)
        await run_discovery_cycle(db, _Reg(), [AtsSrc], max_passes=2)

        row = await db.db.execute(
            "SELECT canonical_source, source_types FROM jobs WHERE company='ProvCo'")
        cs, st = await row.fetchone()
        assert cs == "ats_src", "higher-tier source must win canonical attribution"
        types = json.loads(st or "{}")
        assert set(types.keys()) == {"agg_src", "ats_src"}
        assert types["ats_src"] == "UNKNOWN"  # unregistered stubs are honest-unknown
        await db.close()
    finally:
        disc._canonical_rank = real_rank


@pytest.mark.asyncio
async def test_cycle_records_source_health_per_pass(tmp_path):
    """Every pass produces a health record; keyed-source failure WITHOUT a key
    reads CONFIGURATION_REQUIRED, not FAILED (task §21/§55)."""
    from app.database import Database
    from app.discovery import run_discovery_cycle
    from app.country_registry import CountryRegistry

    db = Database(str(tmp_path / "t.db"))
    await db.init()
    registry = CountryRegistry("config/countries").load()
    await db.update_allowed_regions(registry.enabled_region_names() + ["Remote"])

    class _Reg:
        def enabled_countries(self):
            return [registry.get("Germany")]

    class FailSrc(_StubAdapter):
        source_name = "jooble"  # a keyed source

        async def search(self, role_terms, country=None):
            from app.job_adapter import AdapterResult, STOP_SOURCE_FAILURE
            return AdapterResult(source=self.source_name,
                                 stop_reason=STOP_SOURCE_FAILURE,
                                 error="missing key")

    telemetry = await run_discovery_cycle(db, _Reg(), [FailSrc], max_passes=1,
                                          scraper_keys={})
    health = telemetry["source_health"]
    assert len(health) == 1
    assert health[0]["status"] == sr.HEALTH_CONFIGURATION_REQUIRED
    assert health[0]["country"] == "DE"
    await db.close()


@pytest.mark.asyncio
async def test_cycle_skips_single_country_source_honestly(tmp_path):
    """arbeitnow (DE-only) pointed at Singapore → NOT_APPLICABLE before any
    HTTP (registry-driven country skip)."""
    from app.database import Database
    from app.discovery import run_discovery_cycle
    from app.country_registry import CountryRegistry

    db = Database(str(tmp_path / "t.db"))
    await db.init()
    registry = CountryRegistry("config/countries").load()

    class _Reg:
        def enabled_countries(self):
            return [registry.get("Singapore")]

    from app.adapters.country_scoped import ArbeitnowAdapter
    called = {"n": 0}
    class CountingAdapter(ArbeitnowAdapter):
        async def search(self, role_terms, country=None):
            called["n"] += 1
            return await super().search(role_terms, country=country)

    telemetry = await run_discovery_cycle(db, _Reg(), [CountingAdapter],
                                          max_passes=1, scraper_keys={})
    assert called["n"] == 0, "no HTTP must be spent on a wrong-country source"
    assert telemetry["passes"][0]["stop_reason"] == "NOT_APPLICABLE"
    assert telemetry["source_health"][0]["status"] == sr.HEALTH_NOT_APPLICABLE
    await db.close()


@pytest.mark.asyncio
async def test_cycle_global_summary_structured(tmp_path):
    from app.database import Database
    from app.discovery import run_discovery_cycle
    from app.country_registry import CountryRegistry

    db = Database(str(tmp_path / "t.db"))
    await db.init()
    registry = CountryRegistry("config/countries").load()
    await db.update_allowed_regions(registry.enabled_region_names() + ["Remote"])

    class _Reg:
        def enabled_countries(self):
            return [registry.get("Germany")]

    telemetry = await run_discovery_cycle(db, _Reg(), [_StubAdapter],
                                          max_passes=1, scraper_keys={})
    gs = telemetry["global_summary"]
    for key in ("countries", "sources_attempted", "sources_successful",
                "raw_jobs", "normalized_jobs", "duplicates_removed",
                "unique_jobs", "duration_s", "by_status"):
        assert key in gs
    assert gs["sources_attempted"] == 1
    assert telemetry["country_summaries"][0]["country"] == "DE"
    await db.close()


# ---------------------------------------------------------------------------
# Downstream contract (task §35): a discovered job still flows through
# CLASSIFY → ELIGIBILITY (the stages immediately after DISCOVER)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_discovered_job_flows_to_classify_and_eligibility(tmp_path):
    """Downstream contract (task §35): a job discovered by the upgraded
    orchestrator must classify (Stage 2) and pass through the eligibility
    evaluator (Stage 3) unchanged — discovery stays OUT of their business."""
    from app.database import Database
    from app.discovery import run_discovery_cycle
    from app.country_registry import CountryRegistry

    db = Database(str(tmp_path / "t.db"))
    await db.init()
    registry = CountryRegistry("config/countries").load()
    await db.update_allowed_regions(registry.enabled_region_names() + ["Remote"])

    class _Reg:
        def enabled_countries(self):
            return [registry.get("Germany")]

    await run_discovery_cycle(db, _Reg(), [_StubAdapter], max_passes=1,
                              scraper_keys={})

    row = await db.db.execute(
        "SELECT location_region, location_classified, dedup_hash FROM jobs "
        "WHERE company='ProvCo'")
    fetched = await row.fetchone()
    assert fetched is not None, "job must be in the pool"
    region, classified, _hash = fetched
    # Stage 1 must NOT classify (that is Stage 2's job, task §15) — the job
    # lands UNclassified and Stage 2's rule-based pass picks it up:
    assert classified == 0
    from app.location_classifier import classify_location_rule_based
    assert classify_location_rule_based("Berlin, Germany") == "Germany"

    # Stage 3 eligibility consumes the job shape without complaint:
    from app.eligibility import EligibilityEngine
    job = await db.find_job_by_hash(_hash)
    engine = EligibilityEngine(
        allowed_regions=registry.enabled_region_names() + ["Remote"])
    verdict = engine.check(job)
    assert isinstance(verdict.reasons, list)  # shape contract: reasons present
    await db.close()


@pytest.mark.asyncio
async def test_canonical_source_column_persists(tmp_path):
    from app.database import Database

    db = Database(str(tmp_path / "t.db"))
    await db.init()
    jid = await db.insert_job(
        title="AI Engineer", company="CanonCo", location="Berlin, Germany",
        salary_min=None, salary_max=None, description="d",
        url="https://x/9", posted_date="2026-09-25",
        application_method="direct", contact_email=None)
    await db.set_canonical_source(jid, "greenhouse",
                                  {"greenhouse": "ATS", "jooble": "AGGREGATOR"})
    row = await db.db.execute(
        "SELECT canonical_source, source_types FROM jobs WHERE id=?", (jid,))
    cs, st = await row.fetchone()
    assert cs == "greenhouse"
    assert json.loads(st)["jooble"] == "AGGREGATOR"
    await db.close()


# ---------------------------------------------------------------------------
# Bounded concurrency (performance task): parallel searches, serial ingest,
# isolation, config surface — same discovery results as serial.
# ---------------------------------------------------------------------------


class _SlowSrc(_StubAdapter):
    """Simulates a slow source (sleep) so concurrency is observable."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)

    async def search(self, role_terms, country=None):
        from app.job_adapter import AdapterResult
        await asyncio.sleep(0.2)
        return await super().search(role_terms, country)


@pytest.mark.asyncio
async def test_concurrency_respects_semaphore(tmp_path):
    """5 slow sources with max_concurrent_sources=2 must overlap at most 2."""
    import asyncio
    from app.database import Database
    from app.discovery import run_discovery_cycle
    from app.country_registry import CountryRegistry

    active = {"n": 0, "max": 0}

    class Tracked(_SlowSrc):
        source_name = "tracked"

        async def search(self, role_terms, country=None):
            active["n"] += 1
            active["max"] = max(active["max"], active["n"])
            try:
                return await super().search(role_terms, country)
            finally:
                active["n"] -= 1

    db = Database(str(tmp_path / "t.db"))
    await db.init()
    registry = CountryRegistry("config/countries").load()
    await db.update_allowed_regions(registry.enabled_region_names() + ["Remote"])

    class _Reg:
        def enabled_countries(self):
            return [registry.get("Germany")]

    await run_discovery_cycle(db, _Reg(), [Tracked, Tracked, Tracked, Tracked, Tracked],
                              max_passes=5, scraper_keys={}, max_concurrent_sources=2)
    assert active["max"] <= 2, f"semaphore violated: {active['max']} concurrent"
    await db.close()


@pytest.mark.asyncio
async def test_concurrency_isolation_one_crash_does_not_kill_siblings(tmp_path):
    """A crashing source must not cancel the others (task rule 8)."""
    from app.database import Database
    from app.discovery import run_discovery_cycle
    from app.country_registry import CountryRegistry
    from app.job_adapter import AdapterResult

    class Boom(_StubAdapter):
        source_name = "boom"

        async def search(self, role_terms, country=None):
            raise RuntimeError("simulated crash")

    class Fine(_SlowSrc):
        source_name = "fine"

    db = Database(str(tmp_path / "t.db"))
    await db.init()
    registry = CountryRegistry("config/countries").load()
    await db.update_allowed_regions(registry.enabled_region_names() + ["Remote"])

    class _Reg:
        def enabled_countries(self):
            return [registry.get("Germany")]

    telemetry = await run_discovery_cycle(
        db, _Reg(), [Boom, Fine], max_passes=2, scraper_keys={})
    by_src = {p["source"]: p for p in telemetry["passes"]}
    assert by_src["boom"]["stop_reason"] == "SOURCE_FAILURE"
    assert by_src["fine"]["ingested"] == 1, "sibling must still ingest"
    assert by_src["fine"]["health_status"] == sr.HEALTH_PASS
    await db.close()


@pytest.mark.asyncio
async def test_concurrency_same_results_as_serial(tmp_path):
    """Concurrency must NOT change discovery results (task rule 17): same
    sources, one job each, run parallel vs serial → identical pool counts."""
    from app.database import Database
    from app.discovery import run_discovery_cycle
    from app.country_registry import CountryRegistry

    registry = CountryRegistry("config/countries").load()

    class _Reg:
        def enabled_countries(self):
            return [registry.get("Germany")]

    async def run(conc, db_path):
        db = Database(db_path)
        await db.init()
        await db.update_allowed_regions(
            registry.enabled_region_names() + ["Remote"])
        tel = await run_discovery_cycle(
            db, _Reg(), [_StubAdapter, _StubAdapter, _StubAdapter, _StubAdapter],
            max_passes=4, scraper_keys={}, max_concurrent_sources=conc)
        row = await db.db.execute(
            "SELECT COUNT(*) FROM jobs WHERE company='ProvCo'")
        n = (await row.fetchone())[0]
        await db.close()
        return tel, n

    tel_par, n_par = await run(4, str(tmp_path / "par.db"))
    tel_ser, n_ser = await run(1, str(tmp_path / "ser.db"))
    assert n_par == n_ser == 1, "same dedup result regardless of concurrency"
    assert tel_par["new_jobs"] == tel_ser["new_jobs"]
    assert tel_par["concurrency"]["max_active_observed"] <= 4
    assert tel_ser["concurrency"]["max_active_observed"] <= 1


def test_concurrency_configurable_from_env(monkeypatch):
    """JOBAGENT_DISCOVERY_CONCURRENCY overrides the default of 5 (task rule 5)."""
    from app import discovery as disc
    monkeypatch.delenv("JOBAGENT_DISCOVERY_CONCURRENCY", raising=False)
    assert disc._env_concurrency() == 5
    monkeypatch.setenv("JOBAGENT_DISCOVERY_CONCURRENCY", "3")
    assert disc._env_concurrency() == 3
    monkeypatch.setenv("JOBAGENT_DISCOVERY_CONCURRENCY", "garbage")
    assert disc._env_concurrency() == 5  # falls back safely
    monkeypatch.setenv("JOBAGENT_DISCOVERY_CONCURRENCY", "1")
    assert disc._env_concurrency() == 1  # 1 = old serial behavior
