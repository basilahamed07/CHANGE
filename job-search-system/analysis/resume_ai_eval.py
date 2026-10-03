#!/usr/bin/env python
"""Phase-0 — one-off AI evaluation of Basil's resume. EXACTLY 3 AI calls, then stops.

Run from the app root (relative config paths depend on it):

    cd job-search-system/root
    .venv/bin/python ../analysis/resume_ai_eval.py

Design notes:
- Reads the resume from a COPY of the workspace DB, never the live file, so the
  running app is never locked or mutated. `data/` stays private.
- The AI client is wrapped in a hard call budget: a 4th call RAISES rather than
  silently spending money. This is the "2 or 3 only" constraint, enforced in code.
- Never prints resume text. Writes results to data/resume_ai_eval.json (private,
  gitignored) and prints a summary.
- Exit 0 = all three calls succeeded; exit 1 = a call failed; exit 2 = not configured.

Prerequisite: JOBAGENT_DEEPSEEK_API_KEY must be set in root/.env (or the env).
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

# --- paths ------------------------------------------------------------------
# analysis/ sits next to root/. Resolve everything from this file's location so
# the script works no matter which directory it is launched from — then chdir
# into the app root, because app.config reads .env relative to the CWD.
ROOT_DIR = Path(__file__).resolve().parents[1]           # job-search-system/
APP_ROOT = ROOT_DIR / "root"                             # job-search-system/root
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))
os.chdir(APP_ROOT)

MAX_AI_CALLS = 3

# Canonical target roles (PROJECT_MEMORY.md §1).
TARGET_ROLES = [
    "AI Engineer",
    "Generative AI Engineer",
    "AI Application Developer",
    "Python AI Developer",
    "LLM Engineer",
    "RAG Engineer",
    "Agentic AI Engineer",
    "Backend/AI Engineer",
]

CRITIQUE_PROMPT = """You are a senior technical recruiter who has screened 10,000+ AI/backend resumes.
Review this resume honestly and critically. Do not be polite — be useful.

RESUME:
{resume}

Return ONLY valid JSON with this exact structure:
{{
    "overall_verdict": "2-3 sentences, blunt",
    "strengths": ["specific strength with the evidence from the resume", "..."],
    "weaknesses": [
        {{"issue": "...", "evidence": "what in the resume shows this", "fix": "concrete action"}}
    ],
    "missing_for_target_roles": ["thing that is absent and expected for AI/LLM roles"],
    "top_rewrites": [
        {{"before": "a weak line pattern (paraphrase, do not copy verbatim)", "after": "a stronger version", "why": "..."}}
    ]
}}

Guidelines:
- Ground EVERY weakness in something actually present or absent in the resume. Never invent experience.
- Focus on what matters for AI Engineer / LLM / RAG / Agentic AI roles.
- top_rewrites: 5 items, the highest-leverage edits.
"""

ROLE_FIT_PROMPT = """You are assessing role fit for one candidate against specific target roles.

RESUME:
{resume}

TARGET ROLES:
{roles}

For EACH target role, rate how well this candidate fits, using only what the resume shows.
Return ONLY valid JSON:
{{
    "roles": [
        {{"role": "...", "fit_score": 85, "matched_evidence": ["..."], "gaps": ["..."], "verdict": "one line"}}
    ],
    "best_role": "...",
    "recommended_primary_search_term": "the single best job-board search string",
    "roles_to_deprioritise": ["..."]
}}

