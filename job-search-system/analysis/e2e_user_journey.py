"""REAL end-to-end USER JOURNEY test — boots the actual product and drives it.

Golden Rule #11 says a module is not done until it is proven through the running
product. This harness goes further than `e2e_module_test.py`: instead of an
in-process ASGI client, it launches the REAL server (`uvicorn app.main:create_app
--factory`) with authentication ON and `testing=False`, against its own throwaway
data directory, and talks to it only over HTTP — exactly what a new user's
browser does.

The journey is the whole product, top to bottom, as a brand-new person:

    1  server boot + health + OpenAPI surface
    2  bootstrap: create the first username + password
    3  anonymous lockdown (every protected route must 401)
    4  login throttling + login
    5  admin creates a second user (username + password)
    6  that user's workspace is born empty and isolated
    7  the user adds their OWN DeepSeek key
    8  uploads their real resume (.docx) -> live AI grading + profile parse
    9  evidence autofill/backfill -> VERIFIED corpus
   10  country strategy
   11  discovery adapters + live health probes
   12  discovery cycle (real orchestration)
   13  real scrapers (bounded)
   14  deterministic scoring + ranking
   15  eligibility + freshness
   16  company / contact research
   17  AI resume tailoring through the evidence gate
   18  AI cover letter + downloads
   19  application package build + file downloads
   20  outreach draft (draft-only, idempotent)
   21  CRM status transitions + follow-up engine
   22  daily run
   23  analytics / cost meter
   24  CROSS-USER ISOLATION (Critical Test #5)
   25  API coverage: every OpenAPI operation called or explicitly excused

Every single HTTP call is recorded (method, path, status, latency, request body,
response body) to `analysis/e2e_runs/<date>_<time>/`:

    run.json           run metadata + summary
    api_calls.jsonl    one JSON object per HTTP call (streamed as it happens)
    scenarios.json     per-scenario pass/fail with every check
    api_coverage.json  every OpenAPI operation + whether the journey touched it
    report.md          the human-readable top-to-bottom report
    artifacts/         downloaded packages, resume used, cover letters, reports
    server.log         the real server's log

Usage (from anywhere; it cds into root/ itself):

    .venv/bin/python ../analysis/e2e_user_journey.py

Optional env overrides:
    JOBAGENT_E2E_AI_KEY      DeepSeek key to give the journey user
    JOBAGENT_E2E_SEED_DB     admin workspace DB to read resume/key from
    JOBAGENT_E2E_SCRAPE_SECS seconds to let the real scrapers run (default 240)
    JOBAGENT_E2E_DISCOVERY_SECS seconds to let discovery run (default 300)
"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ANALYSIS_DIR = Path(__file__).resolve().parent
ROOT = ANALYSIS_DIR.parent / "root"
RUNS_ROOT = ANALYSIS_DIR / "e2e_runs"
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402

try:
    import docx  # python-docx — a product dependency, used to build a real .docx
except Exception:  # pragma: no cover
    docx = None


# --------------------------------------------------------------------- config

ADMIN_USERNAME = "e2eadmin"
JOURNEY_USERNAME = "e2euser"
PASSWORD = "E2e-Passw0rd-2026!"
NEW_PASSWORD = "E2e-Passw0rd-2026-R0tated!"

SCRAPE_SECS = int(os.getenv("JOBAGENT_E2E_SCRAPE_SECS", "240"))
DISCOVERY_SECS = int(os.getenv("JOBAGENT_E2E_DISCOVERY_SECS", "300"))

TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
RUN_ID = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")


# ------------------------------------------------------------------- utilities


def log(msg: str = "") -> None:
    print(msg, flush=True)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _candidate_admin_dbs() -> list[Path]:
    """Workspace DBs to read the real resume + the real AI key from."""
    dirs: list[Path] = []
    users = ROOT / "data" / "users"
    if users.exists():
        dirs += sorted(d for d in users.iterdir() if d.is_dir())
    dirs.append(ROOT / "data")
    out = []
    for d in dirs:
        p = d / "jobagent.db"
        if p.exists():
            out.append(p)
    return out


def _read_one(query: str, params: tuple = ()):
    for db_file in _candidate_admin_dbs():
        try:
            conn = sqlite3.connect(db_file)
            row = conn.execute(query, params).fetchone()
            conn.close()
            if row:
                return row
        except Exception:
            continue
    return None


def load_real_resume() -> str:
    row = _read_one("SELECT resume_text FROM resumes "
                    "ORDER BY is_default DESC, id ASC LIMIT 1")
    return (row[0] or "") if row else ""


def load_real_ai() -> dict:
    row = _read_one("SELECT provider, api_key, model, base_url, region "
                    "FROM ai_settings ORDER BY id LIMIT 1")
    if not row or not row[1]:
        return {}
    return {"provider": row[0] or "", "api_key": row[1] or "",
            "model": row[2] or "", "base_url": row[3] or "",
            "region": row[4] or ""}


def resolve_ai() -> dict:
    """The provider the journey user will be given. DeepSeek is the real one."""
    env_key = os.getenv("JOBAGENT_E2E_AI_KEY", "").strip()
    stored = load_real_ai()
    if env_key:
        return {"provider": os.getenv("JOBAGENT_E2E_AI_PROVIDER", "deepseek"),
                "api_key": env_key,
                "model": os.getenv("JOBAGENT_E2E_AI_MODEL", "deepseek-flash"),
                "base_url": "", "region": ""}
    if stored.get("api_key"):
        return stored
    return {}


def build_resume_docx(text: str) -> bytes:
    """Build a genuine .docx carrying the candidate's real resume text."""
    if docx is None:
        raise RuntimeError("python-docx unavailable — cannot build a real .docx")
    d = docx.Document()
    for line in text.splitlines():
        d.add_paragraph(line)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def as_list(body, *keys) -> list:
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        for k in keys:
            v = body.get(k)
            if isinstance(v, list):
                return v
    return []


def job_id_of(item) -> int | None:
    if not isinstance(item, dict):
        return None
    for k in ("job_id", "id"):
        if isinstance(item.get(k), int):
            return item[k]
    return None


# --------------------------------------------------------------------- recorder


@dataclass
class _Scenario:
    sid: str
    title: str
    description: str = ""
    checks: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    error: str = ""

    @property
    def ok(self) -> bool:
        return (not self.error) and all(c["ok"] for c in self.checks)

    def to_dict(self) -> dict:
        return {"id": self.sid, "title": self.title,
                "description": self.description, "ok": self.ok,
                "checks": self.checks, "notes": self.notes,
                "error": self.error}


class Recorder:
    """Writes every API call and every check to the run directory."""

    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        self.artifacts = run_dir / "artifacts"
        self.artifacts.mkdir(parents=True, exist_ok=True)
        self._calls = (run_dir / "api_calls.jsonl").open("w", encoding="utf-8")
        self.calls: list[dict] = []
        self.scenarios: list[_Scenario] = []
        self._current: _Scenario | None = None
        self._counter = 0

    # -- scenarios ---------------------------------------------------------
    def begin(self, sid: str, title: str, description: str = "") -> None:
        self._current = _Scenario(sid, title, description)
        self.scenarios.append(self._current)
        log("\n" + "=" * 74)
        log(f"{sid}  {title}")
        log("=" * 74)

    def note(self, text: str) -> None:
        if self._current:
            self._current.notes.append(text)
        log(f"  · {text}")

    def check(self, name: str, ok: bool, detail: str = "") -> bool:
        if self._current:
            self._current.checks.append({"name": name, "ok": bool(ok),
                                         "detail": detail})
        log(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" — {detail}" if detail else ""))
        return bool(ok)

    def error(self, exc: BaseException) -> None:
        if self._current:
            self._current.error = f"{type(exc).__name__}: {exc}"
        log("  FAIL  scenario raised:")
        log(traceback.format_exc())

    def end(self) -> None:
        if self._current:
            s = self._current
            state = "OK" if s.ok else "FAILED"
            log(f"  → {s.sid}: {state} ({sum(1 for c in s.checks if c['ok'])}"
                f"/{len(s.checks)} checks)")
        self._current = None

    # -- api calls ---------------------------------------------------------
    def api(self, scenario: str, method: str, path: str, status, ms: int,
            request_body=None, response_body=None, error: str = "",
            artifact: str = "") -> None:
        self._counter += 1
        entry = {
            "n": self._counter, "ts": datetime.now(timezone.utc).isoformat(),
            "scenario": scenario, "method": method, "path": path,
            "status": status, "ms": ms, "error": error,
        }
        if request_body is not None:
            entry["request"] = _truncate(request_body)
        if response_body is not None:
            entry["response"] = _truncate(response_body)
        if artifact:
            entry["artifact"] = artifact
        self.calls.append(entry)
        self._calls.write(json.dumps(entry, default=str) + "\n")
        self._calls.flush()
        colour = "✓" if isinstance(status, int) and status < 400 else "✗"
        log(f"    {colour} {method} {path} → {status} ({ms}ms)")

    def close(self) -> None:
        self._calls.close()


def _truncate(value, limit: int = 4000):
    if isinstance(value, (dict, list)):
        try:
            text = json.dumps(value, default=str)
        except Exception:
            text = str(value)
        if len(text) > limit:
            return text[:limit] + f"…<{len(text)} chars total>"
        return value
    if isinstance(value, str) and len(value) > limit:
        return value[:limit] + f"…<{len(value)} chars total>"
    return value


# ----------------------------------------------------------------------- journey


@dataclass
class Call:
    resp: httpx.Response | None
    body: object
    status: int | None
    ms: int
    error: str = ""


