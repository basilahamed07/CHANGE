"""M15a — Auth endpoints: bootstrap, login, logout, me, change password.

All routes live under /api/auth/ (public by design). The bootstrap endpoint
refuses once any user exists (the first account is always the admin).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.auth import (
    LOCKOUT_SECONDS,
    SESSION_COOKIE,
    SESSION_TTL_SECONDS,
    LoginThrottler,
    SystemStore,
    verify_password,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


class Credentials(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class BootstrapRequest(Credentials):
    pass


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=256)


def _get_store(request: Request) -> SystemStore:
    store = getattr(request.app.state, "auth_store", None)
    if store is None:
        raise HTTPException(503, "auth store not initialized")
    return store


async def _ensure_store(request: Request) -> SystemStore:
    store = _get_store(request)
    await store.ensure()  # clients without lifespan (ASGITransport) never ran init
    return store


def _get_throttler(request: Request) -> LoginThrottler:
    return request.app.state.login_throttler


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE, token,
        max_age=SESSION_TTL_SECONDS,
        httponly=True, samesite="lax",
        secure=False,  # set True behind an HTTPS reverse proxy (M15e hardening)
    )


@router.get("/status")
async def auth_status(request: Request):
    """Frontend boot probe: is bootstrap needed / are we logged in?"""
    store = await _ensure_store(request)
    count = await store.user_count()
    token = request.cookies.get(SESSION_COOKIE, "")
    user = await store.resolve_session(token)
    return {
        "needs_bootstrap": count == 0,
        "authenticated": user is not None,
        "user": user,
    }


@router.post("/bootstrap")
async def bootstrap(body: BootstrapRequest, request: Request, response: Response):
    """Create the FIRST account (always admin). Refuses forever afterwards."""
    store = await _ensure_store(request)
    if await store.user_count() > 0:
        raise HTTPException(403, "bootstrap already completed")
    try:
        user = await store.create_user(body.username, body.password, role="admin")
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    await store.record_admin_action(user["id"], "bootstrap_admin", user["username"])
    token = await store.create_session(user["id"])
    await store.touch_last_login(user["id"])
    _set_session_cookie(response, token)
    return {"ok": True, "user": user}


@router.post("/login")
async def login(body: Credentials, request: Request, response: Response):
    store = await _ensure_store(request)
    throttler = _get_throttler(request)

    if throttler.is_locked(body.username):
        remaining = throttler.lockout_remaining(body.username)
        raise HTTPException(
            429,
            f"too many failed logins — locked for {remaining or LOCKOUT_SECONDS // 60} min",
        )

    user = await store.get_user_by_username(body.username)
    ok = (
        user is not None
        and user["is_active"]
        and verify_password(body.password, user["password_hash"])
    )
    # Uniform failure — never reveal whether the username exists.
    if not ok:
        throttler.record_failure(body.username)
        raise HTTPException(401, "invalid username or password")

    throttler.reset(body.username)
    token = await store.create_session(user["id"])
    await store.touch_last_login(user["id"])
    _set_session_cookie(response, token)
    return {"ok": True, "user": {"id": user["id"], "username": user["username"],
                                 "role": user["role"]}}


@router.post("/logout")
async def logout(request: Request, response: Response):
    store = _get_store(request)
    token = request.cookies.get(SESSION_COOKIE, "")
    if token:
        await store.destroy_session(token)
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


@router.get("/me")
async def me(request: Request):
    """Returns the session user; 401 when anonymous (auth middleware active)."""
    store = _get_store(request)
    user = await store.resolve_session(request.cookies.get(SESSION_COOKIE, ""))
    if user is None:
        raise HTTPException(401, "not authenticated")
    return {"user": user}


@router.post("/change-password")
async def change_password(body: ChangePasswordRequest, request: Request):
    store = _get_store(request)
    current = await store.resolve_session(request.cookies.get(SESSION_COOKIE, ""))
    if current is None:
        raise HTTPException(401, "not authenticated")
    user = await store.get_user(current["id"])
    if not user or not verify_password(body.current_password, user["password_hash"]):
        raise HTTPException(401, "current password is incorrect")
    await store.set_password(user["id"], body.new_password)
    # set_password destroys all sessions (including this one) — user re-logs in.
    return {"ok": True, "message": "password changed — please log in again"}
