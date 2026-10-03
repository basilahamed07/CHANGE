"""Stage-8 D2 — the personal-facts guard (NEXT_5_PLAN N4).

The gate previously enforced only numbers, similarity and skills. Proven live
in run `2026-09-24_125119`: DeepSeek rewrote a personal fact —

    verified:  "Open to relocation: Singapore (visa sponsorship welcomed)"
    generated: "Open to relocation: Amsterdam, Netherlands (visa sponsorship welcomed)"
    second run: "...(visa sponsorship required)"

— and the gate passed both times, because:

  * no digits are involved, so `fabricated_number` is blind to it;
  * neither place nor stance is a skill, so `_check_skills` is blind to it;
  * the line differs from its verified original by ONE token, so containment
    stays far above the 0.18 similarity floor.

Contract now:
  * contradiction with evidence  -> FAILURE (`personal_fact_mismatch`)
  * evidence silent, output asserts -> WARNING (`unsupported_personal_fact`)
  * evidence has it, output omits it -> fine (omission is not fabrication)
"""

from __future__ import annotations

import pytest

from app.evidence_checker import (
    EvidenceChecker,
    relocation_targets,
    relocation_willingness,
    sponsorship_stances,
)

VERIFIED = "Open to relocation: Singapore (visa sponsorship welcomed)"
REL_HEADER = "Relocating to Singapore | Open to regional travel | Work pass sponsorship required"


def _checker(*values: str) -> EvidenceChecker:
    return EvidenceChecker(list(values))


def _types(result) -> list[str]:
    return [f["type"] for f in result.failures]


# ------------------------------------------------------- the proven defect


def test_changed_relocation_country_is_refused():
    """THE 2026-09-24 defect: Singapore -> Amsterdam must be blocked."""
    result = _checker(VERIFIED).check(
        "Open to relocation: Amsterdam, Netherlands (visa sponsorship welcomed)")

    assert not result.ok
    assert "personal_fact_mismatch" in _types(result)
    failure = next(f for f in result.failures if f["type"] == "personal_fact_mismatch")
    assert any("Amsterdam" in item for item in failure["items"])
    assert "relocation target" in failure["detail"]


def test_flipped_visa_sponsorship_stance_is_refused():
    """THE second half of the same defect: welcomed -> required."""
    result = _checker(VERIFIED).check(
        "Open to relocation: Singapore (visa sponsorship required)")

    assert not result.ok
    failure = next(f for f in result.failures if f["type"] == "personal_fact_mismatch")
    assert "required" in failure["items"]
    assert "visa sponsorship stance" in failure["detail"]


def test_identical_personal_facts_pass_the_gate():
    result = _checker(VERIFIED).check(
        "Open to relocation: Singapore (visa sponsorship welcomed)")
    assert result.ok, result.failures


def test_the_guard_catches_what_similarity_alone_cannot():
    """Proves the other three rules genuinely miss this (the audit's claim)."""
    generated = "Open to relocation: Amsterdam, Netherlands (visa sponsorship welcomed)"
    result = _checker(VERIFIED).check(generated)

    assert not any(f["type"] == "fabricated_number" for f in result.failures)
    assert not any(f["type"] == "unsupported_claim" for f in result.failures)
    assert any(f["type"] == "personal_fact_mismatch" for f in result.failures)


# ------------------------------------------------------------ header format


def test_header_line_relocation_and_stance_agree_and_pass():
    result = _checker(REL_HEADER).check(REL_HEADER)
    assert result.ok, result.failures


def test_header_line_relocation_target_mismatch_is_refused():
    result = _checker(REL_HEADER).check(
        "Relocating to Amsterdam, Netherlands | Work pass sponsorship required")
    assert not result.ok
    assert "personal_fact_mismatch" in _types(result)


def test_header_line_stance_flip_is_refused():
    result = _checker(REL_HEADER).check(
        "Relocating to Singapore | Work pass sponsorship welcomed")
    assert not result.ok


# ------------------------------------------- fail on proof, not on ignorance


def test_evidence_that_is_silent_only_warns():
    """No relocation in evidence + a relocation claim = warning, not a wall.

    Failing here would reject honest resumes whenever the evidence phrase was
    worded differently from our extraction patterns. (The claim is kept under
    `min_line_length` so the similarity rule stays out of the way and this test
    measures only the new rule.)
    """
    result = _checker("Built RAG pipelines in production for four years.").check(
        "Relocating to Delhi")

    assert result.ok, result.failures
    assert any(w["type"] == "unsupported_personal_fact" for w in result.warnings)


def test_omitting_a_verified_fact_is_not_fabrication():
    """Evidence states it, output drops it — omission is always allowed."""
    result = _checker(VERIFIED).check("AI Engineer, RAG")   # under min_line_length
    assert result.ok, result.failures
    assert not any(w["type"] == "unsupported_personal_fact" for w in result.warnings)


def test_relocation_willingness_flip_is_refused():
    evidence = "Open to relocation: Singapore"
    result = _checker(evidence).check("Not willing to relocate for this role.")
    assert not result.ok
    failure = next(f for f in result.failures if f["type"] == "personal_fact_mismatch")
    assert "relocation willingness" in failure["detail"]


# ------------------------------------------------------------------ numbers


def test_number_rule_still_fails_a_fabricated_metric():
    """The new rule must not weaken the existing number gate."""
    result = _checker("Led a team of 40 engineers.").check(
        "Led a team of 900 engineers for six years.")
    assert "fabricated_number" in _types(result)


# --------------------------------------------------------------- extraction


def test_relocation_targets_extraction():
    assert relocation_targets("Relocating to Singapore") == {"Singapore"}
    assert relocation_targets("Open to relocation: Amsterdam, Netherlands (visa sponsorship welcomed)") \
        == {"Amsterdam, Netherlands"}
    assert relocation_targets("Nothing about moving here") == set()


def test_sponsorship_stances_extraction():
    assert sponsorship_stances("Work pass sponsorship required") == {"required"}
    assert sponsorship_stances("visa sponsorship welcomed") == {"welcomed"}
    assert sponsorship_stances("visa sponsorship not required") == {"not_required"}
    assert sponsorship_stances("We sponsor freely") == set()   # no 'sponsorship'


def test_relocation_willingness_extraction():
    assert relocation_willingness("Open to relocation: Singapore") == "open"
    assert relocation_willingness("Not willing to relocate") == "closed"
    assert relocation_willingness("Built distributed systems") is None


def test_extraction_is_deterministic():
    a = _checker(VERIFIED).check("Open to relocation: Singapore (visa sponsorship welcomed)")
    b = _checker(VERIFIED).check("Open to relocation: Singapore (visa sponsorship welcomed)")
    assert a.to_dict() == b.to_dict()
