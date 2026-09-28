"""docs_server.py — serve job-search-system/docs/ on 0.0.0.0 behind login.

Same auth model as the main app (SystemStore + AuthGuardMiddleware): only
users who exist in system.db can read anything. There is no bootstrap here —
this server NEVER creates users; it reuses the accounts created by the main
jobagent app (same system.db) or ones you seed with `--create-user` (admin
role, for standalone installs).

Endpoints:
  GET /                 → index listing every .md file (login screen if anonymous)
  GET /docs/<file>.md   → the file, rendered as HTML (stdlib only, no deps)
  GET /raw/<file>.md    → the raw markdown text
Everything else → 401 (JSON) or 303 → / (browser).

Run:  .venv/bin/python ../docs_server.py --host 0.0.0.0 --port 8090
"""

from __future__ import annotations

import argparse
import html
import os
import re
import sys
from pathlib import Path

# Make the app package importable regardless of cwd.
_ROOT = Path(__file__).resolve().parent / "root"
sys.path.insert(0, str(_ROOT))

import uvicorn  # noqa: E402
from fastapi import FastAPI, Request  # noqa: E402
from fastapi.responses import (  # noqa: E402
    FileResponse, HTMLResponse, JSONResponse, PlainTextResponse,
)

from app.auth import (  # noqa: E402
    AuthGuardMiddleware, LoginThrottler, SystemStore, SESSION_COOKIE,
    PUBLIC_EXACT, PUBLIC_PREFIXES,
)

_DOCS_DIR = Path(__file__).resolve().parent / "docs"
_PAGE = """<!doctype html><html><head><meta charset="utf-8">
<title>{title} — jobagent docs</title>
<style>
 body{{font-family:ui-sans-serif,system-ui,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;line-height:1.55;color:#1c2430}}
 h1,h2,h3{{line-height:1.2}} table{{border-collapse:collapse}} td,th{{border:1px solid #cbd5e1;padding:.35rem .55rem}}
 code,pre{{background:#f1f5f9;border-radius:4px;font-size:.92em}} pre{{padding:.8rem;overflow-x:auto}}
 a{{color:#0b62d6}} .files a{{display:block;padding:.3rem 0}} .bar{{font-size:.85rem;color:#64748b;margin-bottom:1rem}}
</style></head><body>
<div class="bar">jobagent docs · signed in as <b>{user}</b> · <a href="/logout">sign out</a></div>
{body}
</body></html>"""

_INLINE = re.compile(r"(`[^`]+`)")


def _md_to_html(text: str) -> str:
    """Tiny stdlib renderer: headings, tables, code fences, lists, bold, links."""
    out: list[str] = []
    in_code = in_table = False
    for line in text.splitlines():
        if line.startswith("```"):
            out.append("</pre>" if in_code else "<pre>")
            in_code = not in_code
            continue
        if in_code:
            out.append(html.escape(line))
            continue
        if line.startswith("|") and line.rstrip().endswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(re.fullmatch(r":?-+:?", c) for c in cells):
                continue  # separator row
            if not in_table:
                out.append("<table>")
                in_table = True
                out.append("<tr>" + "".join(f"<th>{_inline_html(c)}</th>" for c in cells) + "</tr>")
            else:
                out.append("<tr>" + "".join(f"<td>{_inline_html(c)}</td>" for c in cells) + "</tr>")
            continue
        if in_table:
            out.append("</table>")
            in_table = False
        m = re.match(r"^(#{1,4})\s+(.*)$", line)
        if m:
            level = len(m.group(1))
            out.append(f"<h{level}>{_inline_html(m.group(2))}</h{level}>")
        elif line.startswith("- "):
            out.append(f"<li>{_inline_html(line[2:])}</li>")
        elif re.match(r"^\d+\.\s", line):
            out.append(f"<li>{_inline_html(re.sub(r'^\\d+\\.\\s', '', line))}</li>")
        elif line.strip() in ("---", "***", "___"):
            out.append("<hr>")
        elif line.strip():
            out.append(f"<p>{_inline_html(line)}</p>")
    if in_table:
        out.append("</table>")
    if in_code:
        out.append("</pre>")
    return "\n".join(out)


