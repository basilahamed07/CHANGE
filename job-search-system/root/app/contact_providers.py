"""M7: Contact research — ContactProvider interface + adapters + confidence.

Golden Rules honored:
- Adapters over vendors (Rule 9): one ContactProvider interface; Hunter/Apollo/
  WebSearch/Manual adapters behind it. A provider failure never breaks research.
- Deterministic code for deterministic problems (Rule 4): role classification,
  confidence scoring, and selection ranking are pure Python — no LLM.

Contact model: role_type taxonomy (recruiter / hiring_manager / referrer / other),
confidence 0-100, relationship_to_job, why_selected rationale.

Fallback chain + per-provider rate limiting + research cache (no re-research per
job within the cache TTL).
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone

import httpx

from app.rate_limiter import AsyncRateLimiter

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------- taxonomy

ROLE_RECRUITER = "recruiter"
ROLE_HIRING_MANAGER = "hiring_manager"
ROLE_REFERRER = "referrer"
ROLE_OTHER = "other"

_RECRUITER_RX = re.compile(
    r"\b(recruiter|recruiting|talent\s?(acquisition|partner|lead|specialist)|"
    r"sourcing|people\s?ops|human\s?resources|\bhr\b|talent)\b", re.I)
_MANAGER_RX = re.compile(
    r"\b(engineering\s?manager|eng\s?manager|head\s?of|director|vp\b|vice\s?president|"
    r"cto\b|ceo\b|chief\s\w+|team\s?lead|tech\s?lead|hiring\s?manager|"
    r"manager\s?of|group\s?lead)\b", re.I)
_PEER_RX = re.compile(
    r"\b(engineer|developer|scientist|architect|analyst|designer)\b", re.I)

GENERIC_INBOX_RX = re.compile(
    r"^(jobs?|careers?|hiring|recruit(?:ing)?|talent|hr|people|info|contact|"
    r"support|hello|team|noreply|no-reply|work)\b", re.I)


def classify_role(title: str) -> str:
    """Deterministic role_type classification from a job/contact title."""
    t = (title or "").strip()
    if not t:
        return ROLE_OTHER
    if _RECRUITER_RX.search(t):
        return ROLE_RECRUITER
    if _MANAGER_RX.search(t):
        return ROLE_HIRING_MANAGER
    if _PEER_RX.search(t):
        return ROLE_REFERRER
    return ROLE_OTHER


@dataclass
class ContactCandidate:
    """One researched contact with its evidence and machine-readable rationale."""

    name: str
    email: str = ""
    title: str = ""
    company: str = ""
    linkedin_url: str = ""
    role_type: str = ROLE_OTHER
    confidence: int = 0
    provider: str = ""
    relationship_to_job: str = ""
    why_selected: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def score_confidence(candidate: ContactCandidate, job_title: str,
                     base_by_provider: dict | None = None) -> int:
    """Deterministic confidence 0-100 for a researched contact.

    Components: provider base + title relevance to the job + role_type weight +
    personal-vs-generic email + LinkedIn presence. Same inputs => same score.
    """
    bases = {"hunter": 70, "apollo": 65, "web_search": 40, "manual": 90}
    if base_by_provider:
        bases.update(base_by_provider)
    score = bases.get(candidate.provider, 40)

    # Title relevance: does the contact's title intersect the job's title words?
    jt_words = {w for w in re.findall(r"[a-z]{3,}", (job_title or "").lower())}
    ct_words = {w for w in re.findall(r"[a-z]{3,}", (candidate.title or "").lower())}
    overlap = jt_words & ct_words - {"senior", "junior", "lead", "staff"}
    if overlap:
        score += 12

    role_weights = {ROLE_RECRUITER: 10, ROLE_HIRING_MANAGER: 8,
                    ROLE_REFERRER: 5, ROLE_OTHER: 0}
    score += role_weights.get(candidate.role_type, 0)

    email = (candidate.email or "")
    if email:
        local = email.split("@")[0]
        name_tokens = {re.sub(r"[^a-z]", "", w) for w in (candidate.name or "").lower().split()}
        name_tokens.discard("")
        if name_tokens and any(t and t in local for t in name_tokens):
            score += 5   # personal mailbox containing the person's name
        if GENERIC_INBOX_RX.match(local):
            score -= 15  # generic role inbox — low reply signal
    else:
        score -= 20      # no email at all — much less actionable

    if candidate.linkedin_url:
        score += 5

    return max(0, min(100, score))


def rank_candidates(candidates: list[ContactCandidate], job_title: str) -> list[ContactCandidate]:
    """Classify + score + sort (confidence desc, stable). Mutates in place, returns too."""
    for c in candidates:
        c.role_type = classify_role(c.title or c.name)
        c.confidence = score_confidence(c, job_title)
        bits = []
        if c.role_type == ROLE_RECRUITER:
            bits.append("recruiter — owns outreach for this role")
        elif c.role_type == ROLE_HIRING_MANAGER:
            bits.append("likely hiring manager for this team")
        elif c.role_type == ROLE_REFERRER:
            bits.append("peer engineer — potential referral path")
        if c.email and not GENERIC_INBOX_RX.match(c.email.split("@")[0]):
            bits.append("personal mailbox")
        if c.linkedin_url:
            bits.append("LinkedIn verified")
        c.why_selected = "; ".join(bits) or "matched company + role context"
        c.relationship_to_job = f"{c.role_type} @ {c.company or 'target company'}"
    candidates.sort(key=lambda c: c.confidence, reverse=True)
    return candidates


# ---------------------------------------------------------------- providers


class ContactProvider:
    """Base adapter. NEVER raises from find() — returns [] on any failure
    (same adapter discipline as M4's JobSourceAdapter)."""

    name = "base"
    available = True

    def __init__(self, rate: float = 1.0, per: float = 1.0):
        self.limiter = AsyncRateLimiter(rate=rate, per=per)

    async def find(self, job: dict) -> list[ContactCandidate]:
        try:
            async with self.limiter:
                return await self._find(job)
        except Exception as e:
            logger.warning("ContactProvider %s failed: %s", self.name, e)
            return []

    async def _find(self, job: dict) -> list[ContactCandidate]:
        raise NotImplementedError


class HunterProvider(ContactProvider):
    """hunter.io domain-search adapter (port from job-application-pipeline, MIT)."""

    name = "hunter"
    BASE = "https://api.hunter.io/v2/domain-search"

    def __init__(self, api_key: str = ""):
        super().__init__(rate=1.0, per=1.0)
        self.api_key = api_key or os.getenv("JOBAGENT_HUNTER_API_KEY", "")
        self.available = bool(self.api_key)

    def _domain(self, company: str, website: str = "") -> str:
        if website:
            m = re.search(r"https?://([^/]+)", website)
            if m:
                return m.group(1).replace("www.", "")
        slug = re.sub(r"[^a-z0-9]", "", (company or "").lower())
        return f"{slug}.com" if slug else ""

    async def _find(self, job: dict) -> list[ContactCandidate]:
        if not self.available:
            return []
        domain = self._domain(job.get("company", ""), job.get("company_website", ""))
        if not domain:
            return []
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(self.BASE, params={
                "domain": domain, "api_key": self.api_key, "limit": 10})
            resp.raise_for_status()
            data = resp.json().get("data", {}) or {}
        out: list[ContactCandidate] = []
        for entry in data.get("emails", []) or []:
            person = entry.get("value", "")
            first = (entry.get("first_name") or "").strip()
            last = (entry.get("last_name") or "").strip()
            name = f"{first} {last}".strip() or person
            out.append(ContactCandidate(
                name=name, email=person,
                title=(entry.get("position") or ""),
                company=job.get("company", ""), provider=self.name))
        return out


class ApolloProvider(ContactProvider):
    """apollo.io people-search adapter (port; org search scoped by company)."""

    name = "apollo"
    BASE = "https://api.apollo.io/v1/mixed_people/search"

    def __init__(self, api_key: str = ""):
        super().__init__(rate=1.0, per=1.0)
        self.api_key = api_key or os.getenv("JOBAGENT_APOLLO_API_KEY", "")
        self.available = bool(self.api_key)

    async def _find(self, job: dict) -> list[ContactCandidate]:
        if not self.available:
            return []
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(self.BASE, json={
                "api_key": self.api_key,
                "organization_names": [job.get("company", "")],
                "person_titles": ["recruiter", "talent acquisition",
                                  "engineering manager", "head of engineering"],
                "page": 1, "per_page": 10})
            resp.raise_for_status()
            people = (resp.json() or {}).get("people", []) or []
        out: list[ContactCandidate] = []
        for p in people:
            name = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
            out.append(ContactCandidate(
                name=name, email=p.get("email") or "",
                title=p.get("title") or "",
                company=job.get("company", ""),
                linkedin_url=p.get("linkedin_url") or "",
                provider=self.name))
        return out


class WebSearchProvider(ContactProvider):
    """Existing DuckDuckGo heuristic (app/contact_finder.py) as an adapter."""

    name = "web_search"

    def __init__(self):
        super().__init__(rate=0.5, per=2.0)  # DDG dislikes fast loops
        self.available = True

    async def _find(self, job: dict) -> list[ContactCandidate]:
        from app.contact_finder import find_hiring_contact
        result = await find_hiring_contact(
            job.get("company", ""), job.get("title", ""),
            job.get("location", "") or "")
        if not result.get("email"):
            return []
        return [ContactCandidate(
            name=result.get("name") or "",
            email=result["email"],
            title=result.get("title") or "",
            company=job.get("company", ""),
            provider=self.name)]


class ManualResearchProvider(ContactProvider):
    """Surfaces contacts Basil already saved for this company (contacts table)."""

    name = "manual"

    def __init__(self, db):
        super().__init__(rate=100.0, per=1.0)  # local DB — no throttle needed
        self.db = db
        self.available = True

    async def _find(self, job: dict) -> list[ContactCandidate]:
        company = (job.get("company") or "").lower()
        if not company:
            return []
        contacts = await self.db.get_contacts()
        out = []
        for c in contacts:
            if (c.get("company") or "").lower() != company:
                continue
            out.append(ContactCandidate(
                name=c.get("name", ""), email=c.get("email", ""),
                title=c.get("role", ""), company=c.get("company", ""),
                linkedin_url=c.get("linkedin_url", ""),
                provider=self.name))
        return out


def default_provider_chain(db, web: bool = True) -> list[ContactProvider]:
    """Fallback order: manual (Basil's own data first) → hunter → apollo → web."""
    chain: list[ContactProvider] = [ManualResearchProvider(db)]
    hunter = HunterProvider()
    if hunter.available:
        chain.append(hunter)
    apollo = ApolloProvider()
    if apollo.available:
        chain.append(apollo)
    if web:
        chain.append(WebSearchProvider())
    return chain


# ---------------------------------------------------------------- service

CACHE_TTL_DAYS = 7


class ContactResearchService:
    """Cache-first research over a provider fallback chain."""

    def __init__(self, db, providers: list[ContactProvider]):
        self.db = db
        self.providers = providers

    async def research(self, job: dict, force: bool = False) -> dict:
        cached = await self.db.get_contact_research(job["id"])
        if cached and not force and self._fresh(cached):
            # M14: cache-hit metric (never allowed to break research)
            try:
                await self.db.increment_metric("research_cache_hits")
            except Exception:  # noqa: BLE001
                pass
            return {**cached, "cache_hit": True}
        try:
            await self.db.increment_metric("research_cache_misses")
        except Exception:  # noqa: BLE001
            pass

        candidates: list[ContactCandidate] = []
        used_provider = ""
        for provider in self.providers:
            if not provider.available:
                continue
            found = await provider.find(job)
            if found:
                candidates = found
                used_provider = provider.name
                break  # first provider with results wins (fallback semantics)
        ranked = rank_candidates(candidates, job.get("title", ""))
        status = "found" if ranked else "not_found"
        await self.db.save_contact_research(
            job["id"], job.get("company", ""), status,
            used_provider or "none", [c.to_dict() for c in ranked])
        return {
            "job_id": job["id"], "company": job.get("company", ""),
            "status": status, "provider": used_provider or "none",
            "candidates": [c.to_dict() for c in ranked],
            "researched_at": _now_iso(), "cache_hit": False,
        }

    async def select_candidate(self, job: dict, index: int) -> dict:
        """Persist the chosen candidate onto the job + contacts table."""
        cached = await self.db.get_contact_research(job["id"])
        if not cached or not cached.get("candidates"):
            raise ValueError("No researched candidates for this job — run research first")
        cands = cached["candidates"]
        if index < 0 or index >= len(cands):
            raise IndexError(f"candidate index {index} out of range (0..{len(cands) - 1})")
        c = cands[index]
        await self.db.update_job_contact(
            job["id"], hiring_manager_name=c.get("name", ""),
            hiring_manager_email=c.get("email", ""),
            hiring_manager_title=c.get("title", ""))
        existing = await self.db.get_contacts()
        dup = next((x for x in existing
                    if x.get("email") and c.get("email")
                    and x["email"].lower() == c["email"].lower()), None)
        if dup:
            contact_id = dup["id"]
        else:
            contact_id = await self.db.create_contact(
                name=c.get("name") or c.get("email") or "Unknown",
                email=c.get("email", ""), company=c.get("company", ""),
                role=c.get("title", ""), linkedin_url=c.get("linkedin_url", ""),
                notes=f"M7 research: {c.get('why_selected', '')} "
                      f"(confidence {c.get('confidence')}, via {c.get('provider')})")
        await self.db.add_event(
            job["id"], "note",
            f"Contact selected: {c.get('name') or c.get('email')} "
            f"({c.get('role_type')}, confidence {c.get('confidence')})")
        return {"job_id": job["id"], "contact_id": contact_id, "candidate": c}

    @staticmethod
    def _fresh(row: dict) -> bool:
        try:
            ts = datetime.fromisoformat(str(row.get("researched_at")).replace("Z", "+00:00"))
            return datetime.now(timezone.utc) - ts < timedelta(days=CACHE_TTL_DAYS)
        except (ValueError, TypeError):
            return False


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
