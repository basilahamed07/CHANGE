"""Tavily web search adapter for job discovery.

Tavily is a non-Google search API built for AI/RAG workflows. We use it as a
fresh-web discovery layer over trusted career domains, then still apply the
same local filters before inserting anything into the job pool.

Required scraper key/env entry:
    tavily_search -> api_key = Tavily API key
"""

from __future__ import annotations

import logging
import re

import httpx

from app.adapters.country_facade import in_country
from app.job_adapter import (
    AdapterResult,
    CanonicalJob,
    JobSourceAdapter,
    STOP_RATE_LIMITED,
    STOP_SOURCE_FAILURE,
)
from app.scrapers.base import BaseScraper, validate_url

logger = logging.getLogger(__name__)

API_URL = "https://api.tavily.com/search"
PAGE_SIZE = 10
MAX_QUERIES_PER_PASS = 3

INCLUDE_DOMAINS = [
    "mycareersfuture.gov.sg",
    "jobs.lever.co",
    "boards.greenhouse.io",
    "jobs.ashbyhq.com",
    "groupcareers.singtel.com",
    "ncs.co",
    "smartrecruiters.com",
    "jobs.workable.com",
    "apply.workable.com",
    "myworkdayjobs.com",
    "jobs.jobvite.com",
    "jobs.sap.com",
    "nodeflair.com",
    "germantechjobs.de",
    "jobbank.gc.ca",
]

_JOB_TITLE_RE = re.compile(
    r"\b("
    r"ai engineer|genai application engineer|gen(?:erative)? ai engineer|"
    r"llm engineer|machine learning engineer|rag engineer|applied ai engineer|"
    r"ai solutions engineer|ai developer|forward deployed engineer|agentic ai engineer"
    r")\b",
    re.I,
)
_HIRING_HINT_RE = re.compile(
    r"\b(job|jobs|career|careers|hiring|opening|vacancy|role|apply)\b", re.I)


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _safe_error(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        return f"HTTP {exc.response.status_code}: {exc.response.reason_phrase}"
    return str(exc)[:160]


class TavilySearchAdapter(JobSourceAdapter, BaseScraper):
    source_name = "tavily_search"

    def __init__(self, search_terms=None, scraper_keys=None):
        BaseScraper.__init__(self, search_terms=search_terms, scraper_keys=scraper_keys)

    def _api_key(self) -> str:
        entry = (self.scraper_keys or {}).get("tavily_search", {})
        if isinstance(entry, dict):
            return (entry.get("api_key") or "").strip()
        return ""

    def _queries(self, role_terms: list[str], country) -> list[str]:
        region = getattr(country, "region", "") or ""
        terms = [t for t in (role_terms or self.search_terms or []) if t]
        if not terms:
            terms = ["AI Engineer", "Generative AI Engineer"]
        location = region or "remote"
        queries = [
            f'{terms[0]} RAG LangGraph LangChain {location} jobs apply',
            f'GenAI Application Engineer LLM RAG agentic AI {location}',
        ]
        if len(terms) > 1:
            queries.append(f'{terms[1]} Python backend AI {location} careers')
        return queries[:MAX_QUERIES_PER_PASS]

    def _headers(self, key: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

    def _body(self, query: str) -> dict:
        return {
            "query": query,
            "search_depth": "basic",
            "topic": "general",
            "max_results": PAGE_SIZE,
            "include_answer": False,
            "include_raw_content": False,
            "include_domains": INCLUDE_DOMAINS,
        }

    async def health_check(self) -> dict:
        key = self._api_key()
        if not key:
            return {"source": self.source_name, "ok": False,
                    "error": "missing tavily_search api_key"}
        try:
            async with self.get_client() as client:
                resp = await self.rate_limited_get(
                    client,
                    API_URL,
                    method="POST",
                    headers=self._headers(key),
                    json=self._body("AI Engineer jobs"),
                )
                return {"source": self.source_name, "ok": resp.status_code == 200,
                        "status": resp.status_code}
        except Exception as e:
            return {"source": self.source_name, "ok": False, "error": _safe_error(e)}

    async def search(self, role_terms: list[str], country=None) -> AdapterResult:
        result = AdapterResult(source=self.source_name)
        key = self._api_key()
        if not key:
            result.stop_reason = STOP_SOURCE_FAILURE
            result.error = "tavily_search key not configured"
            return result

        try:
            async with self.get_client() as client:
                seen: set[str] = set()
                for query in self._queries(role_terms, country):
                    try:
                        resp = await self.rate_limited_get(
                            client,
                            API_URL,
                            method="POST",
                            headers=self._headers(key),
                            json=self._body(query),
                        )
                        if resp.status_code == 429:
                            result.stop_reason = STOP_RATE_LIMITED
                            return result
                        resp.raise_for_status()
                        data = resp.json()
                    except (httpx.HTTPStatusError, httpx.TimeoutException,
                            httpx.ConnectError) as e:
                        logger.warning("Tavily search query failed: %s", _safe_error(e))
                        result.stop_reason = STOP_SOURCE_FAILURE
                        result.error = _safe_error(e)
                        break

                    for item in data.get("results", []) if isinstance(data, dict) else []:
                        title = _clean(str(item.get("title", "")))
                        link = _clean(str(item.get("url", "")))
                        snippet = _clean(str(item.get("content", "")))
                        if not link or link in seen or not validate_url(link):
                            continue
                        haystack = f"{title} {snippet} {link}"
                        if not _JOB_TITLE_RE.search(haystack) or not _HIRING_HINT_RE.search(haystack):
                            continue
                        if country is not None and getattr(country, "region", None):
                            if not in_country(haystack, country):
                                continue
                        seen.add(link)
                        company = link.split("/")[2].removeprefix("www.")
                        result.listings.append(CanonicalJob(
                            title=title[:140],
                            company=company,
                            location=getattr(country, "region", "") or "Remote",
                            description=snippet,
                            url=link,
                            source=self.source_name,
                            source_job_id=link,
                            tags=["tavily_search", "web_search"],
                        ))
            return result
        except Exception as e:
            logger.exception("Tavily search adapter crashed")
            result.stop_reason = STOP_SOURCE_FAILURE
            result.error = str(e)[:160]
            return result
