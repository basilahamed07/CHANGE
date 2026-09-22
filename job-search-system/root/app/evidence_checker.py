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
