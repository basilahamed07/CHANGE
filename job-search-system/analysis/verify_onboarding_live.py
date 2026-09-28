"""Live-server verification of the login-first setup flow (runs against :8085).

Mirrors exactly what the browser does:
  - an anonymous visit must get the LOGIN screen, never the resume wizard
  - after login the user completes the 4 setup stages
  - stage 2 (resume upload) must really run the AI and write the YAML evidence

Creates a throwaway user, then removes it again.
"""
import asyncio
import json
import os
import shutil
import sqlite3
import sys

import httpx

BASE = "http://127.0.0.1:8085"
ROOT = "/home/ubuntu/personal_project/CHANGE/job-search-system/root"
DATA = os.path.join(ROOT, "data")
USERS_DIR = os.path.join(DATA, "users")
DEMO_USER = "flowdemo"
DEMO_PASS = "flowdemo-pass-123"

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"   <- {detail}" if detail else ""))


def demo_workspace_dir(user_id):
    return os.path.join(USERS_DIR, f"{user_id}-{DEMO_USER}")


async def ensure_demo_user():
    sys.path.insert(0, ROOT)
    from app.auth import SystemStore

    store = SystemStore(os.path.join(DATA, "system.db"))
    await store.init()
    users = await store.list_users()
    for u in users:
        if u["username"] == DEMO_USER:
            return u["id"], True
    created = await store.create_user(DEMO_USER, DEMO_PASS, role="user")
    return created["id"], False


def copy_admin_ai_settings(dst_db_path):
    """Point the throwaway user at the same provider/key the admin already uses,
    so the resume analysis runs for real instead of landing on an empty key."""
    src = sqlite3.connect(os.path.join(USERS_DIR, "1-basil", "jobagent.db"))
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


def admin_resume_text():
    """The admin's real stored resume — used as the uploaded document."""
    src = sqlite3.connect(os.path.join(USERS_DIR, "1-basil", "jobagent.db"))
    text = src.execute("select resume_text from resumes limit 1").fetchone()[0]
    src.close()
    return text