def _inline_html(s: str) -> str:
    s = html.escape(s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", s)


def _safe_name(name: str) -> str | None:
    """Allow only plain .md/.docx files inside docs/ — no traversal, no subdirs."""
    if "/" in name or "\\" in name or ".." in name \
            or not name.endswith((".md", ".docx")):
        return None
    p = (_DOCS_DIR / name).resolve()
    return name if p.parent == _DOCS_DIR and p.is_file() else None


def create_docs_app(db_path: str | None = None) -> FastAPI:
    default_db = Path(__file__).resolve().parent / "root" / "data" / "jobagent.db"
    system_db = str(Path(db_path or default_db).parent / "system.db")

    app = FastAPI(title="jobagent-docs", lifespan=None)
    app.state.auth_store = SystemStore(system_db)
    app.state.login_throttler = LoginThrottler()
    app.state.testing = False

    # Public only what the login screen needs; everything else is guarded.
    # (The middleware is added LAST below so it wraps the whole app — FastAPI
    # applies middleware in reverse registration order.)
    PUBLIC_EXACT.update({"/login", "/favicon.ico"})
    PUBLIC_EXACT.discard("/docs")  # here /docs/<file> is PROTECTED, not Swagger
    PUBLIC_PREFIXES  # unchanged: /static/, /api/auth/, /assets/ (unused here)

    async def _user(request: Request) -> dict | None:
        await app.state.auth_store.ensure()
        token = request.cookies.get(SESSION_COOKIE, "")
        return await app.state.auth_store.resolve_session(token)

    async def _guard(request: Request) -> dict | None:
        user = await _user(request)
        if user is None:
            wants_html = "text/html" in request.headers.get("accept", "")
            if wants_html:
                return None  # caller renders the login page
            raise _AuthNeeded()
        return user

    class _AuthNeeded(Exception):
        pass

    @app.exception_handler(_AuthNeeded)
    async def _auth_needed(request, exc):
        return JSONResponse({"detail": "Authentication required"}, status_code=401,
                            headers={"WWW-Authenticate": "Session"})

    @app.get("/")
    async def index(request: Request):
        # The guard has already authenticated here; anonymous browsers never
        # reach this handler (they get 303 → / from the middleware, which is
        # this same route serving the login page).
        user = await _user(request)
        if user is None:
            return HTMLResponse(_LOGIN_PAGE, status_code=200)
        files = sorted(p.name for p in _DOCS_DIR.glob("*.md"))
        links = "".join(f'<a href="/docs/{f}">{f}</a>' for f in files)
        return HTMLResponse(_PAGE.format(
            title="All documents", user=html.escape(user["username"]),
            body=f"<h1>jobagent documentation</h1><div class='files'>{links}</div>"))

    @app.get("/docs/{name}")
    async def doc(request: Request, name: str):
        user = await _user(request)
        safe = _safe_name(name)
        if user is None:
            raise _AuthNeeded()
        if safe is None:
            return JSONResponse({"detail": "not found"}, status_code=404)
        path = _DOCS_DIR / safe
        if safe.endswith(".docx"):
            return FileResponse(
                path,
                media_type="application/vnd.openxmlformats-officedocument"
                           ".wordprocessingml.document",
                filename=safe)
        text = path.read_text(encoding="utf-8", errors="replace")
        body = _md_to_html(text)
        return HTMLResponse(_PAGE.format(
            title=html.escape(safe), user=html.escape(user["username"]), body=body))

    @app.get("/raw/{name}")
    async def raw(request: Request, name: str):
        user = await _guard(request)
        safe = _safe_name(name)
        if user is None:
            raise _AuthNeeded()
        if safe is None:
            return JSONResponse({"detail": "not found"}, status_code=404)
        return PlainTextResponse((_DOCS_DIR / safe).read_text(encoding="utf-8",
                                                              errors="replace"))

    @app.get("/logout")
    async def logout(request: Request):
        token = request.cookies.get(SESSION_COOKIE, "")
        if token:
            await app.state.auth_store.destroy_session(token)
        resp = HTMLResponse(_LOGIN_PAGE)
        resp.delete_cookie(SESSION_COOKIE)
        return resp

    # Login routes — POST /login (form), reused from the main app's semantics.
    from fastapi import Form

    @app.post("/login")
    async def login(request: Request, username: str = Form(...),
                    password: str = Form(...)):
        throttler: LoginThrottler = app.state.login_throttler
        if throttler.is_locked(username):
            remain = throttler.lockout_remaining(username)
            return HTMLResponse(_LOGIN_PAGE.replace("<!--err-->",
                                 f"<p class='err'>locked — try in {remain}s</p>"),
                                 status_code=429)
        user = await app.state.auth_store.get_user_by_username(username)
        from app.auth import verify_password
        if user is None or not user.get("is_active") or not verify_password(password, user["password_hash"]):
            throttler.record_failure(username)
            return HTMLResponse(_LOGIN_PAGE.replace("<!--err-->",
                                 "<p class='err'>wrong username or password</p>"),
                                 status_code=401)
        throttler.reset(username)
        await app.state.auth_store.touch_last_login(user["id"])
        token = await app.state.auth_store.create_session(user["id"])
        resp = HTMLResponse(status_code=303, headers={"Location": "/"})
        resp.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax",
                        max_age=7 * 24 * 3600)
        return resp

    # Guard added LAST so it runs FIRST (reverse order): every path not in
    # PUBLIC_EXACT / PUBLIC_PREFIXES now requires a valid session — including
    # GET / (which renders the login page for browsers) and /docs/<file>.
    app.add_middleware(AuthGuardMiddleware, store=app.state.auth_store,
                       throttler=app.state.login_throttler)
    return app


