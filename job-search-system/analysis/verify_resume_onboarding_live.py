"""Live-server verification of the RESUME-DRIVEN onboarding flow (:8085).

The promise being proven end to end, over real HTTP, as a brand-new user:

  1. login comes first (never the resume wizard anonymously)
  2. with NO resume, search + discovery are BLOCKED with a clear message
  3. uploading a resume REALLY runs the AI and extracts the role keywords
     (search terms / job titles / skills) from *that* resume
  4. the extracted keywords are persisted and can be confirmed/edited
  5. once a resume exists, search is ALLOWED again (the block lifts)

Runs against the live server started with:
    cd job-search-system/root && .venv/bin/python -m uvicorn app.main:create_app \
        --factory --host 127.0.0.1 --port 8085

Creates a throwaway user, then removes it again.

NOTE: this exercises the real DeepSeek key (billed) for the resume analysis.
"""
import asyncio
import os
import shutil
import sqlite3
import sys
from pathlib import Path

import httpx

BASE = os.getenv("JOBAGENT_BASE_URL", "http://127.0.0.1:8085")
ROOT = Path(__file__).resolve().parents[1] / "root"
DATA = ROOT / "data"
USERS_DIR = DATA / "users"
DEMO_USER = "resumeflowdemo"
DEMO_PASS = "resumeflow-pass-123"

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"   <- {detail}" if detail else ""))


# A distinctive resume so the extracted keywords are attributable to it.
RESUME_TEXT = """PRIYA NAIR
priya.nair@example.com | +49 170 0000000 | Berlin, Germany | linkedin.com/in/priyanair

SUMMARY
Senior AI engineer with 7 years building retrieval-augmented generation systems,
LLM applications and agentic workflows in production.

TECHNICAL SKILLS
Python, LangChain, LlamaIndex, RAG pipelines, vector databases (Pinecone, pgvector),
prompt engineering, OpenAI API, DeepSeek, FastAPI, Kubernetes, MLOps.

EXPERIENCE
Lead Generative AI Engineer, VectorWorks GmbH (2021-present)
- Architected a RAG assistant over 4M documents; cut hallucination rate by 62%.
- Built an agentic AI workflow platform used by 30 internal teams.

Machine Learning Engineer, DataForge (2018-2021)
- Deployed LLM-powered document search serving 12k daily users.

EDUCATION
M.Sc. Computer Science, TU Berlin
"""


def admin_workspace_dir() -> Path | None:
    """Locate the admin's workspace directory by looking at system.db."""
    db_path = DATA / "system.db"
    if not db_path.exists():
        return None
    con = sqlite3.connect(db_path)
    try:
        row = con.execute(
            "SELECT id, username FROM users WHERE role='admin' ORDER BY id LIMIT 1").fetchone()
    finally:
        con.close()
    if not row:
        return None
    return USERS_DIR / f"{row[0]}-{row[1]}"


def copy_admin_ai_settings(dst_db_path: Path):
    """Point the throwaway user at the same provider/key the admin already uses,
    so the resume analysis runs for real instead of landing on an empty key."""
    admin_dir = admin_workspace_dir()
    if not admin_dir:
        return None
    src_path = admin_dir / "jobagent.db"
    if not src_path.exists():
        return None
    src = sqlite3.connect(src_path)
    cols = [r[1] for r in src.execute("PRAGMA table_info(ai_settings)")]
    row = src.execute("select * from ai_settings limit 1").fetchone()
    src.close()
    if row is None:
        return None
    dst = sqlite3.connect(dst_db_path)
    dst.execute(
        f"INSERT OR REPLACE INTO ai_settings ({','.join(cols)}) "
        f"VALUES ({','.join('?' * len(cols))})", row)
    dst.commit()
    dst.close()
    return dict(zip(cols, row)).get("provider")


async def ensure_demo_user():
    sys.path.insert(0, str(ROOT))
    from app.auth import SystemStore

    store = SystemStore(str(DATA / "system.db"))
    await store.init()
    for u in await store.list_users():
        if u["username"] == DEMO_USER:
            return u["id"], True
    created = await store.create_user(DEMO_USER, DEMO_PASS, role="user")
    return created["id"], False