async def main():
    print("=" * 78)
    print("LIVE SERVER", BASE)
    print("=" * 78)

    user_id, existed = await ensure_demo_user()
    print(f"\n[setup] throwaway user '{DEMO_USER}' (id={user_id}); existed={existed}\n")

    async with httpx.AsyncClient(base_url=BASE, timeout=180.0) as c:
        # ---------------- anonymous: login must come first ----------------
        print("--- anonymous visitor ---")
        r = await c.get("/")
        check("GET / serves the app shell", r.status_code == 200, f"HTTP {r.status_code}")

        r = await c.get("/static/js/app.js")
        check("served app.js contains the fix (setup runs post-auth)",
              "maybeShowSetupUI" in r.text and "await maybeShowSetupUI()" in r.text)

        r = await c.get("/api/auth/status")
        st = r.json()
        check("anonymous session is not authenticated",
              st.get("authenticated") is False, json.dumps(st))

        # These are exactly what the wizard's calls resolve to before login.
        for path in ("/api/profile", "/api/resumes", "/api/ai-settings"):
            r = await c.get(path)
            check(f"anonymous {path} is blocked (401)", r.status_code == 401,
                  f"HTTP {r.status_code}")

        # If the wizard had opened here, the user would see a dead upload box.
        r = await c.post("/api/resume/upload",
                         files={"file": ("x.txt", b"hello", "text/plain")})
        check("anonymous resume upload is refused (401)", r.status_code == 401,
              f"HTTP {r.status_code}")

        # ---------------- stage 1: login ----------------
        print("\n--- STAGE 1: login ---")
        r = await c.post("/api/auth/login",
                         json={"username": DEMO_USER, "password": DEMO_PASS})
        check("POST /api/auth/login succeeds", r.status_code == 200, f"HTTP {r.status_code}")
        r = await c.get("/api/auth/me")
        me = r.json()["user"]
        check("session identifies the demo user",
              me["username"] == DEMO_USER and me["role"] == "user",
              json.dumps(me))

        r = await c.get("/api/profile")
        check("workspace is created on the first authenticated request",
              r.status_code == 200, f"HTTP {r.status_code}")
        ws = demo_workspace_dir(user_id)
        check("per-user workspace exists on disk", os.path.isdir(ws), ws)
        yaml_before = sorted(f for f in os.listdir(os.path.join(ws, "profile"))
                             if f.endswith(".yaml"))
        check("user starts with the 8 pristine evidence templates",
              len(yaml_before) == 8, f"{len(yaml_before)} files")

        provider = copy_admin_ai_settings(os.path.join(ws, "jobagent.db"))
        print(f"        (AI provider for this user: {provider})")

        # ---------------- stage 2: profile ----------------
        print("\n--- STAGE 2: profile (wizard step 1) ---")
        r = await c.post("/api/profile", json={
            "full_name": "Flow Demo", "email": "flow.demo@example.com",
            "location": "Berlin, Germany"})
        check("POST /api/profile saves", r.status_code == 200, f"HTTP {r.status_code}")

        # ---------------- stage 3: resume upload = AI analyse + extract ------
        print("\n--- STAGE 3: resume upload (wizard step 2) ---")
        text = admin_resume_text()
        r = await c.post("/api/resume/upload",
                         files={"file": ("flow_demo_resume.txt",
                                         text.encode(), "text/plain")})
        check("POST /api/resume/upload succeeds", r.status_code == 200,
              f"HTTP {r.status_code}")
        body = r.json()

        terms = body.get("search_terms") or []
        skills = body.get("key_skills") or []
        titles = body.get("job_titles") or []
        check("AI returned search terms", bool(terms), f"{len(terms)}: {terms[:6]}")
        check("AI returned key skills", bool(skills), f"{len(skills)}: {skills[:8]}")
        check("AI returned job titles", bool(titles), f"{len(titles)}")
        check("AI returned a seniority + ATS grade",
              bool(body.get("seniority")) and body.get("ats_score", 0) > 0,
              f"seniority={body.get('seniority')!r} ats={body.get('ats_score')}")

        autofill = body.get("evidence_autofill") or {}
        check("evidence autofill reported per category", bool(autofill),
              json.dumps(autofill))

        # settings really were updated (this is what discovery/matching use)
        cfg = (await c.get("/api/search-config")).json()
        check("search config now carries the extracted skills",
              bool(cfg.get("key_skills")), f"{len(cfg.get('key_skills') or [])} skills")
        check("search config carries the ATS score", cfg.get("ats_score", 0) > 0,
              str(cfg.get("ats_score")))

        # evidence really became VERIFIED, sourced to the resume
        ev = (await c.get("/api/evidence")).json()
        verified = [x for x in ev["claims"] if x["status"] == "VERIFIED"]
        from_resume = [x for x in verified
                       if "uploaded resume" in (x.get("source") or "")]
        check("claims became VERIFIED evidence", bool(verified), f"{len(verified)} verified")
        check("verified claims cite the uploaded resume", bool(from_resume),
              f"{len(from_resume)} claims")
        check("DO_NOT_USE / DISPUTED claims were not touched",
              all(x["status"] in ("VERIFIED", "UNVERIFIED", "DO_NOT_USE", "DISPUTED")
                  for x in ev["claims"]))

        # and the YAML files on disk were rewritten (with a .bak backup)
        prof = os.path.join(ws, "profile")
        skills_yaml = open(os.path.join(prof, "skills.yaml")).read()
        check("skills.yaml on disk now contains VERIFIED",
              "VERIFIED" in skills_yaml)
        check("skills.yaml cites the uploaded resume",
              "uploaded resume" in skills_yaml)
        check("a .bak backup was written before the rewrite",
              os.path.exists(os.path.join(prof, "skills.yaml.bak")))
        changed = [f for f in os.listdir(prof)
                   if f.endswith(".yaml") and "VERIFIED" in open(os.path.join(prof, f)).read()]
        check("the resume filled in more than one evidence category",
              len(changed) >= 2, f"{sorted(changed)}")

        # ---------------- stage 4: AI provider + done ----------------
        print("\n--- STAGE 4: AI provider (wizard step 3) + setup complete ---")
        r = await c.get("/api/ai-settings")
        ai = r.json()
        check("GET /api/ai-settings returns the provider", bool(ai.get("provider")),
              f"provider={ai.get('provider')} key_set={bool(ai.get('api_key'))}")
        r = await c.post("/api/ai-settings", json={"provider": ai.get("provider"),
                                                   "model": ai.get("model")})
        check("POST /api/ai-settings saves", r.status_code == 200, f"HTTP {r.status_code}")

        # the checklist the UI computes (profile complete + resume + ai) is now 3/3
        prof_ok = bool((await c.get("/api/profile")).json().get("full_name"))
        res_ok = bool(((await c.get("/api/resumes")).json().get("resumes") or []))
        check("setup checklist completes: profile + resume + AI all present",
              prof_ok and res_ok and bool(ai.get("provider")),
              f"profile={prof_ok} resume={res_ok} ai={bool(ai.get('provider'))}")

        # ---------------- isolation sanity ----------------
        r = await c.get("/api/jobs")
        check("the new user has their own (empty) job pool",
              r.status_code == 200 and (r.json().get("jobs") or []) == [],
              f"HTTP {r.status_code}, jobs={len(r.json().get('jobs') or [])}")

    # ---------------- cleanup ----------------
    print("\n--- cleanup: removing the throwaway user ---")
    removed_dir = False
    ws = demo_workspace_dir(user_id)
    if os.path.isdir(ws):
        shutil.rmtree(ws)
        removed_dir = True

    from app.auth import SystemStore
    store = SystemStore(os.path.join(DATA, "system.db"))
    await store.init()
    db = sqlite3.connect(os.path.join(DATA, "system.db"))
    db.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
    db.execute("DELETE FROM users WHERE id=?", (user_id,))
    db.commit()
    remaining = [r[0] for r in db.execute("select username from users")]
    db.close()
    check("throwaway user + workspace removed",
          removed_dir and DEMO_USER not in remaining,
          f"remaining users: {remaining}")

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print("\n" + "=" * 78)
    print(f"RESULT: {passed}/{len(RESULTS)} checks passed, "
          f"{len(RESULTS) - passed} failed")
    print("=" * 78)
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
