"""M15b — CRITICAL TEST #5: users must NEVER see each other's data.

Runs against a REAL app (testing=False) so the auth guard AND the workspace
middleware are fully active: admin creates users, each user logs in with their
own session, and every data domain (jobs, applications, contacts, resumes,
settings, API keys, search config, evidence, packages) must be isolated
per workspace. Structural guarantee — each request only ever opens the
requesting user's own SQLite DB.
"""

from __future__ import annotations

import os

import pytest
from httpx import ASGITransport, AsyncClient

ADMIN = ("basil", "admin-pass-123")
ALICE = ("alice", "alice-pass-123")
BOB = ("bob", "bob-pass-123")


@pytest.fixture
async def world(tmp_path, monkeypatch):
    """A real app + admin/alice/bob, each with their own logged-in client."""
    from app.main import create_app
    application = create_app(db_path=str(tmp_path / "data" / "jobagent.db"),
                             testing=False)
    async with application.router.lifespan_context(application):
        clients: dict[str, AsyncClient] = {}

        async def fresh():
            c = AsyncClient(transport=ASGITransport(app=application),
                            base_url="http://test", timeout=60)
            return c

        admin = await fresh()
        r = await admin.post("/api/auth/bootstrap",
                             json={"username": ADMIN[0], "password": ADMIN[1]})
        assert r.status_code == 200, r.text
        clients["admin"] = admin
        for name, pwd in (("alice", ALICE[1]), ("bob", BOB[1])):
            r = await admin.post("/api/auth/users",
                                 json={"username": name, "password": pwd,
                                       "role": "user"})
            assert r.status_code == 200, r.text
            c = await fresh()
            r = await c.post("/api/auth/login",
                             json={"username": name, "password": pwd})
            assert r.status_code == 200, r.text
            clients[name] = c

        yield application, clients
        for c in clients.values():
            await c.aclose()


async def _add_external_job(client, title):
    r = await client.post("/api/jobs/save-external",
                          json={"title": title, "company": "ACME",
                                "description": "isolation probe"})
    assert r.status_code == 200, r.text
    return r.json().get("id") or r.json().get("job_id")


# ------------------------------------------------------------------ jobs

@pytest.mark.asyncio
async def test_jobs_are_isolated(world):
    _app, clients = world
    jid = await _add_external_job(clients["alice"], "Alice Secret Job")

    alice_jobs = (await clients["alice"].get("/api/jobs")).json()["jobs"]
    bob_jobs = (await clients["bob"].get("/api/jobs")).json()["jobs"]
    admin_jobs = (await clients["admin"].get("/api/jobs")).json()["jobs"]

    assert any(j["id"] == jid for j in alice_jobs), "alice must see her own job"
    assert all(j["id"] != jid for j in bob_jobs), "BOB MUST NOT see alice's job"
    assert all(j["id"] != jid for j in admin_jobs), "admin must not see it either"
    # Direct fetch by id must 404 for the other users.
    assert (await clients["bob"].get(f"/api/jobs/{jid}")).status_code == 404
    assert (await clients["admin"].get(f"/api/jobs/{jid}")).status_code == 404


# ------------------------------------------------------------------ contacts

@pytest.mark.asyncio
async def test_contacts_are_isolated(world):
    _app, clients = world
    r = await clients["alice"].post("/api/contacts",
                                    json={"name": "Alice Recruiter",
                                          "email": "recruiter@alice-only.test"})
    assert r.status_code == 200, r.text

    alice = (await clients["alice"].get("/api/contacts")).json()["contacts"]
    bob = (await clients["bob"].get("/api/contacts")).json()["contacts"]
    assert any(c["email"] == "recruiter@alice-only.test" for c in alice)
    assert bob == [], "bob must have zero contacts from alice"


# ------------------------------------------------------------------ settings / keys