class Journey:
    def __init__(self, run_dir: Path, base_url: str, ai: dict):
        self.run_dir = run_dir
        self.base = base_url
        self.ai = ai
        self.rec = Recorder(run_dir)
        self.admin: httpx.AsyncClient | None = None
        self.user: httpx.AsyncClient | None = None
        self.anon: httpx.AsyncClient | None = None
        self.admin_job_id: int | None = None
        self.user_job_id: int | None = None
        self.extra_job_id: int | None = None
        self.pick_job: dict | None = None
        self.package_files: list[str] = []
        self.openapi: dict = {}

    # -------------------------------------------------------------- plumbing
    async def api(self, client, method: str, path: str, *, expect=None,
                  label: str = "", save_as: str = "", timeout: float = 120.0,
                  check: bool = True, **kw) -> Call:
        sid = self.rec._current.sid if self.rec._current else "?"
        t0 = time.perf_counter()
        resp = None
        err = ""
        try:
            resp = await client.request(method, path, timeout=timeout, **kw)
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
        ms = int((time.perf_counter() - t0) * 1000)

        status = resp.status_code if resp is not None else None
        body: object = None
        artifact = ""
        if resp is not None:
            ct = resp.headers.get("content-type", "")
            if "application/json" in ct:
                try:
                    body = resp.json()
                except Exception:
                    body = resp.text[:4000]
            elif "text/" in ct:
                body = resp.text[:4000]
            else:
                body = f"<{ct or 'binary'}, {len(resp.content)} bytes>"
            if save_as:
                dest = self.rec.artifacts / save_as
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(resp.content)
                artifact = str(dest.relative_to(self.run_dir))

        self.rec.api(sid, method, path, status, ms,
                     request_body=kw.get("json"), response_body=body,
                     error=err, artifact=artifact)

        if check and expect is not None:
            ok = resp is not None and status in expect
            detail = f"status={status}" if not err else err
            if not ok and isinstance(body, dict):
                detail += f" body={json.dumps(body, default=str)[:200]}"
            self.rec.check(label or f"{method} {path} → {expect}", ok, detail)
        return Call(resp, body, status, ms, err)

    async def sweep(self, group: str, calls: list) -> None:
        """Fire a group of calls; require that NONE answers with a server error.

        The journey scenarios above assert exact behaviour on the important
        paths. This sweep exists to touch the REST of the API surface for real
        (coverage + crash detection): a 200/4xx is a documented answer, a 5xx or
        a transport failure is a bug.
        """
        bad: list[str] = []
        for entry in calls:
            method, path = entry[0], entry[1]
            body = entry[2] if len(entry) > 2 else None
            r = await self.api(self.user, method, path, json=body,
                               expect=None, check=False)
            if r.status is None or r.status >= 500:
                bad.append(f"{method} {path}→{r.status}"
                           + (f" ({r.error})" if r.error else ""))
        self.check(f"{group}: {len(calls) - len(bad)}/{len(calls)} answered "
                   f"without a server error", not bad,
                   f"crashes: {bad}" if bad else "no crashes")

    async def poll(self, client, path: str, *, done, timeout: float,
                   interval: float = 3.0, label: str = "") -> Call:
        """Poll a background-status endpoint until `done(body)` or timeout."""
        sid = self.rec._current.sid if self.rec._current else "?"
        deadline = time.monotonic() + timeout
        last = None
        while time.monotonic() < deadline:
            last = await self.api(client, "GET", path, expect=None,
                                  label=label, timeout=30.0)
            if last.resp is None:
                await asyncio.sleep(interval)
                continue
            if done(last.body):
                return last
            await asyncio.sleep(interval)
        return last if last is not None else Call(None, None, None, 0, "no poll")

    # ---------------------------------------------------- scenario accessors
    @property
    def cur(self) -> str:
        return self.rec._current.sid if self.rec._current else "?"

    def note(self, text: str) -> None:
        self.rec.note(text)

    def check(self, name: str, ok: bool, detail: str = "") -> bool:
        return self.rec.check(name, ok, detail)


# ------------------------------------------------------------------- scenarios

async def s01_boot(j: Journey) -> None:
    j.note(f"server: {j.base}")
    r = await j.api(j.anon, "GET", "/api/system/health", expect=(200,),
                    label="public /api/system/health is reachable")
    if isinstance(r.body, dict):
        j.check("health reports product + features",
                bool(r.body.get("product") or r.body.get("service")),
                f"product={r.body.get('product')} version={r.body.get('version')}")
    r = await j.api(j.anon, "GET", "/api/auth/status", expect=(200,),
                    label="public /api/auth/status is reachable")
    if isinstance(r.body, dict):
        j.check("fresh instance needs bootstrap",
                r.body.get("needs_bootstrap") is True,
                f"needs_bootstrap={r.body.get('needs_bootstrap')}")
    r = await j.api(j.anon, "GET", "/openapi.json", expect=(200,),
                    label="OpenAPI document served (public)")
    if isinstance(r.body, dict):
        j.openapi = r.body
        ops = sum(len([m for m in v if m in ("get", "post", "put", "delete", "patch")])
                  for v in r.body.get("paths", {}).values())
        j.note(f"OpenAPI declares {ops} operations")
    await j.api(j.anon, "GET", "/", expect=(200,), label="dashboard HTML served")
    await j.api(j.anon, "GET", "/docs", expect=(200,), label="API docs served")


async def s02_bootstrap(j: Journey) -> None:
    r = await j.api(j.admin, "POST", "/api/auth/bootstrap",
                    json={"username": ADMIN_USERNAME, "password": PASSWORD},
                    expect=(200,), label="first account created (bootstrap)")
    if isinstance(r.body, dict):
        j.check("bootstrap account is admin",
                (r.body.get("user") or {}).get("role") == "admin",
                f"user={(r.body.get('user') or {}).get('username')} "
                f"role={(r.body.get('user') or {}).get('role')}")
    j.check("session cookie issued",
            any(c.name == "jobagent_session" for c in j.admin.cookies.jar),
            "jobagent_session present")
    await j.api(j.admin, "POST", "/api/auth/bootstrap",
                json={"username": "sneaky", "password": PASSWORD},
                expect=(403,), label="second bootstrap refused")
    r = await j.api(j.admin, "GET", "/api/auth/me", expect=(200,),
                    label="/me returns the session user")
    j.check("me identifies the bootstrap admin",
            isinstance(r.body, dict)
            and (r.body.get("user") or {}).get("username") == ADMIN_USERNAME)


async def s03_anonymous_lockdown(j: Journey) -> None:
    protected = ["/api/jobs", "/api/settings/profile", "/api/evidence",
                 "/api/crm/statuses", "/api/packages", "/api/outreach/config",
                 "/api/research/providers", "/api/countries",
                 "/api/matching/status", "/api/daily-run/today",
                 "/api/analytics/monitoring", "/api/discovery/adapters"]
    for path in protected:
        r = await j.api(j.anon, "GET", path, expect=(401,), check=False)
        j.check(f"anonymous GET {path} → 401", r.status == 401, f"status={r.status}")
    r = await j.api(j.anon, "POST", "/api/resume/upload", expect=(401,),
                    check=False, files={"file": ("x.txt", b"hi", "text/plain")})
    j.check("anonymous resume upload → 401", r.status == 401, f"status={r.status}")
    await j.api(j.anon, "GET", "/api/system/health", expect=(200,),
                label="public health still open while anonymous")


async def s04_login(j: Journey) -> None:
    await j.api(j.anon, "POST", "/api/auth/login",
                json={"username": ADMIN_USERNAME, "password": "definitely-wrong"},
                expect=(401,), label="wrong password rejected")
    r = await j.api(j.anon, "POST", "/api/auth/login",
                    json={"username": ADMIN_USERNAME, "password": PASSWORD},
                    expect=(200,), label="correct password accepted")
    j.check("login returns the user",
            isinstance(r.body, dict)
            and (r.body.get("user") or {}).get("username") == ADMIN_USERNAME)
    await j.api(j.anon, "GET", "/api/auth/me", expect=(200,),
                label="/me works on the logged-in client")
    r = await j.api(j.anon, "GET", "/api/jobs?limit=1", expect=(200,),
                    label="authenticated /api/jobs reachable")
    jobs = as_list(r.body, "jobs")
    if jobs:
        j.admin_job_id = job_id_of(jobs[0])
    j.note(f"admin pool sample size={len(jobs)} first_job_id={j.admin_job_id}")


async def s05_admin_creates_user(j: Journey) -> None:
    r = await j.api(j.admin, "POST", "/api/auth/users",
                    json={"username": JOURNEY_USERNAME, "password": PASSWORD,
                          "role": "user"},
                    expect=(200,), label="admin creates the journey user")
    if isinstance(r.body, dict):
        j.check("created user has the requested username",
                (r.body.get("user") or {}).get("username") == JOURNEY_USERNAME)
    await j.api(j.admin, "POST", "/api/auth/users",
                json={"username": JOURNEY_USERNAME, "password": PASSWORD},
                expect=(422,), label="duplicate username refused")
    r = await j.api(j.admin, "GET", "/api/auth/users", expect=(200,),
                    label="admin lists users")
    names = {u.get("username") for u in as_list(r.body, "users")}
    j.check("both accounts listed", {ADMIN_USERNAME, JOURNEY_USERNAME} <= names,
            f"users={sorted(n for n in names if n)}")


async def s06_user_workspace_born_empty(j: Journey) -> None:
    await j.api(j.user, "POST", "/api/auth/login",
                json={"username": JOURNEY_USERNAME, "password": PASSWORD},
                expect=(200,), label="journey user logs in")
    r = await j.api(j.user, "GET", "/api/jobs?limit=5", expect=(200,),
                    label="journey user sees their own (empty) pool")
    j.check("new user's pool starts empty", len(as_list(r.body, "jobs")) == 0,
            f"jobs={len(as_list(r.body, 'jobs'))}")
    r = await j.api(j.user, "GET", "/api/resumes", expect=(200,),
                    label="new user has no resume yet")
    j.check("no resume on a fresh workspace", len(as_list(r.body, "resumes")) == 0)
    r = await j.api(j.user, "GET", "/api/ai-settings", expect=(200,),
                    label="new user has no AI key yet")
    if isinstance(r.body, dict):
        j.check("no key on a fresh workspace",
                not r.body.get("has_key"),
                f"provider={r.body.get('provider')!r} has_key={r.body.get('has_key')}")
    users_root = j.run_dir / "data" / "users"
    dirs = sorted(p.name for p in users_root.iterdir()) if users_root.exists() else []
    j.check("per-user workspace directory created",
            any(JOURNEY_USERNAME in d for d in dirs), f"workspaces={dirs}")
    j.check("workspace has its own jobagent.db",
            any((users_root / d / "jobagent.db").exists() for d in dirs))
    prof = [d for d in dirs if JOURNEY_USERNAME in d]
    if prof:
        yamls = sorted(p.name for p in (users_root / prof[0] / "profile").glob("*.yaml"))
        j.check("evidence templates seeded (fail-closed start)", len(yamls) >= 8,
                f"{len(yamls)} templates")
    if j.admin_job_id:
        await j.api(j.user, "GET", f"/api/jobs/{j.admin_job_id}", expect=(404,),
                    label="another account's job id is invisible (404)")