_LOGIN_PAGE = """<!doctype html><html><head><meta charset="utf-8">
<title>Sign in — jobagent docs</title><style>
body{font-family:system-ui,sans-serif;background:#f1f5f9;display:grid;place-items:center;height:100vh;margin:0}
form{background:#fff;padding:2rem;border-radius:10px;box-shadow:0 2px 8px #0001;width:280px}
input{width:100%;box-sizing:border-box;padding:.5rem;margin:.35rem 0 .8rem;border:1px solid #cbd5e1;border-radius:6px}
button{width:100%;padding:.55rem;border:0;border-radius:6px;background:#0b62d6;color:#fff;font-weight:600}
.err{color:#b91c1c;font-size:.85rem}</style></head><body>
<form method="post" action="/login"><h2>jobagent docs</h2>
<!--err-->
<input name="username" placeholder="Username" autofocus required>
<input name="password" type="password" placeholder="Password" required>
<button>Sign in</button></form></body></html>"""


def main() -> None:
    ap = argparse.ArgumentParser(description="Serve docs/ behind jobagent auth")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8090)
    ap.add_argument("--db", default=None,
                    help="path to a jobagent.db whose system.db holds the users")
    ap.add_argument("--create-user", nargs=2, metavar=("USERNAME", "PASSWORD"),
                    help="create an admin account first (standalone installs)")
    args = ap.parse_args()

    db_path = args.db or str(Path(__file__).resolve().parent / "root" / "data" / "jobagent.db")
    if args.create_user:
        import asyncio
        store = SystemStore(str(Path(db_path).parent / "system.db"))
        username, password = args.create_user
        try:
            asyncio.run(store.create_user(username, password, role="admin"))
            print(f"created admin user {username!r}")
        except ValueError as e:
            print(f"skipped user creation: {e}")

    app = create_docs_app(db_path)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
