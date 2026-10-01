"""STAGE-2 CLASSIFY tests — classification.py + scheduler integration.

All deterministic (no AI needed for these paths). Covers task §22:
explicit country, city-only, aliases, remote-specific/region/worldwide,
hybrid, multi-location, missing location, description evidence, source-hint
fallback, conflicts, UNKNOWN honesty, idempotency, ELIGIBILITY contract,
all 10 configured countries.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from app.classification import (
    CITY_TO_COUNTRY,
    COUNTRY_ALIASES,
    CONF_HIGH,
    CONF_LOW,
    CONF_MEDIUM,
    CONF_UNKNOWN,
    GLOBAL,
    SRC_AI_FALLBACK,
    SRC_CITY_MAP,
    SRC_DESCRIPTION,
    SRC_SOURCE_HINT,
    SRC_TEXT_LOCATION,
    SRC_UNKNOWN,
    classify_job,
    classify_job_ai,
    detect_conflict,
    normalize_country_code,
)


# ---------------------------------------------------------------------------
# Country normalization (task §5) — all 10 configured countries
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("token,expected", [
    ("United Kingdom", "GB"), ("UK", "GB"), ("U.K.", "GB"),
    ("Great Britain", "GB"), ("GB", "GB"), ("England", "GB"),
    ("United Arab Emirates", "AE"), ("UAE", "AE"), ("U.A.E.", "AE"),
    ("Singapore", "SG"), ("SG", "SG"),
    ("Germany", "DE"), ("Deutschland", "DE"),
    ("Netherlands", "NL"), ("Holland", "NL"),
    ("Ireland", "IE"), ("Canada", "CA"), ("Australia", "AU"),
    ("Poland", "PL"), ("India", "IN"),
])
def test_normalize_country_aliases(token, expected):
    assert normalize_country_code(token) == expected


def test_normalize_rejects_unconfigured():
    assert normalize_country_code("Malaysia") is None
    assert normalize_country_code("") is None
    assert normalize_country_code(None) is None


# ---------------------------------------------------------------------------
# Priority chain — the core cases (task §3/§7/§9)
# ---------------------------------------------------------------------------

def test_city_only_location():
    r = classify_job({"location": "Berlin"})
    assert (r.country_code, r.classification_confidence, r.classification_source) \
        == ("DE", CONF_HIGH, SRC_CITY_MAP)
    assert r.city == "berlin"


def test_explicit_country_in_text():
    r = classify_job({"location": "Berlin, Germany"})
    assert r.country_code == "DE" and r.classification_confidence == CONF_HIGH
    assert r.classification_source == SRC_TEXT_LOCATION


def test_remote_country_specific_is_not_generic():
    r = classify_job({"location": "Remote - Singapore"})
    assert r.country_code == "SG" and r.remote_type == "REMOTE"
    assert r.classification_confidence == CONF_HIGH

    r = classify_job({"location": "Remote - Germany"})
    assert r.country_code == "DE" and r.remote_type == "REMOTE"


def test_remote_region_only_stays_unknown_country():
    r = classify_job({"location": "Remote - APAC"})
    assert r.country_code is None and r.region == "APAC"
    assert r.remote_type == "REMOTE" and r.classification_confidence == CONF_MEDIUM


def test_remote_worldwide_is_global():
    r = classify_job({"location": "Remote - Worldwide"})
    assert r.country_code is None and r.region == GLOBAL
    assert r.remote_type == "REMOTE"


def test_pure_remote_is_low_not_certified():
    r = classify_job({"location": "Remote"})
    assert r.country_code is None and r.remote_type == "REMOTE"
    assert r.classification_confidence in (CONF_LOW, CONF_UNKNOWN)


def test_hybrid_keeps_country():
    r = classify_job({"location": "Hybrid - London"})
    assert r.country_code == "GB" and r.remote_type == "HYBRID"
    assert r.region == "UK"  # classifier string for GB is 'UK'


def test_onsite_keyword():
    r = classify_job({"location": "On-site - Dubai"})
    assert r.country_code == "AE" and r.remote_type == "ONSITE"


def test_multi_location_primary_plus_supported():
    r = classify_job({"location": "Singapore / London / New York"})
    assert r.country_code == "SG"
    assert r.supported_countries == ["SG", "GB"]
    assert r.classification_confidence == CONF_HIGH


def test_multi_location_does_not_pick_falsely():
    # 'Berlin or Amsterdam' → both cities are DE + NL → honest multi-list
    r = classify_job({"location": "Berlin or Amsterdam"})
    assert r.country_code == "DE"  # primary = first
    assert r.supported_countries == ["DE", "NL"]  # both recorded


def test_missing_location_is_honest_unknown():
    r = classify_job({"location": "", "description": ""})
    assert r.country_code is None
    assert r.classification_confidence == CONF_UNKNOWN
    assert r.classification_source == SRC_UNKNOWN


def test_region_only_ambiguity_never_fabricates():
    for loc in ("EMEA", "Europe", "Flexible", "Multiple Locations"):
        r = classify_job({"location": loc})
        assert r.country_code is None, loc
        assert r.classification_confidence in (CONF_MEDIUM, CONF_UNKNOWN)


def test_unconfigured_country_is_unknown_not_fabricated():
    r = classify_job({"location": "Kuala Lumpur, Malaysia"})
    assert r.country_code is None
    assert r.classification_confidence == CONF_UNKNOWN


# ---------------------------------------------------------------------------
# Source hint is ONLY a hint (task §10)
# ---------------------------------------------------------------------------

def test_source_hint_never_overrides_text():
    r = classify_job({"location": "Remote - India", "search_country": "SG"})
    assert r.country_code == "IN"
    assert r.classification_source != SRC_SOURCE_HINT


def test_source_hint_fallback_is_low_confidence():
    r = classify_job({"location": "Innovation City",
                      "search_country": "SG",
                      "description": "We build AI products"})
    assert r.country_code == "SG"
    assert r.classification_confidence == CONF_LOW
    assert r.classification_source == SRC_SOURCE_HINT


def test_no_hint_no_evidence_is_unknown():
    r = classify_job({"location": "Innovation City", "description": "AI"})
    assert r.country_code is None and r.classification_confidence == CONF_UNKNOWN


# ---------------------------------------------------------------------------
# Description evidence (task §11) — deterministic patterns
# ---------------------------------------------------------------------------

def test_description_location_evidence():
    r = classify_job({"location": "Hybrid",
                      "description": "Exciting role.\nLocation: Amsterdam\nApply now"})
    assert r.country_code == "NL"
    assert r.classification_source == SRC_DESCRIPTION
    assert r.classification_confidence == CONF_MEDIUM


def test_description_residency_evidence():
    """Residency evidence applies when the LOCATION itself is ambiguous —
    'Remote (EU)' stays region-constrained (EUROPE), but a location with no
    region signal picks up the country from the description."""
    r = classify_job({"location": "Remote",
                      "description": "Candidates must reside in Germany for this role."})
    assert r.country_code == "DE"
    assert r.classification_source == SRC_DESCRIPTION
    # location text with its own region signal wins over description:
    r2 = classify_job({"location": "Remote (EU)",
                       "description": "Candidates must reside in Germany."})
    assert r2.country_code is None and r2.region == "EUROPE"


def test_deterministic_beats_ai_no_ai_needed():
    """Rules resolved it — classification must not need AI at all (task §13)."""
    r = classify_job({"location": "Dubai"})
    assert r.country_code == "AE" and r.classification_confidence == CONF_HIGH
    # classification_source is deterministic, never AI_FALLBACK
    assert "AI" not in r.classification_source


# ---------------------------------------------------------------------------
# Conflict detection (task §15)
# ---------------------------------------------------------------------------

def test_conflict_detected_and_recorded_not_applied():
    job = {"location": "Singapore",
           "description": "Great team.\nLocation: Kuala Lumpur office"}
    r = classify_job(job)
    assert r.country_code == "SG"  # structured/text wins
    conflict = detect_conflict(job, r)
    assert conflict is not None
    assert "MY" in conflict or "conflict" in conflict


def test_no_conflict_when_agreement():
    job = {"location": "Singapore",
           "description": "Location: Singapore downtown hub"}
    r = classify_job(job)
    assert detect_conflict(job, r) is None


# ---------------------------------------------------------------------------
# Idempotency (task §16)
# ---------------------------------------------------------------------------

def test_classification_is_idempotent():
    job = {"location": "Remote - Germany", "description": "AI role",
           "search_country": "SG"}
    a, b = classify_job(job), classify_job(job)
    assert a.to_dict() == b.to_dict()


# ---------------------------------------------------------------------------
# All 10 configured countries via city mapping
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("city,expected_code", [
    ("Singapore", "SG"), ("Berlin", "DE"), ("Munich", "DE"),
    ("Amsterdam", "NL"), ("Dublin", "IE"), ("London", "GB"),
    ("Dubai", "AE"), ("Abu Dhabi", "AE"), ("Toronto", "CA"),
    ("Sydney", "AU"), ("Melbourne", "AU"), ("Warsaw", "PL"),
    ("Bangalore", "IN"), ("Bengaluru", "IN"), ("Chennai", "IN"),
    ("Hyderabad", "IN"),
])
def test_city_map_all_countries(city, expected_code):
    r = classify_job({"location": city})
    assert r.country_code == expected_code, (city, r)


def test_city_map_has_no_orphan_codes():
    """Every city maps to one of the 10 CONFIGURED countries."""
    valid = set(COUNTRY_ALIASES)
    assert set(CITY_TO_COUNTRY.values()) <= valid


# ---------------------------------------------------------------------------
# Scheduler integration + persistence + idempotency + contract (tmp DB)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scheduler_pass_persists_and_is_idempotent(tmp_path):
    from app.database import Database
    from app.scheduler import run_location_classification

    db = Database(str(tmp_path / "t.db"))
    await db.init()
    await db.update_allowed_regions(["Germany", "Singapore", "Remote", "APAC", "Unknown"])
    for i, loc in enumerate(["Berlin", "Remote - APAC", "Singapore"]):
        await db.insert_job(title="AI Engineer", company=f"C{i}", location=loc,
                            salary_min=None, salary_max=None, description="d",
                            url=f"https://x/{i}", posted_date=None,
                            application_method="direct", contact_email=None)

    n1 = await run_location_classification(db, ai_client=None)
    assert n1 == 3
    row = await db.db.execute(
        "SELECT COUNT(*) FROM jobs WHERE location_classified=1 AND "
        "classification_confidence IS NOT NULL AND country_code IS NOT NULL")
    # Berlin + Singapore have countries; Remote-APAC honest-unknown (None)
    assert (await row.fetchone())[0] == 2

    # Second run: nothing to do (idempotent — unchanged jobs not reclassified)
    n2 = await run_location_classification(db, ai_client=None)
    assert n2 == 0
    await db.close()


@pytest.mark.asyncio
async def test_downstream_eligibility_contract(tmp_path):
    """A classified job must flow into ELIGIBILITY unchanged (task §22/§29)."""
    from app.database import Database
    from app.scheduler import run_location_classification
    from app.eligibility import EligibilityEngine
    from app.country_registry import CountryRegistry

    db = Database(str(tmp_path / "t.db"))
    await db.init()
    registry = CountryRegistry("config/countries").load()
    await db.update_allowed_regions(registry.enabled_region_names() + ["Remote"])
    await db.insert_job(title="AI Engineer", company="ProvCo",
                        location="Berlin, Germany",
                        salary_min=None, salary_max=None, description="d",
                        url="https://x/1", posted_date="2026-09-28",
                        application_method="direct", contact_email=None)
    await run_location_classification(db, ai_client=None)

    row = await db.db.execute(
        "SELECT * FROM jobs WHERE company='ProvCo'")
    job = dict(await row.fetchone())
    assert job["location_classified"] == 1
    assert job["location_region"] == "Germany"
    assert job["country_code"] == "DE"

    engine = EligibilityEngine(
        allowed_regions=registry.enabled_region_names() + ["Remote"])
    verdict = engine.check(job)
    assert isinstance(verdict.reasons, list)
    # classified + fresh + not dismissed → eligible here
    assert "not_classified" not in verdict.reasons
    await db.close()


@pytest.mark.asyncio
async def test_multi_user_isolation_of_classification(tmp_path):
    """User A's classification writes never touch user B's DB (task §18)."""
    from app.database import Database

    db_a = Database(str(tmp_path / "a.db"))
    db_b = Database(str(tmp_path / "b.db"))
    await db_a.init()
    await db_b.init()
    for db, n in ((db_a, 1), (db_b, 2)):
        await db.insert_job(title="AI Engineer", company=f"C{n}",
                            location="Remote - APAC",
                            salary_min=None, salary_max=None, description="d",
                            url=f"https://x/{n}", posted_date=None,
                            application_method="direct", contact_email=None)

    from app.scheduler import run_location_classification
    await run_location_classification(db_a, ai_client=None)

    row_a = await db_a.db.execute(
        "SELECT location_region FROM jobs WHERE company='C1'")
    row_b = await db_b.db.execute(
        "SELECT location_region, location_classified FROM jobs WHERE company='C2'")
    assert (await row_a.fetchone())[0] == "APAC"
    b = await row_b.fetchone()
    assert b[0] is None and b[1] == 0, "B must be untouched"
    await db_a.close()
    await db_b.close()


@pytest.mark.asyncio
async def test_classification_metrics_recorded(tmp_path):
    from app.database import Database
    from app.scheduler import run_location_classification

    db = Database(str(tmp_path / "t.db"))
    await db.init()
    await db.insert_job(title="AI", company="C", location="Berlin",
                        salary_min=None, salary_max=None, description="d",
                        url="https://x/1", posted_date=None,
                        application_method="direct", contact_email=None)
    await run_location_classification(db, ai_client=None)
    row = await db.db.execute("SELECT classification_metrics FROM search_config")
    blob = (await row.fetchone())[0]
    m = json.loads(blob)
    assert m["total"] >= 1
    assert m["no_ai_needed"] >= 1  # deterministic pass needed zero AI
    assert m["HIGH"] >= 1
    await db.close()


# ---------------------------------------------------------------------------
# AI fallback (priority 7) — bounded, validated, residue-only (task §7/§10)
# ---------------------------------------------------------------------------

class _AiMock:
    """Minimal stand-in for AIClient: counts calls, returns a canned reply."""

    def __init__(self, reply):
        self.reply = reply
        self.calls = 0

    async def chat(self, prompt, max_tokens=0, timeout=0.0):
        self.calls += 1
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


@pytest.mark.asyncio
async def test_ai_fallback_resolves_residue_country():
    ai = _AiMock('{"country_code": "SG", "confidence": "HIGH", "reason": "hq"}')
    r = await classify_job_ai({"location": "Nowhereville"}, ai)
    assert r.country_code == "SG"
    assert r.classification_source == SRC_AI_FALLBACK
    assert r.classification_confidence == CONF_MEDIUM
    assert ai.calls == 1


@pytest.mark.asyncio
async def test_ai_fallback_rejects_unconfigured_country():
    ai = _AiMock('{"country_code": "MY", "confidence": "HIGH"}')
    r = await classify_job_ai({"location": "Kuala Lumpur"}, ai)
    assert r.country_code is None
    assert r.classification_source == SRC_UNKNOWN


@pytest.mark.asyncio
async def test_ai_fallback_rejects_low_confidence():
    ai = _AiMock('{"country_code": "SG", "confidence": "LOW"}')
    r = await classify_job_ai({"location": "Nowhereville"}, ai)
    assert r.country_code is None
    assert r.classification_source == SRC_UNKNOWN


@pytest.mark.asyncio
async def test_ai_fallback_handles_garbage_and_errors():
    r1 = await classify_job_ai({"location": "X"}, _AiMock("not json at all"))
    assert r1.country_code is None and r1.classification_source == SRC_UNKNOWN
    r2 = await classify_job_ai({"location": "X"},
                               _AiMock(RuntimeError("boom")))
    assert r2.country_code is None and r2.classification_source == SRC_UNKNOWN


@pytest.mark.asyncio
async def test_ai_fallback_not_called_for_empty_evidence():
    ai = _AiMock('{"country_code": "SG", "confidence": "HIGH"}')
    r = await classify_job_ai({"location": "", "description": ""}, ai)
    assert r.country_code is None
    assert ai.calls == 0  # no evidence → no spend


@pytest.mark.asyncio
async def test_scheduler_ai_only_for_residue(tmp_path):
    """A deterministically-resolved job must NEVER hit AI; an UNKNOWN job may."""
    from app.database import Database
    from app.scheduler import run_location_classification

    db = Database(str(tmp_path / "t.db"))
    await db.init()
    await db.insert_job(title="AI", company="C1", location="Berlin",
                        salary_min=None, salary_max=None, description="d",
                        url="https://x/1", posted_date=None,
                        application_method="direct", contact_email=None)
    await db.insert_job(title="AI", company="C2", location="Nowhereville",
                        salary_min=None, salary_max=None, description="",
                        url="https://x/2", posted_date=None,
                        application_method="direct", contact_email=None)
    ai = _AiMock('{"country_code": "SG", "confidence": "HIGH"}')
    await run_location_classification(db, ai_client=ai)
    assert ai.calls == 1  # only the UNKNOWN job hit AI

    row = await db.db.execute(
        "SELECT country_code, classification_source FROM jobs WHERE company='C2'")
    cc, src = await row.fetchone()
    assert cc == "SG" and src == SRC_AI_FALLBACK

    row = await db.db.execute(
        "SELECT classification_source FROM jobs WHERE company='C1'")
    assert (await row.fetchone())[0] != SRC_AI_FALLBACK

    row = await db.db.execute("SELECT classification_metrics FROM search_config")
    m = json.loads((await row.fetchone())[0])
    assert m["ai_fallback"] == 1
    assert m["no_ai_needed"] >= 1
    await db.close()
