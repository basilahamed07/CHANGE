"""Candidate Evidence Store (M2) — the authoritative source of candidate truth.

Golden rule: LLMs are forbidden from inventing skills, employment dates, companies,
metrics, technologies, certifications, education, visa status, work authorization,
or project outcomes. Every candidate claim lives here with an explicit status:

    VERIFIED    — confirmed by a source (document, offer letter, live product...)
    UNVERIFIED  — plausible but unconfirmed; must NEVER render as VERIFIED
    DISPUTED    — conflicting evidence exists; excluded from generation
    DO_NOT_USE  — explicitly banned from any generated artifact

Claims with status UNVERIFIED may only be used when the caller explicitly opts in
(never for resumes); DISPUTED and DO_NOT_USE are never returned at all.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

VALID_STATUSES = ("VERIFIED", "UNVERIFIED", "DISPUTED", "DO_NOT_USE")
DEFAULT_PROFILE_DIR = "data/profile"
_PROFILE_FILES = (
    "candidate.yaml",
    "experience.yaml",
    "projects.yaml",
    "skills.yaml",
    "achievements.yaml",
    "education.yaml",
    "preferences.yaml",
    "exclusions.yaml",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Claim:
    category: str
    claim_id: str
    value: str
    status: str = "UNVERIFIED"
    source: str = ""
    last_verified: str = ""
    notes: str = ""

    @property
    def is_verified(self) -> bool:
        return self.status == "VERIFIED"

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "claim_id": self.claim_id,
            "value": self.value,
            "status": self.status,
            "source": self.source,
            "last_verified": self.last_verified,
            "notes": self.notes,
        }


def normalize_skill(value: str) -> str:
    """Skill identity for matching: lowercase alphanumerics, '+' kept."""
    return re.sub(r"[^a-z0-9+]", "", value.lower())


@dataclass
class EvidenceStore:
    """Loads and serves the candidate evidence corpus from YAML files."""

    profile_dir: str = DEFAULT_PROFILE_DIR
    claims: dict[str, Claim] = field(default_factory=dict)  # key: (category, claim_id)
    loaded_at: str = ""

    def __post_init__(self):
        self.reload()

    # ------------------------------------------------------------------ load
    def reload(self) -> int:
        """(Re)load all profile YAML files. Returns claim count."""
        self.claims = {}
        root = Path(self.profile_dir)
        if not root.exists():
            logger.warning("Evidence store: profile dir %s not found", self.profile_dir)
            self.loaded_at = _now_iso()
            return 0

        for fname in _PROFILE_FILES:
            path = root / fname
            if not path.exists():
                continue
            category = fname.removesuffix(".yaml")
            try:
                with open(path, encoding="utf-8") as fh:
                    data = yaml.safe_load(fh) or {}
            except Exception:
                logger.exception("Evidence store: failed to parse %s", path)
                continue
            for entry in self._iter_entries(data):
                self._register(category, entry)

        self.loaded_at = _now_iso()
        logger.info("Evidence store: loaded %d claims from %s", len(self.claims), self.profile_dir)
        return len(self.claims)

    @staticmethod
    def _iter_entries(data: dict):
        """Yield claim dicts from a profile file's list-shaped values."""
        for value in data.values():
            if isinstance(value, list):
                for entry in value:
                    if isinstance(entry, dict):
                        yield entry
            elif isinstance(value, dict) and "value" in value:
                yield value

    def _register(self, category: str, entry: dict) -> None:
        value = str(entry.get("value", "")).strip()
        if not value:
            return
        status = str(entry.get("status", "UNVERIFIED")).strip().upper()
        if status not in VALID_STATUSES:
            logger.warning(
                "Evidence store: invalid status %r for %s/%s — forcing UNVERIFIED",
                status, category, entry.get("id"),
            )
            status = "UNVERIFIED"
        claim_id = str(entry.get("id") or value[:64])
        key = f"{category}:{claim_id}"
        existing = self.claims.get(key)
        if existing is not None:
            logger.warning("Evidence store: duplicate claim key %s — keeping first", key)
            return
        self.claims[key] = Claim(
            category=category,
            claim_id=claim_id,
            value=value,
            status=status,
            source=str(entry.get("source", "")),
            last_verified=str(entry.get("last_verified", "")),
            notes=str(entry.get("notes", "")),
        )

    # ----------------------------------------------------------------- serve
    def verified_only(self, categories: list[str] | None = None) -> list[Claim]:
        """Claims safe for generation: VERIFIED only (never UNVERIFIED/DISPUTED/DO_NOT_USE)."""
        return [
            c for c in self.claims.values()
            if c.status == "VERIFIED" and (categories is None or c.category in categories)
        ]

    def verified_values(self, categories: list[str] | None = None) -> list[str]:
        return [c.value for c in self.verified_only(categories)]

    def all_claims(self) -> list[Claim]:
        return list(self.claims.values())

    def by_status(self, status: str) -> list[Claim]:
        return [c for c in self.claims.values() if c.status == status]

    def verified_skill_values(self) -> set[str]:
        return {normalize_skill(v) for v in self.verified_values(["skills"])}

    def skill_values_all_statuses(self) -> list[str]:
        """All skill values regardless of status — the full 'candidate might claim' set.

        The EvidenceChecker checks generated text against this: an UNVERIFIED,
        DISPUTED, or DO_NOT_USE skill appearing in a generated resume must fail.
        """
        return [c.value for c in self.claims.values() if c.category == "skills"]

    def verified_corpus_lines(self) -> list[str]:
        """One line per VERIFIED claim — the generation corpus."""
        return [c.value for c in self.verified_only()]

    # ------------------------------------------------------------- persistence
    async def sync_to_db(self, db) -> int:
        """Mirror claims into the candidate_evidence table (UI/API reads)."""
        now = _now_iso()
        rows = [
            (c.category, c.claim_id, c.value, c.status, c.source, c.last_verified, c.notes, now)
            for c in self.claims.values()
        ]
        await db.db.executemany(
            """
            INSERT INTO candidate_evidence
                (category, claim_id, value, status, source, last_verified, notes, synced_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(category, claim_id) DO UPDATE SET
                value = excluded.value,
                status = excluded.status,
                source = excluded.source,
                last_verified = excluded.last_verified,
                notes = excluded.notes,
                synced_at = excluded.synced_at
            """,
            rows,
        )
        await db.db.commit()
        return len(rows)
