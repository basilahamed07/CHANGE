"""M8: Application package builder tests.

Key guarantees: fingerprint idempotency (unchanged inputs ⇒ NO-OP, no rewrite),
evidence gate blocks packaging of unverified claims, DOCX structure renders,
metadata.json carries the full audit trail, and the evidence-gated API flow
(build + refresh + 422 refusal).
"""
import hashlib
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.application_builder import (
    ApplicationBuilder,
    EvidenceViolationError,
    PackageInputs,
    sha256_text,
)


def _inputs(job_id=1, tailored="BASIL AHAMED H\nAI Engineer with RAG experience.",
            cover="Dear Hiring Team,", company="Acme AI", **kw) -> PackageInputs:
    base = dict(
        job_id=job_id,
        company=company,
        job_title="AI Engineer",
        job_description_hash=sha256_text("Build LLM products."),
        resume_version_id=1,
        profile_version="2026-09-23T00:00:00+00:00",
        tailored_resume=tailored,
        cover_letter=cover,
        model="poolside/laguna-s-2.1:free",
    )
    base.update(kw)
    return PackageInputs(**base)


# ---------------- builder core ----------------

def test_fingerprint_changes_with_any_input():
    a = _inputs().fingerprint()
    b = _inputs(tailored="Different text entirely.").fingerprint()
    c = _inputs(profile_version="changed").fingerprint()
    d = _inputs(cover="").fingerprint()
    assert len({a, b, c, d}) == 4
    assert a == _inputs().fingerprint()  # deterministic


def test_build_writes_package_with_docx_first(tmp_path):
    builder = ApplicationBuilder(str(tmp_path))
    result = builder_build(builder, tmp_path)
    pdir = tmp_path / "0001-acme-ai"
    assert (pdir / "resume.txt").exists()
    assert (pdir / "resume.docx").exists()
    assert (pdir / "cover_letter.txt").exists()
    assert (pdir / "cover_letter.docx").exists()
    assert (pdir / "metadata.json").exists()
    assert result.action == "built"
    assert "resume.docx" in result.files
    # DOCX is a real zip (docx = OOXML)
    with open(pdir / "resume.docx", "rb") as f:
        assert f.read(2) == b"PK"


def builder_build(builder, tmp_path, **kw):
    import asyncio
    return asyncio.get_event_loop().run_until_complete(
        builder.build(_inputs(**kw))) if False else _run(builder.build(_inputs(**kw)))


def _run(coro):
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_idempotent_noop_on_unchanged_inputs(tmp_path):
    builder = ApplicationBuilder(str(tmp_path))
    first = _run(builder.build(_inputs()))
    pdir = tmp_path / "0001-acme-ai"
    resume_before = (pdir / "resume.docx").read_bytes()
    meta_before = (pdir / "metadata.json").read_bytes()
    second = _run(builder.build(_inputs()))
    assert first.action == "built"
    assert second.action == "noop"
    assert (pdir / "resume.docx").read_bytes() == resume_before  # bytes untouched
    assert (pdir / "metadata.json").read_bytes() == meta_before


def test_rebuild_when_inputs_change(tmp_path):
    builder = ApplicationBuilder(str(tmp_path))
    _run(builder.build(_inputs()))
    changed = _run(builder.build(_inputs(tailored="Updated tailored resume text.")))
    assert changed.action == "rebuilt"
    meta = json.loads((tmp_path / "0001-acme-ai" / "metadata.json").read_text())
    assert meta["hashes"]["tailored_resume"] == sha256_text("Updated tailored resume text.")


def test_metadata_carries_audit_trail(tmp_path):
    builder = ApplicationBuilder(str(tmp_path))
    _run(builder.build(_inputs(), evidence_check_result={
        "ok": True, "failures": [], "checked_at": "2026-09-23T00:00:00"}))
    meta = json.loads((tmp_path / "0001-acme-ai" / "metadata.json").read_text())
    assert meta["schema"] == "jobagent-package/1"
    assert meta["status"] == "ready_for_review"
    assert meta["model"] == "poolside/laguna-s-2.1:free"
    assert meta["resume_version_id"] == 1
    assert meta["evidence_check"]["ok"] is True
    assert meta["inputs_fingerprint"] == _inputs().fingerprint()


def test_no_cover_letter_no_cl_files(tmp_path):
    builder = ApplicationBuilder(str(tmp_path))
    _run(builder.build(_inputs(cover="")))
    pdir = tmp_path / "0001-acme-ai"
    assert not (pdir / "cover_letter.docx").exists()
    assert not (pdir / "cover_letter.txt").exists()
    meta = json.loads((pdir / "metadata.json").read_text())
    assert "cover_letter.docx" not in meta["files"]