@pytest.mark.asyncio
async def test_ai_key_and_search_config_are_isolated(world):
    _app, clients = world
    # Alice configures HER own provider + key + search terms.
    r = await clients["alice"].post("/api/ai-settings",
                                    json={"provider": "deepseek",
                                          "api_key": "sk-alice-secret-key",
                                          "model": "deepseek-flash"})
    assert r.status_code == 200, r.text
    r = await clients["alice"].post("/api/search-config/terms",
                                    json={"search_terms": ["AliceOnlyTerm"]})
    assert r.status_code == 200, r.text

    alice_ai = (await clients["alice"].get("/api/ai-settings")).json()
    bob_ai = (await clients["bob"].get("/api/ai-settings")).json()
    assert alice_ai.get("provider") == "deepseek"
    assert alice_ai.get("has_key") is True
    assert bob_ai.get("provider") != "deepseek", "bob must not inherit alice's provider"
    assert bob_ai.get("has_key") in (False, None), "BOB MUST NOT see alice's key"

    alice_cfg = (await clients["alice"].get("/api/search-config")).json()
    bob_cfg = (await clients["bob"].get("/api/search-config")).json()
    assert "AliceOnlyTerm" in (alice_cfg.get("search_terms") or [])
    assert "AliceOnlyTerm" not in (bob_cfg.get("search_terms") or [])


@pytest.mark.asyncio
async def test_resumes_are_isolated(world):
    _app, clients = world
    r = await clients["alice"].post("/api/resumes",
                                    json={"name": "alice_cv.txt",
                                          "resume_text": "ALICE ONLY RESUME TEXT"})
    assert r.status_code == 200, r.text
    alice = (await clients["alice"].get("/api/resumes")).json()["resumes"]
    bob = (await clients["bob"].get("/api/resumes")).json()["resumes"]
    assert any("alice_cv" in (rv.get("name") or "") for rv in alice)
    assert bob == [], "bob must have no resumes from alice"


# ------------------------------------------------------------------ profile / CRM

@pytest.mark.asyncio
async def test_profile_and_applications_are_isolated(world):
    _app, clients = world
    await clients["alice"].post("/api/profile", json={"full_name": "Alice A"})
    alice_profile = (await clients["alice"].get("/api/profile")).json()
    bob_profile = (await clients["bob"].get("/api/profile")).json()
    assert alice_profile.get("full_name") == "Alice A"
    assert bob_profile.get("full_name") in ("", None)

    jid = await _add_external_job(clients["alice"], "Tracked Job")
    r = await clients["alice"].post(f"/api/jobs/{jid}/status?to_status=applied")
    assert r.status_code == 200, r.text
    alice_pipeline = (await clients["alice"].get("/api/pipeline")).json()
    bob_pipeline = (await clients["bob"].get("/api/pipeline")).json()
    assert alice_pipeline and alice_pipeline != bob_pipeline
    assert not (bob_pipeline.get("jobs") or []), "bob's pipeline must stay empty"


# ------------------------------------------------------------------ evidence

@pytest.mark.asyncio
async def test_evidence_profiles_are_isolated(world):
    app, clients = world
    r = await clients["alice"].get("/api/evidence")
    assert r.status_code == 200, r.text
    # Each user's evidence store loads from THEIR OWN workspace profile dir.
    from app.main import _db  # noqa: F401  (documents the bridge contract)
    ws_alice = app.state.workspaces._cache  # populated by authenticated traffic
    assert ws_alice, "workspaces must be created for authenticated users"
    dirs = {ws.user_id: ws.profile_dir for ws in ws_alice.values()}
    assert len(set(dirs.values())) == len(dirs), "each user needs a distinct profile dir"
    for path in dirs.values():
        assert os.path.isdir(path), f"missing profile dir {path}"


# ------------------------------------------------------------------ workspaces

@pytest.mark.asyncio
async def test_workspace_dirs_and_dbs_are_distinct(world):
    app, clients = world
    await clients["alice"].get("/api/jobs")
    await clients["bob"].get("/api/jobs")
    await clients["admin"].get("/api/jobs")

    cache = app.state.workspaces._cache
    assert len(cache) >= 3, f"expected 3 workspaces, got {len(cache)}"
    db_paths = {ws.db.path if hasattr(ws.db, "path") else ws.dir for ws in cache.values()}
    assert len(db_paths) == len(cache), "each user must map to their own DB"
    for ws in cache.values():
        assert os.path.isdir(ws.dir)
        assert os.path.isdir(ws.applications_dir)
        assert os.path.isdir(ws.drafts_dir)


