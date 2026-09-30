"""Automatic ATS DETECTION from a career-page URL (task §12).

Given any careers/jobs URL, identify which ATS hosts it — so direct company
career discovery can route to the right adapter INSTEAD of duplicating ATS
parsing inside career-page crawlers:

    provider = detect_ats(url)
    if provider: jobs = <the existing ATS adapter for provider>.search(...)

Detection = registered host-pattern rules (public URL shapes, no guessing):
  boards.greenhouse.io, jobs.lever.co, *.myworkdayjobs.com, jobs.smartrecruiters.com,
  jobs.ashbyhq.com, *.teamtailor.com, apply.workable.com, *.recruitee.com,
  jobs.bamboohr.com, *.myworkdaysite.com ... extended as evidence arrives.

Each rule carries `adapter_hint` — the name of the adapter that already knows
how to talk to that ATS (the registry keeps parsing in ONE place).
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class AtsRule:
    """One ATS host pattern.

    host_suffix  — host must equal or end with this ('.example.com' = subdomain
                   wildcard; plain 'example.com' = exact host or subdomain).
    ats          — canonical ATS provider id.
    adapter_hint — existing adapter source_name that can query this ATS
                   ('' when no adapter exists yet — detection still reports).
    """
    host_suffix: str
    ats: str
    adapter_hint: str = ""


# Public, documented ATS URL shapes (extend ONLY with verified shapes).
ATS_RULES: tuple[AtsRule, ...] = (
    AtsRule("boards.greenhouse.io", "greenhouse", "greenhouse"),
    AtsRule("job-boards.greenhouse.io", "greenhouse", "greenhouse"),
    AtsRule("jobs.lever.co", "lever", "lever"),
    AtsRule("jobs.eu.lever.co", "lever", "lever"),
    AtsRule("jobs.ashbyhq.com", "ashby", "ashby"),
    AtsRule("jobs.smartrecruiters.com", "smartrecruiters", "smartrecruiters"),
    AtsRule(".bamboohr.com", "bamboohr", ""),
    AtsRule(".myworkdayjobs.com", "workday", ""),
    AtsRule(".myworkdaysite.com", "workday", ""),
    AtsRule(".teamtailor.com", "teamtailor", ""),
    AtsRule("apply.workable.com", "workable", ""),
    AtsRule(".recruitee.com", "recruitee", "recruitee"),
    AtsRule("jobs.jobvite.com", "jobvite", ""),
    AtsRule(".icims.com", "icims", ""),
    AtsRule("careers.pageuppeople.com", "pageup", ""),
    AtsRule("jobs.taleo.net", "taleo", ""),
    AtsRule(".successfactors.com", "sap_successfactors", ""),
    AtsRule("jobs.comeet.com", "comeet", ""),
    AtsRule("jobs.gusto.com", "gusto", ""),
)

# Longest host_suffix first so 'jobs.eu.lever.co' wins over suffix collisions.
_SORTED_RULES = sorted(ATS_RULES, key=lambda r: -len(r.host_suffix))


def _host(url: str) -> str:
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""
    return host[:-1] if host.endswith(".") else host


def detect_ats(url: str) -> str | None:
    """Return the canonical ATS provider id for a URL, or None.

    Deterministic, zero network — a URL-shape lookup, not scraping.
    """
    host = _host(url or "")
    if not host:
        return None
    for rule in _SORTED_RULES:
        suffix = rule.host_suffix
        if suffix.startswith("."):
            # '*.myworkdayjobs.com': any subdomain (or the bare domain)
            if host.endswith(suffix) or host == suffix[1:]:
                return rule.ats
        elif host == suffix or host.endswith("." + suffix):
            return rule.ats
    return None


def adapter_for(url: str) -> str | None:
    """The existing adapter source_name able to query this ATS, or None.

    A URL can be ATS-detected yet have NO adapter (workday/teamtailor today):
    detection reports honestly, routing falls back to JSON-LD parsing.
    """
    host = _host(url or "")
    for rule in _SORTED_RULES:
        suffix = rule.host_suffix
        if suffix.startswith("."):
            if host.endswith(suffix) or host == suffix[1:]:
                return rule.adapter_hint or None
        elif host == suffix or host.endswith("." + suffix):
            return rule.adapter_hint or None
    return None


def known_ats_providers() -> list[str]:
    """Canonical provider ids (deduplicated) — used by reports/tests."""
    return sorted({r.ats for r in ATS_RULES})


def rules_summary() -> list[dict]:
    return [{"host_pattern": r.host_suffix, "ats": r.ats,
             "adapter_hint": r.adapter_hint or None}
            for r in _SORTED_RULES]
