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


# ---------------- O2: draft dedup is scoped by subject + recipient ----------------


def test_build_query_scopes_by_subject_and_recipient():
    q = GmailProvider._build_query("AI Engineer at Acme", "Jane <jane@acme.ai>")
    assert q == 'subject:"AI Engineer at Acme" to:jane@acme.ai'
    # no recipient -> subject-only (call site only dedups when it has an address)
    assert GmailProvider._build_query("S", "") == 'subject:"S"'
    # stray quotes must not break the Gmail query grammar
    assert '"' not in GmailProvider._build_query('Say "hi"', "a@b.co").split(" ", 1)[0][9:-1]


def test_headers_match_requires_same_recipient_and_subject():
    headers = {"subject": "Role at Acme", "to": "jane@acme.ai"}
    assert GmailProvider._headers_match(headers, "Role at Acme", "jane@acme.ai")
    # display-name form and case differences still match
    assert GmailProvider._headers_match(headers, "Role at Acme", "Jane <JANE@Acme.AI>")
    # O2 core: same subject, different recipient => NEVER adopt
    assert not GmailProvider._headers_match(headers, "Role at Acme", "bob@beta.io")
    # different subject => never adopt either
    assert not GmailProvider._headers_match(headers, "Other Role", "jane@acme.ai")


@pytest.mark.asyncio
async def test_find_existing_draft_rejects_mismatched_recipient():
    """Mailbox holds jane's draft; asking about bob's must return None (O2)."""
    gmail = GmailProvider(token="fake")

    async def _api_get(url, params):
        if url == GmailProvider.DRAFTS_URL:
            return {"drafts": [{"id": "d1"}]}
        return {"message": {"payload": {"headers": [
            {"name": "To", "value": "jane@acme.ai"},
            {"name": "Subject", "value": "Same subject"}]}}}

    gmail._api_get = _api_get
    assert await gmail.find_existing_draft("Same subject", "bob@beta.io") is None
    assert await gmail.find_existing_draft("Same subject", "jane@acme.ai") == {"id": "d1"}
    # listing must have been scoped by recipient too
    queries = []

    async def _spy(url, params):
        queries.append(params.get("q", ""))
        return None

    gmail._api_get = _spy
    await gmail.find_existing_draft("Same subject", "bob@beta.io")
    assert queries and "to:bob@beta.io" in queries[0]


@pytest.mark.asyncio
async def test_find_existing_draft_fails_closed_when_unverifiable():
    """No metadata / no listing => no adoption (a dup draft beats a mislink)."""
    gmail = GmailProvider(token="fake")

    async def _no_metadata(url, params):
        if url == GmailProvider.DRAFTS_URL:
            return {"drafts": [{"id": "d1"}]}
        return None  # header fetch failed

    gmail._api_get = _no_metadata
    assert await gmail.find_existing_draft("S", "jane@acme.ai") is None

    gmail._api_get = AsyncMock(return_value=None)  # listing failed
    assert await gmail.find_existing_draft("S", "jane@acme.ai") is None


@pytest.mark.asyncio
async def test_two_jobs_same_subject_get_distinct_drafts(db):
    """O2 regression: two jobs rendering the SAME subject must each own a draft.

    The mailbox only holds job A's draft. Job B (different recipient) must NOT
    adopt it — it must create its own draft and store its own draft id.
    """
    jid_a = await _mk_job(db, url="https://x/o2a")
    jid_b = await _mk_job(db, url="https://x/o2b")
    gmail = GmailProvider(token="fake")
    queries: list[str] = []

    async def _api_get(url, params):
        if url == GmailProvider.DRAFTS_URL:            # draft listing
            q = params.get("q", "")
            queries.append(q)
            return {"drafts": [{"id": "draft-A"}]}
        # metadata: only jane's draft exists, addressed to jane
        subject = queries[-1].split('subject:"', 1)[1].split('"', 1)[0]
        return {"message": {"payload": {"headers": [
            {"name": "To", "value": "jane@acme.ai"},
            {"name": "Subject", "value": subject}]}}}

    created: list[dict] = []

    async def _create(to, subject, body, thread_hint=""):
        created.append({"to": to, "subject": subject})
        return {"id": f"draft-{len(created)}", "provider": "gmail", "thread_id": ""}

    gmail._api_get = _api_get
    gmail.create_draft = _create
    service = _seqs_service(db, gmail=gmail)

    ra = await service.create_outreach(jid_a, contact_email="jane@acme.ai")
    rb = await service.create_outreach(jid_b, contact_email="bob@beta.io")

    # A adopted the verified draft; B created its own — ids must differ
    assert ra["message"]["draft_id"] == "draft-A"
    assert rb["message"]["draft_id"] == "draft-1"
    assert ra["message"]["draft_id"] != rb["message"]["draft_id"]
    assert len(created) == 1  # only B needed a new draft
    # both lookups were scoped by recipient
    assert any("to:jane@acme.ai" in q for q in queries)
    assert any("to:bob@beta.io" in q for q in queries)
