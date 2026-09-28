"""Real-scenario multi-user tests — two logged-in users over live HTTP.

Unlike the main unit suite (which runs `testing=True` and therefore bypasses the
auth guard), these run a REAL app with `testing=False`, so
`AuthGuardMiddleware` and `WorkspaceMiddleware` are fully active and every
request lands in that user's own workspace. This is the shape of test that
answers: *what actually happens when two people are signed in at the same time?*

One test per item in `docs/NEXT_5_PLAN.md`.

    N1  test_gmail_token_is_per_user        — two tokens, two mailboxes, masked
"""

from __future__ import annotations

import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.outreach import GmailProvider

PASSWORD = "scenario-pass-123"
ENV_TOKEN = "shared-env-token-XYZ"
ADMIN_TOK = "tok-admin-AAAA1111"
ALICE_TOK = "tok-alice-BBBB2222"


# ------------------------------------------------------------------ fixtures


@pytest.fixture
async def app(tmp_path):
    """A REAL app instance (auth guard active) with a live lifespan."""
    from app.main import create_app

    application = create_app(db_path=str(tmp_path / "scenario.db"), testing=False)
    async with application.router.lifespan_context(application):
        yield application


def _client(application) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=application), base_url="http://test")


@pytest.fixture
async def two_users(app):
    """An admin plus a second user, BOTH logged in with their own cookies."""
    admin = _client(app)
    alice = _client(app)
    try:
        r = await admin.post("/api/auth/bootstrap",
                             json={"username": "basil", "password": PASSWORD})
        assert r.status_code == 200, r.text
        r = await admin.post("/api/auth/users",
                             json={"username": "alice", "password": PASSWORD,
                                   "role": "user"})
        assert r.status_code == 200, r.text
        r = await alice.post("/api/auth/login",
                             json={"username": "alice", "password": PASSWORD})
        assert r.status_code == 200, r.text
        # Sanity: genuinely different sessions.
        assert (await admin.get("/api/auth/me")).json()["user"]["username"] == "basil"
        assert (await alice.get("/api/auth/me")).json()["user"]["username"] == "alice"
        yield admin, alice
    finally:
        await admin.aclose()
        await alice.aclose()


async def _save_job(client, tag: str) -> int:
    """Create a real job in THIS user's workspace through the public API."""
    r = await client.post("/api/jobs/save-external", json={
        "title": f"ML Engineer {tag}",
        "company": f"Acme {tag}",
        "location": "Berlin, Germany",
        "url": f"https://example.com/jobs/{tag}",
        "description": ("Build production RAG systems with Python, FastAPI, "
                        "LangChain and vector databases. Visa sponsorship "
                        "available for relocation to Berlin."),
        "posted_date": "2026-09-20",
    })
    assert r.status_code == 200, r.text
    return r.json()["job_id"]


@pytest.fixture
def fake_gmail(monkeypatch):
    """Record the token every Gmail draft is built with; never dedup."""
    captured: list[dict] = []

    async def _no_dedup(self, subject):
        return None

    async def _create(self, to, subject, body, thread_hint=""):
        captured.append({"token": self.token, "to": to, "subject": subject})
        return {"id": f"draft-{len(captured)}", "provider": "gmail",
                "thread_id": ""}

    monkeypatch.setattr(GmailProvider, "find_existing_draft", _no_dedup)
    monkeypatch.setattr(GmailProvider, "create_draft", _create)
    return captured


# --------------------------------------------------------------------- N1