Guidelines:
- fit_score 0-100. Be calibrated: 90+ means they would likely pass a screen today.
- matched_evidence must cite real content from the resume. Do not credit skills that are absent.
- Order the roles array by fit_score descending.
"""


class CallBudget:
    """Thin proxy over AIClient that refuses to exceed a hard call limit.

    Raises rather than silently making the extra call — the whole point of the
    budget is that it cannot be exceeded by accident.
    """

    def __init__(self, client, limit: int = MAX_AI_CALLS):
        self._client = client
        self._limit = limit
        self.count = 0
        self.log: list[dict] = []

    async def chat(self, prompt: str, **kwargs):
        if self.count >= self._limit:
            raise RuntimeError(
                f"AI call budget exceeded: {self.count} calls already made, "
                f"limit is {self._limit}. Refusing to spend more."
            )
        self.count += 1
        started = time.monotonic()
        result = await self._client.chat(prompt, **kwargs)
        self.log.append({
            "call": self.count,
            "prompt_chars": len(prompt),
            "response_chars": len(result),
            "seconds": round(time.monotonic() - started, 1),
        })
        return result

    def __getattr__(self, name):
        return getattr(self._client, name)


def find_workspace_db() -> Path:
    """Locate the workspace DB that actually holds a resume."""
    users_dir = APP_ROOT / "data" / "users"
    if not users_dir.is_dir():
        raise FileNotFoundError(f"No workspace directory at {users_dir}")
    candidates = sorted(users_dir.glob("*/jobagent.db"))
    if not candidates:
        raise FileNotFoundError(f"No jobagent.db under {users_dir}")
    for db in candidates:
        try:
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            try:
                row = con.execute(
                    "SELECT COUNT(*) FROM resumes WHERE resume_text IS NOT NULL "
                    "AND resume_text != ''"
                ).fetchone()
            finally:
                con.close()
            if row and row[0]:
                return db
        except sqlite3.Error:
            continue
    raise FileNotFoundError("No workspace DB contains a non-empty resume.")


def copy_db_readonly(src: Path) -> Path:
    """Copy the DB (plus WAL/SHM) to a temp dir so the live file is untouched."""
    tmp = Path(tempfile.mkdtemp(prefix="resume_eval_"))
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(str(src) + suffix)
        if candidate.exists():
            shutil.copy2(candidate, tmp / candidate.name)
    return tmp / src.name


def load_resume(copy_path: Path) -> tuple[str, str]:
    """Return (name, resume_text) using the same selection the E2E harness uses."""
    con = sqlite3.connect(str(copy_path))
    try:
        row = con.execute(
            "SELECT name, resume_text FROM resumes "
            "WHERE resume_text IS NOT NULL AND resume_text != '' "
            "ORDER BY is_default DESC, id ASC LIMIT 1"
        ).fetchone()
    finally:
        con.close()
    if not row:
        raise RuntimeError("No usable resume row found in the workspace DB copy.")
    return row[0] or "(unnamed)", row[1]


async def run() -> int:
    from app.ai_client import parse_json_response
    from app.config import get_settings
    from app.resume_analyzer import analyze_resume
    from app.ai_client import AIClient

    settings = get_settings()
    api_key = (settings.deepseek_api_key or "").strip()
    if not api_key:
        print("ERROR: JOBAGENT_DEEPSEEK_API_KEY is not set.", file=sys.stderr)
        print("Add it to job-search-system/root/.env, then re-run.", file=sys.stderr)
        return 2

    db_copy = copy_db_readonly(find_workspace_db())
    resume_name, resume_text = load_resume(db_copy)
    print(f"Resume: {resume_name}  ({len(resume_text)} chars)")
    print(f"Model : deepseek / deepseek-flash")
    print(f"Budget: {MAX_AI_CALLS} AI calls, hard-capped\n")

    client = CallBudget(
        AIClient(provider="deepseek", api_key=api_key, model="deepseek-flash")
    )

    results: dict = {"resume_name": resume_name, "resume_chars": len(resume_text)}
    ok = True

    # --- call 1: the app's own resume analysis ------------------------------
    print("[1/3] analyze_resume() ...", flush=True)
    try:
        analysis = await analyze_resume(client, resume_text)
        results["analysis"] = analysis
        print(f"      ATS score {analysis.get('ats_score')}/100, "
              f"{len(analysis.get('search_terms') or [])} search terms, "
              f"{len(analysis.get('ats_issues') or [])} issues")
    except Exception as e:
        ok = False
        results["analysis_error"] = str(e)
        print(f"      FAILED: {e}", file=sys.stderr)

    # --- call 2: honest critique --------------------------------------------
    print("[2/3] critique() ...", flush=True)
    try:
        raw = await client.chat(
            CRITIQUE_PROMPT.format(resume=resume_text),
            max_tokens=4000, json_mode=True,
        )
        critique = parse_json_response(raw)
        results["critique"] = critique
        print(f"      {len(critique.get('weaknesses') or [])} weaknesses, "
              f"{len(critique.get('top_rewrites') or [])} rewrites")
    except Exception as e:
        ok = False
        results["critique_error"] = str(e)
        print(f"      FAILED: {e}", file=sys.stderr)

    # --- call 3: role fit ----------------------------------------------------
    print("[3/3] role_fit() ...", flush=True)
    try:
        raw = await client.chat(
            ROLE_FIT_PROMPT.format(resume=resume_text, roles="\n".join(f"- {r}" for r in TARGET_ROLES)),
            max_tokens=4000, json_mode=True,
        )
        role_fit = parse_json_response(raw)
        results["role_fit"] = role_fit
        print(f"      best role: {role_fit.get('best_role')}")
    except Exception as e:
        ok = False
        results["role_fit_error"] = str(e)
        print(f"      FAILED: {e}", file=sys.stderr)

    results["ai_calls"] = client.count
    results["call_log"] = client.log
    results["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())

    out_path = APP_ROOT / "data" / "resume_ai_eval.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nAI calls made: {client.count}/{MAX_AI_CALLS}")
    print(f"Results written to: {out_path}")
    if client.count > MAX_AI_CALLS:
        print("ERROR: call budget was exceeded.", file=sys.stderr)
        return 1
    return 0 if ok else 1


def main() -> int:
    try:
        return asyncio.run(run())
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        print(f"FATAL: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