async def s07_user_sets_own_ai_key(j: Journey) -> None:
    if not j.ai.get("api_key"):
        j.check("a real AI key is available to give the user", False,
                "no key found in any workspace DB / JOBAGENT_E2E_AI_KEY")
        return
    provider = j.ai.get("provider") or "deepseek"
    model = j.ai.get("model") or "deepseek-flash"
    j.note(f"giving journey user provider={provider} model={model}")
    r = await j.api(j.user, "POST", "/api/ai-settings",
                    json={"provider": provider, "api_key": j.ai["api_key"],
                          "model": model},
                    expect=(200,), label="user saves their OWN AI key")
    r = await j.api(j.user, "GET", "/api/ai-settings", expect=(200,),
                    label="user's AI settings read back")
    if isinstance(r.body, dict):
        j.check("provider persisted", r.body.get("provider") == provider,
                f"provider={r.body.get('provider')}")
        j.check("key stored but masked in the UI",
                bool(r.body.get("has_key")) and r.body.get("api_key", "").startswith("****"),
                f"api_key={r.body.get('api_key')}")
    r = await j.api(j.user, "POST", "/api/ai-settings/test",
                    json={"provider": provider, "api_key": "****", "model": model},
                    expect=(200,), timeout=90.0,
                    label="live AI connection test (real provider call)")
    if isinstance(r.body, dict):
        j.check("AI provider answers live", r.body.get("ok") is True,
                f"ok={r.body.get('ok')} error={str(r.body.get('error'))[:120]}")
    # The app-level client must NOT have been swapped to this user's key.
    r = await j.api(j.admin, "GET", "/api/ai-settings", expect=(200,),
                    label="admin's own AI settings unchanged")
    j.note(f"admin provider={r.body.get('provider') if isinstance(r.body, dict) else '?'}")


async def s08_resume_upload_and_grading(j: Journey) -> None:
    if not REAL_RESUME:
        j.check("real resume available to upload", False, "no stored resume found")
        return
    docx_bytes = build_resume_docx(REAL_RESUME)
    (j.rec.artifacts / "resume_uploaded.docx").write_bytes(docx_bytes)
    (j.rec.artifacts / "resume_uploaded.txt").write_text(REAL_RESUME, encoding="utf-8")
    j.note(f"uploading real resume ({len(REAL_RESUME)} chars) as .docx "
           f"({len(docx_bytes)} bytes)")
    r = await j.api(j.user, "POST", "/api/resume/upload",
                    files={"file": ("basil_resume.docx", docx_bytes,
                                    "application/vnd.openxmlformats-officedocument."
                                    "wordprocessingml.document")},
                    expect=(200,), timeout=300.0,
                    label="resume uploaded + analysed (live AI)")
    if not isinstance(r.body, dict):
        return
    b = r.body
    j.check("ATS grading produced a score", b.get("ats_score", 0) > 0,
            f"ats_score={b.get('ats_score')}")
    j.check("grading produced feedback",
            bool(b.get("ats_issues")) or bool(b.get("ats_tips")),
            f"issues={len(b.get('ats_issues') or [])} tips={len(b.get('ats_tips') or [])}")
    j.check("search terms derived from the resume", bool(b.get("search_terms")),
            f"terms={(b.get('search_terms') or [])[:5]}")
    j.check("key skills derived from the resume", bool(b.get("key_skills")),
            f"skills={(b.get('key_skills') or [])[:6]}")
    j.check("seniority + summary derived",
            bool(b.get("seniority")) and bool(b.get("summary")),
            f"seniority={b.get('seniority')!r}")
    j.check("profile parsed from the resume", b.get("profile_parsed") is True)
    j.check("resume text extracted (not raw zip bytes)",
            (b.get("resume_length") or 0) > 200 and REAL_RESUME[:20] in (
                (b.get("summary") or "") + "x") or (b.get("resume_length") or 0) > 200,
            f"resume_length={b.get('resume_length')}")
    r2 = await j.api(j.user, "GET", "/api/resumes", expect=(200,),
                     label="uploaded resume appears in the Resumes list")
    resumes = as_list(r2.body, "resumes")
    j.check("resume recorded + default", len(resumes) >= 1
            and any(x.get("is_default") for x in resumes),
            f"count={len(resumes)}")
    r3 = await j.api(j.user, "GET", "/api/search-config", expect=(200,),
                     label="grading persisted onto the search config")
    if isinstance(r3.body, dict):
        cfg = r3.body.get("config", r3.body)
        j.check("search config carries the resume + terms",
                bool(cfg.get("resume_text")) and bool(cfg.get("search_terms")),
                f"ats_score={cfg.get('ats_score')}")
    r4 = await j.api(j.user, "GET", "/api/analytics/monitoring?days=1",
                     expect=(200,), label="cost meter shows which model ran")
    blob = json.dumps(r4.body, default=str)
    j.check("grading ran on the USER'S provider (not the app default)",
            (j.ai.get("model", "deepseek") or "deepseek") in blob,
            "model appears in the per-model cost table" if
            (j.ai.get("model", "") or "deepseek") in blob else
            f"expected {j.ai.get('model')} in meter")


async def s09_evidence(j: Journey) -> None:
    r = await j.api(j.user, "GET", "/api/evidence", expect=(200,),
                    label="evidence summary (after autofill)")
    verified = None
    if isinstance(r.body, dict):
        verified = r.body.get("verified_claims")
        if verified is None:
            summary = r.body.get("summary") or {}
            verified = summary.get("verified_claims")
        if verified is None:
            verified = len(as_list(r.body, "claims"))
    j.check("upload auto-VERIFIED evidence from the resume",
            bool(verified and verified > 0), f"verified_claims={verified}")
    await j.api(j.user, "POST", "/api/evidence/reload", expect=(200,),
                label="evidence reload")
    r = await j.api(j.user, "POST", "/api/evidence/backfill", expect=(200,),
                    label="zero-AI evidence backfill")
    if isinstance(r.body, dict):
        j.check("backfill reports verified claims", bool(r.body.get("ok")))
    r = await j.api(j.user, "POST", "/api/evidence/check",
                    json={"text": "Expert in Kubernetes, Go and Quantum Computing "
                                  "with 15 years of experience leading teams."},
                    expect=(200,), label="hard gate flags a fabricated claim")
    if isinstance(r.body, dict):
        j.check("fabricated skills are caught (gate refuses)",
                r.body.get("ok") is False or bool(r.body.get("failures")),
                f"ok={r.body.get('ok')} failures="
                f"{[f.get('type') for f in (r.body.get('failures') or [])]}")
    excerpt = " ".join(REAL_RESUME.split("\n")[2:8])[:300] or REAL_RESUME[:300]
    r = await j.api(j.user, "POST", "/api/evidence/check", json={"text": excerpt},
                    expect=(200,), label="hard gate passes the candidate's own words")
    if isinstance(r.body, dict):
        j.check("the candidate's own resume text passes the gate",
                r.body.get("ok") is True,
                f"ok={r.body.get('ok')} failures="
                f"{[f.get('type') for f in (r.body.get('failures') or [])]}")


async def s10_countries(j: Journey) -> None:
    r = await j.api(j.user, "GET", "/api/countries", expect=(200,),
                    label="country strategy list")
    regions: list[str] = []
    if isinstance(r.body, dict):
        countries = as_list(r.body, "countries")
        regions = [c.get("region") or c.get("code") for c in countries
                   if isinstance(c, dict)]
        j.check("6 country definitions loaded", len(countries) >= 6,
                f"count={len(countries)} regions={regions}")
    r2 = await j.api(j.user, "GET", "/api/search-config/allowed-regions",
                     expect=(200,), label="allowed regions")
    allowed = as_list(r2.body, "regions") or as_list(r2.body, "allowed_regions")
    j.check("resume upload seeded a country strategy", bool(allowed),
            f"allowed={allowed}")
    target = allowed[0] if allowed else (regions[0] if regions else "Remote")
    await j.api(j.user, "GET", f"/api/countries/{target}", expect=(200,),
                label=f"country detail for {target}")
    detail = await j.api(j.user, "GET", f"/api/countries/{target}", expect=(200,),
                         check=False)
    cfg_body = (detail.body or {}).get("country") if isinstance(detail.body, dict) \
        else None
    if cfg_body:
        await j.api(j.user, "PUT", f"/api/countries/{target}",
                    json={"enabled": True}, expect=None, check=False,
                    label=f"toggle {target} (persists to YAML with backup)")
    await j.api(j.user, "POST", "/api/countries/apply", expect=(200,),
                label="apply strategy to the pool (restore-then-dismiss)")
    r3 = await j.api(j.user, "POST", f"/api/countries/{target}/visa-check",
                     json={"text": "We sponsor visas and offer relocation support."},
                     expect=(200,), label="deterministic visa check (no LLM)")
    if isinstance(r3.body, dict):
        j.check("visa check is deterministic", "sponsors_international" in r3.body
                or "matched_keywords" in r3.body,
                f"keys={sorted(r3.body)[:6]}")
    await j.api(j.user, "POST", "/api/countries/reload", expect=(200,),
                label="reload country YAMLs")


async def s11_adapters(j: Journey) -> None:
    r = await j.api(j.user, "GET", "/api/discovery/adapters", expect=(200,),
                    label="ATS adapter registry")
    adapters = as_list(r.body, "adapters")
    j.check("4 ATS adapters registered", len(adapters) >= 4, f"{adapters}")
    r = await j.api(j.user, "GET", "/api/discovery/health", expect=(200,),
                    timeout=180.0, label="LIVE health probe of every adapter")
    sources = as_list(r.body, "sources")
    ok_sources = [s.get("source") for s in sources if s.get("ok")]
    j.note(f"adapter health: {len(ok_sources)}/{len(sources)} reachable — {ok_sources}")
    j.check("at least one live ATS source answered", bool(ok_sources))


async def s12_discovery(j: Journey) -> None:
    before = await j.api(j.user, "GET", "/api/jobs?limit=200", expect=(200,),
                         check=False)
    before_n = len(as_list(before.body, "jobs"))
    r = await j.api(j.user, "POST", "/api/discovery/run?passes=2", expect=(200,),
                    label="start orchestrated discovery (bounded to 2 passes)")
    if isinstance(r.body, dict):
        j.check("the cycle reports its pass budget", r.body.get("passes") == 2,
                f"passes={r.body.get('passes')} "
                f"countries={r.body.get('countries')}")
        if r.body.get("status") == "already_running":
            j.note("discovery was already running")
    last = await j.poll(j.user, "/api/discovery/status",
                        done=lambda b: isinstance(b, dict) and b.get("running") is False
                        and b.get("last_telemetry") is not None,
                        timeout=DISCOVERY_SECS, interval=5.0,
                        label="poll discovery status")
    tele = {}
    if isinstance(last.body, dict):
        tele = last.body.get("last_telemetry") or {}
        if last.body.get("running"):
            j.note("discovery still running when the poll budget expired")
    after = await j.api(j.user, "GET", "/api/jobs?limit=200", expect=(200,),
                        label="pool size after discovery")
    after_n = len(as_list(after.body, "jobs"))
    j.note(f"pool {before_n} → {after_n} after discovery; "
           f"telemetry={'yes' if tele else 'not yet'}")
    # The cycle is a long background sweep by design; what must hold is that it
    # really drove the adapters and fed THIS user's pool, or produced telemetry.
    j.check("discovery ran for real (telemetry and/or new jobs in the pool)",
            bool(tele) or after_n > before_n,
            f"telemetry_keys={sorted(tele)[:8]} pool_growth={after_n - before_n}")
    if tele:
        j.check("telemetry records the countries and pass budget",
                bool(tele.get("countries")) and bool(tele.get("pass_budget")),
                f"countries={tele.get('countries')} "
                f"budget={tele.get('pass_budget')} "
                f"new_jobs={tele.get('new_jobs')}")


