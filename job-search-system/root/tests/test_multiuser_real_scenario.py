"""Real-scenario multi-user tests — two logged-in users over live HTTP.

Unlike the main unit suite (which runs `testing=True` and therefore bypasses the
auth guard), these run a REAL app with `testing=False`, so
`AuthGuardMiddleware` and `WorkspaceMiddleware` are fully active and every
request lands in that user's own workspace. This is the shape of test that
answers: *what actually happens when two people are signed in at the same time?*

One test per item in `docs/NEXT_5_PLAN.md`.

    N1  test_gmail_token_is_per_user        — two tokens, two mailboxes, masked
    N3  test_two_users_runs_are_isolated    — concurrent runs, no cross-user leak
    N2  test_scheduler_runs_per_user        — scheduled tick reaches every user
"""

from __future__ import annotations

import asyncio
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


# --------------------------------------------------------------------- N3


async def _seed_resume(client) -> None:
    """Give this user a usable resume so the no-resume gate (428) lets them search."""
    r = await client.post(
        "/api/resume/upload",
        files={"file": ("candidate.txt",
                        b"AI Engineer\nPython, LLM, RAG, FastAPI", "text/plain")})
    assert r.status_code == 200, r.text


async def _wait_until(predicate, timeout=5.0, interval=0.01) -> bool:
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if predicate():
            return True
        await asyncio.sleep(interval)
    return False


@pytest.mark.asyncio
async def test_two_users_runs_are_isolated(two_users, monkeypatch):
    """N3: one user's run must never block or leak into another's.

    Before the run-state registry, discovery/scrape progress lived in single
    process-global slots: B's "start" returned already_running (or 409), and B's
    progress bar showed A's numbers. Now every run is keyed by user id.
    """
    import app.discovery as discovery_mod
    import app.main as main_mod
    import app.routers.scraping as scraping_mod

    # No AI anywhere: resume upload takes its reduced-analysis path, no network.
    monkeypatch.setattr(main_mod, "_build_ai_client",
                        lambda *a, **k: None)

    admin, alice = two_users
    await _seed_resume(admin)
    await _seed_resume(alice)

    gate = asyncio.Event()
    entered: list = []

    async def _blocking_discovery(db, registry, adapters, progress=None,
                                  max_passes=None, scraper_keys=None):
        entered.append(progress)
        await gate.wait()
        return {"done": True}

    async def _blocking_scrape(*args, **kwargs):
        await gate.wait()

    async def _noop(*args, **kwargs):
        return 0

    monkeypatch.setattr(discovery_mod, "run_discovery_cycle", _blocking_discovery)
    monkeypatch.setattr(scraping_mod, "run_scrape_cycle", _blocking_scrape)
    monkeypatch.setattr(scraping_mod, "run_enrichment_cycle", _noop)
    monkeypatch.setattr(scraping_mod, "run_location_classification", _noop)

    try:
        # --- discovery: BOTH can run at once, over separate progress dicts ---
        r1 = await admin.post("/api/discovery/run?passes=1")
        r2 = await alice.post("/api/discovery/run?passes=1")
        assert r1.status_code == 200, r1.text
        assert r2.status_code == 200, r2.text
        assert r1.json()["status"] == "discovery_started"
        # The whole point: B is NOT told "already_running".
        assert r2.json()["status"] == "discovery_started"

        assert await _wait_until(lambda: len(entered) == 2), \
            "both discovery cycles should have entered"
        # ...and each got its OWN progress dict, not a shared global.
        assert entered[0] is not entered[1]

        a_status = (await admin.get("/api/discovery/status")).json()
        b_status = (await alice.get("/api/discovery/status")).json()
        assert a_status["running"] is True
        assert b_status["running"] is True

        # --- scrape: A running must not make B see A's progress or a 409 ----
        a_scrape = await admin.post("/api/scrape")
        assert a_scrape.status_code == 202, a_scrape.text
        await asyncio.sleep(0.05)

        a_prog = (await admin.get("/api/scrape/progress")).json()
        b_prog = (await alice.get("/api/scrape/progress")).json()
        assert a_prog["active"] is True
        assert b_prog["active"] is False        # B does not see A's run

        b_scrape = await alice.post("/api/scrape")
        assert b_scrape.status_code == 202, b_scrape.text   # not 409
    finally:
        gate.set()
        await asyncio.sleep(0.1)


