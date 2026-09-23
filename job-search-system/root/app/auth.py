"""M15a — Auth foundation: system.db users + sessions, scrypt passwords, ASGI guard.

Design (docs/MULTI_USER_PLAN.md §3.4):
- data/system.db holds users + sessions ONLY. Workspace DBs come in M15b.
- Password hashing: hashlib.scrypt (stdlib, memory-hard). Zero new dependencies.
- Sessions: secrets.token_urlsafe(32); only the SHA-256 of the token is stored.
- Transport: HttpOnly + SameSite=Lax cookie `jobagent_session`, 7-day sliding expiry.
- First-run bootstrap: if no users exist, POST /api/auth/bootstrap creates the
  FIRST account as admin and locks itself forever afterwards.
- ASGI middleware enforces auth on every path EXCEPT: /api/system/health,
  /api/auth/*, /static/*, /favicon.ico, / (login page shell), /docs,
  /openapi.json. When testing=True the middleware is a no-op so the 800+ unit
  tests and the E2E harness keep their pre-auth behavior; auth correctness is
  covered by tests/test_auth.py against the REAL middleware with testing=False.

Login throttling: 5 consecutive failures per username → 15-minute lockout
(tracked in-memory; resets on successful login or process restart).
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
import time
from datetime import datetime, timezone

import aiosqlite
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

SESSION_COOKIE = "jobagent_session"
SESSION_TTL_SECONDS = 7 * 24 * 3600          # 7-day sliding expiry
MAX_LOGIN_FAILURES = 5
LOCKOUT_SECONDS = 15 * 60

# Paths reachable without a session (exact match or prefix).
PUBLIC_EXACT = {
    "/", "/favicon.ico", "/docs", "/redoc", "/openapi.json",
    "/api/system/health",
}
PUBLIC_PREFIXES = (
    "/static/", "/api/auth/", "/assets/",
)


# ------------------------------------------------------------------ hashing

def hash_password(password: str) -> str:
    """scrypt with random 16-byte salt → 'scrypt$salt_hex$hash_hex'."""
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt_hex, hash_hex = stored.split("$", 2)
        if scheme != "scrypt":
            return False
        digest = hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt_hex),
                                n=2**14, r=8, p=1)
        return hmac.compare_digest(digest.hex(), hash_hex)
    except (ValueError, TypeError):
        return False


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# ------------------------------------------------------------- system store

class SystemStore:
    """users + sessions on a dedicated system.db (workspace DBs arrive in M15b)."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._initialized = False

    async def init(self) -> None:
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('admin','user')),
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    last_login_at TEXT
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
                CREATE TABLE IF NOT EXISTS admin_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    actor_user_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    detail TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );
                """
            )
            await conn.commit()
        self._initialized = True

    async def ensure(self) -> None:
        """Idempotent lazy init — safe for clients that never run lifespan."""
        if not self._initialized:
            await self.init()

    async def close(self) -> None:  # parity with Database API
        return None

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    # ----- users

    async def user_count(self) -> int:
        async with aiosqlite.connect(self.db_path) as conn:
            cur = await conn.execute("SELECT COUNT(*) FROM users")
            return (await cur.fetchone())[0]

    async def create_user(self, username: str, password: str, role: str = "user",
                          is_active: bool = True) -> dict:
        username = username.strip()
        if not username or len(username) > 64:
            raise ValueError("username must be 1-64 characters")
        if len(password) < 8:
            raise ValueError("password must be at least 8 characters")
        if role not in ("admin", "user"):
            raise ValueError("role must be admin or user")
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            try:
                cur = await conn.execute(
                    "INSERT INTO users (username, password_hash, role, is_active, created_at)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (username, hash_password(password), role,
                     1 if is_active else 0, self._now()),
                )
                await conn.commit()
            except aiosqlite.IntegrityError as e:
                raise ValueError(f"username already taken: {username}") from e
            return await self.get_user(cur.lastrowid, conn=conn)

    async def get_user(self, user_id: int, conn=None) -> dict | None:
        if conn is not None:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            row = await cur.fetchone()
            return dict(row) if row else None
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            row = await cur.fetchone()
            return dict(row) if row else None

    async def get_user_by_username(self, username: str) -> dict | None:
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute(
                "SELECT * FROM users WHERE username = ?", (username.strip(),))
            row = await cur.fetchone()
            return dict(row) if row else None

    async def list_users(self) -> list[dict]:
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute(
                "SELECT id, username, role, is_active, created_at, last_login_at"
                " FROM users ORDER BY id")
            return [dict(r) for r in await cur.fetchall()]

    async def set_user_active(self, user_id: int, is_active: bool) -> None:
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("UPDATE users SET is_active = ? WHERE id = ?",
                               (1 if is_active else 0, user_id))
            if not is_active:
                await conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            await conn.commit()

    async def set_password(self, user_id: int, password: str) -> None:
        if len(password) < 8:
            raise ValueError("password must be at least 8 characters")
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                               (hash_password(password), user_id))
            await conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            await conn.commit()

    async def touch_last_login(self, user_id: int) -> None:
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("UPDATE users SET last_login_at = ? WHERE id = ?",
                               (self._now(), user_id))
            await conn.commit()

    # ----- sessions

    async def create_session(self, user_id: int) -> str:
        token = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        expires = datetime.fromtimestamp(now.timestamp() + SESSION_TTL_SECONDS,
                                         tz=timezone.utc)
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                "INSERT INTO sessions (token_hash, user_id, created_at, expires_at)"
                " VALUES (?, ?, ?, ?)",
                (hash_token(token), user_id, self._now(), expires.isoformat()))
            await conn.commit()
        return token

    async def resolve_session(self, token: str) -> dict | None:
        """Return the session's user dict if the token is valid and unexpired."""
        if not token:
            return None
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute(
                """
                SELECT u.id, u.username, u.role, u.is_active, s.expires_at
                FROM sessions s JOIN users u ON u.id = s.user_id
                WHERE s.token_hash = ?
                """,
                (hash_token(token),))
            row = await cur.fetchone()
        if not row:
            return None
        expires = datetime.fromisoformat(row["expires_at"])
        if datetime.now(timezone.utc) >= expires or not row["is_active"]:
            await self.destroy_session(token)
            return None
        return {"id": row["id"], "username": row["username"], "role": row["role"]}

    async def destroy_session(self, token: str) -> None:
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("DELETE FROM sessions WHERE token_hash = ?",
                               (hash_token(token),))
            await conn.commit()

    async def record_admin_action(self, actor_user_id: int, action: str,
                                  detail: str = "") -> None:
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                "INSERT INTO admin_actions (actor_user_id, action, detail, created_at)"
                " VALUES (?, ?, ?, ?)",
                (actor_user_id, action, detail, self._now()))
            await conn.commit()