# ------------------------------------------------------------------ admin powers

@pytest.mark.asyncio
async def test_admin_does_not_auto_see_user_data(world):
    """Full admin access is explicit (user management + audit log), NOT an
    accidental side effect of sharing one database."""
    _app, clients = world
    jid = await _add_external_job(clients["alice"], "Alice Private Job")
    admin_jobs = (await clients["admin"].get("/api/jobs")).json()["jobs"]
    assert all(j["id"] != jid for j in admin_jobs)
    # But admin CAN manage the accounts themselves.
    r = await clients["admin"].get("/api/auth/users")
    assert r.status_code == 200
    names = [u["username"] for u in r.json()["users"]]
    assert {"basil", "alice", "bob"} <= set(names)


# ------------------------------------------------------------------ migration

@pytest.mark.asyncio
async def test_migration_never_moves_a_wal_belonging_to_another_db(tmp_path):
    """Regression: main.py re-creates the pre-multi-user DB at data/jobagent.db
    on EVERY boot, so when the (idempotent) migration runs again its -wal/-shm
    sidecars belong to that fresh file — not to the admin's workspace DB.

    Migrating a sidecar on its own grafts the old DB's WAL onto the workspace
    DB; SQLite then reads page 1 from the wrong database and startup dies with
    "database disk image is malformed".
    """
    import sqlite3

    from app.workspace import WorkspaceManager

    users_root = tmp_path / "users"
    wdir = users_root / "1-basil"
    wdir.mkdir(parents=True)
    ws_db = wdir / "jobagent.db"

    # The already-migrated admin workspace DB, cleanly shut down (no sidecars).
    con = sqlite3.connect(ws_db)
    con.execute("CREATE TABLE jobs(id INTEGER)")
    con.execute("INSERT INTO jobs VALUES (1)")
    con.commit()
    con.close()
    assert not (wdir / "jobagent.db-wal").exists()

    # The fresh main DB this boot created, with ACTIVE WAL/SHM sidecars.
    data = tmp_path / "data"
    data.mkdir()
    fresh = sqlite3.connect(data / "jobagent.db", isolation_level=None)
    try:
        fresh.execute("CREATE TABLE jobs(id INTEGER)")
        fresh.execute("PRAGMA journal_mode=WAL")
        fresh.execute("INSERT INTO jobs VALUES (2)")
        assert (data / "jobagent.db-wal").exists(), "precondition: fresh DB has a WAL"

        mgr = WorkspaceManager(users_root=str(users_root))
        moved = await mgr.migrate_single_user(
            str(data), {"id": 1, "username": "basil"})

        assert not (wdir / "jobagent.db-wal").exists(), \
            "a WAL from another DB was hijacked into the workspace"
        assert not (wdir / "jobagent.db-shm").exists()
        assert "jobagent.db-wal" not in moved
        assert (data / "jobagent.db-wal").exists(), "the main DB keeps its own WAL"

        # The workspace DB must still be readable — this is what broke startup.
        check = sqlite3.connect(ws_db)
        try:
            assert check.execute("SELECT count(*) FROM jobs").fetchone()[0] == 1
        finally:
            check.close()
    finally:
        fresh.close()


@pytest.mark.asyncio
async def test_first_migration_moves_db_together_with_its_wal(tmp_path):
    """The sidecars of the DB being migrated must still travel WITH it."""
    import sqlite3

    from app.workspace import WorkspaceManager

    data = tmp_path / "data"
    data.mkdir()
    con = sqlite3.connect(data / "jobagent.db", isolation_level=None)
    try:
        con.execute("CREATE TABLE jobs(id INTEGER)")
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("INSERT INTO jobs VALUES (7)")
        assert (data / "jobagent.db-wal").exists(), "precondition: DB has a WAL"

        mgr = WorkspaceManager(users_root=str(tmp_path / "users"))
        await mgr.migrate_single_user(str(data), {"id": 1, "username": "basil"})

        wdir = tmp_path / "users" / "1-basil"
        assert (wdir / "jobagent.db").exists()
        assert (wdir / "jobagent.db-wal").exists()
        assert not (data / "jobagent.db").exists()
    finally:
        con.close()

    check = sqlite3.connect(tmp_path / "users" / "1-basil" / "jobagent.db")
    try:
        assert check.execute(
            "SELECT count(*) FROM jobs").fetchone()[0] == 1
    finally:
        check.close()