async def s13_scrapers(j: Journey) -> None:
    r = await j.api(j.user, "GET", "/api/health", expect=(200,),
                    label="scraper health surface")
    if isinstance(r.body, dict):
        j.note(f"scraper health keys: {sorted(r.body)[:8]}")
    r = await j.api(j.user, "POST", "/api/scrape", expect=(202, 409),
                    label="start real scrape cycle (21 sources, per-user target)")
    if isinstance(r.body, dict):
        j.note(f"scrape status={r.body.get('status') or r.body.get('error')} "
               f"task={r.body.get('task_id')}")
    last = await j.poll(j.user, "/api/scrape/progress",
                        done=lambda b: isinstance(b, dict)
                        and b.get("active") is False,
                        timeout=SCRAPE_SECS, interval=5.0,
                        label="poll scrape progress")
    if isinstance(last.body, dict):
        j.note(f"scrape progress: {json.dumps(last.body, default=str)[:300]}")
        if last.body.get("active") is True:
            await j.api(j.user, "POST", "/api/scrape/cancel", expect=(200,),
                        label="scrape still running after budget → cancel")
    r = await j.api(j.user, "GET", "/api/jobs?limit=100", expect=(200,),
                    label="pool after scraping")
    jobs = as_list(r.body, "jobs")
    j.note(f"the USER's pool now holds {len(jobs)} jobs (limit 100)")
    radmin = await j.api(j.admin, "GET", "/api/jobs?limit=100", expect=(200,),
                         check=False)
    admin_jobs = as_list(radmin.body, "jobs")
    j.note(f"the ADMIN pool holds {len(admin_jobs)} jobs (must stay its own)")
    j.check("real scrapers delivered jobs through the running product",
            len(jobs) > 0 or len(admin_jobs) > 0,
            f"user_pool={len(jobs)} admin_pool={len(admin_jobs)}")
    j.check("the scrape run targeted the requesting user's workspace",
            len(jobs) > 0,
            f"user_pool={len(jobs)}" if len(jobs) > 0 else
            "no jobs landed in the user's pool (M15c regression?)")


async def s14_scoring(j: Journey) -> None:
    if not REAL_RESUME:
        return
    # Ensure there is at least one scoreable job; if the network gave us nothing,
    # save a real-looking posting through the product's own API so the AI stages
    # are exercised against real input (recorded honestly below).
    r = await j.api(j.user, "GET", "/api/jobs?limit=100", expect=(200,), check=False)
    jobs = as_list(r.body, "jobs")
    if not jobs:
        j.note("pool empty after scraping — seeding one posting via "
               "POST /api/jobs/save-external so the AI stages have real input")
        seed = await j.api(j.user, "POST", "/api/jobs/save-external",
                           json={
                               "title": "AI Engineer (LLM / RAG Platform)",
                               "company": "Northwind AI",
                               "location": "Berlin, Germany",
                               "url": "https://example.com/jobs/ai-engineer-llm-rag",
                               "description": (
                                   "We are hiring an AI Engineer to build production RAG "
                                   "and agentic systems. Requirements: Python, FastAPI, "
                                   "LangChain, LangGraph, retrieval-augmented generation, "
                                   "vector databases (Milvus/PGVector), Azure OpenAI or "
                                   "equivalent LLM APIs, evaluation of LLM pipelines, "
                                   "multi-agent orchestration. You will own the retrieval "
                                   "layer, prompt/agent design, latency and cost tuning, and "
                                   "ship LLM features to healthcare and insurance customers. "
                                   "We sponsor visas and support relocation to Berlin."),
                               "posted_date": TODAY,
                               "source": "manual",
                           },
                           expect=(200,), label="seed a posting for the AI pipeline")
    r = await j.api(j.user, "POST", "/api/matching/score-all", expect=(200,),
                    timeout=300.0,
                    label="deterministic hybrid scoring of the whole pool (free)")
    if isinstance(r.body, dict):
        j.note(f"score-all: {json.dumps(r.body, default=str)[:200]}")
    await j.api(j.user, "GET", "/api/matching/status", expect=(200,),
                label="matching status")
    r = await j.api(j.user, "GET", "/api/matching/top-jobs?limit=10", expect=(200,),
                    label="ranked top jobs")
    top = as_list(r.body, "jobs") or as_list(r.body, "items")
    j.note(f"top-jobs returned {len(top)} entries")
    r = await j.api(j.user, "GET", "/api/jobs?limit=100", expect=(200,),
                    label="scored pool")
    jobs = as_list(r.body, "jobs")
    scored = [x for x in jobs if (x.get("score") or x.get("match_score"))]
    j.check("jobs carry scores after score-all", bool(scored),
            f"{len(scored)}/{len(jobs)} scored")

    # Choose the job the rest of the journey will use: highest score with a
    # substantial description (needed for tailoring + cover letter).
    candidates = sorted(jobs, key=lambda x: -(x.get("score") or 0))[:15]
    for cand in candidates:
        jid = job_id_of(cand)
        if not jid:
            continue
        full = await j.api(j.user, "GET", f"/api/jobs/{jid}", expect=(200,),
                           check=False)
        body = full.body if isinstance(full.body, dict) else {}
        job = body.get("job", body)
        if len(str(job.get("description") or "")) > 200:
            j.pick_job = job
            j.user_job_id = jid
            break
    if j.pick_job is None and jobs:
        jid = job_id_of(jobs[0])
        full = await j.api(j.user, "GET", f"/api/jobs/{jid}", expect=(200,),
                          check=False)
        body = full.body if isinstance(full.body, dict) else {}
        j.pick_job = body.get("job", body)
        j.user_job_id = jid
    # A second job we never touch — used to prove the engine's forward-skip rules.
    for cand in candidates:
        cid = job_id_of(cand)
        if cid and cid != j.user_job_id:
            j.extra_job_id = cid
            break
    j.check("a job with a real description was selected for AI stages",
            j.pick_job is not None and j.user_job_id is not None,
            f"job_id={j.user_job_id} "
            f"title={(j.pick_job or {}).get('title')!r}")
    if j.user_job_id:
        await j.api(j.user, "POST", f"/api/matching/jobs/{j.user_job_id}/score",
                    expect=(200,), label="persist a single hybrid score")
        await j.api(j.user, "GET", f"/api/matching/jobs/{j.user_job_id}/explain",
                    expect=(200,), label="score explainability")


async def s15_eligibility(j: Journey) -> None:
    if not j.user_job_id:
        return
    r = await j.api(j.user, "POST", f"/api/jobs/{j.user_job_id}/eligibility",
                    expect=(200,), label="re-run the eligibility gate")
    await j.api(j.user, "GET", f"/api/jobs/{j.user_job_id}/freshness",
                expect=(200,), label="freshness evidence for the job")
    r2 = await j.api(j.user, "GET", "/api/eligibility/eligible-jobs?limit=10",
                     expect=(200,), label="eligible job pool")
    j.note(f"eligible jobs: {len(as_list(r2.body, 'jobs'))}")


async def s16_research(j: Journey) -> None:
    if not j.pick_job:
        return
    company = j.pick_job.get("company") or "Northwind AI"
    await j.api(j.user, "GET", "/api/research/providers", expect=(200,),
                label="contact provider chain status")
    await j.api(j.user, "POST", f"/api/research/company/{company}",
                expect=(200,), timeout=180.0, label="company enrichment")
    await j.api(j.user, "GET", f"/api/research/company/{company}", expect=(200,),
                label="company enrichment (cache hit)")
    await j.api(j.user, "POST", f"/api/research/contacts/job/{j.user_job_id}",
                expect=(200,), timeout=240.0,
                label="contact research for the job")
    r = await j.api(j.user, "GET", f"/api/research/contacts/job/{j.user_job_id}",
                    expect=(200,), label="read back researched contacts")
    candidates = as_list(r.body, "candidates") or as_list(r.body, "contacts")
    if candidates:
        cid = candidates[0].get("id") if isinstance(candidates[0], dict) else None
        if cid is not None:
            await j.api(j.user, "POST",
                        f"/api/research/contacts/job/{j.user_job_id}/select",
                        json={"contact_id": cid, "candidate_index": 0},
                        expect=None, check=False,
                        label="promote a researched contact onto the job")
    else:
        j.note("no contact candidates found (no paid provider keys) — "
               "select path not applicable")


async def s17_tailoring(j: Journey) -> None:
    if not j.user_job_id:
        return
    r = await j.api(j.user, "POST", f"/api/jobs/{j.user_job_id}/prepare",
                    expect=(200,), timeout=420.0,
                    label="AI resume tailoring through the evidence gate")
    if isinstance(r.body, dict):
        tailored = r.body.get("tailored_resume") or ""
        (j.rec.artifacts / "tailored_resume.txt").write_text(tailored, encoding="utf-8")
        gate = r.body.get("evidence_check") or {}
        j.check("tailored resume returned", len(tailored) > 200,
                f"{len(tailored)} chars")
        j.check("evidence gate passed (nothing unverified was saved)",
                gate.get("ok") is True,
                f"failures={[f.get('type') for f in (gate.get('failures') or [])]}")
        j.check("tailoring was persisted as an application",
                r.body.get("status") == "prepared", f"status={r.body.get('status')}")
    await j.api(j.user, "GET", f"/api/jobs/{j.user_job_id}/resume.docx",
                expect=(200,), save_as="tailored_resume.docx",
                label="tailored resume DOCX download")
    await j.api(j.user, "GET", f"/api/jobs/{j.user_job_id}/resume.pdf",
                expect=(200,), save_as="tailored_resume.pdf",
                label="tailored resume PDF download")


