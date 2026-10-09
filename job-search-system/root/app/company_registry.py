"""Config-backed company ATS board registry.

ATS providers expose company-scoped public feeds. Keeping board identifiers in
YAML lets operators refresh coverage without changing adapter code, while the
adapter contract remains responsible for HTTP, normalization, and filtering.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


DEFAULT_PATH = Path(__file__).resolve().parents[1] / "config" / "job_sources" / "company_registry.yaml"


def load_company_registry(path: str | os.PathLike[str] | None = None) -> list[dict[str, Any]]:
    """Load valid company records; malformed entries are ignored safely."""
    registry_path = Path(path or os.getenv("JOBAGENT_COMPANY_REGISTRY_PATH", DEFAULT_PATH))
    try:
        data = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return []
    companies = data.get("companies", []) if isinstance(data, dict) else []
    return [item for item in companies if isinstance(item, dict) and item.get("id")
            and isinstance(item.get("ats"), dict)]


def board_tokens(ats_type: str, path: str | os.PathLike[str] | None = None) -> list[str]:
    """Return unique board/site identifiers for one ATS type in YAML order."""
    out: list[str] = []
    for company in load_company_registry(path):
        ats = company.get("ats") or {}
        if str(ats.get("type", "")).lower() != ats_type.lower():
            continue
        token = ats.get("board") or ats.get("site") or ats.get("slug")
        if isinstance(token, str) and token.strip() and token.strip() not in out:
            out.append(token.strip())
    return out


def companies_for(ats_type: str, country_code: str | None = None,
                  path: str | os.PathLike[str] | None = None) -> list[dict[str, Any]]:
    """Return registry entries for an ATS, optionally filtered by country."""
    wanted = (country_code or "").upper()
    out = []
    for company in load_company_registry(path):
        ats = company.get("ats") or {}
        if str(ats.get("type", "")).lower() != ats_type.lower():
            continue
        countries = {str(c).upper() for c in (company.get("countries") or [])}
        if wanted and countries and wanted not in countries:
            continue
        out.append(company)
    return out
