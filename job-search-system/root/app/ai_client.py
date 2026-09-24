import asyncio
import json
import logging
import os
import re

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
    before_sleep_log,
)

from app.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)

_ai_breaker = CircuitBreaker(failure_threshold=5, cooldown_seconds=300.0)

RETRYABLE_STATUS_CODES = {429, 500, 502, 503}


class AIOutputError(RuntimeError):
    """The provider answered HTTP 200 but produced no usable text.

    Typical cause: a reasoning model whose hidden "thinking" tokens consumed
    the whole max_tokens budget, leaving an empty or mid-string-truncated
    completion. Distinct from a transport failure, so it does not trip the
    circuit breaker — the caller can retry or fall back deliberately.
    """


class _ChatResult(str):
    """The model's text plus transport metadata.

    Subclasses ``str`` so every existing caller — and every test — that treats
    a chat response as a plain string keeps working unchanged, while ``chat()``
    can still see whether the answer was cut off by the output budget.
    """

    def __new__(cls, text: str, finish_reason: str = "", reasoning_tokens: int = 0):
        obj = super().__new__(cls, text or "")
        obj.finish_reason = finish_reason or ""
        obj.reasoning_tokens = int(reasoning_tokens or 0)
        return obj

    @property
    def truncated(self) -> bool:
        """True when the provider hit max_tokens mid-answer."""
        return self.finish_reason in ("length", "max_tokens")

    @property
    def empty(self) -> bool:
        return not str(self).strip()


def _reasoning_tokens(response) -> int:
    """Hidden reasoning ("thinking") tokens, when the provider reports them."""
    try:
        details = getattr(response.usage, "completion_tokens_details", None)
        return int(getattr(details, "reasoning_tokens", 0) or 0)
    except Exception:
        return 0


def _extract_retry_after(exc: BaseException) -> float | None:
    """Extract retry-after seconds from a rate limit error's response headers."""
    response = getattr(exc, "response", None)
    if response is None:
        return None
    headers = getattr(response, "headers", {})
    raw = headers.get("retry-after")
    if raw is None:
        return None
    try:
        return float(raw)
    except (ValueError, TypeError):
        return None


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in RETRYABLE_STATUS_CODES
    if isinstance(exc, httpx.TransportError):
        return True
    try:
        import anthropic
        if isinstance(exc, anthropic.RateLimitError):
            return True
        if isinstance(exc, anthropic.InternalServerError):
            return True
    except ImportError:
        pass
    try:
        import openai
        if isinstance(exc, openai.RateLimitError):
            return True
        if isinstance(exc, openai.InternalServerError):
            return True
    except ImportError:
        pass
    return False


def _rate_limit_aware_wait(retry_state) -> float:
    """Use retry-after header when available, otherwise exponential backoff."""
    exc = retry_state.outcome.exception()
    if exc is not None:
        retry_after = _extract_retry_after(exc)
        if retry_after is not None and retry_after > 0:
            # Cap at 120s to avoid infinite waits from buggy headers
            return min(retry_after, 120.0)
    # Fall back to exponential jitter for non-rate-limit errors
    return wait_exponential_jitter(initial=2, max=30)(retry_state)


_ai_retry = retry(
    retry=retry_if_exception(_is_retryable),
    stop=stop_after_attempt(4),  # 1 initial + 3 retries
    wait=_rate_limit_aware_wait,
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)


def _resolve_ollama_url(url: str) -> str:
    """Rewrite localhost URLs to host.docker.internal when running in Docker."""
    if os.path.exists("/.dockerenv"):
        return url.replace("localhost", "host.docker.internal").replace("127.0.0.1", "host.docker.internal")
    return url


OPENAI_COMPAT_PROVIDERS = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o",
    },
    "google": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "default_model": "gemini-2.0-flash",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "anthropic/claude-sonnet-4",
    },
    # DeepSeek API is OpenAI-compatible (per api-docs.deepseek.com):
    # base_url https://api.deepseek.com, auth via Bearer DEEPSEEK_API_KEY.
    # "deepseek-flash" serves DeepSeek-V4.1-Flash; legacy deepseek-v4-flash
    # names are accepted but billed at Flash price — prefer the current name.
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "default_model": "deepseek-flash",
    },
}