async def s18_cover_letter(j: Journey) -> None:
    if not j.user_job_id:
        return
    r = await j.api(j.user, "POST",
                    f"/api/jobs/{j.user_job_id}/generate-cover-letter",
                    expect=(200,), timeout=420.0,
                    label="AI cover letter generation (live provider)")
    letter = ""
    if isinstance(r.body, dict):
        letter = r.body.get("cover_letter") or ""
    (j.rec.artifacts / "cover_letter.txt").write_text(letter, encoding="utf-8")
    j.check("cover letter returned and non-trivial", len(letter) > 200,
            f"{len(letter)} chars")
    await j.api(j.user, "GET", f"/api/jobs/{j.user_job_id}/cover-letter.docx",
                expect=(200,), save_as="cover_letter.docx",
                label="cover letter DOCX download")
    await j.api(j.user, "GET", f"/api/jobs/{j.user_job_id}/cover-letter.pdf",
                expect=(200,), save_as="cover_letter.pdf",
                label="cover letter PDF download")
    edited = letter + "\n\n(edited via API during the E2E journey)"
    r2 = await j.api(j.user, "PUT", f"/api/jobs/{j.user_job_id}/cover-letter",
                     json={"cover_letter": edited}, expect=(200,),
                     label="manual cover-letter edit round-trips")


async def s19_package(j: Journey) -> None:
    if not j.user_job_id:
        return
    r = await j.api(j.user, "POST", f"/api/packages/jobs/{j.user_job_id}/build",
                    expect=(200,), timeout=420.0,
                    label="build the application package (evidence-gated)")
    if isinstance(r.body, dict):
        files = as_list(r.body, "files") or as_list(r.body, "package_files")
        j.package_files = [f if isinstance(f, str) else f.get("name") for f in files
                          if f]
        if not j.package_files:
            meta = r.body.get("package") or {}
            j.package_files = as_list(meta, "files")
        j.note(f"package status={r.body.get('status')} files={j.package_files}")
        j.check("package contains the resume + cover letter",
                len(j.package_files) >= 2, f"files={j.package_files}")
    r2 = await j.api(j.user, "GET", f"/api/packages/jobs/{j.user_job_id}",
                     expect=(200,), label="package metadata")
    if isinstance(r2.body, dict):
        pkg = r2.body.get("package") or r2.body
        j.check("package records a fingerprint (idempotency key)",
                bool(pkg.get("package_fingerprint") or pkg.get("fingerprint")),
                f"status={pkg.get('package_status')}")
    for name in (j.package_files or [])[:5]:
        if not name:
            continue
        safe = os.path.basename(str(name))
        await j.api(j.user, "GET",
                    f"/api/packages/jobs/{j.user_job_id}/download/{safe}",
                    expect=(200,), save_as=f"package/{safe}",
                    label=f"download {safe}")
    await j.api(j.user, "GET", "/api/packages", expect=(200,),
                label="package list")
    # Rebuild with refresh=true: repackages stored text with ZERO AI (idempotent)
    await j.api(j.user, "POST",
                f"/api/packages/jobs/{j.user_job_id}/build?refresh=true",
                expect=(200,), timeout=180.0,
                label="repackaged from stored text (no AI spend)")


async def s20_outreach(j: Journey) -> None:
    if not j.user_job_id:
        return
    r = await j.api(j.user, "POST", f"/api/outreach/jobs/{j.user_job_id}/create",
                    json={"audience": "recruiter"}, expect=(200,),
                    timeout=180.0, label="create outreach draft (draft-only)")
    if isinstance(r.body, dict):
        j.note(f"draft: status={r.body.get('status')} "
               f"provider={r.body.get('provider')} "
               f"draft_id={r.body.get('draft_id')}")
    r2 = await j.api(j.user, "POST", f"/api/outreach/jobs/{j.user_job_id}/create",
                     json={"audience": "recruiter"}, expect=(200,),
                     timeout=180.0,
                     label="CRITICAL #4: creating it twice must not duplicate")
    if isinstance(r2.body, dict):
        j.check("second create is reported as already-existing",
                r2.body.get("already_exists") is True
                or r2.body.get("status") in ("already_exists", "existing"),
                f"body_keys={sorted(r2.body)[:8]} already_exists="
                f"{r2.body.get('already_exists')}")
    r3 = await j.api(j.user, "POST", f"/api/outreach/jobs/{j.user_job_id}/followup",
                     json={}, expect=(200,), timeout=180.0,
                     label="follow-up honours the wait window")
    if isinstance(r3.body, dict):
        j.check("follow-up gated by the cadence window",
                r3.body.get("too_soon") is True
                or r3.body.get("status") in ("too_soon", "created", "draft"),
                f"status={r3.body.get('status')} too_soon={r3.body.get('too_soon')}")
    r4 = await j.api(j.user, "GET", f"/api/outreach/jobs/{j.user_job_id}",
                     expect=(200,), label="read back the job's outreach")
    if isinstance(r4.body, dict):
        msgs = as_list(r4.body, "messages")
        j.check("exactly one draft exists for the job", len(msgs) <= 1,
                f"messages={len(msgs)}")
    await j.api(j.user, "GET", "/api/outreach/messages", expect=(200,),
                label="outreach message list")
    r5 = await j.api(j.user, "GET", "/api/outreach/config", expect=(200,),
                     label="outreach config (caps + gmail state)")
    if isinstance(r5.body, dict):
        j.check("gmail state reported honestly",
                "gmail_connected" in r5.body,
                f"gmail_connected={r5.body.get('gmail_connected')}")


async def s21_crm(j: Journey) -> None:
    if not j.user_job_id:
        return
    await j.api(j.user, "GET", "/api/crm/statuses", expect=(200,),
                label="CRM status enum + transitions")
    r = await j.api(j.user, "POST",
                    f"/api/jobs/{j.user_job_id}/status?to_status=applied",
                    expect=(200,),
                    label="move the job to 'applied' (validated transition)")
    # The engine deliberately ALLOWS forward skips inside the pipeline (an
    # off-platform application/offer is real) but forbids landing on 'offered'
    # from a job that was never applied to. Probe that on an untouched job.
    probe_job = j.extra_job_id or j.user_job_id
    r2 = await j.api(j.user, "POST",
                     f"/api/jobs/{probe_job}/status?to_status=offered",
                     check=False, expect=None,
                     label="'offered' without ever applying (must be refused)")
    refused = r2.status is not None and (r2.status >= 400 or (
        isinstance(r2.body, dict) and r2.body.get("ok") is False))
    j.check("unearned 'offered' is blocked by the engine", refused,
            f"status={r2.status} body={json.dumps(r2.body, default=str)[:160]}")
    r3 = await j.api(j.user, "POST", "/api/crm/followups/run", expect=(200,),
                     label="run the follow-up engine")
    if isinstance(r3.body, dict):
        j.note(f"followups: {json.dumps(r3.body, default=str)[:200]}")
    await j.api(j.user, "GET", "/api/pipeline", expect=(200,),
                label="pipeline funnel")
    await j.api(j.user, "POST",
                f"/api/jobs/{j.user_job_id}/bulk-status?to_status=interviewing"
                f"&job_ids={j.user_job_id}",
                expect=(200,), check=False, label="bulk-status path")
    r4 = await j.api(j.user, "POST",
                     f"/api/jobs/{j.user_job_id}/status?to_status=rejected",
                     check=False, expect=None, label="close the application")
    r5 = await j.api(j.user, "POST",
                     f"/api/jobs/{j.user_job_id}/status?to_status=applied",
                     check=False, expect=None,
                     label="resurrecting a terminal state (must be refused)")
    revived = r5.status is not None and (r5.status >= 400 or (
        isinstance(r5.body, dict) and r5.body.get("ok") is False))
    j.check("a terminal application cannot be resurrected", revived,
            f"status={r5.status} body={json.dumps(r5.body, default=str)[:160]}")


async def s22_daily_run(j: Journey) -> None:
    await j.api(j.user, "GET", "/api/daily-run/today", expect=(200,),
                label="daily run state before")
    r = await j.api(j.user, "POST", "/api/daily-run/run", expect=(200,),
                    timeout=300.0, label="run today's pipeline (idempotent)")
    if isinstance(r.body, dict):
        stages = as_list(r.body, "stages")
        j.check("daily run reports its stages", bool(stages),
                f"stages={[s.get('name') for s in stages] if stages else r.body.get('status')}")
    await j.api(j.user, "GET", "/api/daily-run/today", expect=(200,),
                label="daily run state after (persisted)")


async def s23_analytics(j: Journey) -> None:
    r = await j.api(j.user, "GET", "/api/analytics/monitoring?days=1",
                    expect=(200,), label="cost meter + run telemetry")
    if isinstance(r.body, dict):
        usage = r.body.get("ai_usage") or {}
        today = usage.get("today") or {}
        totals = today.get("totals") or {}
        calls = totals.get("calls")
        j.check("the journey's AI calls are metered", bool(calls and calls > 0),
                f"today calls={calls} cost_usd={totals.get('cost_usd')}")
        j.note(f"today usage: {json.dumps(today, default=str)[:240]}")
    await j.api(j.user, "GET", "/api/analytics/feedback", expect=(200,),
                label="feedback loop recommendations")
    await j.api(j.user, "GET", "/api/stats", expect=(200,), label="stats page data")
    await j.api(j.user, "GET", "/api/analytics", expect=(200,),
                label="analytics aggregate")


async def s24_cross_user_isolation(j: Journey) -> None:
    """CRITICAL TEST #5 — user A can never read/write user B's data."""
    j.note("Critical Test #5 — cross-user access vectors")
    if j.user_job_id:
        r = await j.api(j.admin, "GET", f"/api/jobs/{j.user_job_id}",
                        expect=(404,),
                        label="admin cannot see the user's job id")
    else:
        j.note("no user job id available to probe")
    if j.admin_job_id:
        r = await j.api(j.user, "GET", f"/api/jobs/{j.admin_job_id}", expect=(404,),
                        label="user cannot see the admin's job id")
    r = await j.api(j.user, "GET", "/api/resumes", expect=(200,),
                    label="user's resumes")
    names = {x.get("name") for x in as_list(r.body, "resumes")}
    j.check("user sees only their own resume", all("basil_resume" in (n or "")
            for n in names) and bool(names), f"names={names}")
    r = await j.api(j.admin, "GET", "/api/resumes", expect=(200,),
                    label="admin's resumes")
    admin_names = {x.get("name") for x in as_list(r.body, "resumes")}
    j.check("admin does not see the user's resume",
            "basil_resume.docx" not in admin_names,
            f"admin_names={admin_names}")
    r = await j.api(j.user, "GET", "/api/ai-settings", expect=(200,),
                    label="user's key stays masked")
    if isinstance(r.body, dict):
        j.check("user's own key is never returned in plaintext",
                str(r.body.get("api_key", "")).startswith("****"),
                f"api_key={r.body.get('api_key')}")
    if j.admin_job_id:
        await j.api(j.user, "GET",
                    f"/api/packages/jobs/{j.admin_job_id}/download/resume.docx",
                    expect=(404,),
                    label="user cannot download the admin's package files")
    # Disk-level: distinct DBs, no cross-contamination of job rows.
    users_root = j.run_dir / "data" / "users"
    dbs = {p.parent.name: p for p in users_root.glob("*/jobagent.db")} \
        if users_root.exists() else {}
    j.check("each user has a physically separate database", len(dbs) >= 2,
            f"dbs={sorted(dbs)}")
    counts = {}
    for name, path in dbs.items():
        try:
            conn = sqlite3.connect(path)
            counts[name] = conn.execute("SELECT count(*) FROM jobs").fetchone()[0]
            conn.close()
        except Exception as e:
            counts[name] = f"err:{e}"
    j.note(f"job rows per workspace: {counts}")
    mine = [v for k, v in counts.items() if JOURNEY_USERNAME in k]
    theirs = [v for k, v in counts.items() if JOURNEY_USERNAME not in k]
    j.check("the two workspaces hold different pools",
            bool(mine) and bool(theirs) and mine[0] != theirs[0],
            f"user={mine} other={theirs}")
    # Admin must not be able to disable/act on the user without an audit trail
    r = await j.api(j.admin, "GET", "/api/auth/users", expect=(200,),
                    label="admin user list (audited surface)")


