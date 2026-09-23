"""M14 cost meter tests — pricing, estimation, extraction, summary, budget."""
import pytest

from app.ai_usage import (
    budget_projection,
    estimate_cost,
    extract_usage,
    increment,
    counters_snapshot,
    price_for,
    record_call,
    summarize,
)

# ------------------------------------------------------------------ pricing

def test_deepseek_flash_pricing_matches_docs():
    """Basil's quoted off-peak rates: $0.15/1M in, $0.60/1M out."""
    assert price_for("deepseek", "deepseek-flash") == (0.15, 0.60)


def test_free_models_cost_zero():
    assert price_for("openrouter", "poolside/laguna-s-2.1:free") == (0.0, 0.0)
    assert estimate_cost("openrouter", "anything:free", 1_000_000, 1_000_000) == 0.0


def test_local_ollama_costs_zero():
    assert estimate_cost("ollama", "llama3", 500_000, 500_000) == 0.0


def test_family_keyword_match_for_dated_ids():
    assert price_for("anthropic", "claude-sonnet-4-20250514") == (3.00, 15.00)
    assert price_for("bedrock", "us.anthropic.claude-opus-4-6-v1") == (15.00, 75.00)
    assert price_for("openai", "gpt-4o-mini-2024-07-18") == (0.15, 0.60)


def test_unknown_model_falls_back_to_provider_default():
    assert price_for("deepseek", "brand-new-model") == (0.15, 0.60)
    assert price_for("totally-unknown-provider", "x") == (0.0, 0.0)


# ------------------------------------------------------------------- cost

def test_full_application_cost_matches_documented_estimate():
    """The number in the README/memory: ~$0.00525 per full application."""
    cost = estimate_cost("deepseek", "deepseek-flash", 15_000, 5_000)
    assert cost == pytest.approx(0.00525, abs=1e-6)


def test_two_dollars_buys_about_380_applications():
    per_app = estimate_cost("deepseek", "deepseek-flash", 15_000, 5_000)
    assert int(2.0 / per_app) == 380


def test_cost_is_linear_in_tokens():
    a = estimate_cost("deepseek", "deepseek-flash", 1_000, 1_000)
    b = estimate_cost("deepseek", "deepseek-flash", 2_000, 2_000)
    assert b == pytest.approx(a * 2, abs=1e-9)


# ---------------------------------------------------------------- extraction

class _Usage:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _Resp:
    def __init__(self, usage):
        self.usage = usage


def test_extract_openai_shape():
    assert extract_usage(_Resp(_Usage(prompt_tokens=100, completion_tokens=50))) == (100, 50)


def test_extract_anthropic_shape():
    assert extract_usage(_Resp(_Usage(input_tokens=200, output_tokens=80))) == (200, 80)


def test_extract_dict_shape():
    assert extract_usage(_Resp({"prompt_tokens": 10, "completion_tokens": 5})) == (10, 5)


def test_extract_missing_usage_is_zero_never_raises():
    assert extract_usage(_Resp(None)) == (0, 0)
    assert extract_usage(object()) == (0, 0)


# ---------------------------------------------------------------- recording

@pytest.mark.asyncio
async def test_record_call_builds_entry_with_cost():
    entry = await record_call("deepseek", "deepseek-flash", 15_000, 5_000)
    assert entry["cost_usd"] == pytest.approx(0.00525, abs=1e-6)
    assert entry["tokens_in"] == 15_000 and entry["provider"] == "deepseek"


@pytest.mark.asyncio
async def test_record_call_survives_broken_sink():
    """A failing sink must never propagate into the AI call path."""
    from app import ai_usage

    async def boom(entry):
        raise RuntimeError("db down")

    ai_usage.set_db_sink(boom)
    try:
        entry = await record_call("deepseek", "deepseek-flash", 10, 10)
        assert entry["provider"] == "deepseek"       # recorded in buffer anyway
    finally:
        ai_usage.set_db_sink(None)


def test_increment_and_snapshot():
    before = counters_snapshot().get("unit_test_counter", 0)
    increment("unit_test_counter", 3)
    assert counters_snapshot()["unit_test_counter"] == before + 3


# ------------------------------------------------------------------ summary

def test_summarize_totals_and_breakdowns():
    rows = [
        {"provider": "deepseek", "model": "deepseek-flash",
         "tokens_in": 15_000, "tokens_out": 5_000, "cost_usd": 0.00525},
        {"provider": "deepseek", "model": "deepseek-flash",
         "tokens_in": 15_000, "tokens_out": 5_000, "cost_usd": 0.00525},
        {"provider": "openrouter", "model": "x:free",
         "tokens_in": 1_000, "tokens_out": 1_000, "cost_usd": 0.0},
    ]
    s = summarize(rows)
    assert s["totals"]["calls"] == 3
    assert s["totals"]["tokens_in"] == 31_000
    assert s["totals"]["cost_usd"] == pytest.approx(0.0105, abs=1e-6)
    assert s["by_provider"]["deepseek"]["calls"] == 2
    assert s["by_model"]["deepseek-flash"]["calls"] == 2
    assert s["avg_cost_per_call_usd"] == pytest.approx(0.0035, abs=1e-6)


def test_summarize_empty_is_safe():
    s = summarize([])
    assert s["totals"]["calls"] == 0 and s["avg_cost_per_call_usd"] == 0.0
    assert s["by_provider"] == {}


# ------------------------------------------------------------------- budget

def test_budget_projection_estimates_remaining_calls():
    # $0.50 spent over 100 calls on a $2 budget
    p = budget_projection(spent_usd=0.5, budget_usd=2.0, calls=100)
    assert p["remaining_usd"] == pytest.approx(1.5)
    assert p["avg_cost_per_call_usd"] == pytest.approx(0.005)
    assert p["calls_remaining_estimate"] == 300
    assert p["percent_used"] == 25.0


def test_budget_projection_without_calls_has_no_estimate():
    p = budget_projection(spent_usd=0.0, calls=0)
    assert p["calls_remaining_estimate"] is None
    assert p["percent_used"] == 0.0


def test_budget_projection_never_negative_remaining():
    p = budget_projection(spent_usd=5.0, budget_usd=2.0, calls=10)
    assert p["remaining_usd"] == 0.0
