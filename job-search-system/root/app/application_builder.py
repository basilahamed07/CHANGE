"""M8: Application package builder — Phase-19 layout, hash-based idempotency.

Package layout (per job):
    {applications_dir}/{job_id:04d}-{company-slug}/
        resume.docx          (DOCX-first renderer; PDF stays on-demand via API)
        cover_letter.docx    (only when a cover letter exists)
        resume.txt           (plain text — review + hashing)
        cover_letter.txt     (plain text — review + hashing)
        metadata.json        (hashes, profile version, evidence-check result,
                              model, status, generated_at)

Golden Rules honored:
- Evidence is sacred (Rule 5): the builder REFUSES to package text that fails
  the EvidenceChecker — packaging is the last line before a human sees a doc.
- Human approval (Rule 6): packages are artifacts for review; nothing is sent.
- Deterministic (Rule 4): same inputs ⇒ same bytes ⇒ same hashes ⇒ NO-OP
  regeneration (unchanged inputs never rewrite files).
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

from app.docx_generator import generate_cover_letter_docx, generate_resume_docx

logger = logging.getLogger(__name__)


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return slug[:40] or "company"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


@dataclass
class PackageInputs:
    """Everything that determines the package content (idempotency key)."""

    job_id: int
    company: str
    job_title: str
    job_description_hash: str   # sha256 of the JD actually used
    resume_version_id: int      # resumes.id used for generation
    profile_version: str        # evidence store loaded_at stamp
    tailored_resume: str
    cover_letter: str
    model: str = ""
    evidence_check_ok: bool = True
    evidence_check_failures: list = field(default_factory=list)

    def fingerprint(self) -> str:
        """Content hash of ALL generation inputs — the no-op regeneration key."""
        payload = json.dumps({
            "job_id": self.job_id,
            "job_description_hash": self.job_description_hash,
            "resume_version_id": self.resume_version_id,
            "profile_version": self.profile_version,
            "tailored_resume_hash": sha256_text(self.tailored_resume),
            "cover_letter_hash": sha256_text(self.cover_letter),
            "model": self.model,
        }, sort_keys=True)
        return sha256_text(payload)


@dataclass
class BuildResult:
    job_id: int
    package_dir: str
    action: str                  # "built" | "noop" | "rebuilt"
    files: list[str]
    metadata: dict

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


class ApplicationBuilder:
    """Writes/refreshes one application package directory per job."""

    def __init__(self, applications_dir: str):
        self.applications_dir = applications_dir

    def package_dir(self, job_id: int, company: str):
        from pathlib import Path
        return Path(self.applications_dir) / f"{job_id:04d}-{_slug(company)}"

    # ------------------------------------------------------------- API

    async def build(self, inputs: PackageInputs,
                    evidence_check_result: dict | None = None) -> BuildResult:
        """Create or no-op-refresh a package. Idempotent via inputs fingerprint."""
        from pathlib import Path

        if not inputs.evidence_check_ok:
            # Sacred-evidence rule: never package unverified claims.
            raise EvidenceViolationError(
                "Refusing to package: evidence check failed "
                f"({[f.get('type') for f in inputs.evidence_check_failures]})")

        pdir = self.package_dir(inputs.job_id, inputs.company)
        meta_path = pdir / "metadata.json"
        new_fp = inputs.fingerprint()
        meta_existed = meta_path.exists()

        if meta_existed:
            try:
                old = json.loads(meta_path.read_text(encoding="utf-8"))
                if old.get("inputs_fingerprint") == new_fp:
                    return BuildResult(
                        job_id=inputs.job_id, package_dir=str(pdir),
                        action="noop", files=sorted(old.get("files", [])),
                        metadata=old)  # unchanged inputs ⇒ no rewrite
            except (json.JSONDecodeError, OSError):
                pass  # corrupt metadata → rebuild

        pdir.mkdir(parents=True, exist_ok=True)
        written: list[str] = []

        resume_txt = inputs.tailored_resume or ""
        (pdir / "resume.txt").write_text(resume_txt, encoding="utf-8")
        written.append("resume.txt")
        (pdir / "resume.docx").write_bytes(
            generate_resume_docx(resume_txt, name=self._name_guess(inputs)))
        written.append("resume.docx")

        if (inputs.cover_letter or "").strip():
            cl = inputs.cover_letter
            (pdir / "cover_letter.txt").write_text(cl, encoding="utf-8")
            written.append("cover_letter.txt")
            (pdir / "cover_letter.docx").write_bytes(
                generate_cover_letter_docx(cl, company=inputs.company))
            written.append("cover_letter.docx")

        action = "rebuilt" if meta_existed else "built"

        metadata = {
            "schema": "jobagent-package/1",
            "job_id": inputs.job_id,
            "company": inputs.company,
            "job_title": inputs.job_title,
            "generated_at": _now_iso(),
            "inputs_fingerprint": new_fp,
            "hashes": {
                "job_description": inputs.job_description_hash,
                "tailored_resume": sha256_text(resume_txt),
                "cover_letter": sha256_text(inputs.cover_letter),
            },
            "resume_version_id": inputs.resume_version_id,
            "profile_version": inputs.profile_version,
            "model": inputs.model,
            "evidence_check": evidence_check_result or {
                "ok": inputs.evidence_check_ok,
                "failures": inputs.evidence_check_failures,
            },
            "status": "ready_for_review",   # human review gate before any send
            "files": sorted(set(written)),
        }
        meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        logger.info("Package %s for job %s (%s)", action, inputs.job_id, pdir)
        return BuildResult(job_id=inputs.job_id, package_dir=str(pdir),
                           action=action, files=metadata["files"],
                           metadata=metadata)

    def read_metadata(self, job_id: int, company: str) -> dict | None:
        from pathlib import Path
        meta = self.package_dir(job_id, company) / "metadata.json"
        if not meta.exists():
            return None
        try:
            return json.loads(meta.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    @staticmethod
    def _name_guess(inputs: PackageInputs) -> str:
        # Renderer only uses the name for a title line; safe to leave generic.
        return ""


class EvidenceViolationError(RuntimeError):
    """Raised when packaging would materialize unverified claims into documents."""