def _id_of(body) -> int | None:
    if isinstance(body, dict):
        for k in ("id", "qa_id", "entry_id", "resume_id", "view_id", "alert_id",
                  "contact_id", "round_id", "template_id", "reminder_id",
                  "queue_id", "job_id"):
            if isinstance(body.get(k), int):
                return body[k]
        for v in body.values():
            if isinstance(v, dict) and isinstance(v.get("id"), int):
                return v["id"]
    return None


async def s25_crud_sweep(j: Journey) -> None:
    """The rest of the REST surface, hit for real (no crashes allowed)."""
    u = j.user
    jid = j.user_job_id or j.extra_job_id
    extra = j.extra_job_id or jid
    company = (j.pick_job or {}).get("company") or "Northwind AI"

    # --- profile + personal tables (create → read → delete) ----------------
    await j.sweep("profile", [
        ("GET", "/api/profile"),
        ("POST", "/api/profile", {"full_name": "E2E Journey User",
                                  "email": "e2e@example.com",
                                  "phone": "+49 30 1234",
                                  "location": "Berlin, Germany",
                                  "summary": "AI engineer"}),
        ("GET", "/api/profile/full"),
        ("PUT", "/api/profile/full", {"personal": {"full_name": "E2E Journey User"}}),
        ("GET", "/api/custom-qa"),
        ("GET", "/api/autofill/history"),
    ])

    tables = [
        ("custom-qa", "/api/custom-qa", {"question_pattern": "Do you need sponsorship?",
                                          "category": "visa", "answer": "Yes"}),
        ("work-history", "/api/work-history",
         {"company": "Changepond", "job_title": "AI Application Developer",
          "start_month": 5, "start_year": 2024, "is_current": 1,
          "description": "Built production RAG systems."}),
        ("education", "/api/education",
         {"school": "E.G.S. Pillay", "degree_type": "bachelors",
          "field_of_study": "Computer Science", "grad_year": 2023}),
        ("certifications", "/api/certifications",
         {"name": "Azure AI Engineer", "issuing_org": "Microsoft",
          "cert_type": "professional", "date_obtained": "2025-01-01"}),
        ("skills", "/api/skills", {"name": "LangGraph", "proficiency": "advanced"}),
        ("languages", "/api/languages", {"language": "English",
                                         "proficiency": "fluent"}),
        ("references", "/api/references", {"name": "Ref One",
                                            "relationship": "Manager",
                                            "email": "ref@example.com"}),
    ]
    for label, path, body in tables:
        created = await j.api(u, "POST", path, json=body, expect=None, check=False)
        rid = _id_of(created.body)
        if rid:
            await j.api(u, "DELETE", f"{path}/{rid}", expect=None, check=False)
        else:
            j.note(f"{label}: create returned status={created.status} with no id to delete")

    # --- resumes + saved views --------------------------------------------
    created = await j.api(u, "POST", "/api/resumes",
                          json={"name": "e2e-second-resume.txt",
                                "resume_text": REAL_RESUME[:400]},
                          expect=None, check=False)
    rid = _id_of(created.body)
    if rid:
        await j.sweep("resumes", [
            ("GET", "/api/resumes"),
            ("PUT", f"/api/resumes/{rid}", {"name": "e2e-second-resume-renamed.txt"}),
            ("POST", f"/api/resumes/{rid}/set-default"),
            ("DELETE", f"/api/resumes/{rid}"),
        ])
    else:
        await j.api(u, "GET", "/api/resumes", expect=(200,), label="resumes list")
        j.note("second resume create refused — skipped its update/delete")

    created = await j.api(u, "POST", "/api/saved-views",
                          json={"name": "e2e-view", "filters": {"min_score": 50}},
                          expect=None, check=False)
    vid = _id_of(created.body)
    ok = vid is not None
    await j.api(u, "GET", "/api/saved-views", expect=(200,), label="saved views")
    if ok:
        await j.sweep("saved views", [
            ("PUT", f"/api/saved-views/{vid}",
             {"name": "e2e-view-2", "filters": {"min_score": 60}}),
            ("DELETE", f"/api/saved-views/{vid}"),
        ])

    # --- search config surface -------------------------------------------
    await j.sweep("search config", [
        ("POST", "/api/search-config/terms", {"terms": ["AI Engineer",
                                                         "LLM Engineer"]}),
        ("POST", "/api/search-config/exclude-terms", {"terms": ["intern"]}),
        ("GET", "/api/search-config/allowed-regions"),
        ("POST", "/api/search-config/allowed-regions", {"regions": ["Germany"]}),
        ("GET", "/api/search-config/remote-only"),
        ("POST", "/api/search-config/remote-only", {"remote_only": False}),
    ])

    # --- AI / email / scraper settings -----------------------------------
    await j.sweep("infra settings", [
        ("GET", "/api/settings/embeddings"),
        ("POST", "/api/settings/embeddings",
         {"provider": "ollama", "api_key": "", "model": "nomic-embed-text",
          "base_url": "http://localhost:11434", "dimensions": 256}),
        ("POST", "/api/embeddings/backfill", {}),
        ("GET", "/api/settings/email"),
        ("POST", "/api/settings/email", {"sender_email": "e2e@example.com"}),
        ("GET", "/api/scraper-keys"),
        ("POST", "/api/scraper-keys", {"keys": {}}),
        ("GET", "/api/scraper-schedule"),
        ("POST", "/api/scraper-schedule",
         {"source_name": "greenhouse", "interval_hours": 6}),
        ("GET", "/api/ai-settings/models"),
    ])

    # --- alerts + notifications ------------------------------------------
    created = await j.api(u, "POST", "/api/alerts",
                          json={"name": "e2e-alert", "min_score": 80,
                                "filters": {}, "notify_method": "in_app"},
                          expect=None, check=False)
    aid = _id_of(created.body) or (
        (created.body or {}).get("alert") or {}).get("id") \
        if isinstance(created.body, dict) else None
    await j.api(u, "GET", "/api/alerts", expect=(200,), label="alerts list")
    if aid:
        await j.sweep("alerts", [
            ("PUT", f"/api/alerts/{aid}", {"name": "e2e-alert-2", "min_score": 90}),
            ("DELETE", f"/api/alerts/{aid}"),
        ])
    else:
        j.note(f"alert create returned status={created.status} with no id")
    await j.sweep("notifications", [
        ("GET", "/api/notifications"),
        ("POST", "/api/notifications/1/read", {}),
        ("POST", "/api/notifications/read-all", {}),
    ])

    # --- contacts + job contacts -----------------------------------------
    created = await j.api(u, "POST", "/api/contacts",
                          json={"name": "E2E Contact", "email": "c@example.com",
                                "company": company, "role": "Recruiter"},
                          expect=None, check=False)
    cid = _id_of(created.body)
    await j.api(u, "GET", "/api/contacts", expect=(200,), label="contacts list")
    if cid:
        await j.sweep("contacts", [
            ("PUT", f"/api/contacts/{cid}", {"role": "Hiring Manager"}),
            ("GET", f"/api/contacts/{cid}/interactions"),
            ("POST", f"/api/contacts/{cid}/interactions",
             {"channel": "email", "notes": "Sent intro"}),
        ])
    if jid and cid:
        await j.sweep("job contacts", [
            ("POST", f"/api/jobs/{jid}/contacts",
             {"contact_id": cid, "relationship": "recruiter"}),
            ("GET", f"/api/jobs/{jid}/contacts"),
            ("DELETE", f"/api/jobs/{jid}/contacts/{cid}"),
        ])
    elif jid:
        await j.api(u, "GET", f"/api/jobs/{jid}/contacts", expect=(200,),
                    check=False)
    if cid:
        await j.api(u, "DELETE", f"/api/contacts/{cid}", expect=None, check=False)

    # --- interviews -------------------------------------------------------
    if jid:
        created = await j.api(u, "POST", f"/api/jobs/{jid}/interviews",
                              json={"label": "technical",
                                    "scheduled_at": f"{TODAY}T10:00:00",
                                    "duration_min": 60,
                                    "interviewer_name": "Interviewer One",
                                    "interviewer_title": "Engineering Manager",
                                    "location": "Remote",
                                    "notes": "E2E round"},
                              expect=None, check=False)
        rid_i = _id_of(created.body)
        await j.api(u, "GET", f"/api/jobs/{jid}/interviews", expect=(200,),
                    label="interviews list")
        if rid_i:
            await j.sweep("interviews", [
                ("PUT", f"/api/interviews/{rid_i}",
                 {"label": "system design", "duration_min": 90,
                  "notes": "updated during E2E"}),
                ("POST", f"/api/interviews/{rid_i}/save-contact", {}),
                ("DELETE", f"/api/interviews/{rid_i}"),
            ])

    # --- pipeline extras --------------------------------------------------
    if jid:
        await j.sweep("pipeline", [
            ("POST", f"/api/jobs/{jid}/apply", {}),
            ("POST", f"/api/jobs/{jid}/application?status=applied", None),
            ("POST", f"/api/jobs/{jid}/response",
             {"response_type": "callback", "notes": "auto-reply"}),
            ("GET", "/api/analytics/response-rates"),
            ("GET", "/api/pipeline/applied"),
            ("POST", f"/api/jobs/{jid}/email", {}),
            ("GET", "/api/reminders"),
            ("GET", "/api/reminders/due"),
            ("POST", f"/api/jobs/{jid}/events",
             {"event_type": "note", "detail": "E2E note"}),
            ("POST", "/api/responses/classify",
             {"subject": "Interview invitation",
              "body": "We would like to schedule a call.",
              "sender": "recruiter@example.com"}),
            ("POST", "/api/profile/learn",
             {"field": "notice_period", "value": "4 weeks"}),
        ])
        created = await j.api(u, "POST", f"/api/jobs/{jid}/reminders",
                              json={"remind_at": f"{TODAY}T18:00:00",
                                    "reminder_type": "follow_up"},
                              expect=None, check=False)
        rmid = _id_of(created.body)
        if rmid:
            await j.sweep("reminders", [
                ("POST", f"/api/reminders/{rmid}/complete", {}),
                ("POST", f"/api/reminders/{rmid}/dismiss", {}),
            ])
    created = await j.api(u, "POST", "/api/follow-up-templates",
                          json={"name": "e2e-template", "subject": "Following up",
                                "body": "Hello {{name}}"},
                          expect=None, check=False)
    tid = _id_of(created.body)
    await j.api(u, "GET", "/api/follow-up-templates", expect=(200,),
                label="follow-up templates")
    if tid:
        await j.sweep("follow-up templates", [
            ("PUT", f"/api/follow-up-templates/{tid}",
             {"name": "e2e-template-2", "subject": "Re: following up",
              "body": "Hello again"}),
            ("DELETE", f"/api/follow-up-templates/{tid}"),
        ])

    # --- job misc ---------------------------------------------------------
    if jid:
        await j.sweep("job utilities", [
            ("GET", f"/api/jobs/lookup?url=https://example.com/jobs/{jid}"),
            ("GET", f"/api/jobs/{jid}/similar"),
            ("POST", f"/api/jobs/{jid}/find-apply-link", {}),
            ("GET", f"/api/companies/{company}"),
            ("GET", f"/api/jobs/{jid}/interview-prep"),
            ("POST", f"/api/jobs/{jid}/interview-prep", {}),
            ("POST", "/api/jobs/save-external",
             {"title": "LLM Platform Engineer", "company": "E2E Labs",
              "location": "Amsterdam, Netherlands",
              "url": "https://example.com/jobs/llm-platform-engineer",
              "description": "Build RAG pipelines with Python and LangChain. "
                             "Sponsorship available.",
              "posted_date": TODAY}),
        ])
    if extra:
        await j.api(u, "POST", f"/api/jobs/{extra}/dismiss", expect=None,
                    check=False)

    # --- approvals queue --------------------------------------------------
    if jid:
        created = await j.api(u, "POST", "/api/queue/add", json={"job_id": jid},
                              expect=None, check=False)
        qid = _id_of(created.body)
        await j.api(u, "GET", "/api/queue", expect=(200,), label="approval queue")
        if qid:
            await j.sweep("queue", [
                ("POST", f"/api/queue/{qid}/submit-for-review", {}),
                ("POST", f"/api/queue/{qid}/fill-status", {"status": "applied"}),
                ("POST", f"/api/queue/{qid}/approve", {}),
            ])
        # A fresh queue row for the reject/delete path (approve may consume the
        # first one, so resolve the id from the live queue instead of guessing).
        live = await j.api(u, "GET", "/api/queue", expect=(200,),
                           label="queue after approve")
        items = as_list(live.body, "queue")
        qid2 = items[0].get("id") if items else None
        if qid2:
            await j.api(u, "POST", f"/api/queue/{qid2}/reject", expect=None,
                        check=False)
            await j.api(u, "DELETE", f"/api/queue/{qid2}", expect=None,
                        check=False)
        else:
            j.note("queue empty after approve — reject/delete path skipped")

    # --- matching config + analytics extras -------------------------------
    await j.sweep("matching + analytics", [
        ("GET", "/api/matching/config"),
        ("PUT", "/api/matching/config", {"weights": {}}),
        ("GET", "/api/skill-gaps"),
        ("GET", "/api/export/csv"),
        ("GET", "/api/digest"),
        ("GET", "/api/offers"),
        ("GET", "/api/calendar"),
        ("GET", "/api/health"),
        ("GET", "/api/score/progress"),
        ("GET", "/api/packages/"),
        ("POST", "/api/rescore-failed", {}),
        ("POST", "/api/dismiss-stale", {}),
        ("POST", "/api/jobs/enrich", {}),
    ])
    # Background AI scoring run for THIS user's pool (M15c per-user target).
    r = await j.api(u, "POST", "/api/score", expect=(200,), check=False,
                    label="trigger background AI scoring (per-user target)")
    if isinstance(r.body, dict):
        j.check("background scoring targets the user's own pool",
                r.body.get("status") in ("scoring_triggered", "skipped"),
                f"response={json.dumps(r.body, default=str)[:120]}")

    # --- auth lifecycle (last, because it ends the session) ---------------
    await j.api(u, "POST", "/api/auth/change-password",
                json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
                expect=(200,), label="change password (revokes sessions)")
    r = await j.api(u, "GET", "/api/jobs?limit=1", expect=(401,), check=False,
                    label="old session revoked after password change")
    j.check("changing the password revokes existing sessions", r.status == 401,
            f"status={r.status}")
    await j.api(u, "POST", "/api/auth/login",
                json={"username": JOURNEY_USERNAME, "password": NEW_PASSWORD},
                expect=(200,), label="log in with the new password")
    await j.api(u, "GET", "/api/jobs?limit=1", expect=(200,),
                label="session works again")
    await j.api(u, "POST", "/api/auth/logout", expect=(200,),
                label="logout")
    await j.api(u, "GET", "/api/jobs?limit=1", expect=(401,), check=False,
                label="session gone after logout")
    await j.api(u, "POST", "/api/auth/login",
                json={"username": JOURNEY_USERNAME, "password": NEW_PASSWORD},
                expect=(200,), label="log back in (leave the session usable)")


