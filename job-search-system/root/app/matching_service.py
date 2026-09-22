"""M6: Application service bridging live config -> HybridMatcher.

Builds the CandidateProfile from the evidence store (VERIFIED claims only —
Golden Rule 5), search_config (targets + work preferences), and the country
registry (visa keywords). Deterministic end to end.
"""

from __future__ import annotations

import logging

from app.hybrid_matcher import (
    DEFAULT_WEIGHTS,
    CandidateProfile,
    HybridMatcher,
    RagProvider,
    _validated_weights,
)
from app.evidence_store import normalize_skill

logger = logging.getLogger(__name__)


def build_candidate_profile(evidence_store, search_config: dict | None,
                            registry=None) -> CandidateProfile:
    """Assemble the candidate profile from the live evidence store + config.

    Golden Rule 5: only VERIFIED claims feed the matching corpus. Skills carry
    status discipline: VERIFIED skills count toward match credit; DO_NOT_USE
    skills become hard blockers; UNVERIFIED/DISPUTED are excluded from credit.
    """
    search_config = search_config or {}
    profile = CandidateProfile()

    if evidence_store is not None:
        # Keep RAW values ("Azure OpenAI") for phrase matching in job text;
        # normalized form is only the dedup key. normalize_skill strips spaces
        # ("azureopenai"), which would make multi-word skills unmatchable
        # (found live in E2E: skills component scored 66.7 instead of 100).
        seen: set[str] = set()
        verified_raw: set[str] = set()
        for v in evidence_store.verified_values(["skills"]):
            n = normalize_skill(v)
            if n and n not in seen:
                seen.add(n)
                verified_raw.add(v)
        profile.verified_skills = verified_raw
        profile.verified_corpus = evidence_store.verified_corpus_lines()
        dnu_seen: set[str] = set()
        dnu_raw: set[str] = set()
        for c in evidence_store.by_status("DO_NOT_USE"):
            if c.category == "skills":
                n = normalize_skill(c.value)
                if n and n not in dnu_seen:
                    dnu_seen.add(n)
                    dnu_raw.add(c.value)
        profile.do_not_use_skills = dnu_raw

    titles = search_config.get("job_titles") or []
    norm_titles = []
    for t in titles[:6]:
        if isinstance(t, dict):
            t = t.get("title", "")
        if isinstance(t, str) and t.strip():
            norm_titles.append(t.strip())
    profile.target_titles = norm_titles
    profile.seniority = search_config.get("seniority", "") or ""

    prefs = search_config.get("_hybrid_prefs") or {}
    profile.prefers_remote = bool(prefs.get("prefers_remote", True))
    profile.requires_sponsorship = bool(prefs.get("requires_sponsorship", True))

    return profile


def collect_visa_keywords(registry) -> list[str]:
    """Union of sponsorship keywords across ENABLED countries (M3 reuse)."""
    kws: set[str] = set()
    if registry is not None:
        for c in registry.enabled_countries():
            # Country exposes sponsorship_keywords directly (visa dict is in to_dict())
            kws.update(getattr(c, "sponsorship_keywords", None) or [])
    return sorted(kws)


async def build_hybrid_matcher_async(app_state, db) -> tuple[HybridMatcher, dict]:
    """Async factory — the one routers and the scheduler should use."""
    search_config = await db.get_search_config()
    prefs = await db.get_hybrid_prefs()
    if search_config is None:
        search_config = {}
    search_config["_hybrid_prefs"] = prefs

    profile = build_candidate_profile(
        getattr(app_state, "evidence_store", None),
        search_config,
        getattr(app_state, "country_registry", None),
    )
    weights = _validated_weights(await db.get_hybrid_weights() or DEFAULT_WEIGHTS)
    keywords = collect_visa_keywords(getattr(app_state, "country_registry", None))

    rag: RagProvider = RagProvider()  # local TF-IDF default (zero cost, deterministic)
    emb = getattr(app_state, "embedding_client", None)
    if emb is not None:
        from app.hybrid_matcher import OpenAIRagProvider
        rag = OpenAIRagProvider(emb)  # has sync fallback via base class

    matcher = HybridMatcher(profile, weights=weights, visa_keywords=keywords,
                            rag_provider=rag)
    meta = {
        "verified_skills": len(profile.verified_skills),
        "corpus_lines": len(profile.verified_corpus),
        "target_titles": profile.target_titles,
        "weights": weights,
        "visa_keywords": len(keywords),
        "rag_provider": type(rag).__name__,
        "do_not_use_skills": len(profile.do_not_use_skills),
    }
    return matcher, meta


async def score_all_unscored(app_state, db, limit: int = 2000) -> dict:
    """Score every unscored, classified, non-dismissed job with the hybrid engine.

    Zero AI cost — this is the free deterministic baseline layer. Returns a
    machine-readable run summary (count, avg, blockers found).
    """
    jobs = await db.get_unscored_jobs(limit=limit)
    if not jobs:
        return {"scored": 0, "total": 0, "avg": None, "blockers": 0, "engine": "hybrid-m6"}

    matcher, meta = await build_hybrid_matcher_async(app_state, db)
    scores = matcher.score_jobs(jobs)
    blockers = 0
    total_weight = 0.0
    for s in scores:
        d = s.to_db_dict()
        await db.upsert_hybrid_score(
            s.job_id, d["match_score"], d["match_reasons"], d["concerns"],
            d["suggested_keywords"], d["role_match"],
            d["component_scores"], d["hard_blockers"])
        if d["hard_blockers"]:
            blockers += 1
        total_weight += d["match_score"]

    avg = round(total_weight / len(scores), 1) if scores else None
    logger.info("Hybrid scoring: %d jobs, avg=%s, blockers=%d, meta=%s",
                len(scores), avg, blockers, meta)
    return {"scored": len(scores), "total": len(jobs), "avg": avg,
            "blockers": blockers, "engine": "hybrid-m6", "meta": meta}
