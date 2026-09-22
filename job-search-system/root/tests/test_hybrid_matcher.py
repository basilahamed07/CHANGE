"""M6: Hybrid matching engine tests.

Golden Rule 4: deterministic code for deterministic problems — same inputs MUST
produce identical outputs, and all arithmetic lives in Python (no LLM).
Covers: weight math, determinism, hard-blocker short-circuit, retrieval
relevance sanity, evidence discipline (VERIFIED-only corpus, DO_NOT_USE blocker).
"""
import json
from datetime import datetime, timedelta, timezone

import pytest

from app.hybrid_matcher import (
    BLOCKER_CAP,
    DEFAULT_WEIGHTS,
    CandidateProfile,
    HybridMatcher,
    RagProvider,
    TfidfIndex,
    _validated_weights,
    component_location,
    component_recency,
    detect_hard_blockers,
)
from app.matching_service import (
    build_candidate_profile,
    collect_visa_keywords,
)


def _profile(**kw) -> CandidateProfile:
    base = dict(
        verified_skills={"python", "langchain", "rag", "azure openai"},
        all_status_skills={"python", "langchain", "rag", "azure openai", "kubernetes"},
        do_not_use_skills=set(),
        requires_sponsorship=True,
        prefers_remote=True,
        target_titles=["AI Engineer", "LLM Engineer"],
        seniority="senior",
        verified_corpus=[
            "Built RAG pipelines with Python, LangChain and Azure OpenAI in production.",
            "Deployed LLM applications with FastAPI behind Docker containers.",
        ],
    )
    base.update(kw)
    return CandidateProfile(**base)


