"""EvidenceChecker (M2) — the HARD gate on all generated candidate artifacts.

Ported and hardened from DavidAromose/job-application-pipeline's fabrication
check (MIT): numbers absent from the candidate corpus are fabrication, and
generated lines must clear a similarity floor against the verified corpus.
Upgraded from upstream's warning-only behavior to a hard FAIL with
machine-readable offending claims, per master prompt Phase 4.

Rules enforced on generated text:
  1. fabricated_number    — a number in the output absent from verified evidence
                            (years 1990-2035 excluded so dates are not flagged)
  2. unsupported_claim    — a content line whose best Jaccard similarity to the
                            verified corpus is below the floor
  3. unsupported_skill    — a candidate-known skill present in the output but
                            absent from VERIFIED evidence (Critical Test #1)
  4. personal_fact_mismatch — the output asserts a personal circumstance
                            (relocation target, visa sponsorship stance,
                            willingness to relocate) that CONTRADICTS the
                            candidate's verified evidence. Proven live in run
                            2026-09-24_125119: Singapore -> Amsterdam and
                            `sponsorship welcomed` -> `required`, straight
                            through the other three rules.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.evidence_store import normalize_skill

logger = logging.getLogger(__name__)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _token_set(text: str) -> set[str]:
    return set(re.sub(r"[^a-z0-9\s]", " ", text.lower()).split())


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# --- personal-fact extraction (Stage-8 D2 / NEXT_5_PLAN N4) ------------------
#
# These describe the CANDIDATE, so they may only come from the candidate's own
# evidence — never from the job description. The three rules above cannot see
# them: "Amsterdam" and "welcomed" carry no digits, they are not skills, and a
# rewritten relocation line differs from its verified original by a single
# token — far above the similarity floor. That is exactly how run
# `2026-09-24_125119` shipped Singapore -> Amsterdam and
# `sponsorship welcomed` -> `sponsorship required`.

# A place name; stops at the separators used in a resume header line
# (` | `), parenthesis, brackets, quotes and newlines.
_PLACE_RE = re.compile(r"([A-Za-z][A-Za-z.,\- ]{0,40})")
_RELOCATION_RE = re.compile(
    r"relocat(?:e|es|ed|ing|ion)|moving\s+to", re.IGNORECASE)
_SPONSORSHIP_RE = re.compile(r"\bsponsorship\b", re.IGNORECASE)
_NEG_RELOCATION_RE = re.compile(
    r"(?:not\s+(?:open|willing)|unwilling|no\s+relocation|unable\s+to\s+relocat)",
    re.IGNORECASE)
_STANCE_NOT_REQUIRED = re.compile(
    r"\bnot\s+(?:require[sd]?|need(?:ed)?|necessary)\b|\bno\s+sponsorship\b",
    re.IGNORECASE)
_STANCE_REQUIRED = re.compile(
    r"\brequire[sd]?\b|\bneeds?\b|\bessential\b", re.IGNORECASE)
_STANCE_WELCOMED = re.compile(
    r"\bwelcome[ds]?\b|\bpreferred\b|\boptional\b", re.IGNORECASE)


def _segments(text: str) -> list[str]:
    """Sentence-ish chunks that never cross a `|` (resume header separators)."""
    out: list[str] = []
    for line in (text or "").splitlines():
        for part in re.split(r"[|;\n]", line):
            if part.strip():
                out.append(part.strip())
    return out


def relocation_targets(text: str) -> set[str]:
    """Place names asserted as a relocation destination."""
    targets: set[str] = set()
    for seg in _segments(text):
        for m in _RELOCATION_RE.finditer(seg):
            tail = seg[m.end():]
            tail = re.sub(r"^\s*(?:to|:|from)\s*", "", tail, flags=re.I)
            place = _PLACE_RE.match(tail)
            if not place:
                continue
            name = place.group(1).strip(" .,-")
            if name:
                targets.add(name)
    return targets


def sponsorship_stances(text: str) -> set[str]:
    """Visa-sponsorship stances asserted: required / welcomed / not_required."""
    stances: set[str] = set()
    for seg in _segments(text):
        if not _SPONSORSHIP_RE.search(seg):
            continue
        if _STANCE_NOT_REQUIRED.search(seg):
            stances.add("not_required")
        elif _STANCE_REQUIRED.search(seg):
            stances.add("required")
        elif _STANCE_WELCOMED.search(seg):
            stances.add("welcomed")
    return stances


def relocation_willingness(text: str) -> str | None:
    """'open' or 'closed', or None when the text says nothing about it."""
    for seg in _segments(text):
        if not _RELOCATION_RE.search(seg):
            continue
        return "closed" if _NEG_RELOCATION_RE.search(seg) else "open"
    return None


def extract_numbers(text: str) -> set[str]:
    """Numeric tokens that could indicate fabricated metrics.

    Years and date-like values (1990-2035) are excluded so employment dates
    and date components are not misread as invented metrics.
    """
    tokens = re.findall(r"\d[\d.,]*\d|\d", text)
    out: set[str] = set()
    for tok in tokens:
        clean = tok.strip(".,")
        if not clean:
            continue
        if clean.isdigit() and 1990 <= int(clean) <= 2035:
            continue
        out.add(clean)
    return out


@dataclass
class EvidenceCheckResult:
    ok: bool
    failures: list[dict] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)
    checked_at: str = ""

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "failures": self.failures,
            "warnings": self.warnings,
            "checked_at": self.checked_at,
        }


class EvidenceChecker:
    """Hard gate: generated artifacts pass or fail, with machine-readable reasons."""

    def __init__(
        self,
        verified_values: list[str],
        similarity_floor: float = 0.18,
        min_line_length: int = 20,
    ):
        self.verified_values = list(verified_values)
        self.similarity_floor = similarity_floor
        self.min_line_length = min_line_length
        # Flattened evidence, used by the personal-fact rules to compare the
        # output's claims against what the candidate actually said.
        self._corpus_text = "\n".join(self.verified_values)
        self._corpus_token_sets = [_token_set(v) for v in self.verified_values]
        self._verified_numbers: set[str] = set()
        for v in self.verified_values:
            self._verified_numbers |= extract_numbers(v)
        # A skill is evidence-backed if it appears anywhere in the verified corpus
        # (standalone entry or inside a verified sentence).
        self._verified_corpus_normalized = normalize_skill(" ".join(self.verified_values))

    # ------------------------------------------------------------------ rules
    def _check_numbers(self, generated_text: str, failures: list[dict]) -> None:
        numbers = extract_numbers(generated_text)
        fabricated = sorted(numbers - self._verified_numbers)
        if fabricated:
            failures.append({
                "type": "fabricated_number",
                "items": fabricated,
                "detail": "Numbers in output not present in verified evidence",
            })

    def _check_similarity(self, generated_text: str, failures: list[dict]) -> None:
        lines = [ln.strip(" -*•\t") for ln in generated_text.splitlines()]
        lines = [ln for ln in lines if ln]
        for ln in lines:
            if len(ln) < self.min_line_length:
                continue
            lt = _token_set(ln)
            best = 0.0
            for ct in self._corpus_token_sets:
                # Jaccard punishes a short line against a long corpus entry;
                # containment (how much of the LINE is covered by the entry)
                # is the fairer test, so either one passing is sufficient.
                containment = (len(lt & ct) / len(lt)) if lt else 0.0
                sim = max(_jaccard(lt, ct), containment)
                if sim > best:
                    best = sim
                if best >= self.similarity_floor:
                    break
            if best < self.similarity_floor:
                failures.append({
                    "type": "unsupported_claim",
                    "items": [ln[:200]],
                    "detail": f"Best similarity {best:.2f} below floor {self.similarity_floor}",
                })

    def _check_thin_lines(self, generated_text: str, warnings: list[dict]) -> None:
        lines = [ln.strip(" -*•\t") for ln in generated_text.splitlines()]
        thin = [ln for ln in lines if 0 < len(ln) < self.min_line_length]
        if thin:
            warnings.append({
                "type": "thin_line",
                "items": thin[:10],
                "detail": "Very short lines (possibly formatting debris)",
            })

    def _check_skills(
        self,
        generated_text: str,
        candidate_skill_values: list[str],
        failures: list[dict],
    ) -> None:
        """Fail if a skill the candidate has listed anywhere appears in the
        generated text but is NOT backed by VERIFIED evidence (Critical Test #1)."""
        if not candidate_skill_values:
            return
        unsupported = []
        for skill in candidate_skill_values:
            ns = normalize_skill(skill)
            if len(ns) < 2:
                continue
            if ns in self._verified_corpus_normalized:
                continue  # backed by verified evidence — free to use
            pattern = re.compile(
                rf"(?<![a-z0-9+#]){re.escape(skill.lower().strip())}(?![a-z0-9+#])",
                re.IGNORECASE,
            )
            if pattern.search(generated_text):
                unsupported.append(skill)
        if unsupported:
            failures.append({
                "type": "unsupported_skill",
                "items": sorted(set(unsupported)),
                "detail": "Skills claimed in output but not present in VERIFIED evidence",
            })

    # ------------------------------------------------------------------ gate
    def _check_personal_facts(
        self,
        generated_text: str,
        failures: list[dict],
        warnings: list[dict],
    ) -> None:
        """Personal circumstances must agree with the candidate's evidence.

        Deliberately **symmetric about the evidence**:

        - evidence says X, output says Y  -> **failure** (a proven contradiction)
        - evidence says nothing, output asserts something -> **warning** (we
          cannot disprove it, and failing would turn this gate into a wall that
          rejects honest resumes because a phrase was parsed differently)
        - evidence says X, output omits it -> fine (omission is never fabrication)
        """
        ref = self._corpus_text
        checks = (
            ("relocation target", relocation_targets(generated_text),
             relocation_targets(ref)),
            ("visa sponsorship stance", sponsorship_stances(generated_text),
             sponsorship_stances(ref)),
            ("relocation willingness",
             {relocation_willingness(generated_text)} - {None},
             {relocation_willingness(ref)} - {None}),
        )
        for label, claimed, evidence in checks:
            if not claimed:
                continue          # output says nothing — omission is safe
            if not evidence:
                warnings.append({
                    "type": "unsupported_personal_fact",
                    "items": sorted(claimed),
                    "detail": (f"Output asserts a {label} the candidate's "
                               "evidence never states — confirm before shipping"),
                })
                continue
            contradicted = claimed - evidence
            if contradicted:
                failures.append({
                    "type": "personal_fact_mismatch",
                    "items": sorted(contradicted),
                    "detail": (f"Output says {label}={sorted(contradicted)} but "
                               f"verified evidence says {sorted(evidence)}. "
                               "Personal facts come from evidence, never the JD."),
                })

    def check(
        self,
        generated_text: str,
        candidate_skill_values: list[str] | None = None,
    ) -> EvidenceCheckResult:
        failures: list[dict] = []
        warnings: list[dict] = []

        self._check_numbers(generated_text, failures)
        self._check_similarity(generated_text, failures)
        self._check_thin_lines(generated_text, warnings)
        if candidate_skill_values:
            self._check_skills(generated_text, candidate_skill_values, failures)
        self._check_personal_facts(generated_text, failures, warnings)

        result = EvidenceCheckResult(
            ok=not failures,
            failures=failures,
            warnings=warnings,
            checked_at=_utc_now(),
        )
        if not result.ok:
            logger.warning(
                "EvidenceChecker FAIL: %d failure(s): %s",
                len(failures),
                [f["type"] for f in failures],
            )
        return result