ALL_PROVIDERS = ["anthropic", "bedrock", "ollama", "openai", "google", "openrouter", "deepseek"]


async def check_ai_reachable(client: "AIClient") -> tuple[bool, str]:
    """Quick connectivity check for the configured AI provider. Returns (reachable, detail)."""
    try:
        if client.provider == "ollama":
            url = f"{_resolve_ollama_url(client.base_url).rstrip('/')}/api/tags"
            async with httpx.AsyncClient(timeout=5.0) as http:
                resp = await http.get(url)
                resp.raise_for_status()
            return True, "ok"
        elif client.provider == "anthropic":
            import anthropic
            c = anthropic.AsyncAnthropic(api_key=client.api_key)
            await c.messages.create(
                model=client.model, max_tokens=1,
                messages=[{"role": "user", "content": "hi"}],
            )
            return True, "ok"
        elif client.provider == "bedrock":
            c = client._bedrock_client()
            await c.messages.create(
                model=client.model, max_tokens=1,
                messages=[{"role": "user", "content": "hi"}],
            )
            return True, "ok"
        elif client.provider in OPENAI_COMPAT_PROVIDERS:
            from openai import AsyncOpenAI
            c = AsyncOpenAI(api_key=client.api_key, base_url=client.base_url)
            await c.models.list()
            return True, "ok"
        return False, f"Unknown provider: {client.provider}"
    except httpx.ConnectError:
        return False, f"{client.provider} unreachable at {client.base_url}"
    except httpx.HTTPStatusError as e:
        return False, f"{client.provider} returned HTTP {e.response.status_code}"
    except Exception as e:
        logger.debug("AI health check failed: %s", e)
        return False, f"{client.provider} error: {type(e).__name__}"