@pytest.mark.asyncio
async def test_gmail_token_is_per_user(two_users, fake_gmail):
    admin, alice = two_users

    ADMIN_TOK = "tok-admin-AAAA1111"
    ALICE_TOK = "tok-alice-BBBB2222"

    # 1) Each user saves THEIR OWN token through the public API.
    for client, token in ((admin, ADMIN_TOK), (alice, ALICE_TOK)):
        r = await client.post("/api/settings/email", json={"gmail_token": token})
        assert r.status_code == 200, r.text

    # 2) Read-back is masked for BOTH users — the raw value never leaves the server.
    for client, token in ((admin, ADMIN_TOK), (alice, ALICE_TOK)):
        email = (await client.get("/api/settings/email")).json()
        assert email["gmail_connected"] is True
        assert token not in json.dumps(email)
        assert email["gmail_token"].startswith("****")
        cfg = (await client.get("/api/outreach/config")).json()
        assert cfg["gmail_connected"] is True
        assert cfg["gmail_source"] == "workspace"
        assert token not in json.dumps(cfg), "outreach config leaked a raw token"

    # 3) Neither user can see the OTHER's token anywhere.
    admin_email = json.dumps((await admin.get("/api/settings/email")).json())
    alice_email = json.dumps((await alice.get("/api/settings/email")).json())
    assert ALICE_TOK[-4:] not in admin_email
    assert ADMIN_TOK[-4:] not in alice_email

    # 4) Round-tripping the masked value must NOT blank the stored credential.
    r = await alice.post("/api/settings/email", json={"gmail_token": "****2222"})
    assert r.status_code == 200, r.text
    assert (await alice.get("/api/outreach/config")).json()["gmail_connected"] is True

    # 5) Each user's draft is created with THAT user's token.
    job_admin = await _save_job(admin, "admin")
    job_alice = await _save_job(alice, "alice")

    r = await admin.post(f"/api/outreach/jobs/{job_admin}/create",
                         json={"audience": "recruiter",
                               "contact_email": "hr@acme-admin.example"})
    assert r.status_code == 200, r.text
    r = await alice.post(f"/api/outreach/jobs/{job_alice}/create",
                         json={"audience": "recruiter",
                               "contact_email": "hr@acme-alice.example"})
    assert r.status_code == 200, r.text
    assert all(b.get("message", {}).get("provider") in ("gmail", "local")
               for b in (r.json(),))

    tokens = [c["token"] for c in fake_gmail]
    assert ADMIN_TOK in tokens, f"admin draft used {tokens}"
    assert ALICE_TOK in tokens, f"alice draft used {tokens}"
    # One draft per user, each rendered for its own job (different subjects).
    assert len(fake_gmail) == 2
    assert len({c["subject"] for c in fake_gmail}) == 2
    assert all(c["to"] for c in fake_gmail)

    # 6) Isolation: the SAME numeric job id points at DIFFERENT rows in each
    #    workspace (ids are per-user), and each workspace holds only its own
    #    outreach — nothing crosses over.
    async def _job(client, jid):
        resp = await client.get(f"/api/jobs/{jid}")
        assert resp.status_code == 200, resp.text
        payload = resp.json()
        return payload.get("job", payload)

    admin_row = await _job(admin, job_alice)   # id 1 in ADMIN's workspace
    alice_row = await _job(alice, job_alice)   # id 1 in ALICE's workspace
    assert admin_row["company"] == "Acme admin"
    assert alice_row["company"] == "Acme alice"
    assert admin_row["title"] != alice_row["title"]

    admin_msgs = json.dumps((await admin.get("/api/outreach/messages")).json())
    alice_msgs = json.dumps((await alice.get("/api/outreach/messages")).json())
    assert "Acme admin" in admin_msgs and "Acme alice" not in admin_msgs
    assert "Acme alice" in alice_msgs and "Acme admin" not in alice_msgs


@pytest.mark.asyncio
async def test_gmail_env_fallback_only_when_no_workspace_token(two_users, fake_gmail,
                                                              monkeypatch):
    """Legacy single-user installs still work: env token is the fallback only."""
    admin, alice = two_users
    monkeypatch.setenv("JOBAGENT_GMAIL_TOKEN", ENV_TOKEN)

    # admin has never stored a token → falls back to env
    cfg = (await admin.get("/api/outreach/config")).json()
    assert cfg["gmail_connected"] is True
    assert cfg["gmail_source"] == "env"

    # alice stores her own → hers wins over the shared env
    await alice.post("/api/settings/email", json={"gmail_token": ALICE_TOK})
    cfg = (await alice.get("/api/outreach/config")).json()
    assert cfg["gmail_source"] == "workspace"

    job_admin = await _save_job(admin, "env-admin")
    job_alice = await _save_job(alice, "env-alice")
    await admin.post(f"/api/outreach/jobs/{job_admin}/create",
                     json={"audience": "recruiter",
                           "contact_email": "hr@env-admin.example"})
    await alice.post(f"/api/outreach/jobs/{job_alice}/create",
                     json={"audience": "recruiter",
                           "contact_email": "hr@env-alice.example"})

    tokens = [c["token"] for c in fake_gmail]
    assert ENV_TOKEN in tokens, f"env fallback not used: {tokens}"
    assert ALICE_TOK in tokens, f"workspace token not used: {tokens}"


@pytest.mark.asyncio
async def test_clear_gmail_token_disconnects_only_that_user(two_users, fake_gmail):
    admin, alice = two_users
    await admin.post("/api/settings/email", json={"gmail_token": "tok-admin-AAAA1111"})
    await alice.post("/api/settings/email", json={"gmail_token": ALICE_TOK})

    r = await alice.post("/api/settings/email", json={"clear_gmail_token": True})
    assert r.status_code == 200, r.text

    alice_cfg = (await alice.get("/api/outreach/config")).json()
    admin_cfg = (await admin.get("/api/outreach/config")).json()
    assert alice_cfg["gmail_connected"] is False
    assert alice_cfg["gmail_source"] == ""
    # the other user is untouched
    assert admin_cfg["gmail_connected"] is True
    assert admin_cfg["gmail_source"] == "workspace"


@pytest.mark.asyncio
async def test_outreach_still_works_without_any_gmail_token(two_users, monkeypatch):
    """No token anywhere → local-draft fallback (pipeline completes offline)."""
    monkeypatch.delenv("JOBAGENT_GMAIL_TOKEN", raising=False)
    admin, alice = two_users
    job = await _save_job(admin, "local-only")
    r = await admin.post(f"/api/outreach/jobs/{job}/create",
                         json={"audience": "recruiter",
                               "contact_email": "nobody@example.com"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "created"
    assert body["message"]["provider"] == "local"
    assert not body["message"].get("draft_id")

    cfg = (await admin.get("/api/outreach/config")).json()
    assert cfg["gmail_connected"] is False