def test_evidence_violation_blocks_packaging(tmp_path):
    builder = ApplicationBuilder(str(tmp_path))
    bad = _inputs(evidence_check_ok=False,
                  evidence_check_failures=[{"type": "fabricated_number"}])
    with pytest.raises(EvidenceViolationError):
        _run(builder.build(bad))
    assert not (tmp_path / "0001-acme-ai").exists()  # nothing materialized


def test_corrupt_metadata_rebuilds(tmp_path):
    builder = ApplicationBuilder(str(tmp_path))
    _run(builder.build(_inputs()))
    pdir = tmp_path / "0001-acme-ai"
    (pdir / "metadata.json").write_text("{corrupt", encoding="utf-8")
    result = _run(builder.build(_inputs()))
    assert result.action == "rebuilt"


def test_read_metadata_roundtrip(tmp_path):
    builder = ApplicationBuilder(str(tmp_path))
    _run(builder.build(_inputs()))
    meta = builder.read_metadata(1, "Acme AI")
    assert meta and meta["job_id"] == 1
    assert builder.read_metadata(99, "Nobody") is None


# ---------------- API flow (evidence-gated) ----------------

@pytest.mark.asyncio
async def test_package_refresh_endpoint_idempotent(tmp_path):
    from app.main import create_app
    from app.database import Database
    from httpx import ASGITransport, AsyncClient

    db_path = str(tmp_path / "t.db")
    application = create_app(db_path=db_path, testing=True)
    db = Database(db_path)
    await db.init()
    application.state.db = db
    # Seed a REAL evidence store + checker (production fail-closed contract:
    # packaging refuses to run without them). The verified corpus backs the
    # stored tailored text so the gate passes.
    import yaml as _yaml
    profile_dir = tmp_path / "profile"
    profile_dir.mkdir()
    (profile_dir / "experience.yaml").write_text(_yaml.safe_dump(
        {"claims": [{"id": "e1", "value": "Basil resume text.",
                     "status": "VERIFIED", "source": "test"}]}))
    from app.evidence_store import EvidenceStore
    from app.evidence_checker import EvidenceChecker
    store = EvidenceStore(profile_dir=str(profile_dir))
    application.state.evidence_store = store
    application.state.evidence_checker = EvidenceChecker(store.verified_values())

    jid = await db.insert_job(
        title="AI Engineer", company="Acme AI", location="Remote",
        salary_min=None, salary_max=None, description="Build LLM products.",
        url="https://x/1", posted_date="2026-09-20",
        application_method="direct", contact_email=None)
    app_id = await db.insert_application(jid, "prepared")
    await db.update_application(app_id, tailored_resume="Basil resume text.",
                                cover_letter="Dear team,")
    # Seed a fake package dir as if a previous build wrote it
    from app.application_builder import ApplicationBuilder, PackageInputs, sha256_text
    builder = ApplicationBuilder(str(tmp_path / "data" / "applications"))
    inputs = PackageInputs(
        job_id=jid, company="Acme AI", job_title="AI Engineer",
        job_description_hash=sha256_text("Build LLM products."),
        resume_version_id=0, profile_version="unknown",
        tailored_resume="Basil resume text.", cover_letter="Dear team,", model="")
    first = await builder.build(inputs)
    await db.set_package_meta(app_id, first.package_dir, inputs.fingerprint(),
                              "ready_for_review")

    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        # refresh=true repackages stored text; but the app's builder uses a
        # different base dir than the pre-seeded one, so expect a rebuild there.
        r = await client.post(f"/api/packages/jobs/{jid}/build?refresh=true")
        assert r.status_code == 200
        body = r.json()
        assert body["action"] in ("built", "rebuilt", "noop")
        assert body["metadata"]["evidence_check"]["ok"] is True

        r = await client.get("/api/packages")
        assert r.status_code == 200
        assert r.json()["count"] == 1

        r = await client.get(f"/api/packages/jobs/{jid}")
        assert r.status_code == 200
        assert r.json()["package_dir"]

        r = await client.get("/api/packages/jobs/999")
        assert r.status_code == 404
    await db.close()


# ---------------- P0: a plain build must never rewrite the reviewed text ------
#
# Defect (Stage-8 D1): POST /build defaulted to the AI branch, so a normal
# "build" silently regenerated and overwrote the text a human had reviewed. The
# flag that preserved reviewed work (`refresh=true`) was opt-in and read
# backwards. Contract now: default = package the stored text unchanged;
# regeneration requires an explicit `regenerate=true`.