class AIClient:
    """Unified async AI client supporting Anthropic, Ollama, OpenAI, Google, and OpenRouter."""

    def __init__(self, provider: str, api_key: str = "", model: str = "",
                 base_url: str = "", region: str = ""):
        self.provider = provider
        self.api_key = api_key
        self.region = region
        self.model = model or self._default_model()
        self.base_url = base_url or self._default_base_url()

    def _default_model(self):
        if self.provider == "anthropic":
            return "claude-sonnet-4-20250514"
        if self.provider == "bedrock":
            return "us.anthropic.claude-sonnet-4-6"
        if self.provider == "ollama":
            return "llama3"
        if self.provider in OPENAI_COMPAT_PROVIDERS:
            return OPENAI_COMPAT_PROVIDERS[self.provider]["default_model"]
        return ""

    def _default_base_url(self):
        if self.provider == "ollama":
            return "http://localhost:11434"
        if self.provider in OPENAI_COMPAT_PROVIDERS:
            return OPENAI_COMPAT_PROVIDERS[self.provider]["base_url"]
        return ""

    # Providers whose OpenAI-compatible API supports JSON mode, which removes
    # markdown fences and (in practice) truncation-induced invalid JSON.
    JSON_MODE_PROVIDERS = ("openai", "deepseek")
    # Output budget per provider. Reasoning models (e.g. DeepSeek's) count their
    # hidden thinking tokens against max_tokens, so a budget that is plenty for
    # plain text can still be exhausted before any JSON is written — observed
    # live as an empty content or a mid-string cut that breaks JSON parsing.
    # These are the largest values each API is known to accept.
    _MAX_OUTPUT = {"deepseek": 16384, "openai": 16384, "openrouter": 4096,
                   "anthropic": 16000, "bedrock": 16000, "ollama": 4096}
    # Learn once per provider: after a reasoning model is detected, later calls
    # start at the full budget instead of paying for a second round trip.
    _reasoning_providers: set[str] = set()

    def output_budget(self, requested: int) -> int:
        cap = self._MAX_OUTPUT.get(self.provider, 4096)
        floor = cap if self.provider in self._reasoning_providers else 0
        return max(256, min(max(int(requested or 0), floor), cap))

    async def chat(self, prompt: str, max_tokens: int = 1024, timeout: float = 300.0,
                   json_mode: bool = False) -> str:
        service = f"ai:{self.provider}"
        if _ai_breaker.is_open(service):
            raise RuntimeError(f"Circuit breaker open for {service}")
        cap = self._MAX_OUTPUT.get(self.provider, 4096)
        budget = self.output_budget(max_tokens)
        budgets = [budget] if budget >= cap else [budget, cap]
        try:
            last: _ChatResult | None = None
            for attempt_budget in budgets:
                try:
                    last = await asyncio.wait_for(
                        self._chat_with_retry(prompt, attempt_budget, json_mode=json_mode),
                        timeout=timeout,
                    )
                except Exception:
                    if attempt_budget == budget:
                        raise
                    # A larger budget can exceed a smaller model's own limit;
                    # keep the first answer instead of failing the request.
                    logger.warning(
                        "Escalated budget %d rejected by %s — using first response",
                        attempt_budget, self.provider)
                    break
                if last.reasoning_tokens:
                    self._reasoning_providers.add(self.provider)
                if not last.empty and not last.truncated:
                    _ai_breaker.record_success(service)
                    return str(last)
                logger.warning(
                    "Unusable AI response (provider=%s model=%s budget=%d finish=%s "
                    "chars=%d reasoning_tokens=%d) — escalating output budget",
                    self.provider, self.model, attempt_budget,
                    last.finish_reason or "?", len(last), last.reasoning_tokens,
                )
            _ai_breaker.record_success(service)
            raise AIOutputError(
                f"{self.provider}/{self.model} returned no usable text "
                f"(finish={getattr(last, 'finish_reason', '?') or 'unknown'}, "
                f"{len(last or '')} chars) even at max_tokens={cap}"
            )
        except asyncio.TimeoutError:
            _ai_breaker.record_failure(service)
            raise RuntimeError(f"AI request timed out after {timeout}s for {service}")
        except (ValueError, AIOutputError, RuntimeError):
            raise
        except Exception:
            _ai_breaker.record_failure(service)
            raise

    @_ai_retry
    async def _chat_with_retry(self, prompt: str, max_tokens: int,
                               json_mode: bool = False) -> str:
        if self.provider == "anthropic":
            return await self._anthropic_chat(prompt, max_tokens)
        elif self.provider == "bedrock":
            return await self._bedrock_chat(prompt, max_tokens)
        elif self.provider == "ollama":
            return await self._ollama_chat(prompt, max_tokens)
        elif self.provider in OPENAI_COMPAT_PROVIDERS:
            return await self._openai_chat(prompt, max_tokens, json_mode=json_mode)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    async def _anthropic_chat(self, prompt: str, max_tokens: int) -> str:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=self.api_key)
        message = await client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        await self._meter(message)
        return _ChatResult(message.content[0].text,
                           getattr(message, "stop_reason", "") or "")

    async def _meter(self, response) -> None:
        """M14 cost meter: record tokens + estimated cost. Never raises."""
        try:
            from app import ai_usage
            tokens_in, tokens_out = ai_usage.extract_usage(response)
            await ai_usage.record_call(self.provider, self.model,
                                       tokens_in, tokens_out)
        except Exception as e:  # noqa: BLE001 — metering must never break a call
            logger.debug("Token metering skipped: %s", e)

    def _bedrock_client(self):
        import anthropic
        kwargs = {"aws_region": self.region or "us-east-1"}
        if self.api_key:
            kwargs["aws_access_key"] = self.api_key
        if self.base_url:
            kwargs["aws_secret_key"] = self.base_url
        return anthropic.AsyncAnthropicBedrock(**kwargs)

    async def _bedrock_chat(self, prompt: str, max_tokens: int) -> str:
        client = self._bedrock_client()
        message = await client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        await self._meter(message)
        return _ChatResult(message.content[0].text,
                           getattr(message, "stop_reason", "") or "")

    async def _openai_chat(self, prompt: str, max_tokens: int,
                           json_mode: bool = False) -> str:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        kwargs: dict = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        # JSON mode guarantees a parseable object (no fences, no prose). Not all
        # OpenAI-compatible endpoints accept it, so fall back silently on error.
        use_json = json_mode and self.provider in self.JSON_MODE_PROVIDERS
        if use_json:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            response = await client.chat.completions.create(**kwargs)
        except Exception:
            if not use_json:
                raise
            logger.warning("JSON mode unsupported for %s — retrying without it",
                           self.provider)
            kwargs.pop("response_format", None)
            response = await client.chat.completions.create(**kwargs)
        await self._meter(response)
        choice = response.choices[0]
        return _ChatResult(choice.message.content or "",
                           getattr(choice, "finish_reason", "") or "",
                           _reasoning_tokens(response))

    async def _ollama_chat(self, prompt: str, max_tokens: int) -> str:
        url = f"{_resolve_ollama_url(self.base_url).rstrip('/')}/api/chat"
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"num_predict": max_tokens},
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                raise RuntimeError(f"Ollama error: {data['error']}")
            try:
                return _ChatResult(data["message"]["content"],
                                   data.get("done_reason", "") or "")
            except (KeyError, TypeError) as e:
                raise RuntimeError(f"Unexpected Ollama response structure: {e}") from e


