"""M9: Outreach engine + Gmail DRAFTS tests.

CRITICAL TEST #4 lives here: creating outreach twice MUST NOT create a second
draft — enforced at the service layer (dedup-first), the DB layer (UNIQUE
(job_id, audience)) and the provider layer (Gmail thread lookup). Also: DRAFT-ONLY
guarantee (no send path), anti-spam caps, deterministic rendering, follow-up gating.
"""
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.outreach import (
    AUDIENCES,
    GmailProvider,
    OutreachLimits,
    OutreachService,
    load_sequences,
    render_message,
)


def _seqs_service(db, gmail=None, limits=None):
    sequences, lim, identity = load_sequences()
    return OutreachService(db, sequences, limits or lim, identity,
                           gmail or GmailProvider(token=""))


async def _mk_job(db, **kw):
    base = dict(title="Senior AI Engineer", company="Acme AI", location="Remote",
                description="LLM products.", url="https://x/1",
                posted_date="2026-09-20")
    base.update(kw)
    jid = await db.insert_job(
        title=base["title"], company=base["company"], location=base["location"],
        salary_min=None, salary_max=None, description=base["description"],
        url=base["url"], posted_date=base["posted_date"],
        application_method="direct", contact_email=None)
    return jid


# ---------------- config + rendering (deterministic) ----------------

def test_sequences_load_with_required_audiences():
    sequences, limits, identity = load_sequences()
    assert "recruiter" in sequences and "hiring_manager" in sequences
    assert limits.max_outreach_per_day > 0
    assert identity.sender_name == "Basil Ahamed H"


def test_render_fills_all_placeholders_deterministically():
    sequences, _, identity = load_sequences()
    a = render_message(sequences["recruiter"], "Jane", "AI Engineer",
                       "Acme", identity)
    b = render_message(sequences["recruiter"], "Jane", "AI Engineer",
                       "Acme", identity)
    assert a == b  # deterministic
    assert "Jane" in a["body"] and "AI Engineer" in a["subject"]
    assert "{contact_name}" not in a["body"]  # nothing left unfilled
    assert "Basil Ahamed H" in a["body"]


def test_render_falls_back_for_unknown_contact():
    sequences, _, identity = load_sequences()
    out = render_message(sequences["recruiter"], "", "AI Engineer", "Acme", identity)
    assert "Hi there" in out["body"]


def test_render_collapses_blank_lines():
    sequences, _, identity = load_sequences()
    out = render_message(sequences["recruiter"], "Jane", "AI", "Acme", identity)
    assert "\n\n\n" not in out["body"]


# ---------------- CRITICAL TEST #4 ----------------

@pytest.mark.asyncio
async def test_critical_4_double_outreach_single_draft(db):
    """CRITICAL #4: outreach twice => exactly ONE message/draft."""
    jid = await _mk_job(db)
    service = _seqs_service(db)
    first = await service.create_outreach(jid)
    assert first["status"] == "created"
    second = await service.create_outreach(jid)
    assert second["status"] == "already_exists"
    # Same underlying message row:
    assert second["message"]["id"] == first["message"]["id"]
    rows = await db.list_outreach(100)
    assert len([r for r in rows if r["job_id"] == jid]) == 1


@pytest.mark.asyncio
async def test_critical_4_enforced_per_audience(db):
    """Same job allows different audiences, but never twice per audience."""
    jid = await _mk_job(db)
    service = _seqs_service(db)
    r1 = await service.create_outreach(jid, audience="recruiter")
    r2 = await service.create_outreach(jid, audience="hiring_manager")
    assert r1["status"] == "created" and r2["status"] == "created"
    dup = await service.create_outreach(jid, audience="recruiter")
    assert dup["status"] == "already_exists"
    assert len(await service.list_messages()) == 2


@pytest.mark.asyncio
async def test_critical_4_db_unique_constraint_backstop(db):
    """Even bypassing the service, the DB UNIQUE(job_id, audience) blocks dupes."""
    jid = await _mk_job(db)
    await db.insert_outreach(jid, "recruiter", "email", "x@y.z", "s", "b")
    with pytest.raises(Exception):
        await db.insert_outreach(jid, "recruiter", "email", "x@y.z", "s", "b")


# ---------------- DRAFT-ONLY guarantee ----------------

def test_gmail_provider_has_no_send_method():
    provider = GmailProvider(token="fake")
    assert not hasattr(provider, "send")
    assert not hasattr(provider, "send_message")
    assert hasattr(provider, "create_draft")  # drafts only


@pytest.mark.asyncio
async def test_gmail_unavailable_uses_local_draft(db):
    jid = await _mk_job(db)
    service = _seqs_service(db, gmail=GmailProvider(token=""))  # no token
    result = await service.create_outreach(jid, contact_email="jane@acme.ai")
    assert result["status"] == "created"
    assert result["message"]["provider"] == "local"  # stored draft, not sent
    assert result["message"]["status"] == "drafted"


