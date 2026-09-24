"""M14 — LLM cost meter + run observability.

Tracks tokens and estimated spend per AI call so Basil can see exactly how
far a $2 DeepSeek top-up goes (the decision that motivated this module).

Design:
- Pricing is a static table (USD per 1M tokens). Unknown models fall back to
  the provider default, and free providers (OpenRouter :free models) cost 0.
- Recording is never allowed to break an AI call: every entry point swallows
  its own errors.
- In-process buffer + optional DB sink (registered by main.py at startup) so
  counts survive a restart and the dashboard reads one aggregate query.
"""

import logging
from collections import defaultdict
from contextvars import ContextVar
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# USD per 1M tokens: (input, output). Cache-hit input is billed separately by
# some providers; we keep the simple two-rate model (conservative — no cache
# discount is assumed, so estimates never under-report).
PRICING: dict[str, tuple[float, float]] = {
    # DeepSeek (api-docs.deepseek.com, off-peak rates Basil was quoted)
    "deepseek-flash": (0.15, 0.60),
    "deepseek-v4-pro": (0.55, 2.20),
    "deepseek-reasoner": (0.55, 2.20),
    # Anthropic
    "claude-sonnet-4": (3.00, 15.00),
    "claude-opus-4": (15.00, 75.00),
    "claude-haiku-4": (1.00, 5.00),
    "claude-3-5": (3.00, 15.00),
    # OpenAI
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4-turbo": (10.00, 30.00),
    "o1": (15.00, 60.00),
    "o3-mini": (1.10, 4.40),
    # Google
    "gemini-2.5-pro": (1.25, 10.00),
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.0-flash": (0.10, 0.40),
}

PROVIDER_DEFAULT_PRICING: dict[str, tuple[float, float]] = {
    "openai": (2.50, 10.00),
    "anthropic": (3.00, 15.00),
    "google": (0.30, 2.50),
    "bedrock": (3.00, 15.00),
    "deepseek": (0.15, 0.60),
    "openrouter": (0.00, 0.00),   # free tier is the product default
    "ollama": (0.00, 0.00),       # local — electricity only
}

# Keyword → pricing entry, so family matches work for dated model ids
# (e.g. "claude-sonnet-4-20250514", "us.anthropic.claude-sonnet-4-6").
_KEYWORD_PRICING: list[tuple[str, tuple[float, float]]] = [
    ("deepseek-v4-pro", (0.55, 2.20)),
    ("deepseek-reasoner", (0.55, 2.20)),
    ("deepseek", (0.15, 0.60)),
    ("opus", (15.00, 75.00)),
    ("haiku", (1.00, 5.00)),
    ("sonnet", (3.00, 15.00)),
    ("gpt-4o-mini", (0.15, 0.60)),
    ("gpt-4o", (2.50, 10.00)),
    ("gpt-4-turbo", (10.00, 30.00)),
    ("o3-mini", (1.10, 4.40)),
    ("gpt-4", (10.00, 30.00)),
    ("gemini-2.5-flash", (0.30, 2.50)),
    ("gemini-2.5-pro", (1.25, 10.00)),
    ("gemini", (0.10, 0.40)),
]

# A free model on a paid gateway (:free suffix) is genuinely $0.
_FREE_MARKERS = (":free", "-free", ":online")  # :online is OpenRouter web-search passthrough


def price_for(provider: str, model: str) -> tuple[float, float]:
    """(input, output) USD per 1M tokens for a provider/model pair."""
    m = (model or "").lower()
    if any(marker in m for marker in _FREE_MARKERS):
        return (0.0, 0.0)
    if m in PRICING:
        return PRICING[m]
    for keyword, rates in _KEYWORD_PRICING:
        if keyword in m:
            return rates
    return PROVIDER_DEFAULT_PRICING.get(provider, (0.0, 0.0))


def estimate_cost(provider: str, model: str,
                  tokens_in: int = 0, tokens_out: int = 0) -> float:
    """USD cost for one call. Rounded to 6 dp (micro-dollars)."""
    rate_in, rate_out = price_for(provider, model)
    cost = (tokens_in / 1_000_000) * rate_in + (tokens_out / 1_000_000) * rate_out
    return round(cost, 6)


def extract_usage(response) -> tuple[int, int]:
    """Pull (input, output) tokens out of an OpenAI- or Anthropic-shaped reply.

    Never raises — returns (0, 0) when the provider omits usage (some free
    gateways do), so the meter stays honest about what it cannot see.
    """
    usage = getattr(response, "usage", None)
    if usage is None:
        return 0, 0
    # OpenAI: prompt_tokens / completion_tokens
    prompt = getattr(usage, "prompt_tokens", None)
    completion = getattr(usage, "completion_tokens", None)
    if prompt is None and isinstance(usage, dict):
        prompt = usage.get("prompt_tokens")
        completion = usage.get("completion_tokens")
    # Anthropic: input_tokens / output_tokens
    if prompt is None:
        prompt = getattr(usage, "input_tokens", None)
        completion = getattr(usage, "output_tokens", None)
    if prompt is None and isinstance(usage, dict):
        prompt = usage.get("input_tokens", 0)
        completion = usage.get("output_tokens", 0)
    return int(prompt or 0), int(completion or 0)


