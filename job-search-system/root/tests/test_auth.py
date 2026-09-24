"""M15a — auth foundation tests.

These run against a REAL app (testing=False) so the AuthGuardMiddleware is
fully active — unlike the main suite where the guard is bypassed.
Critical: every non-public API route must 401 without a session.
"""

from __future__ import annotations

import time

import pytest
from http import HTTPStatus
from httpx import ASGITransport, AsyncClient

from app.auth import (
    MAX_LOGIN_FAILURES,
    hash_password,
    verify_password,
)


# ------------------------------------------------------------------ hashing

def test_password_hash_roundtrip():
    stored = hash_password("correct horse battery staple")
    assert stored.startswith("scrypt$")
    assert verify_password("correct horse battery staple", stored)


def test_password_hash_rejects_wrong_password():
    stored = hash_password("secret-password")
    assert not verify_password("wrong-password", stored)


def test_password_hash_is_salted():
    assert hash_password("same") != hash_password("same")


def test_verify_password_malformed_stored_value():
    assert not verify_password("x", "not-a-valid-hash")
    assert not verify_password("x", "")


# ------------------------------------------------------------------ fixtures

@pytest.fixture
async def auth_app(tmp_path):
    from app.main import create_app
    application = create_app(db_path=str(tmp_path / "test.db"), testing=False)
    async with application.router.lifespan_context(application):
        yield application


@pytest.fixture
async def auth_client(auth_app):
    async with AsyncClient(transport=ASGITransport(app=auth_app),
                           base_url="http://test") as c:
        yield c


async def _bootstrap_admin(client) -> None:
    r = await client.post("/api/auth/bootstrap",
                          json={"username": "basil", "password": "admin-pass-123"})
    assert r.status_code == 200, r.text


async def _login(client, username="basil", password="admin-pass-123"):
    return await client.post("/api/auth/login",
                             json={"username": username, "password": password})


# ------------------------------------------------------------------ bootstrap

@pytest.mark.asyncio
async def test_status_reports_needs_bootstrap(auth_client):
    r = await auth_client.get("/api/auth/status")
    assert r.status_code == 200
    body = r.json()
    assert body["needs_bootstrap"] is True
    assert body["authenticated"] is False


@pytest.mark.asyncio
async def test_bootstrap_creates_admin_and_session(auth_client):
    await _bootstrap_admin(auth_client)
    status = (await auth_client.get("/api/auth/status")).json()
    assert status["needs_bootstrap"] is False
    assert status["authenticated"] is True
    assert status["user"]["role"] == "admin"