# ------------------------------------------------------------- rate limiting

class LoginThrottler:
    """In-memory consecutive-failure lockout per username."""

    def __init__(self) -> None:
        self._failures: dict[str, list[float]] = {}

    def is_locked(self, username: str) -> bool:
        window_start = time.monotonic() - LOCKOUT_SECONDS
        recent = [t for t in self._failures.get(username, []) if t > window_start]
        self._failures[username] = recent
        return len(recent) >= MAX_LOGIN_FAILURES

    def record_failure(self, username: str) -> None:
        self._failures.setdefault(username, []).append(time.monotonic())

    def reset(self, username: str) -> None:
        self._failures.pop(username, None)

    def lockout_remaining(self, username: str) -> int:
        recent = sorted(self._failures.get(username, []))
        if len(recent) < MAX_LOGIN_FAILURES:
            return 0
        elapsed = time.monotonic() - recent[-1]
        return max(0, int(LOCKOUT_SECONDS - elapsed))


# ------------------------------------------------------------------ ASGI guard

def _is_public(path: str) -> bool:
    return path in PUBLIC_EXACT or path.startswith(PUBLIC_PREFIXES)


class AuthGuardMiddleware(BaseHTTPMiddleware):
    """Enforce a valid session on every non-public path.

    Bypassed entirely when app.state.testing is True — the unit-test suite and
    the E2E harness were built pre-auth; auth is verified by test_auth.py with
    a real (testing=False) app instance.
    """

    def __init__(self, app, store: SystemStore, throttler: LoginThrottler):
        super().__init__(app)
        self.store = store
        self.throttler = throttler

    async def dispatch(self, request: Request, call_next):
        if getattr(request.app.state, "testing", False):
            return await call_next(request)

        await self.store.ensure()
        request.state.user = None
        if not _is_public(request.url.path):
            token = request.cookies.get(SESSION_COOKIE, "")
            user = await self.store.resolve_session(token)
            if user is None:
                wants_html = "text/html" in request.headers.get("accept", "")
                if wants_html:
                    from starlette.responses import RedirectResponse
                    return RedirectResponse(url="/", status_code=303)
                return JSONResponse(
                    {"detail": "Authentication required"},
                    status_code=401,
                    headers={"WWW-Authenticate": "Session"},
                )
            request.state.user = user
        return await call_next(request)
