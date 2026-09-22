"""M3: Country strategy engine tests.

Key guarantee (per implementation plan): adding a country = dropping a YAML
file — ZERO code changes; per-country settings override defaults; visa engine
is deterministic.
"""
from pathlib import Path

import pytest
import yaml
from httpx import ASGITransport, AsyncClient

from app.country_registry import CountryConfigError, CountryRegistry
from app.location_classifier import (
    classify_location_rule_based,
    set_extra_country_terms,
)
from app.visa_engine import scan_visa_mentions

SEEDS = Path(__file__).resolve().parents[1] / "config" / "countries"


# ---------------- registry loading / schema ----------------

def test_all_six_seed_countries_load():
    reg = CountryRegistry(SEEDS).load()
    # region strings = what the classifier emits / jobs.location_region stores
    assert set(reg.region_names()) == {
        "Germany", "Netherlands", "Ireland", "UK", "Singapore", "UAE",
    }
    assert len(reg.enabled_countries()) == 6


def test_adding_country_requires_zero_code_changes(tmp_path):
    """THE M3 guarantee: drop a YAML → registry picks it up."""
    (tmp_path / "france.yaml").write_text(yaml.safe_dump({
        "code": "FR", "name": "France", "enabled": True,
        "aliases": ["france"], "cities": ["paris", "lyon"],
        "work_types": {"remote": True, "hybrid": True, "onsite": False},
        "visa": {"requires_sponsorship": True,
                 "sponsorship_keywords": ["visa sponsorship"]},
        "salary": {"currency": "EUR", "min": 50000},
    }))
    reg = CountryRegistry(tmp_path).load()
    assert "France" in reg.region_names()
    fr = reg.get("France")
    assert fr.code == "FR"
    assert fr.work_types["onsite"] is False  # per-country override respected


def test_bad_schema_fails_loud(tmp_path):
    (tmp_path / "bad.yaml").write_text("code: XX\nname: Nowhere\n")  # no visa section
    with pytest.raises(CountryConfigError):
        CountryRegistry(tmp_path).load()


def test_duplicate_region_fails_loud(tmp_path):
    for name in ("a.yaml", "b.yaml"):
        (tmp_path / name).write_text(yaml.safe_dump({
            "code": "XX", "name": "Nowhere", "enabled": True,
            "visa": {"requires_sponsorship": True, "sponsorship_keywords": []},
        }))
    with pytest.raises(CountryConfigError):
        CountryRegistry(tmp_path).load()


def test_disabled_country_excluded_from_enabled_regions(tmp_path):
    (tmp_path / "x.yaml").write_text(yaml.safe_dump({
        "code": "XX", "name": "Nowhere", "enabled": False,
        "visa": {"requires_sponsorship": True, "sponsorship_keywords": []},
    }))
    reg = CountryRegistry(tmp_path).load()
    assert "Nowhere" in reg.region_names()          # still known
    assert reg.enabled_region_names() == []          # but not active


# ---------------- classifier integration ----------------

def test_uae_locations_classify_to_uae():
    assert classify_location_rule_based("Dubai, UAE") == "UAE"
    assert classify_location_rule_based("Abu Dhabi") == "UAE"


def test_ukraine_not_misclassified_as_uk():
    """Regression: bare substring matching made 'uk' match inside 'ukraine'."""
    assert classify_location_rule_based("Remote - Ukraine") == "Ukraine"
    assert classify_location_rule_based("Kyiv, Ukraine") == "Ukraine"


def test_registry_terms_flow_into_classifier():
    set_extra_country_terms({"deutschland": "Germany"})
    try:
        assert classify_location_rule_based("Munchen, Deutschland") == "Germany"
    finally:
        set_extra_country_terms({})


# ---------------- visa engine (deterministic) ----------------

def test_visa_scan_matches_and_is_deterministic():
    kw = ["visa sponsorship", "blue card", "skilled worker visa"]
    text = "We offer visa sponsorship and support a Blue Card application."
    r1 = scan_visa_mentions(text, kw)
    r2 = scan_visa_mentions(text, kw)
    assert r1 == r2  # deterministic
    assert r1["sponsors_international"] is True
    assert set(r1["matched"]) == {"visa sponsorship", "blue card"}


def test_visa_scan_no_false_positives():
    kw = ["visa sponsorship", "work permit"]
    assert scan_visa_mentions("Great team, great pay.", kw)["count"] == 0
    assert scan_visa_mentions("", kw)["sponsors_international"] is False


def test_visa_scan_longest_keyword_preferred():
    kw = ["visa", "skilled worker visa"]
    r = scan_visa_mentions("We sponsor the skilled worker visa.", kw)
    assert "skilled worker visa" in r["matched"]


# ---------------- API surface ----------------

@pytest.fixture
async def seeded_app(tmp_path):
    """App with registry pointed at the real seed dir (read-only use here)."""
    from app.main import create_app
    application = create_app(db_path=str(tmp_path / "t.db"), testing=True)
    from app.country_registry import CountryRegistry
    application.state.country_registry = CountryRegistry(SEEDS).load()
    return application


@pytest.mark.asyncio
async def test_countries_api_list(seeded_app):
    transport = ASGITransport(app=seeded_app)
    async with AsyncClient(transport=transport, base_url="http://t") as ac:
        r = await ac.get("/api/countries")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 6
    codes = {c["code"] for c in body["countries"]}
    assert codes == {"DE", "NL", "IE", "GB", "SG", "AE"}


@pytest.mark.asyncio
async def test_countries_api_get_unknown_404(seeded_app):
    transport = ASGITransport(app=seeded_app)
    async with AsyncClient(transport=transport, base_url="http://t") as ac:
        r = await ac.get("/api/countries/Atlantis")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_countries_api_visa_check(seeded_app):
    transport = ASGITransport(app=seeded_app)
    async with AsyncClient(transport=transport, base_url="http://t") as ac:
        r = await ac.post("/api/countries/Germany/visa-check",
                          json={"text": "We provide visa sponsorship (Blue Card)."})
    assert r.status_code == 200
    body = r.json()
    assert body["sponsors_international"] is True
    assert "blue card" in body["matched"]