@pytest.mark.asyncio
async def test_bootstrap_refuses_second_time(auth_client):
    await _bootstrap_admin(auth_client)
    r = await auth_client.post("/api/auth/bootstrap",
                               json={"username": "evil", "password": "whatever-123"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_bootstrap_validates_password_length(auth_client):
    r = await auth_client.post("/api/auth/bootstrap",
                               json={"username": "basil", "password": "short"})
    assert r.status_code == 422


# ------------------------------------------------------------------ guard

@pytest.mark.asyncio
async def test_health_is_public(auth_client):
    assert (await auth_client.get("/api/system/health")).status_code == 200


@pytest.mark.asyncio
async def test_protected_routes_401_without_session(auth_client):
    for method, path in [
        ("GET", "/api/jobs"),
        ("GET", "/api/countries"),
        ("GET", "/api/analytics"),
        ("GET", "/api/crm/statuses"),
        ("POST", "/api/daily-run/run"),
        ("GET", "/api/evidence"),
        ("GET", "/api/packages"),
        ("GET", "/api/matching/top-jobs"),
        ("GET", "/api/auth/me"),
    ]:
        r = await auth_client.request(method, path)
        assert r.status_code == 401, f"{method} {path} → {r.status_code}"
        if path != "/api/auth/me":  # public path → its own 401 message
            assert "Authentication required" in r.json()["detail"]


@pytest.mark.asyncio
async def test_html_requests_redirect_to_login(auth_client):
    r = await auth_client.get("/stats", headers={"accept": "text/html"})
    assert r.status_code == 303
    assert r.headers["location"] == "/"


# ------------------------------------------------------------------ login

@pytest.mark.asyncio
async def test_login_success_sets_httponly_cookie(auth_client):
    await _bootstrap_admin(auth_client)
    r = await _login(auth_client)
    assert r.status_code == 200
    cookie = r.headers["set-cookie"]
    assert "jobagent_session=" in cookie
    assert "HttpOnly" in cookie
    assert "samesite=lax" in cookie.lower()


@pytest.mark.asyncio
async def test_login_with_session_grants_access(auth_client):
    await _bootstrap_admin(auth_client)
    await _login(auth_client)
    r = await auth_client.get("/api/jobs")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_login_wrong_password_401(auth_client):
    await _bootstrap_admin(auth_client)
    r = await _login(auth_client, password="wrong-password")
    assert r.status_code == 401
    # Uniform error — must not reveal whether the username exists.
    assert r.json()["detail"] == "invalid username or password"


@pytest.mark.asyncio
async def test_login_unknown_user_same_error(auth_client):
    await _bootstrap_admin(auth_client)
    r = await _login(auth_client, username="ghost", password="whatever-99")
    assert r.status_code == 401
    assert r.json()["detail"] == "invalid username or password"


@pytest.mark.asyncio
async def test_lockout_after_max_failures(auth_client):
    await _bootstrap_admin(auth_client)
    for _ in range(MAX_LOGIN_FAILURES):
        r = await _login(auth_client, password="bad-pass-xxx")
        assert r.status_code == 401
    r = await _login(auth_client, password="admin-pass-123")  # even correct pw
    assert r.status_code == 429
    assert "locked" in r.json()["detail"]


@pytest.mark.asyncio
async def test_successful_login_resets_failure_counter(auth_client):
    await _bootstrap_admin(auth_client)
    for _ in range(MAX_LOGIN_FAILURES - 1):
        await _login(auth_client, password="bad-pass-xxx")
    await _login(auth_client)  # success resets
    r = await _login(auth_client, password="bad-pass-xxx")
    assert r.status_code == 401  # not locked — counter was reset


# ------------------------------------------------------------------ session

@pytest.mark.asyncio
async def test_logout_destroys_session(auth_client):
    await _bootstrap_admin(auth_client)
    await _login(auth_client)
    assert (await auth_client.get("/api/auth/me")).status_code == 200
    await auth_client.post("/api/auth/logout")
    assert (await auth_client.get("/api/auth/me")).status_code == 401


@pytest.mark.asyncio
async def test_tampered_cookie_is_rejected(auth_client):
    await _bootstrap_admin(auth_client)
    await _login(auth_client)
    auth_client.cookies.set("jobagent_session", "forged-token-value")
    assert (await auth_client.get("/api/auth/me")).status_code == 401


@pytest.mark.asyncio
async def test_inactive_user_sessions_revoked(auth_app, auth_client):
    await _bootstrap_admin(auth_client)
    await _login(auth_client)
    store = auth_app.state.auth_store
    user = await store.get_user_by_username("basil")
    await store.set_user_active(user["id"], False)
    assert (await auth_client.get("/api/auth/me")).status_code == 401


@pytest.mark.asyncio
async def test_expired_session_rejected(auth_app, auth_client):
    await _bootstrap_admin(auth_client)
    await _login(auth_client)
    from app.auth import SESSION_COOKIE, hash_token
    import aiosqlite
    # Force-expire the session row directly.
    async with aiosqlite.connect(auth_app.state.auth_store.db_path) as conn:
        await conn.execute("UPDATE sessions SET expires_at = ?",
                           ("2020-01-01T00:00:00+00:00",))
        await conn.commit()
    r = await auth_client.get("/api/auth/me")
    assert r.status_code == 401


# ------------------------------------------------------------------ password

@pytest.mark.asyncio
async def test_change_password_requires_current(auth_client):
    await _bootstrap_admin(auth_client)
    await _login(auth_client)
    r = await auth_client.post("/api/auth/change-password",
                               json={"current_password": "wrong-current",
                                     "new_password": "new-pass-12345"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_change_password_revokes_sessions(auth_client):
    await _bootstrap_admin(auth_client)
    await _login(auth_client)
    r = await auth_client.post("/api/auth/change-password",
                               json={"current_password": "admin-pass-123",
                                     "new_password": "new-pass-12345"})
    assert r.status_code == 200
    # Old session was destroyed by set_password.
    assert (await auth_client.get("/api/auth/me")).status_code == 401
    # New password works.
    assert (await _login(auth_client, password="new-pass-12345")).status_code == 200


# ------------------------------------------------------------------ store

@pytest.mark.asyncio
async def test_create_user_duplicate_rejected(auth_app):
    store = auth_app.state.auth_store
    await store.create_user("alice", "password-1", role="user")
    with pytest.raises(ValueError):
        await store.create_user("alice", "password-2", role="user")


@pytest.mark.asyncio
async def test_set_password_destroys_all_sessions(auth_app):
    store = auth_app.state.auth_store
    user = await store.create_user("bob", "password-1", role="user")
    token = await store.create_session(user["id"])
    assert await store.resolve_session(token) is not None
    await store.set_password(user["id"], "password-2")
    assert await store.resolve_session(token) is None


# ------------------------------------------------------- admin user management

async def _create_second_user(client, username="alice", password="alice-pass-123",
                              role="user"):
    r = await client.post("/api/auth/users",
                          json={"username": username, "password": password,
                                "role": role})
    assert r.status_code == 200, r.text
    return r.json()["user"]


@pytest.mark.asyncio
async def test_admin_can_create_user(auth_client):
    await _bootstrap_admin(auth_client)
    user = await _create_second_user(auth_client)
    assert user["username"] == "alice"
    assert user["role"] == "user"
    assert bool(user["is_active"]) is True
    # The new user can actually log in.
    r = await _login(auth_client, username="alice", password="alice-pass-123")
    assert r.status_code == 200


def _fresh_client(app):
    from httpx import ASGITransport, AsyncClient
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_non_admin_cannot_manage_users(auth_app, auth_client):
    await _bootstrap_admin(auth_client)
    await _create_second_user(auth_client)
    # Alice's own session:
    async with _fresh_client(auth_app) as alice:
        await _login(alice, username="alice", password="alice-pass-123")
        r = await alice.get("/api/auth/users")
        assert r.status_code == 403
        r = await alice.post("/api/auth/users",
                             json={"username": "mallory", "password": "mallory-99"})
        assert r.status_code == 403


@pytest.mark.asyncio
async def test_created_user_is_isolated_session(auth_app, auth_client):
    """The admin's cookie must not leak into a new user's client."""
    await _bootstrap_admin(auth_client)
    await _create_second_user(auth_client)
    async with _fresh_client(auth_app) as alice:
        r = await _login(alice, username="alice", password="alice-pass-123")
        me = (await alice.get("/api/auth/me")).json()["user"]
        assert me["username"] == "alice"
        assert me["role"] == "user"


@pytest.mark.asyncio
async def test_admin_cannot_disable_self(auth_client):
    await _bootstrap_admin(auth_client)
    me = (await auth_client.get("/api/auth/me")).json()["user"]
    r = await auth_client.post(f"/api/auth/users/{me['id']}/disable")
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_disable_user_kills_sessions_and_blocks_login(auth_app, auth_client):
    await _bootstrap_admin(auth_client)
    user = await _create_second_user(auth_client)
    async with _fresh_client(auth_app) as alice:
        await _login(alice, username="alice", password="alice-pass-123")
        assert (await alice.get("/api/auth/me")).status_code == 200
        # Admin disables Alice:
        r = await auth_client.post(f"/api/auth/users/{user['id']}/disable")
        assert r.status_code == 200
        # Alice's live session is destroyed:
        assert (await alice.get("/api/auth/me")).status_code == 401
        # And she cannot log back in:
        r = await _login(alice, username="alice", password="alice-pass-123")
        assert r.status_code == 401
    # Re-enable → login works again:
    r = await auth_client.post(f"/api/auth/users/{user['id']}/enable")
    assert r.status_code == 200
    async with _fresh_client(auth_app) as alice2:
        assert (await _login(alice2, username="alice",
                             password="alice-pass-123")).status_code == 200


@pytest.mark.asyncio
async def test_admin_reset_password(auth_app, auth_client):
    await _bootstrap_admin(auth_client)
    user = await _create_second_user(auth_client)
    r = await auth_client.post(f"/api/auth/users/{user['id']}/reset-password",
                               json={"new_password": "brand-new-pass-1"})
    assert r.status_code == 200
    # Old password dead, new one works:
    async with _fresh_client(auth_app) as c:
        assert (await _login(c, username="alice",
                             password="alice-pass-123")).status_code == 401
        assert (await _login(c, username="alice",
                             password="brand-new-pass-1")).status_code == 200


@pytest.mark.asyncio
async def test_duplicate_username_rejected_via_api(auth_client):
    await _bootstrap_admin(auth_client)
    await _create_second_user(auth_client)
    r = await auth_client.post("/api/auth/users",
                               json={"username": "alice",
                                     "password": "other-pass-123"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_user_management_requires_auth(auth_client):
    r = await auth_client.get("/api/auth/users")
    assert r.status_code == 401
