import os
import uuid

import pytest

from app.config import Settings


def test_settings_defaults():
    s = Settings(
        anthropic_api_key="test-key",
        _env_file=None,  # isolate from any local .env during tests
    )
    assert s.db_path == "data/jobagent.db"
    assert s.scrape_interval_hours == 6
    assert s.min_salary == 150000
    assert s.min_hourly_rate == 95
    assert s.anthropic_api_key == "test-key"


def test_settings_custom():
    s = Settings(anthropic_api_key="k", scrape_interval_hours=12, min_salary=180000, _env_file=None)
    assert s.scrape_interval_hours == 12
    assert s.min_salary == 180000


def test_env_prefix_is_jobagent(monkeypatch):
    """The unified config spine must read JOBAGENT_* env vars (D24)."""
    monkeypatch.setenv("JOBAGENT_DB_PATH", f"/tmp/jobagent-{uuid.uuid4().hex}.db")
    monkeypatch.setenv("JOBAGENT_SCRAPE_INTERVAL_HOURS", "12")
    s = Settings(_env_file=None)
    assert s.db_path.startswith("/tmp/jobagent-")
    assert s.scrape_interval_hours == 12


def test_feature_flags_default_off():
    """D22: US-specific features are disabled by default, not deleted."""
    s = Settings(_env_file=None)
    assert s.enable_salary_tools is False
    assert s.enable_career_advisor is False
    assert s.enable_success_predictor is False
    # These stay on:
    assert s.enable_extension_autofill is True
    assert s.enable_linkedin_guest is False


def test_allow_send_defaults_false():
    """Golden rule: draft-only. Sending requires an explicit, deliberate act."""
    s = Settings(_env_file=None)
    assert s.allow_send is False


def test_openrouter_key_env(monkeypatch):
    monkeypatch.setenv("JOBAGENT_OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setenv("JOBAGENT_DEEPSEEK_API_KEY", "sk-deepseek-test")
    s = Settings(_env_file=None)
    assert s.openrouter_api_key == "sk-or-test"
    assert s.deepseek_api_key == "sk-deepseek-test"


def test_deepseek_provider_registered():
    """DeepSeek is an OpenAI-compatible provider with correct routing defaults."""
    from app.ai_client import ALL_PROVIDERS, OPENAI_COMPAT_PROVIDERS, AIClient

    assert "deepseek" in ALL_PROVIDERS
    ds = OPENAI_COMPAT_PROVIDERS["deepseek"]
    assert ds["base_url"] == "https://api.deepseek.com"
    assert ds["default_model"] == "deepseek-flash"

    client = AIClient("deepseek", api_key="sk-test")
    assert client.base_url == "https://api.deepseek.com"
    assert client.model == "deepseek-flash"


def test_deepseek_model_override():
    from app.ai_client import AIClient

    client = AIClient("deepseek", api_key="sk-test", model="deepseek-v4-pro")
    assert client.model == "deepseek-v4-pro"
