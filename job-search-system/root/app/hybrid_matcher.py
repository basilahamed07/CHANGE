"""M6: Hybrid matching engine — deterministic components + TF-IDF ATS overlap + RAG.

Golden Rule 4: deterministic code for deterministic problems. This module owns ALL
arithmetic (skill overlap, role signals, location/visa/recency, TF-IDF). No LLM.
Python owns the math; the AI scorer (app/matcher.py) adds semantic judgment on top.

Score composition (all components 0..100, combined by configurable weights):
  skills     — verified-skill overlap between candidate evidence and the job text
               (boundary-aware token matching, partial credit for adjacency)
  role       — role-track alignment: does the job title/requirement language match
               the candidate's target titles (from search_config)?
  location   — work-type + region fit (remote/hybrid/onsite vs candidate preference)
  visa       — sponsorship signals (reuses M3 visa_engine, deterministic)
  recency    — freshness boost from M5 freshness evidence (fresh > stale > unknown)
  semantic   — RAG component: TF-IDF cosine similarity between the job and the
               candidate's VERIFIED evidence corpus (local, zero-cost default)

Hard blockers short-circuit to a capped score (default 25) with reasons:
  - explicit "no sponsorship" language when candidate needs sponsorship
  - a must-have skill the candidate explicitly lists as DO_NOT_USE
Output is machine-readable: overall_score, component_scores, matched/missing
requirements, hard_blockers, advantages, explanation.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field

from app.evidence_store import normalize_skill
from app.freshness import FRESH, STALE, UNKNOWN, assess_freshness
from app.visa_engine import scan_visa_mentions

# --------------------------------------------------------------------------
# Skill adjacency (deterministic partial credit, from CareerPulse-era mapping)

SKILL_ADJACENCY: dict[str, set[str]] = {
    "azure": {"openai", "azureopenai", "az", "cloud"},
    "aws": {"lambda", "s3", "ec2", "cloud"},
    "gcp": {"bigquery", "googlecloud", "cloud"},
    "langchain": {"llm", "agents", "rag"},
    "langgraph": {"langchain", "agents", "llm"},
    "llm": {"gpt", "openai", "genai", "genai"},
    "rag": {"embeddings", "vectordb", "llm", "retrieval"},
    "pytorch": {"tensorflow", "deeplearning", "ml"},
    "tensorflow": {"pytorch", "deeplearning", "ml"},
    "docker": {"kubernetes", "containers", "devops"},
    "kubernetes": {"docker", "k8s", "devops"},
    "fastapi": {"python", "rest", "api"},
    "django": {"python", "rest", "api"},
    "flask": {"python", "rest", "api"},
    "postgresql": {"sql", "database"},
    "mysql": {"sql", "database"},
    "mlops": {"ml", "devops", "ci/cd"},
    "nlp": {"llm", "ml", "textprocessing"},
    "spark": {"bigdata", "etl", "scala"},
    "airflow": {"etl", "orchestration", "dags"},
}

STOP_TOKENS = {
    "and", "or", "the", "with", "for", "a", "an", "to", "of", "in", "on",
    "experience", "years", "strong", "good", "excellent", "plus", "etc",
}


# --------------------------------------------------------------------------
@dataclass
class CandidateProfile:
    """What the matcher needs to know about the candidate — all from evidence/config."""

    verified_skills: set[str] = field(default_factory=set)      # normalized
    all_status_skills: set[str] = field(default_factory=set)    # incl. UNVERIFIED (for blockers)
    do_not_use_skills: set[str] = field(default_factory=set)    # normalized
    requires_sponsorship: bool = False
    prefers_remote: bool = False
    target_titles: list[str] = field(default_factory=list)
    seniority: str = ""
    verified_corpus: list[str] = field(default_factory=list)    # VERIFIED claim lines


@dataclass
class HybridScore:
    """Machine-readable hybrid score for one job."""

    job_id: int
    overall_score: int
    component_scores: dict[str, float]
    matched_requirements: list[str]
    missing_requirements: list[str]
    hard_blockers: list[str]
    advantages: list[str]
    explanation: str
    engine: str = "hybrid-m6"

    def to_db_dict(self) -> dict:
        return {
            "match_score": self.overall_score,
            "match_reasons": self.matched_requirements,
            "concerns": self.missing_requirements + self.hard_blockers,
            "suggested_keywords": self.advantages,
            "role_match": self.component_scores.get("role", 0) >= 50,
            "component_scores": self.component_scores,
            "hard_blockers": self.hard_blockers,
        }


# --------------------------------------------------------------------------
# Tokenization + TF-IDF (pure python — no new dependencies)


def _tokens(text: str) -> list[str]:
    t = (text or "").lower()
    t = re.sub(r"[^a-z0-9+#./\- ]", " ", t)
    raw = re.split(r"[\s/,\-]+", t)
    out = []
    for tok in raw:
        tok = tok.strip(".+#/")
        if not tok or tok in STOP_TOKENS or tok.isdigit():
            continue
        out.append(tok)
    return out


class TfidfIndex:
    """Tiny TF-IDF cosine index over documents (jobs + evidence corpus)."""

    def __init__(self, documents: list[str]):
        self.doc_tokens = [_tokens(d) for d in documents]
        df = Counter()
        for toks in self.doc_tokens:
            df.update(set(toks))
        self.idf = {t: math.log((1 + len(documents)) / (1 + n)) + 1.0
                    for t, n in df.items()}
        self.doc_vecs = [self._tfidf(c) for c in self.doc_tokens]

    def _tfidf(self, tokens: list[str]) -> dict[str, float]:
        tf = Counter(tokens)
        vec = {}
        for tok, n in tf.items():
            idf = self.idf.get(tok)
            if idf is None:  # unseen term — default weight
                idf = math.log((1 + len(self.doc_tokens)) / 1) + 1.0
            vec[tok] = (n / max(1, len(tokens))) * idf
        return vec

    @staticmethod
    def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
        if not a or not b:
            return 0.0
        num = sum(v * b.get(t, 0.0) for t, v in a.items())
        da = math.sqrt(sum(v * v for v in a.values()))
        db = math.sqrt(sum(v * v for v in b.values()))
        if da == 0 or db == 0:
            return 0.0
        return num / (da * db)

    def query(self, text: str) -> list[tuple[int, float]]:
        """Return [(doc_index, cosine_sim)] sorted desc."""
        qv = self._tfidf(_tokens(text))
        sims = [(i, self._cosine(qv, dv)) for i, dv in enumerate(self.doc_vecs)]
        sims.sort(key=lambda x: x[1], reverse=True)
        return sims


# --------------------------------------------------------------------------
# Deterministic components


def _skill_in_text(text_lower: str, raw_skill: str) -> bool:
    """Boundary-aware skill match. Single words use word-boundary regex; phrases
    (e.g. 'azure openai', 'ci/cd') match as word sequences with punctuation
    allowed between words. Never matches inside a larger token ('ai' != 'said').
    """
    words = [w for w in re.split(r"[^a-z0-9+#]+", (raw_skill or "").lower()) if w]
    if not words or not text_lower:
        return False
    if len(words) == 1:
        return re.search(r"(?<![a-z0-9])" + re.escape(words[0]) + r"(?![a-z0-9])",
                         text_lower) is not None
    pattern = (r"(?<![a-z0-9])" + r"[^a-z0-9]{1,10}".join(re.escape(w) for w in words)
               + r"(?![a-z0-9])")
    return re.search(pattern, text_lower) is not None


def component_skills(job_text: str, profile: CandidateProfile) -> tuple[float, list[str], list[str]]:
    """Verified-skill overlap: 100 * matched / (matched + missing). Returns (score, matched, missing)."""
    matched: list[str] = []
    missing: list[str] = []
    for raw in profile.verified_skills:
        if not raw or not normalize_skill(raw):
            continue
        if _skill_in_text(job_text.lower(), raw):
            matched.append(raw)
        else:
            missing.append(raw)
    # Adjacent partial credit: a missing skill with an adjacency hit on a matched one
    matched_norms = {normalize_skill(m) for m in matched}
    adjacent_hits = 0
    for m in missing:
        norm = normalize_skill(m)
        for adj in SKILL_ADJACENCY.get(norm, set()):
            if adj in matched_norms:
                adjacent_hits += 1
                break
    denom = len(matched) + len(missing)
    if denom == 0:
        return 50.0, matched, missing  # nothing comparable — neutral
    base = 100.0 * len(matched) / denom
    partial = 100.0 * (adjacent_hits / denom) * 0.5
    return min(100.0, base + partial), matched, missing


def component_role(job: dict, profile: CandidateProfile) -> float:
    """Role-track alignment from target titles vs job title/requirement language."""
    title = (job.get("title") or "").lower()
    desc = (job.get("description") or "").lower()
    hay = f"{title} {desc[:600]}"
    if not profile.target_titles:
        return 50.0  # no declared targets — neutral
    hay_toks = {w for w in _tokens(hay) if len(w) >= 3}
    best = 0.0
    for t in profile.target_titles:
        if _skill_in_text(title, t):
            best = max(best, 100.0)
        elif _skill_in_text(hay, t):
            best = max(best, 60.0)
        else:
            # token overlap fallback (e.g. 'AI Engineer' vs 'Machine Learning Engineer')
            t_toks = {w for w in _tokens(t) if len(w) >= 3}
            if t_toks and t_toks & hay_toks:
                best = max(best, 40.0)
    return best


def component_location(job: dict, profile: CandidateProfile) -> float:
    """Work-type fit: remote preference vs job location string."""
    loc = f"{job.get('location') or ''} {job.get('title') or ''}".lower()
    remote_job = "remote" in loc
    hybrid_job = "hybrid" in loc
    if profile.prefers_remote:
        return 100.0 if remote_job else (60.0 if hybrid_job else 30.0)
    return 80.0 if (remote_job or hybrid_job) else 60.0


def component_visa(job: dict, profile: CandidateProfile, keywords: list[str]) -> float:
    """Deterministic visa signals. Sponsorship mention is good; explicit refusal blocks."""
    text = (job.get("description") or "")
    scan = scan_visa_mentions(text, keywords)
    refusal = re.search(
        r"no (?:visa )?sponsorship|not (?:eligible|offer) (?:for )?sponsorship|"
        r"must (?:be (?:authorized|eligible) )?(?:to work|without sponsorship)|"
        r"without (?:visa )?sponsorship|citizenship (?:required|is required)",
        text.lower())
    if refusal and profile.requires_sponsorship:
        return 0.0  # hard-blocker signal (blocker recorded separately)
    if scan["sponsors_international"]:
        return 100.0
    if profile.requires_sponsorship:
        return 40.0  # silent on sponsorship — uncertain
    return 70.0  # candidate doesn't need it — mild weight


def component_recency(job: dict, now=None) -> float:
    """Freshness-aware boost from M5 evidence (no AI)."""
    posted = job.get("posted_date") or job.get("created_at")
    ev = assess_freshness(posted, now=now)
    if ev["state"] == FRESH:
        age = ev.get("age_days")
        return 100.0 if age is not None and age <= 2 else 85.0
    if ev["state"] == STALE:
        return 30.0
    return 45.0  # DATE_UNKNOWN: neutral-low (never treated as fresh — Critical #3 spirit)


def component_semantic(job_text: str, profile: CandidateProfile,
                       rag: "RagProvider") -> float:
    """RAG semantic component: job vs VERIFIED evidence corpus."""
    return rag.similarity_score(job_text, profile.verified_corpus)


# --------------------------------------------------------------------------
# RAG layer — EmbeddingProvider abstraction (local TF-IDF default, zero cost)


class RagProvider:
    """Base RAG provider. Local default = TF-IDF cosine over verified evidence.

    Golden Rule 5: retrieval feeds ONLY relevant VERIFIED evidence into anything
    downstream. UNVERIFIED/DISPUTED/DO_NOT_USE claims never enter this corpus.
    """

    def embed(self, text: str) -> dict[str, float]:
        raise NotImplementedError

    def similarity_score(self, query_text: str, corpus: list[str]) -> float:
        if not corpus:
            return 50.0  # neutral when no verified evidence exists
        idx = TfidfIndex(corpus)
        sims = idx.query(query_text)
        top = [s for _, s in sims[:3]]
        if not top or top[0] <= 0:
            return 0.0
        # Map best cosine (~0..1) onto 0..100 with diminishing returns
        return min(100.0, 100.0 * (1 - math.exp(-2.2 * top[0])))

    def retrieve_relevant(self, query_text: str, corpus: list[str],
                          limit: int = 3) -> list[str]:
        """Retrieve the most relevant VERIFIED evidence lines for this job.

        Used to feed ONLY relevant evidence into AI prompts (Golden Rule 5).
        """
        if not corpus:
            return []
        idx = TfidfIndex(corpus)
        sims = idx.query(query_text)
        return [corpus[i] for i, s in sims[:limit] if s > 0.02]


class OpenAIRagProvider(RagProvider):
    """Optional remote embedding provider (OpenAI-compatible). Never raises —
    falls back to neutral 50 on any failure so scoring always completes."""

    def __init__(self, embedding_client):
        self.client = embedding_client

    async def similarity_score_async(self, query_text: str, corpus: list[str]) -> float:
        try:
            if not corpus:
                return 50.0
            qv = await self.client.embed(query_text[:8000])
            cvecs = await self.client.embed_batch([c[:8000] for c in corpus])
            import struct

            def cos(a, b):
                num = sum(x * y for x, y in zip(a, b))
                da = math.sqrt(sum(x * x for x in a))
                db = math.sqrt(sum(x * x for x in b))
                return num / (da * db) if da and db else 0.0

            best = max((cos(qv, cv) for cv in cvecs), default=0.0)
            return min(100.0, 100.0 * (1 - math.exp(-2.2 * max(0.0, best))))
        except Exception as e:  # never fail scoring over embeddings
            return 50.0


# --------------------------------------------------------------------------
# Blockers + engine


def _requirement_terms(job: dict) -> list[str]:
    """Extract requirement-ish sentences from the description (deterministic)."""
    desc = job.get("description") or ""
    out = []
    for sent in re.split(r"[.\n]", desc):
        s = sent.strip()
        if re.search(r"\b(must have|required|require|expertise|proficien|experience (?:with|in)|solid|deep)\b",
                     s.lower()) and 10 < len(s) < 200:
            out.append(s)
    return out[:8]


def detect_hard_blockers(job: dict, profile: CandidateProfile,
                         keywords: list[str]) -> list[str]:
    """Hard blockers — deterministic, evidence-aware. Short-circuit the score."""
    blockers: list[str] = []
    text = (job.get("description") or "").lower()
    if profile.requires_sponsorship and re.search(
            r"no (?:visa )?sponsorship|without (?:visa )?sponsorship|"
            r"citizenship (?:required|is required)", text):
        blockers.append("NO_SPONSORSHIP_STATED")
    for s in profile.do_not_use_skills:
        if _skill_in_text(text, str(s)):
            blockers.append(f"DO_NOT_USE_SKILL_{str(s).upper().replace(' ', '_')}")
    return blockers


DEFAULT_WEIGHTS = {
    "skills": 0.35,
    "role": 0.15,
    "location": 0.10,
    "visa": 0.10,
    "recency": 0.10,
    "semantic": 0.20,
}

BLOCKER_CAP = 25


class HybridMatcher:
    """Deterministic hybrid matcher. Same inputs => same outputs (no LLM)."""

    def __init__(self, profile: CandidateProfile, weights: dict | None = None,
                 visa_keywords: list[str] | None = None,
                 rag_provider: RagProvider | None = None):
        self.profile = profile
        self.weights = _validated_weights(weights or dict(DEFAULT_WEIGHTS))
        self.visa_keywords = visa_keywords or []
        self.rag = rag_provider or RagProvider()

    def score_job(self, job: dict, now=None) -> HybridScore:
        text = f"{job.get('title') or ''}\n{job.get('description') or ''}"
        blockers = detect_hard_blockers(job, self.profile, self.visa_keywords)

        skill_score, matched, missing = component_skills(text, self.profile)
        role_score = component_role(job, self.profile)
        loc_score = component_location(job, self.profile)
        visa_score = component_visa(job, self.profile, self.visa_keywords)
        rec_score = component_recency(job, now=now)
        sem_score = self.rag.similarity_score(text, self.profile.verified_corpus)

        components = {
            "skills": round(skill_score, 1),
            "role": round(role_score, 1),
            "location": round(loc_score, 1),
            "visa": round(visa_score, 1),
            "recency": round(rec_score, 1),
            "semantic": round(sem_score, 1),
        }
        weighted = sum(self.weights[k] * components[k] for k in self.weights)

        hard_blockers: list[str] = []
        if blockers:
            weighted = min(weighted, BLOCKER_CAP)
            hard_blockers = blockers

        advantages = _advantages(components)
        explanation = _explain(job, components, weighted, hard_blockers,
                               len(matched), len(missing))

        reqs = _requirement_terms(job)
        matched_reqs = [r for r in reqs
                        if any(_skill_in_text(r.lower(), m) for m in self.profile.verified_skills)]
        missing_reqs = [r for r in reqs if r not in matched_reqs]

        return HybridScore(
            job_id=int(job.get("id") or 0),
            overall_score=int(round(max(0.0, min(100.0, weighted)))),
            component_scores=components,
            matched_requirements=matched_reqs,
            missing_requirements=missing_reqs,
            hard_blockers=hard_blockers,
            advantages=advantages,
            explanation=explanation,
        )

    def score_jobs(self, jobs: list[dict], now=None) -> list[HybridScore]:
        return [self.score_job(j, now=now) for j in jobs]


def _validated_weights(w: dict) -> dict:
    """Weights must be present for every component and sum to ~1.0."""
    merged = {**DEFAULT_WEIGHTS, **{k: float(v) for k, v in w.items() if k in DEFAULT_WEIGHTS}}
    total = sum(merged.values())
    if total <= 0:
        return dict(DEFAULT_WEIGHTS)
    return {k: v / total for k, v in merged.items()}


def _advantages(components: dict[str, float]) -> list[str]:
    adv = []
    if components.get("skills", 0) >= 70:
        adv.append("Strong verified-skill coverage of the listing")
    if components.get("semantic", 0) >= 60:
        adv.append("Profile closely resembles verified experience corpus")
    if components.get("visa", 0) >= 100:
        adv.append("Job explicitly mentions visa/sponsorship support")
    if components.get("recency", 0) >= 85:
        adv.append("Posted within the last 2 days")
    if components.get("location", 0) >= 100:
        adv.append("Remote work available (matches preference)")
    return adv


def _explain(job, components, weighted, blockers, n_match, n_missing) -> str:
    top = sorted(components.items(), key=lambda kv: kv[1], reverse=True)[:2]
    bits = [f"{k}={v:.0f}" for k, v in top]
    base = (f"Hybrid score driven by {', '.join(bits)}; "
            f"{n_match} verified skills matched, {n_missing} not found in listing.")
    if blockers:
        base += f" Hard blocker(s) {', '.join(blockers)} cap the score at {BLOCKER_CAP}."
    return base