def _job(**kw) -> dict:
    base = dict(
        id=1,
        title="Senior AI Engineer",
        company="Acme",
        location="Remote",
        description="Build RAG pipelines with Python, LangChain and Azure OpenAI. "
                    "Visa sponsorship provided.",
        posted_date=(datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat(),
    )
    base.update(kw)
    return base


# ---------------- weight math ----------------

def test_weights_normalized_to_sum_one():
    w = _validated_weights({"skills": 2.0, "semantic": 1.0})
    assert abs(sum(w.values()) - 1.0) < 1e-9
    # 2:1 ratio preserved
    assert w["skills"] == pytest.approx(2 * w["semantic"])


def test_weights_reject_unknown_keys_and_fill_missing():
    w = _validated_weights({"bogus": 5.0, "skills": 1.0})
    assert "bogus" not in w
    assert set(w.keys()) == set(DEFAULT_WEIGHTS.keys())


def test_all_default_weights_sum_to_one():
    assert abs(sum(DEFAULT_WEIGHTS.values()) - 1.0) < 1e-9


# ---------------- determinism ----------------

def test_same_inputs_same_outputs():
    m = HybridMatcher(_profile())
    a = m.score_job(_job())
    b = m.score_job(_job())
    assert a.overall_score == b.overall_score
    assert a.component_scores == b.component_scores
    assert a.matched_requirements == b.matched_requirements


def test_score_in_valid_range_and_components_bounded():
    m = HybridMatcher(_profile())
    r = m.score_job(_job())
    assert 0 <= r.overall_score <= 100
    assert all(0 <= v <= 100 for v in r.component_scores.values())


# ---------------- component behavior ----------------

def test_perfect_skills_match_scores_high():
    prof = _profile()
    m = HybridMatcher(prof)
    r = m.score_job(_job())
    assert r.component_scores["skills"] >= 90  # all 4 verified skills in listing


def test_missing_skills_lower_component():
    prof = _profile()
    m = HybridMatcher(prof)
    full = m.score_job(_job())
    partial = m.score_job(_job(description="Build pipelines with Python."))
    assert partial.component_scores["skills"] < full.component_scores["skills"]


def test_remote_preference_affects_location_component():
    remote_job = _job(location="Remote")
    onsite_job = _job(location="Berlin, Germany (On-site)")
    assert component_location(remote_job, _profile()) > component_location(onsite_job, _profile())


def test_fresh_job_beats_stale_and_unknown():
    now = datetime.now(timezone.utc)
    fresh = _job(posted_date=(now - timedelta(days=1)).date().isoformat())
    stale = _job(posted_date=(now - timedelta(days=20)).date().isoformat())
    unknown = _job(posted_date=None)
    # Fresh always wins; unknown is neutral-low (never treated as fresh —
    # Critical #3 spirit); known-stale is a confirmed dead lead, ranked lowest.
    assert component_recency(fresh) > component_recency(unknown)
    assert component_recency(fresh) > component_recency(stale)
    assert component_recency(unknown) < 60  # not fresh by any means


def test_semantic_component_correlates_with_corpus():
    m = HybridMatcher(_profile())
    close = m.score_job(_job(description="Production RAG pipelines with LangChain and LLM deployment."))
    far = m.score_job(_job(description="Manage payroll administration and office logistics."))
    assert close.component_scores["semantic"] > far.component_scores["semantic"]


# ---------------- hard blockers ----------------

def test_no_sponsorship_blocker_caps_score():
    prof = _profile(requires_sponsorship=True)
    m = HybridMatcher(prof)
    r = m.score_job(_job(description="Great role. No sponsorship provided. Must be authorized to work."))
    assert "NO_SPONSORSHIP_STATED" in r.hard_blockers
    assert r.overall_score <= BLOCKER_CAP


def test_do_not_use_skill_blocks():
    prof = _profile(do_not_use_skills={"cobol"})
    m = HybridMatcher(prof)
    r = m.score_job(_job(description="Maintain legacy COBOL systems."))
    assert any(b.startswith("DO_NOT_USE_SKILL_COBOL") for b in r.hard_blockers)
    assert r.overall_score <= BLOCKER_CAP


def test_no_blockers_when_candidate_does_not_need_sponsorship():
    m = HybridMatcher(_profile(requires_sponsorship=False))
    r = m.score_job(_job(description="No sponsorship available for this role."))
    assert "NO_SPONSORSHIP_STATED" not in r.hard_blockers


def test_sponsorship_mention_is_advantage():
    # Visa keywords come from the country registry (M3) — pass them explicitly.
    m = HybridMatcher(_profile(), visa_keywords=["sponsorship"])
    r = m.score_job(_job())  # description mentions sponsorship
    assert r.component_scores["visa"] == 100.0
    assert any("sponsorship" in a.lower() for a in r.advantages)


# ---------------- evidence discipline (Golden Rule 5) ----------------

def test_unverified_skills_never_enter_corpus():
    """The corpus must contain ONLY verified claim lines."""
    class FakeStore:
        def __init__(self):
            self.claims = {}
    prof = build_candidate_profile(None, {})
    assert prof.verified_corpus == []
    assert prof.verified_skills == set()


def test_do_not_use_skill_not_in_verified_credit():
    """DO_NOT_USE skill in the listing must BLOCK, never credit."""
    prof = _profile(do_not_use_skills={"cobol"})
    m = HybridMatcher(prof)
    r = m.score_job(_job(description="COBOL maintenance role with Python scripting."))
    # Python still matches, but blocker caps the score
    assert r.overall_score <= BLOCKER_CAP
    assert any("COBOL" in b for b in r.hard_blockers)


# ---------------- TF-IDF + retrieval sanity ----------------

def test_tfidf_ranks_relevant_doc_first():
    corpus = [
        "RAG pipelines with LangChain and Azure OpenAI deployment.",
        "Payroll administration and office logistics management.",
        "Kubernetes cluster operations and observability.",
    ]
    idx = TfidfIndex(corpus)
    sims = idx.query("Build production RAG systems with LangChain")
    assert sims[0][0] == 0  # RAG doc ranks first
    assert sims[0][1] > sims[1][1]


def test_retrieval_returns_relevant_verified_lines_only():
    rp = RagProvider()
    corpus = [
        "Built RAG pipelines with Python and LangChain.",
        "Managed payroll and office supplies.",
    ]
    got = rp.retrieve_relevant("Deploy LLM RAG application", corpus, limit=1)
    assert len(got) == 1
    assert "RAG" in got[0]


def test_empty_corpus_is_neutral_not_zero():
    rp = RagProvider()
    assert rp.similarity_score("anything", []) == 50.0


def test_semantic_never_negative_or_over_100():
    rp = RagProvider()
    for text in ["x", "RAG " * 50, ""]:
        v = rp.similarity_score(text, ["some verified line"])
        assert 0.0 <= v <= 100.0


# ---------------- matching_service ----------------

def test_collect_visa_keywords_unions_enabled_countries():
    class C:  # mirrors the real Country attribute surface
        def __init__(self, kws):
            self.sponsorship_keywords = kws
    class Reg:
        def __init__(self, cs):
            self._cs = cs
        def enabled_countries(self):
            return self._cs
    reg = Reg([C(["blue card"]), C(["employment pass"]), C(["blue card"])])
    kws = collect_visa_keywords(reg)
    assert kws == ["blue card", "employment pass"]


def test_target_titles_accept_dicts_or_strings():
    prof = build_candidate_profile(None, {"job_titles": [
        {"title": "AI Engineer", "why": "x"}, "LLM Engineer"]})
    assert prof.target_titles == ["AI Engineer", "LLM Engineer"]


# ---------------- DB persistence round-trip ----------------

@pytest.mark.asyncio
async def test_hybrid_score_db_roundtrip(tmp_path):
    from app.database import Database
    db = Database(str(tmp_path / "t.db"))
    await db.init()
    jid = await db.insert_job(
        title="AI Engineer", company="C", location="Remote", salary_min=None,
        salary_max=None, description="d", url="https://x/1", posted_date="2026-09-20",
        application_method="direct", contact_email=None)
    await db.upsert_hybrid_score(
        jid, 77, ["matched python"], ["missing cobol"], ["advantage"],
        True, {"skills": 90.0, "semantic": 61.3}, [])
    got = await db.get_score(jid)
    assert got["match_score"] == 77
    assert got["component_scores"] == {"skills": 90.0, "semantic": 61.3}
    assert got["hard_blockers"] == []
    assert got["role_match"] is True
    await db.close()


@pytest.mark.asyncio
async def test_hybrid_config_upsert_survives_fresh_db(tmp_path):
    """M4 lesson regression: bare UPDATE no-ops when search_config row is absent."""
    from app.database import Database
    db = Database(str(tmp_path / "t.db"))
    await db.init()
    await db.save_hybrid_weights({"skills": 1.0})
    assert (await db.get_hybrid_weights())["skills"] == pytest.approx(1.0)
    await db.save_hybrid_prefs(False, False)
    prefs = await db.get_hybrid_prefs()
    assert prefs == {"prefers_remote": False, "requires_sponsorship": False}
    await db.close()