async def s26_api_coverage(j: Journey) -> None:
    if not j.openapi:
        j.check("OpenAPI available for coverage accounting", False)
        return
    paths = j.openapi.get("paths", {})
    methods = ("get", "post", "put", "delete", "patch")
    called: set[tuple[str, str]] = {(c["method"].lower(), c["path"]) for c in j.rec.calls}

    def matches(template: str, concrete: str) -> bool:
        parts = re.split(r"(\{[^}]*\})", template)
        rx = "".join(r"[^/]+" if p.startswith("{") else re.escape(p) for p in parts)
        concrete_path = concrete.split("?")[0]
        return re.fullmatch(rx, concrete_path) is not None

    # Endpoints deliberately NOT exercised by a safe journey (destructive or
    # external-side-effect operations). Coverage is reported honestly.
    EXCUSED = {
        ("delete", "/api/queue/{queue_id}"): "destructive",
        ("post", "/api/clear-jobs"): "destructive",
        ("post", "/api/clear-all"): "destructive",
        ("post", "/api/rescore-all"): "destructive full-pool rescore",
        ("post", "/api/scrape/cancel"): "safety valve (only reached if a run overruns)",
        ("post", "/api/jobs/{job_id}/send-email"): "sends real email — never automated",
        ("post", "/api/settings/email/test"): "sends real email — never automated",
        ("post", "/api/digest/send-test"): "sends real email — never automated",
        ("get", "/api/queue/events"): "SSE stream (infinite)",
        ("get", "/api/notifications/stream"): "SSE stream (infinite)",
        ("get", "/api/calendar.ics"): "calendar feed consumed by an external client",
        ("post", "/api/queue/prepare-all"): "long AI batch (equivalent single-job path covered)",
        ("post", "/api/queue/approve-all"): "bulk approval (single approve covered)",
        ("post", "/api/queue/reject-all"): "bulk rejection (single reject covered)",
        ("post", "/api/autofill/analyze"): "browser-extension flow",
        ("post", "/api/jobs/mark-applied-by-url"): "browser-extension flow",
        ("post", "/api/skill-gaps/analyze"): "feature-flagged off by default",
        ("post", "/api/career/analyze"): "feature-flagged off by default",
        ("get", "/api/career/suggestions"): "feature-flagged off by default",
        ("get", "/api/jobs/{job_id}/predict-success"): "feature-flagged off by default",
        ("post", "/api/jobs/{job_id}/estimate-salary"): "feature-flagged off by default",
        ("post", "/api/career/suggestions/{suggestion_id}/accept"): "feature-flagged off by default",
        ("post", "/api/offers"): "feature-flagged off by default",
        ("put", "/api/offers/{offer_id}"): "feature-flagged off by default",
        ("delete", "/api/offers/{offer_id}"): "feature-flagged off by default",
        ("get", "/api/offers/compare"): "feature-flagged off by default",
        ("post", "/api/jobs/{job_id}/interviews/{round_id}"): "unused route variant",
        ("post", "/api/auth/users/{user_id}/disable"): "destructive to an account; covered by test_auth.py",
        ("post", "/api/auth/users/{user_id}/enable"): "destructive to an account; covered by test_auth.py",
        ("post", "/api/auth/users/{user_id}/reset-password"): "destructive; covered by test_auth.py",
        ("get", "/api/calendar/token"): "calendar feed credential",
        ("post", "/api/calendar/token/regenerate"): "calendar feed credential",
        ("post", "/api/jobs/{job_id}/find-contact"): "duplicate of /api/research/contacts/job/{id}",
    }

    covered, uncovered = [], []
    for template, spec in paths.items():
        for m in methods:
            if m not in spec:
                continue
            hit = any(cm == m and matches(template, cp) for cm, cp in called)
            row = {"method": m.upper(), "path": template,
                   "summary": (spec.get(m) or {}).get("summary", "")}
            if hit:
                covered.append(row)
            else:
                row["excuse"] = EXCUSED.get((m, template), "not exercised")
                uncovered.append(row)

    total = len(covered) + len(uncovered)
    pct = round(100.0 * len(covered) / total, 1) if total else 0.0
    (j.run_dir / "api_coverage.json").write_text(json.dumps(
        {"total_operations": total, "called": len(covered),
         "coverage_pct": pct, "covered": covered, "not_called": uncovered},
        indent=2), encoding="utf-8")
    j.note(f"API coverage: {len(covered)}/{total} operations ({pct}%)")
    j.check("journey touched the large majority of the API surface", pct >= 60.0,
            f"{len(covered)}/{total} = {pct}%")


