"""Live-server verification of the DISCOVERY phase (:8085, 0.0.0.0).

Proves the discovery stage of the pipeline over REAL HTTP with a throwaway
user, on the real server, with the real 19 adapters and real job boards:

  1. login first (anonymous is 401)
  2. with NO resume, discovery is BLOCKED (428)
  3. the adapter registry exposes all 19 sources (ATS + keyed + country-scoped)
  4. per-source health probe: keyless sources reachable LIVE, keyed sources
     honest no-ops without keys
  5. country strategy: 10 countries known; apply() syncs allowed_regions
  6. resume upload (real AI) lifts the gate
  7. a BOUNDED discovery cycle (passes=2) ingests REAL jobs, records
     per-pass telemetry, and the region gate holds on every row

Run against the live server:
    cd job-search-system/root && setsid nohup .venv/bin/python -m uvicorn \
        app.main:create_app --factory --host 0.0.0.0 --port 8085 \
        > /tmp/jobagent_server.log 2>&1 &
    .venv/bin/python ../analysis/verify_discovery_live.py

NOTE: the resume upload runs the real AI (billed) — same cost as the
onboarding verification. The throwaway user + workspace are removed at the end.
"""
import asyncio
import os
import shutil
import sqlite3
import sys
import time
from pathlib import Path

import httpx

BASE = os.getenv("JOBAGENT_BASE_URL", "http://127.0.0.1:8085")
ROOT = Path(__file__).resolve().parents[1] / "root"
DATA = ROOT / "data"
USERS_DIR = DATA / "users"
DEMO_USER = "discoverydemo"
DEMO_PASS = "discovery-pass-123"
PASSES = int(os.getenv("DISCOVERY_PASSES", "2"))
POLL_TIMEOUT_S = int(os.getenv("DISCOVERY_POLL_SECS", "300"))

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"   <- {detail}" if detail else ""))


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