@pytest.mark.asyncio
async def test_gmail_draft_created_when_token_present(db):
    jid = await _mk_job(db)
    gmail = GmailProvider(token="fake-token")
    gmail.find_existing_draft = AsyncMock(return_value=None)
    gmail.create_draft = AsyncMock(
        return_value={"id": "draft-123", "provider": "gmail", "thread_id": "th-9"})
    service = _seqs_service(db, gmail=gmail)
    result = await service.create_outreach(jid, contact_email="jane@acme.ai")
    assert result["message"]["provider"] == "gmail"
    assert result["message"]["draft_id"] == "draft-123"
    gmail.create_draft.assert_awaited_once()


@pytest.mark.asyncio
async def test_gmail_thread_dedup_prevents_second_draft(db):
    """Provider-layer dedup: existing Gmail draft with same subject => reuse id."""
    jid = await _mk_job(db)
    gmail = GmailProvider(token="fake")
    gmail.find_existing_draft = AsyncMock(return_value={"id": "existing-draft"})
    gmail.create_draft = AsyncMock()
    service = _seqs_service(db, gmail=gmail)
    result = await service.create_outreach(jid, contact_email="jane@acme.ai")
    gmail.create_draft.assert_not_awaited()  # never created a second draft
    assert result["message"]["draft_id"] == "existing-draft"


# ---------------- audience selection + caps ----------------

@pytest.mark.asyncio
async def test_audience_defaults_from_contact_on_file(db):
    jid = await _mk_job(db, hiring_manager_email="jane@acme.ai",
                        hiring_manager_title="Technical Recruiter")
    service = _seqs_service(db)
    result = await service.create_outreach(jid)
    assert result["message"]["audience"] == "recruiter"


@pytest.mark.asyncio
async def test_daily_cap_blocks_new_outreach(db):
    jid = await _mk_job(db)
    limits = OutreachLimits(max_outreach_per_day=0)  # everything blocked
    service = _seqs_service(db, limits=limits)
    result = await service.create_outreach(jid)
    assert result["status"] == "capped"
    assert "daily cap" in result["reason"]


@pytest.mark.asyncio
async def test_company_cap_counts_only_that_company(db):
    jid1 = await _mk_job(db, company="Flooded Co", url="https://x/1")
    jid2 = await _mk_job(db, company="Other Co", url="https://x/2")
    limits = OutreachLimits(max_outreach_per_day=10, per_company_daily_cap=1)
    service = _seqs_service(db, limits=limits)
    r1 = await service.create_outreach(jid1)
    r2 = await service.create_outreach(jid2, audience="hiring_manager")
    r3 = await service.create_outreach(jid1, audience="hiring_manager")
    assert r1["status"] == "created"
    assert r2["status"] == "created"          # other company unaffected
    assert r3["status"] == "capped"           # Flooded Co hit its cap


# ---------------- follow-up gating ----------------

@pytest.mark.asyncio
async def test_followup_requires_initial_outreach(db):
    jid = await _mk_job(db)
    service = _seqs_service(db)
    with pytest.raises(ValueError):
        await service.create_followup(jid)


@pytest.mark.asyncio
async def test_followup_too_soon_then_allowed(db):
    jid = await _mk_job(db)
    service = _seqs_service(db)
    await service.create_outreach(jid)
    soon = await service.create_followup(jid)
    assert soon["status"] == "too_soon"
    # Time-travel the first message beyond the wait window:
    old = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    await db.db.execute("UPDATE outreach_messages SET created_at = ? WHERE job_id = ?",
                        (old, jid))
    await db.db.commit()
    later = await service.create_followup(jid)
    assert later["status"] == "created"
    assert later["message"]["audience"] == "followup"


# ---------------- API surface ----------------

@pytest.mark.asyncio
async def test_outreach_api_create_twice_returns_same(tmp_path):
    from app.main import create_app
    from app.database import Database
    from httpx import ASGITransport, AsyncClient

    db_path = str(tmp_path / "t.db")
    application = create_app(db_path=db_path, testing=True)
    db = Database(db_path)
    await db.init()
    application.state.db = db
    jid = await db.insert_job(
        title="AI Engineer", company="Acme AI", location="Remote",
        salary_min=None, salary_max=None, description="d", url="https://x/3",
        posted_date="2026-09-20", application_method="direct", contact_email=None)
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r1 = await client.post(f"/api/outreach/jobs/{jid}/create", json={})
        assert r1.status_code == 200
        b1 = r1.json()
        assert b1["status"] == "created"
        r2 = await client.post(f"/api/outreach/jobs/{jid}/create", json={})
        b2 = r2.json()
        assert b2["status"] == "already_exists"
        assert b2["message"]["id"] == b1["message"]["id"]  # SAME message

        r = await client.get("/api/outreach/config")
        assert r.status_code == 200
        assert r.json()["gmail_connected"] is False  # no send capability configured
    await db.close()
