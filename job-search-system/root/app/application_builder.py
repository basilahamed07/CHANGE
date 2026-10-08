"""M8: Application package builder — Phase-19 layout, hash-based idempotency.

Package layout (per job):
    {applications_dir}/{job_id:04d}-{company-slug}/
        resume.md            (ATS Markdown — THE SOURCE for every other format)
        resume.pdf           (Chromium-rendered from resume.md; text fallback)
        resume.docx          (DOCX renderer)
        cover_letter.docx    (only when a cover letter exists)
        cover_letter.md      (only when a cover letter exists)
        resume.txt           (plain text — review + hashing)
        cover_letter.txt     (plain text — review + hashing)
        metadata.json        (hashes, profile version, evidence-check result,
                              model, status, generated_at, generated_by)

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

from app.ats_resume import (
    build_resume_markdown,
    is_structured,
    looks_like_resume_markdown,
    resume_json_to_text,
)
from app.docx_generator import generate_cover_letter_docx, generate_resume_docx
from app.html_docx import generate_docx_from_markdown
from app.markdown_generator import generate_cover_letter_markdown

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
    # Structured resume (JSON text). Empty for rows prepared before the
    # structured schema existed — those render from tailored_resume instead.
    resume_json: str = ""
    resume_markdown: str = ""
    target_country: str = ""
    model: str = ""
    evidence_check_ok: bool = True
    evidence_check_failures: list = field(default_factory=list)
    # Provenance only — deliberately NOT part of the fingerprint, so recording
    # how the text was produced cannot change package identity or force a rebuild.
    generated_by: str = "stored"   # "stored" (human-reviewed text) | "regenerated" (AI)

    def fingerprint(self) -> str:
        """Content hash of ALL generation inputs — the no-op regeneration key.

        ``resume_json`` is included because it changes what gets rendered: a
        package built before the structured resume existed must rebuild once to
        gain the structured ``resume.md`` and the PDF.
        """
        payload = json.dumps({
            "job_id": self.job_id,
            "job_description_hash": self.job_description_hash,
            "resume_version_id": self.resume_version_id,
            "profile_version": self.profile_version,
            "tailored_resume_hash": sha256_text(self.tailored_resume),
            "cover_letter_hash": sha256_text(self.cover_letter),
            "resume_json_hash": sha256_text(self.resume_json),
            "resume_markdown_hash": sha256_text(self.resume_markdown),
            "target_country": self.target_country,
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

    # A file locked by Word (or any open handle) must not be silently dropped:
    # the write returns False so the caller can keep it out of `files` and leave
    # the stored fingerprint untouched, which makes the next build retry it
    # instead of no-op'ing forever against a stale artifact.
    @staticmethod
    def _write_text_preserve_locked(path, text: str) -> bool:
        try:
            path.write_text(text, encoding="utf-8")
            return True
        except PermissionError:
            if not path.exists():
                raise
            logger.warning("Package file locked; preserving existing file: %s", path)
            return False

    @staticmethod
    def _write_bytes_preserve_locked(path, data: bytes) -> bool:
        try:
            path.write_bytes(data)
            return True
        except PermissionError:
            if not path.exists():
                raise
            logger.warning("Package file locked; preserving existing file: %s", path)
            return False

    @staticmethod
    def _record(written: list, skipped: list, name: str, ok: bool) -> None:
        (written if ok else skipped).append(name)

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
        old_fp = None
        meta_existed = meta_path.exists()

        if meta_existed:
            try:
                old = json.loads(meta_path.read_text(encoding="utf-8"))
                old_fp = old.get("inputs_fingerprint")
                if old_fp == new_fp:
                    return BuildResult(
                        job_id=inputs.job_id, package_dir=str(pdir),
                        action="noop", files=sorted(old.get("files", [])),
                        metadata=old)  # unchanged inputs ⇒ no rewrite
            except (json.JSONDecodeError, OSError):
                pass  # corrupt metadata → rebuild

        pdir.mkdir(parents=True, exist_ok=True)
        written: list[str] = []
        skipped: list[str] = []

        # Markdown is the source of truth: prefer the structured resume, fall
        # back to the stored plain text for pre-structured rows.
        structured = inputs.resume_json if is_structured(inputs.resume_json) else ""
        direct_md = (inputs.resume_markdown or "").strip()
        resume_md = (direct_md if looks_like_resume_markdown(direct_md) else
                     (build_resume_markdown(structured)
                      if structured else build_resume_markdown(inputs.tailored_resume)))
        # Plain text keeps every section in reading order for DOCX + hashing.
        resume_txt = (resume_json_to_text(structured) if structured
                      else (inputs.tailored_resume or ""))

        self._record(written, skipped, "resume.txt",
                     self._write_text_preserve_locked(pdir / "resume.txt", resume_txt))
        self._record(written, skipped, "resume.md",
                     self._write_text_preserve_locked(pdir / "resume.md", resume_md))
        self._record(written, skipped, "resume.docx", self._write_bytes_preserve_locked(
            pdir / "resume.docx",
            self._render_docx(
                resume_md, resume_txt, self._name_guess(inputs), inputs.target_country)))

        # PDF is rendered from the Markdown so it matches the .md exactly.
        # A missing browser binary degrades to the text renderer, never fails
        # the build: the package is still complete and reviewable.
        pdf_bytes, pdf_renderer = await self._render_resume_pdf(
            resume_md, resume_txt, inputs.job_title, inputs.target_country)
        if pdf_bytes:
            self._record(written, skipped, "resume.pdf", self._write_bytes_preserve_locked(
                pdir / "resume.pdf", pdf_bytes))

        if (inputs.cover_letter or "").strip():
            cl = inputs.cover_letter
            cl_md = generate_cover_letter_markdown(cl)
            self._record(written, skipped, "cover_letter.txt",
                         self._write_text_preserve_locked(pdir / "cover_letter.txt", cl))
            self._record(written, skipped, "cover_letter.md",
                         self._write_text_preserve_locked(pdir / "cover_letter.md", cl_md))
            self._record(written, skipped, "cover_letter.docx",
                         self._write_bytes_preserve_locked(
                             pdir / "cover_letter.docx",
                             generate_docx_from_markdown(cl_md, name=inputs.company)))
            cl_pdf, _ = await self._render_cover_letter_pdf(cl, cl_md, inputs.company)
            if cl_pdf:
                self._record(written, skipped, "cover_letter.pdf",
                             self._write_bytes_preserve_locked(
                                 pdir / "cover_letter.pdf", cl_pdf))

        action = "rebuilt" if meta_existed else "built"

        metadata = {
            "schema": "jobagent-package/1",
            "job_id": inputs.job_id,
            "company": inputs.company,
            "job_title": inputs.job_title,
            "generated_at": _now_iso(),
            # A locked file leaves the package stale. Keeping the *previous*
            # fingerprint means the next build is not a no-op, so the artifact
            # is regenerated once the lock clears instead of drifting forever.
            "inputs_fingerprint": new_fp if not skipped else old_fp,
            "hashes": {
                "job_description": inputs.job_description_hash,
                "tailored_resume": sha256_text(resume_txt),
                "cover_letter": sha256_text(inputs.cover_letter),
            },
            "resume_version_id": inputs.resume_version_id,
            "profile_version": inputs.profile_version,
            "model": inputs.model,
            "target_country": inputs.target_country,
            "generated_by": inputs.generated_by,
            "evidence_check": evidence_check_result or {
                "ok": inputs.evidence_check_ok,
                "failures": inputs.evidence_check_failures,
            },
            "status": "ready_for_review",   # human review gate before any send
            "files": sorted(set(written)),
        }
        meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        if skipped:
            logger.warning(
                "Package %s for job %s incomplete; locked, close and rebuild: %s",
                action, inputs.job_id, ", ".join(sorted(skipped)))
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

    def _render_docx(self, markdown_text: str, plain_text: str, name: str = "",
                     target_country: str = "") -> bytes:
        """DOCX from the Markdown — the same source the PDF renders.

        Falls back to the plain-text renderer when the Markdown is empty, so a
        package can never be produced without a resume document.
        """
        try:
            if markdown_text and markdown_text.strip():
                return generate_docx_from_markdown(
                    markdown_text, name=name, resume_country=target_country)
        except Exception:
            logger.exception("Markdown DOCX render failed; using the text renderer")
        return generate_resume_docx(plain_text, name=name)

    async def _render_resume_pdf(self, markdown_text: str, plain_text: str,
                                 job_title: str, target_country: str = "") -> tuple:
        """Render resume.pdf from the Markdown. Returns (bytes|None, renderer)."""
        from app.pdf_renderer import markdown_to_pdf
        try:
            pdf, renderer = await markdown_to_pdf(
                markdown_text, title="Resume", plain_text=plain_text,
                resume_country=target_country)
            return pdf, renderer
        except Exception:
            logger.exception("resume.pdf render failed")
            return None, ""

    async def _render_cover_letter_pdf(self, text: str, markdown_text: str,
                                       company: str) -> tuple:
        """Render cover_letter.pdf from its Markdown. Returns (bytes|None, renderer)."""
        from app.pdf_renderer import markdown_to_pdf
        from app.pdf_generator import generate_cover_letter_pdf
        try:
            pdf, renderer = await markdown_to_pdf(
                markdown_text, title="Cover Letter", plain_text=text)
            if renderer == "text":
                # The text fallback has a cover-letter-specific layout.
                pdf = generate_cover_letter_pdf(text, company=company)
            return pdf, renderer
        except Exception:
            logger.exception("cover_letter.pdf render failed")
            return None, ""

    @staticmethod
    def _name_guess(inputs: PackageInputs) -> str:
        """Candidate name for the DOCX title line, taken from the resume."""
        from app.ats_resume import parse_resume_json
        data = parse_resume_json(inputs.resume_json)
        if data:
            basics = data.get("basics") if isinstance(data.get("basics"), dict) else {}
            if basics.get("name"):
                return str(basics["name"]).strip()
        first = next((ln.strip() for ln in (inputs.tailored_resume or "").splitlines()
                      if ln.strip()), "")
        return first


class EvidenceViolationError(RuntimeError):
    """Raised when packaging would materialize unverified claims into documents."""