@pytest.mark.asyncio
async def test_scrape_per_ip_cap_returns_429(two_users, monkeypatch):
    """N3: the per-IP advisory cap answers 429, not a silent no-op."""
    import app.main as main_mod
    import app.routers.scraping as scraping_mod

    monkeypatch.setattr(main_mod, "_build_ai_client", lambda *a, **k: None)
    monkeypatch.setattr(scraping_mod, "MAX_CONCURRENT_SCRAPES_PER_IP", 1)

    admin, alice = two_users
    await _seed_resume(admin)
    await _seed_resume(alice)

    gate = asyncio.Event()

    async def _blocking(*args, **kwargs):
        await gate.wait()

    async def _noop(*args, **kwargs):
        return 0

    monkeypatch.setattr(scraping_mod, "run_scrape_cycle", _blocking)
    monkeypatch.setattr(scraping_mod, "run_enrichment_cycle", _noop)
    monkeypatch.setattr(scraping_mod, "run_location_classification", _noop)

    try:
        first = await admin.post("/api/scrape")
        assert first.status_code == 202, first.text
        await asyncio.sleep(0.05)

        second = await alice.post("/api/scrape")
        assert second.status_code == 429, second.text
        assert second.json()["error"] == "too_many_concurrent_scrapes"
    finally:
        gate.set()
        await asyncio.sleep(0.1)


# --------------------------------------------------------------------- N2


@pytest.mark.asyncio
async def test_scheduler_runs_per_user(app, two_users, monkeypatch):
    """N2: one scheduled tick must reach EVERY active user's workspace.

    Before N2 every APScheduler job ran against `app.state.bg_db` — the ADMIN's
    workspace — so a second user's pool never got background discovery, scoring
    or refresh at all. Disabled users must be skipped.

    `Database.get_scraper_keys` is the last thing each per-user scrape does
    before building scrapers; patching it records WHICH workspace DB the cycle
    was pointed at, then aborts that user's run before any network call.
    """
    from app.database import Database

    admin, alice = two_users
    admin_job = await _save_job(admin, "sched-admin")
    await _save_job(alice, "sched-alice")

    # A third, DISABLED user must be skipped entirely.
    r = await admin.post("/api/auth/users",
                         json={"username": "carol", "password": PASSWORD,
                               "role": "user"})
    assert r.status_code == 200, r.text
    carol_id = r.json()["user"]["id"]
    r = await admin.post(f"/api/auth/users/{carol_id}/disable")
    assert r.status_code == 200, r.text

    class _AbortRun(Exception):
        """Abort this user's scheduled run before it touches the network."""

    seen: list = []

    async def _record_then_abort(self):
        seen.append(self)
        raise _AbortRun()

    monkeypatch.setattr(Database, "get_scraper_keys", _record_then_abort)

    await app.state.scheduled_jobs["scrape"]()

    # Exactly the two ACTIVE users — carol is disabled, so never visited.
    assert len(seen) == 2, f"expected 2 active users, saw {len(seen)}"
    assert seen[0] is not seen[1]          # two distinct workspace DBs

    owners = []
    for db in seen:
        # Job ids are per-workspace rowids, so they collide (both first jobs are
        # id 1). Identify the workspace by the job's own tag instead.
        job = await db.get_job(admin_job)
        owners.append(job["title"] if job else None)
    # Each cycle ran against that user's OWN workspace, holding their own job.
    assert sorted(t for t in owners if t) == [
        "ML Engineer sched-admin", "ML Engineer sched-alice"]