def parse_json_response(raw: str) -> dict:
    """Extract and parse JSON from an AI response.

    Handles markdown code fences, leading/trailing prose, and (as a last
    resort) truncated responses from a max_tokens cut-off by finding the
    outermost balanced ``{...}`` and trimming any unterminated trailing
    string/array before attempting to load.
    """
    raw = (raw or "").strip()
    if not raw:
        # chat() normally raises AIOutputError before this point; keep a clear
        # message for any direct caller that passes an empty response.
        raise json.JSONDecodeError(
            "empty AI response (no text to parse — the output budget was likely "
            "consumed by reasoning tokens)", raw, 0)
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        raw = raw.rsplit("```", 1)[0]
        raw = raw.strip()

    # Find the first top-level container — either an object or an array.
    obj_start = raw.find("{")
    arr_start = raw.find("[")
    if obj_start == -1 and arr_start == -1:
        raise json.JSONDecodeError("no JSON object or array found", raw, 0)
    if obj_start == -1:
        start = arr_start
    elif arr_start == -1:
        start = obj_start
    else:
        start = min(obj_start, arr_start)
    top_level = raw[start]  # '{' or '['

    stack: list[str] = []  # open '{' and '[' in order
    in_string = False
    escape = False
    end = -1
    for i in range(start, len(raw)):
        ch = raw[i]
        if escape:
            escape = False
            continue
        if ch == "\\" and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{" or ch == "[":
            stack.append(ch)
        elif ch == "}" and stack and stack[-1] == "{":
            stack.pop()
            if not stack:
                end = i + 1
                break
        elif ch == "]" and stack and stack[-1] == "[":
            stack.pop()
            if not stack:
                end = i + 1
                break

    if end != -1:
        return _loads_lenient(raw[start:end])

    # ---- Truncated mid-object (max_tokens cut-off): repair progressively.
    # The live failure was a cut INSIDE a long string value; the previous
    # single-shot repair could not close it. Try, in order:
    #   1. close the open string, drop the trailing partial token, close containers
    #   2. keep the unfinished string as-is but drop its key entirely
    #   3. walk back to each earlier comma and close containers there
    body = raw[start:]

    candidate = body
    if in_string:
        candidate += '"'
    candidate = re.sub(r",\s*[^,{}\[\]]*$", "", candidate.rstrip())
    candidate = candidate.rstrip().rstrip(",")
    for opener in reversed(stack):
        candidate += "}" if opener == "{" else "]"
    attempts = [candidate]

    # Drop the last (possibly half-written) key/value pair, then retry.
    attempts.append(re.sub(r',\s*"[^"]*"\s*:\s*[^,}\]]*(?=[}\]]+$)', "", candidate))

    # Walk back to earlier commas — the most robust fallback for deep cuts.
    closers = "".join("}" if o == "{" else "]" for o in reversed(stack))
    positions = [m.start() for m in re.finditer(",", body)]
    for pos in reversed(positions[-25:]):
        trimmed = body[:pos].rstrip()
        for opener in reversed(stack):
            trimmed += "}" if opener == "{" else "]"
        attempts.append(trimmed)

    last_err: Exception | None = None
    for attempt in attempts:
        try:
            return _loads_lenient(attempt)
        except json.JSONDecodeError as e:
            last_err = e
    raise last_err if last_err else json.JSONDecodeError("unrepairable JSON", raw, 0)


def _loads_lenient(text: str):
    """json.loads plus a strict-control-char tolerant retry."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", text)
        return json.loads(cleaned)