def copy_admin_ai_settings(dst_db_path: Path):
    """Give the throwaway user the admin's AI provider so upload analysis runs."""
    src_db = DATA / "users"
    admin_dbs = sorted(src_db.glob("*/jobagent.db"))
    src = None
    for db in admin_dbs:
        try:
            con = sqlite3.connect(db)
            if con.execute("select 1 from ai_settings limit 1").fetchone():
                src = con
                break
            con.close()
        except sqlite3.Error:
            continue
    if src is None:
        return None
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
    print(f"LIVE SERVER {BASE}  —  DISCOVERY PHASE VERIFICATION (passes={PASSES})")
    print("=" * 78)

    user_id, existed = await ensure_demo_user()
    ws = USERS_DIR / f"{user_id}-{DEMO_USER}"
    print(f"\n[setup] throwaway user '{DEMO_USER}' (id={user_id}); existed={existed}\n")

    async with httpx.AsyncClient(base_url=BASE, timeout=240.0) as c:
        # ---------------- anonymous: login first --------------------------
        r = await c.get("/api/jobs")
        check("anonymous access to jobs is blocked (401)", r.status_code == 401,
              f"HTTP {r.status_code}")

        # ---------------- login -------------------------------------------
        r = await c.post("/api/auth/login",
                         json={"username": DEMO_USER, "password": DEMO_PASS})
        check("POST /api/auth/login succeeds", r.status_code == 200,
              f"HTTP {r.status_code}")
        me = (await c.get("/api/auth/me")).json()["user"]
        check("session identifies the throwaway user", me["username"] == DEMO_USER, str(me))
        await c.get("/api/profile")
        check("workspace created on first authenticated request", ws.is_dir(), str(ws))
        provider = copy_admin_ai_settings(ws / "jobagent.db")
        print(f"        (AI provider for this user: {provider})")

        # ---------------- GATE: no resume => discovery blocked ------------
        r = await c.post("/api/discovery/run?passes=1")
        check("discovery is BLOCKED without a resume (428)", r.status_code == 428,
              f"HTTP {r.status_code} {r.text[:120]}")

        # ---------------- adapter registry ---------------------------------
        print("\n--- adapter registry (19 sources) ---")
        r = await c.get("/api/discovery/adapters")
        check("GET /api/discovery/adapters works", r.status_code == 200, f"HTTP {r.status_code}")
        adapters = r.json().get("adapters") or r.json().get("sources") or []
        names = {a if isinstance(a, str) else (a.get("source") or a.get("name"))
                 for a in adapters}
        expected = {"greenhouse", "lever", "ashby", "smartrecruiters",
                    "jooble", "adzuna", "reed",
                    "arbeitnow", "remotive", "jobicy", "weworkremotely", "remoteok",
                    "himalayas", "4dayweek", "landingjobs", "recruitee",
                    "mycareersfuture", "wellfound", "workingnomads"}
        check("all 19 expected sources are registered", expected <= names,
              f"missing={expected - names}" if not expected <= names else f"{len(names)} sources")
        keyed = {"jooble", "adzuna", "reed"}
        check("keyed adapters (jooble/adzuna/reed) are in the registry", keyed <= names,
              f"keyed present: {sorted(keyed & names)}")

        # ---------------- per-source live health probe ----------------------
        print("\n--- per-source health probes (LIVE) ---")
        r = await c.get("/api/discovery/health")
        sources = (r.json() or {}).get("sources", [])
        ok_sources = [s["source"] for s in sources if s.get("ok")]
        down = [s for s in sources if not s.get("ok")]
        check("health probe returns every registered source",
              {s.get("source") for s in sources} == names, f"{len(sources)} probed")
        check("at least 8 keyless sources are reachable LIVE", len(ok_sources) >= 8,
              f"ok={ok_sources}")
        keyed_down = {s["source"] for s in down} & keyed
        check("keyed sources are honest no-ops without keys (not crashes)",
              all("key" in (s.get("error") or "").lower() for s in down if s["source"] in keyed)
              or not keyed_down,
              f"keyed errors: {[(s['source'], (s.get('error') or '')[:60]) for s in down if s['source'] in keyed]}")

        # ---------------- country strategy ----------------------------------
        print("\n--- countries ---")
        r = await c.get("/api/countries")
        countries = (r.json() or {}).get("countries", [])
        codes = {x.get("code") for x in countries}
        check("10 countries are known (6 seeds + IN/CA/AU/PL)",
              {"DE", "NL", "IE", "GB", "SG", "AE", "IN", "CA", "AU", "PL"} <= codes,
              f"codes={sorted(codes)}")
        r = await c.post("/api/countries/apply")
        check("POST /api/countries/apply syncs the user's strategy", r.status_code == 200,
              f"HTTP {r.status_code} {str(r.json())[:140]}")

        # ---------------- upload resume (real AI) → gate lifts --------------
        print("\n--- resume upload (real AI extraction) ---")
        r = await c.post("/api/resume/upload",
                         files={"file": ("priya_nair_resume.txt",
                                         RESUME_TEXT.encode(), "text/plain")})
        check("POST /api/resume/upload succeeds (AI extraction ran)",
              r.status_code == 200, f"HTTP {r.status_code} {r.text[:140]}")
        terms = (r.json() or {}).get("search_terms") or []
        check("AI extracted search terms from the resume", bool(terms),
              f"{len(terms)}: {terms[:6]}")

        # ---------------- BOUNDED discovery cycle ---------------------------
        print(f"\n--- discovery cycle (passes={PASSES}, real boards) ---")
        r = await c.post(f"/api/discovery/run?passes={PASSES}")
        check("POST /api/discovery/run starts (200)", r.status_code == 200,
              f"HTTP {r.status_code} {r.text[:140]}")
        started_countries = (r.json() or {}).get("countries") or []
        check("run reports the enabled countries it will search",
              len(started_countries) >= 6, f"countries={started_countries}")

        t0 = time.monotonic()
        status = {}
        while time.monotonic() - t0 < POLL_TIMEOUT_S:
            await asyncio.sleep(3)
            status = (await c.get("/api/discovery/status")).json()
            if not status.get("running"):
                break
        check("discovery cycle finished within the poll budget",
              status.get("running") is False, f"waited {round(time.monotonic()-t0,1)}s")

        tel = status.get("last_telemetry") or {}
        passes = tel.get("passes") or []
        new_jobs = tel.get("new_jobs", 0)
        dupes = tel.get("duplicates_seen", 0)
        check("telemetry records per-pass stop reasons",
              bool(passes) and all(p.get("stop_reason") for p in passes),
              f"passes={[(p.get('source') or p.get('adapter'), p.get('stop_reason')) for p in passes][:4]}")
        check("the cycle ingested REAL jobs from live boards", new_jobs > 0,
              f"new_jobs={new_jobs} duplicates_seen={dupes} duration={tel.get('duration_s')}s")

        # ---------------- region gate + attribution audit -------------------
        print("\n--- pool audit ---")
        r = await c.get("/api/jobs?limit=500")
        jobs = (r.json() or {}).get("jobs") or []
        check("the user's pool grew with the ingested jobs", len(jobs) >= new_jobs,
              f"pool={len(jobs)}")
        allowed = {"Germany", "Netherlands", "Ireland", "UK", "Singapore", "UAE",
                   "India", "Canada", "Australia", "Poland", "Remote", "Unknown"}
        bad = [j for j in jobs
               if (j.get("location_region") or "Unknown") not in allowed]
        check("region gate holds: every job classifies inside the strategy",
              not bad, f"violations={[(j.get('title'), j.get('location_region')) for j in bad[:3]]}")
        unattributed = [j for j in jobs if not j.get("source")]
        check("source attribution on every ingested row", not unattributed,
              f"missing source: {[j.get('title') for j in unattributed[:3]]}")

    # ---------------- cleanup ---------------------------------------------
    print("\n--- cleanup: removing the throwaway user ---")
    removed_dir = False
    if ws.is_dir():
        shutil.rmtree(ws, ignore_errors=True)
        removed_dir = True
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