# ------------------------------------------------- resume-driven search gate

async def _seed_resume(client) -> None:
    """Upload a .txt resume without touching a real provider.

    In test mode the analysis call is stubbed to an empty result, but the upload
    still stores resume_text into search_config — exactly what the gate needs.
    """
    r = await client.post(
        "/api/resume/upload",
        files={"file": ("candidate.txt", b"AI Engineer\nPython, LLM, RAG", "text/plain")})
    assert r.status_code == 200, r.text


def _stub_resume_ai(monkeypatch) -> None:
    """Replace the two resume-AI calls with deterministic empty results so no
    provider is contacted and no key is needed."""
    import app.resume_analyzer as resume_analyzer

    async def _empty_analysis(client, text):
        return {"search_terms": [], "job_titles": [], "key_skills": [],
                "seniority": "", "summary": "", "ats_score": 0,
                "ats_issues": [], "ats_tips": []}

    async def _empty_profile(client, text):
        return {}

    monkeypatch.setattr(resume_analyzer, "analyze_resume", _empty_analysis)
    monkeypatch.setattr(resume_analyzer, "parse_resume_to_profile", _empty_profile)


@pytest.mark.asyncio
async def test_search_blocked_until_a_resume_exists(world, monkeypatch):
    """A brand-new user cannot search/discover before uploading a resume, and
    the block is per-user (one user's resume never unlocks another's search)."""
    _stub_resume_ai(monkeypatch)

    _app, clients = world
    r = await clients["alice"].post("/api/scrape")
    assert r.status_code == 428, r.text
    assert "resume" in r.text.lower()
    r = await clients["alice"].post("/api/discovery/run?passes=1")
    assert r.status_code == 428, r.text

    # Alice uploads; Bob still has none and must stay blocked.
    await _seed_resume(clients["alice"])
    r = await clients["bob"].post("/api/scrape")
    assert r.status_code == 428, "bob must not inherit alice's resume"

    # Alice's gate is now lifted: scrape is accepted (not 428). The pipeline is
    # stubbed so no real network scrape is launched.
    import app.routers.scraping as scraping_router

    async def _noop(app_, task_id, db=None, matcher=None):
        return None

    monkeypatch.setattr(scraping_router, "_scrape_and_score", _noop)
    r = await clients["alice"].post("/api/scrape")
    assert r.status_code == 202, r.text


@pytest.mark.asyncio
async def test_keyword_confirm_screen_saves_and_is_isolated(world, monkeypatch):
    """The onboarding confirm/edit step saves the user's own keywords and those
    keywords never leak into another user's search config."""
    _stub_resume_ai(monkeypatch)

    _app, clients = world
    await _seed_resume(clients["alice"])
    r = await clients["alice"].post(
        "/api/search-config/keywords",
        json={"search_terms": ["RAG Engineer", "LLM Engineer"],
              "key_skills": ["Python", "LangChain"]})
    assert r.status_code == 200, r.text

    alice_cfg = (await clients["alice"].get("/api/search-config")).json()
    assert alice_cfg["search_terms"] == ["RAG Engineer", "LLM Engineer"]
    assert "Python" in alice_cfg["key_skills"]

    bob_cfg = (await clients["bob"].get("/api/search-config")).json()
    assert bob_cfg.get("search_terms") in ([], None)

    # Empty payloads are rejected rather than silently clearing the config.
    r = await clients["alice"].post("/api/search-config/keywords", json={})
    assert r.status_code == 400, r.text