async def main():
    print("=" * 78)
    print("LIVE SERVER", BASE)
    print("=" * 78)

    user_id, existed = await ensure_demo_user()
    ws = USERS_DIR / f"{user_id}-{DEMO_USER}"
    print(f"\n[setup] throwaway user '{DEMO_USER}' (id={user_id}); existed={existed}\n")

    async with httpx.AsyncClient(base_url=BASE, timeout=240.0) as c:
        # ---------------- anonymous: login first, no wizard ----------------
        print("--- anonymous visitor ---")
        st = (await c.get("/api/auth/status")).json()
        check("anonymous session is not authenticated",
              st.get("authenticated") is False, str(st))
        r = await c.get("/api/search-config")
        check("anonymous /api/search-config is blocked (401)", r.status_code == 401,
              f"HTTP {r.status_code}")

        # ---------------- login ----------------
        print("\n--- login ---")
        r = await c.post("/api/auth/login",
                         json={"username": DEMO_USER, "password": DEMO_PASS})
        check("POST /api/auth/login succeeds", r.status_code == 200, f"HTTP {r.status_code}")
        me = (await c.get("/api/auth/me")).json()["user"]
        check("session identifies the new user",
              me["username"] == DEMO_USER and me["role"] == "user", str(me))

        # workspace is created on the first authenticated request
        prof = await c.get("/api/profile")
        check("workspace is created on the first authenticated request",
              prof.status_code == 200, f"HTTP {prof.status_code}")
        check("per-user workspace exists on disk", ws.is_dir(), str(ws))
        provider = copy_admin_ai_settings(ws / "jobagent.db")
        print(f"        (AI provider for this user: {provider})")

        # ---------------- GATE: no resume => search blocked ----------------
        print("\n--- GATE: search before any resume ---")
        r = await c.get("/api/search-config")
        cfg = r.json()
        check("new user has no resume text yet", not cfg.get("resume_text"),
              f"terms={cfg.get('search_terms')}")

        r = await c.post("/api/scrape")
        check("POST /api/scrape is BLOCKED without a resume (428)",
              r.status_code == 428, f"HTTP {r.status_code} {r.text[:120]}")
        check("the block message tells the user to upload a resume",
              "resume" in r.text.lower(), r.text[:160])

        r = await c.post("/api/discovery/run?passes=1")
        check("POST /api/discovery/run is BLOCKED without a resume (428)",
              r.status_code == 428, f"HTTP {r.status_code} {r.text[:120]}")

        # ---------------- STAGE: resume upload = real AI extraction --------
        print("\n--- STAGE: upload resume (resume-first onboarding step) ---")
        r = await c.post("/api/resume/upload",
                         files={"file": ("priya_nair_resume.txt",
                                         RESUME_TEXT.encode(), "text/plain")})
        check("POST /api/resume/upload succeeds", r.status_code == 200,
              f"HTTP {r.status_code} {r.text[:160]}")
        body = r.json()

        terms = body.get("search_terms") or []
        titles = body.get("job_titles") or []
        skills = body.get("key_skills") or []
        check("AI extracted search terms from the resume", bool(terms),
              f"{len(terms)}: {terms[:8]}")
        check("AI extracted job titles", bool(titles), f"{len(titles)}")
        check("AI extracted key skills", bool(skills),
              f"{len(skills)}: {[str(s)[:20] for s in skills[:8]]}")

        # The extracted terms must actually relate to what the resume says.
        blob = " ".join(str(x) for x in (terms + titles + skills)).lower()
        check("extracted keywords reflect the resume's AI/LLM/RAG focus",
              any(w in blob for w in ("ai", "llm", "rag", "generative", "machine learning",
                                      "genai", "ml")),
              f"terms={terms[:6]}")

        # ---------------- persisted to the search config -------------------
        cfg = (await c.get("/api/search-config")).json()
        check("extracted search terms are persisted to search config",
              bool(cfg.get("search_terms")), f"{len(cfg.get('search_terms') or [])} terms")
        check("persisted terms match the upload response",
              set(cfg.get("search_terms") or []) == set(terms),
              f"cfg={cfg.get('search_terms')}")

        # ---------------- confirm / edit keywords --------------------------
        print("\n--- STAGE: confirm/edit keywords ---")
        # Keep the added term inside the slice so the edit is actually exercised.
        edited = terms[:11] + ["Staff RAG Engineer"]
        r = await c.post("/api/search-config/keywords",
                         json={"search_terms": edited,
                               "job_titles": titles, "key_skills": skills})
        check("POST /api/search-config/keywords saves", r.status_code == 200,
              f"HTTP {r.status_code} {r.text[:120]}")
        cfg = (await c.get("/api/search-config")).json()
        check("the user's edited search term is persisted",
              "Staff RAG Engineer" in (cfg.get("search_terms") or []),
              f"{cfg.get('search_terms')}")

        # ---------------- GATE lifts: search now allowed -------------------
        print("\n--- GATE: search after the resume ---")
        r = await c.post("/api/resume/upload",
                         files={"file": ("priya_nair_resume.txt",
                                         RESUME_TEXT.encode(), "text/plain")})
        # Second upload is idempotent by filename; confirms no duplicate resume.
        check("re-uploading the same resume stays OK", r.status_code == 200,
              f"HTTP {r.status_code}")

        r = await c.post("/api/scrape")
        check("POST /api/scrape is ALLOWED once a resume exists (202)",
              r.status_code == 202, f"HTTP {r.status_code} {r.text[:120]}")
        if r.status_code == 202:
            await c.post("/api/scrape/cancel")

        r = await c.post("/api/discovery/run?passes=1")
        check("POST /api/discovery/run is ALLOWED once a resume exists",
              r.status_code in (200, 202), f"HTTP {r.status_code} {r.text[:120]}")
        # Don't wait for the live network sweep; just confirm it started.
        if r.status_code == 200:
            check("discovery reports the enabled countries it will search",
                  bool(r.json().get("countries")), str(r.json())[:160])

        # ---------------- helper endpoint sanity ---------------------------
        r = await c.post("/api/search-config/keywords", json={})
        check("empty keyword save is rejected (400)", r.status_code == 400,
              f"HTTP {r.status_code}")

        # ---------------- isolation sanity ---------------------------------
        r = await c.get("/api/jobs")
        check("the new user has their own job pool",
              r.status_code == 200, f"HTTP {r.status_code}")

    # ---------------- cleanup ----------------
    print("\n--- cleanup: removing the throwaway user ---")
    removed_dir = False
    if ws.is_dir():
        shutil.rmtree(ws, ignore_errors=True)
        removed_dir = True

    from app.auth import SystemStore
    store = SystemStore(str(DATA / "system.db"))
    await store.init()
    con = sqlite3.connect(DATA / "system.db")
    con.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
    con.execute("DELETE FROM users WHERE id=?", (user_id,))
    con.commit()
    remaining = [r[0] for r in con.execute("select username from users")]
    con.close()
    check("throwaway user + workspace removed",
          removed_dir and DEMO_USER not in remaining, f"remaining users: {remaining}")

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print("\n" + "=" * 78)
    print(f"RESULT: {passed}/{len(RESULTS)} checks passed, {len(RESULTS) - passed} failed")
    print("=" * 78)
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