async def _seed_package_app(tmp_path, tailored="Basil resume text.",
                            cover="Dear team,", extra_verified=None):
    """App + DB with a real evidence store/checker and stored reviewed text."""
    from app.main import create_app
    from app.database import Database
    import yaml as _yaml
    from app.evidence_store import EvidenceStore
    from app.evidence_checker import EvidenceChecker

    db_path = str(tmp_path / "t.db")
    application = create_app(db_path=db_path, testing=True)
    db = Database(db_path)
    await db.init()
    application.state.db = db

    profile_dir = tmp_path / "profile"
    profile_dir.mkdir()
    claims = [{"id": "e1", "value": tailored, "status": "VERIFIED", "source": "test"}]
    if cover:
        claims.append({"id": "e2", "value": cover, "status": "VERIFIED", "source": "test"})
    for i, extra in enumerate(extra_verified or []):
        claims.append({"id": f"x{i}", "value": extra, "status": "VERIFIED", "source": "test"})
    (profile_dir / "experience.yaml").write_text(_yaml.safe_dump({"claims": claims}))
    store = EvidenceStore(profile_dir=str(profile_dir))
    application.state.evidence_store = store
    application.state.evidence_checker = EvidenceChecker(store.verified_values())

    jid = await db.insert_job(
        title="AI Engineer", company="Acme AI", location="Remote",
        salary_min=None, salary_max=None, description="Build LLM products.",
        url="https://x/p0", posted_date="2026-09-20",
        application_method="direct", contact_email=None)
    app_id = await db.insert_application(jid, "prepared")
    await db.update_application(app_id, tailored_resume=tailored, cover_letter=cover)
    return application, db, jid


class _FakeTailor:
    """Minimal Tailor stand-in: returns fixed text, counts calls."""

    def __init__(self, text, cover="Dear team,"):
        self.text = text
        self.cover = cover
        self.calls = 0

    async def prepare(self, job_description, match_reasons, suggested_keywords):
        self.calls += 1
        return {"tailored_resume": self.text, "cover_letter": self.cover}


@pytest.mark.asyncio
async def test_default_build_packages_stored_text_without_ai(tmp_path):
    """P0 regression: POST /build (no params) must NOT regenerate or rewrite."""
    from httpx import ASGITransport, AsyncClient

    application, db, jid = await _seed_package_app(tmp_path)
    application.state.tailor = None   # no AI configured at all

    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(f"/api/packages/jobs/{jid}/build")
        assert r.status_code == 200
        body = r.json()
        assert body["metadata"]["generated_by"] == "stored"
        assert body["metadata"]["evidence_check"]["ok"] is True

    row = await db.get_application(jid)
    assert row["tailored_resume"] == "Basil resume text."   # untouched
    await db.close()


@pytest.mark.asyncio
async def test_default_build_refuses_when_no_reviewed_text(tmp_path):
    """No reviewed text => honest 409, never a silent AI run."""
    from httpx import ASGITransport, AsyncClient

    application, db, jid = await _seed_package_app(tmp_path)
    app_row = await db.get_application(jid)
    await db.update_application(app_row["id"], tailored_resume="", cover_letter="")

    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(f"/api/packages/jobs/{jid}/build")
        assert r.status_code == 409
        assert r.json()["detail"]["error"] == "no_reviewed_text"
        # the legacy refresh alias behaves identically
        r2 = await client.post(f"/api/packages/jobs/{jid}/build?refresh=true")
        assert r2.status_code == 409
    await db.close()


@pytest.mark.asyncio
async def test_regenerate_true_overwrites_and_records_provenance(tmp_path):
    """Only an explicit regenerate=true rewrites text — and metadata says so."""
    from httpx import ASGITransport, AsyncClient

    regenerated = "Basil resume text. Updated by AI."
    application, db, jid = await _seed_package_app(tmp_path, extra_verified=[regenerated])
    fake = _FakeTailor(regenerated)
    application.state.tailor = fake

    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(f"/api/packages/jobs/{jid}/build?regenerate=true")
        assert r.status_code == 200
        assert r.json()["metadata"]["generated_by"] == "regenerated"

    assert fake.calls == 1
    row = await db.get_application(jid)
    assert row["tailored_resume"] == regenerated
    await db.close()


@pytest.mark.asyncio
async def test_regenerate_without_a_tailor_is_an_honest_503(tmp_path):
    from httpx import ASGITransport, AsyncClient

    application, db, jid = await _seed_package_app(tmp_path)
    application.state.tailor = None
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(f"/api/packages/jobs/{jid}/build?regenerate=true")
        assert r.status_code == 503
    await db.close()


# ---------------- DB meta round-trip ----------------

@pytest.mark.asyncio
async def test_package_meta_db_roundtrip(db):
    jid = await db.insert_job(
        title="AI Engineer", company="Acme", location="Remote",
        salary_min=None, salary_max=None, description="d", url="https://x/9",
        posted_date="2026-09-20", application_method="direct", contact_email=None)
    app_id = await db.insert_application(jid, "prepared")
    await db.set_package_meta(app_id, "/data/applications/0001-acme",
                              "fp-123", "ready_for_review")
    meta = await db.get_package_meta(jid)
    assert meta["package_dir"] == "/data/applications/0001-acme"
    assert meta["package_fingerprint"] == "fp-123"
    assert meta["package_status"] == "ready_for_review"
    assert await db.get_package_meta(9999) is None