# ------------------------------------------------------------ recording

_buffer: list[dict] = []
_db_sink = None            # async callable(dict) registered by main.py
_counters: dict[str, int] = defaultdict(int)

# M15c: per-request sink. In a multi-user deploy every AI call made while
# serving user X must be billed to X's workspace DB — the global sink always
# pointed at the admin's. The workspace middleware sets this per request; the
# value flows into any task the request spawns (asyncio copies the context).
_request_sink: ContextVar = ContextVar("ai_usage_request_sink", default=None)


def set_db_sink(sink) -> None:
    """Register the process-wide persistence hook (the admin/legacy DB)."""
    global _db_sink
    _db_sink = sink


def set_request_sink(sink) -> None:
    """Bind usage recording to ONE workspace for the current request context."""
    _request_sink.set(sink)


def current_sink():
    """The sink that will receive the next recorded call (per-request wins)."""
    return _request_sink.get() or _db_sink


async def record_call(provider: str, model: str, tokens_in: int, tokens_out: int,
                      purpose: str = "") -> dict:
    """Record one AI call. Swallows its own errors — never breaks a request."""
    entry = {
        "provider": provider,
        "model": model or "",
        "tokens_in": int(tokens_in or 0),
        "tokens_out": int(tokens_out or 0),
        "cost_usd": estimate_cost(provider, model, tokens_in, tokens_out),
        "purpose": purpose,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        _buffer.append(entry)
        _counters["ai_calls"] += 1
        _counters[f"ai_calls:{provider}"] += 1
        sink = _request_sink.get() or _db_sink
        if sink is not None:
            await sink(entry)
    except Exception as e:  # noqa: BLE001 — metering must never fail a call
        logger.debug("AI usage record skipped: %s", e)
    return entry


def increment(name: str, amount: int = 1) -> None:
    """Generic counter for observability (cache hits, etc.). Never raises."""
    try:
        _counters[name] += amount
    except Exception:  # noqa: BLE001
        pass


def counters_snapshot() -> dict[str, int]:
    return dict(_counters)


def summarize(rows: list[dict]) -> dict:
    """Aggregate usage rows into dashboard numbers."""
    totals = {"calls": 0, "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0}
    by_provider: dict[str, dict] = {}
    by_model: dict[str, dict] = {}
    for r in rows:
        cost = float(r.get("cost_usd") or 0.0)
        tin = int(r.get("tokens_in") or 0)
        tout = int(r.get("tokens_out") or 0)
        totals["calls"] += 1
        totals["tokens_in"] += tin
        totals["tokens_out"] += tout
        totals["cost_usd"] += cost

        key = r.get("provider") or "unknown"
        agg = by_provider.setdefault(key, {"calls": 0, "tokens_in": 0,
                                           "tokens_out": 0, "cost_usd": 0.0})
        agg["calls"] += 1
        agg["tokens_in"] += tin
        agg["tokens_out"] += tout
        agg["cost_usd"] += cost

        mkey = r.get("model") or "(default)"
        magg = by_model.setdefault(mkey, {"calls": 0, "cost_usd": 0.0,
                                          "tokens_in": 0, "tokens_out": 0})
        magg["calls"] += 1
        magg["cost_usd"] += cost
        magg["tokens_in"] += tin
        magg["tokens_out"] += tout

    for d in (totals, *by_provider.values(), *by_model.values()):
        d["cost_usd"] = round(d["cost_usd"], 6)

    avg = round(totals["cost_usd"] / totals["calls"], 6) if totals["calls"] else 0.0
    return {
        "totals": totals,
        "avg_cost_per_call_usd": avg,
        "by_provider": by_provider,
        "by_model": by_model,
    }


def budget_projection(spent_usd: float, budget_usd: float = 2.0,
                      calls: int = 0) -> dict:
    """How far a top-up goes — the number Basil actually asked for."""
    remaining = max(0.0, budget_usd - spent_usd)
    per_call = (spent_usd / calls) if calls else 0.0
    return {
        "budget_usd": budget_usd,
        "spent_usd": round(spent_usd, 6),
        "remaining_usd": round(remaining, 6),
        "avg_cost_per_call_usd": round(per_call, 6),
        "calls_remaining_estimate": int(remaining / per_call) if per_call > 0 else None,
        "percent_used": round((spent_usd / budget_usd) * 100, 2) if budget_usd else 0.0,
    }


def buffer_size() -> int:
    return len(_buffer)