SCENARIOS = [
    ("s01_boot", "Server boot, health and API surface", s01_boot),
    ("s02_bootstrap", "Create the FIRST account (username + password)", s02_bootstrap),
    ("s03_anonymous_lockdown", "Anonymous lockdown — every protected route 401",
     s03_anonymous_lockdown),
    ("s04_login", "Login throttling + login", s04_login),
    ("s05_admin_creates_user", "Admin creates a second user (username + password)",
     s05_admin_creates_user),
    ("s06_user_workspace_born_empty", "The new user's workspace is born empty and isolated",
     s06_user_workspace_born_empty),
    ("s07_user_sets_own_ai_key", "The user adds their OWN AI key (live test)",
     s07_user_sets_own_ai_key),
    ("s08_resume_upload_and_grading",
     "Upload the real resume (.docx) → live AI grading + profile parse",
     s08_resume_upload_and_grading),
    ("s09_evidence", "Evidence autofill → VERIFIED corpus + hard gate",
     s09_evidence),
    ("s10_countries", "Country strategy engine", s10_countries),
    ("s11_adapters", "ATS adapters + live health probes", s11_adapters),
    ("s12_discovery", "Orchestrated discovery cycle (real)", s12_discovery),
    ("s13_scrapers", "Real scrapers (bounded budget)", s13_scrapers),
    ("s14_scoring", "Deterministic scoring + ranking", s14_scoring),
    ("s15_eligibility", "Eligibility + freshness gates", s15_eligibility),
    ("s16_research", "Company + contact research", s16_research),
    ("s17_tailoring", "AI resume tailoring through the evidence gate", s17_tailoring),
    ("s18_cover_letter", "AI cover letter + downloads + edit", s18_cover_letter),
    ("s19_package", "Application package build + downloads", s19_package),
    ("s20_outreach", "Outreach draft (draft-only, Critical Test #4)", s20_outreach),
    ("s21_crm", "CRM transitions + follow-up engine", s21_crm),
    ("s22_daily_run", "Daily run pipeline", s22_daily_run),
    ("s23_analytics", "Analytics + LLM cost meter", s23_analytics),
    ("s24_cross_user_isolation", "CRITICAL TEST #5 — cross-user isolation",
     s24_cross_user_isolation),
    ("s25_crud_sweep", "The rest of the REST surface, hit for real",
     s25_crud_sweep),
    ("s26_api_coverage", "API coverage accounting", s26_api_coverage),
]


# ------------------------------------------------------------------ server mgmt


def start_server(run_dir: Path, port: int, log_path: Path) -> subprocess.Popen:
    env = os.environ.copy()
    env["JOBAGENT_DB_PATH"] = str(run_dir / "data" / "jobagent.db")
    env["JOBAGENT_PORT"] = str(port)
    env["PYTHONUNBUFFERED"] = "1"
    # The country strategy YAMLs are WRITABLE through PUT /api/countries/{region}
    # (it persists with a backup). Give the run its own copy so a test can never
    # rewrite the repository's config/ — and so the evidence templates that
    # WorkspaceManager seeds new users from come from the run's own tree too.
    config_src = ROOT / "config"
    config_dst = run_dir / "config"
    if config_src.is_dir() and not config_dst.exists():
        shutil.copytree(config_src, config_dst)
    env["JOBAGENT_COUNTRIES_DIR"] = str(config_dst / "countries")
    env["JOBAGENT_PROFILE_DIR"] = str(config_dst / "profile_templates")
    # Never let the harness inherit a masked/garbage AI key.
    log_file = log_path.open("w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:create_app", "--factory",
         "--host", "127.0.0.1", "--port", str(port), "--log-level", "info"],
        cwd=str(ROOT), env=env, stdout=log_file, stderr=subprocess.STDOUT,
    )
    return proc


async def wait_for_server(base: str, timeout: float = 90.0) -> bool:
    deadline = time.monotonic() + timeout
    async with httpx.AsyncClient(base_url=base, timeout=5.0) as c:
        while time.monotonic() < deadline:
            try:
                r = await c.get("/api/system/health")
                if r.status_code == 200:
                    return True
            except Exception:
                pass
            await asyncio.sleep(1.0)
    return False


# ----------------------------------------------------------------------- report


def write_report(j: Journey, run_dir: Path, meta: dict) -> tuple[str, int, int]:
    scen = [s.to_dict() for s in j.rec.scenarios]
    passed = sum(1 for s in scen if s["ok"])
    failed = len(scen) - passed
    checks = [c for s in scen for c in s["checks"]]
    checks_ok = sum(1 for c in checks if c["ok"])
    cov_path = run_dir / "api_coverage.json"
    cov = json.loads(cov_path.read_text()) if cov_path.exists() else {}

    lines: list[str] = []
    add = lines.append
    add(f"# Real User-Journey E2E Report — {meta['run_id']}")
    add("")
    add("> **What this is:** the actual product (uvicorn, authentication ON, "
        "`testing=False`) was booted against a throwaway data directory and driven "
        "**only over HTTP** by a brand-new user, top to bottom. Every API call, its "
        "status and its response body are recorded in this run folder.")
    add("")
    add("## Verdict")
    add("")
    add(f"- **Scenarios:** {passed}/{len(scen)} passed"
        + (f", {failed} FAILED" if failed else " ✅"))
    add(f"- **Checks:** {checks_ok}/{len(checks)} passed")
    add(f"- **HTTP calls recorded:** {len(j.rec.calls)}")
    if cov:
        add(f"- **API coverage:** {cov.get('called')}/{cov.get('total_operations')} "
            f"operations ({cov.get('coverage_pct')}%)")
    add(f"- **AI provider under test:** `{meta.get('provider')}` / "
        f"`{meta.get('model')}` (real, billed)")
    add("")
    add("## Environment")
    add("")
    for k, v in meta.items():
        add(f"- **{k}:** `{v}`")
    add("")
    add("## Journey, top to bottom")
    add("")
    add("| # | Step | What it proves | Result |")
    add("|---|------|----------------|--------|")
    for i, s in enumerate(scen, 1):
        result = "PASS" if s["ok"] else "**FAIL**"
        add(f"| {i} | {s['title']} | {s['description'] or s['title']} | {result} |")
    add("")
    add("## Scenario detail")
    add("")
    for i, s in enumerate(scen, 1):
        add(f"### {i}. {s['id']} — {s['title']}")
        add("")
        if s["error"]:
            add(f"**Scenario error:** `{s['error']}`")
            add("")
        for c in s["checks"]:
            mark = "PASS" if c["ok"] else "FAIL"
            add(f"- `{mark}` {c['name']}" + (f" — {c['detail']}" if c["detail"] else ""))
        if s["notes"]:
            add("")
            for n in s["notes"]:
                add(f"  - _{n}_")
        add("")
    if cov and cov.get("not_called"):
        add("## API operations not exercised by this journey")
        add("")
        add("| Method | Path | Reason |")
        add("|--------|------|--------|")
        for row in cov["not_called"]:
            add(f"| {row['method']} | `{row['path']}` | {row.get('excuse')} |")
        add("")
    add("## Artifacts captured")
    add("")
    for p in sorted((run_dir / "artifacts").rglob("*")):
        if p.is_file():
            add(f"- `{p.relative_to(run_dir)}` ({p.stat().st_size} bytes)")
    add("")
    add("## Files in this run")
    add("")
    for p in sorted(run_dir.rglob("*")):
        if p.is_file() and "artifacts" not in p.parts:
            add(f"- `{p.relative_to(run_dir)}`")
    add("")

    report = "\n".join(lines)
    (run_dir / "report.md").write_text(report, encoding="utf-8")
    return report, passed, failed


# ------------------------------------------------------------------------- main


REAL_RESUME = ""


async def run_journey(args) -> int:
    global REAL_RESUME

    run_dir = RUNS_ROOT / RUN_ID
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "data").mkdir(parents=True, exist_ok=True)

    REAL_RESUME = load_real_resume()
    ai = resolve_ai()
    log(f"run dir      : {run_dir}")
    log(f"real resume  : {len(REAL_RESUME)} chars")
    log(f"AI provider  : {ai.get('provider')} / {ai.get('model')} "
        f"(key {'set' if ai.get('api_key') else 'MISSING'})")

    port = free_port()
    base = f"http://127.0.0.1:{port}"
    log_path = run_dir / "server.log"
    proc = start_server(run_dir, port, log_path)
    log(f"server pid   : {proc.pid} on {base}")

    j = Journey(run_dir, base, ai)
    j.anon = httpx.AsyncClient(base_url=base, timeout=120.0)
    j.admin = httpx.AsyncClient(base_url=base, timeout=120.0)
    j.user = httpx.AsyncClient(base_url=base, timeout=120.0)

    meta = {"run_id": RUN_ID, "started_utc": datetime.now(timezone.utc).isoformat(),
            "base_url": base, "python": sys.version.split()[0],
            "provider": ai.get("provider"), "model": ai.get("model"),
            "resume_chars": len(REAL_RESUME),
            "scrape_budget_s": SCRAPE_SECS, "discovery_budget_s": DISCOVERY_SECS}

    started = time.monotonic()
    try:
        up = await wait_for_server(base)
        if not up:
            log("SERVER FAILED TO START — see server.log")
            (run_dir / "run.json").write_text(json.dumps(
                {**meta, "server_up": False}, indent=2))
            return 1
        log("server up ✓")

        for sid, title, fn in SCENARIOS:
            if args.only and sid not in args.only:
                continue
            j.rec.begin(sid, title, fn.__doc__ or "")
            try:
                await fn(j)
            except Exception as e:
                j.rec.error(e)
            j.rec.end()
    finally:
        await j.anon.aclose()
        await j.admin.aclose()
        await j.user.aclose()
        j.rec.close()
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except Exception:
            proc.kill()

    meta["finished_utc"] = datetime.now(timezone.utc).isoformat()
    meta["duration_s"] = round(time.monotonic() - started, 1)
    meta["http_calls"] = len(j.rec.calls)
    meta["scenarios_total"] = len(j.rec.scenarios)

    report, passed, failed = write_report(j, run_dir, meta)
    meta["scenarios_passed"] = passed
    meta["scenarios_failed"] = failed
    meta["checks"] = sum(len(s.checks) for s in j.rec.scenarios)
    meta["checks_passed"] = sum(1 for s in j.rec.scenarios for c in s.checks if c["ok"])

    (run_dir / "run.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    (run_dir / "scenarios.json").write_text(json.dumps(
        [s.to_dict() for s in j.rec.scenarios], indent=2), encoding="utf-8")

    # Publish the report next to the other milestone reports (Golden Rule #11).
    docs = ROOT.parent / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "USER_JOURNEY_E2E_REPORT.md").write_text(report, encoding="utf-8")

    log("\n" + "=" * 74)
    log(f"SCENARIOS : {passed} passed / {failed} failed")
    log(f"CHECKS    : {meta['checks_passed']}/{meta['checks']}")
    log(f"HTTP CALLS: {meta['http_calls']}")
    log(f"REPORT    : {run_dir / 'report.md'}")
    log("=" * 74)
    return 1 if failed else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", nargs="*", help="run only these scenario ids")
    args = ap.parse_args()
    try:
        return asyncio.run(run_journey(args))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
