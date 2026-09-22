"""Benchmark ALL free OpenRouter models against jobagent's real workload.

Uses Basil's actual stored resume text and the app's own resume-analysis
prompt (the production task). For each model measures:
  - availability / errors
  - latency (sanity chat + full resume analysis)
  - JSON validity and completeness of the analysis (the quality that matters)

Results -> docs/MODEL_BENCHMARK_REPORT.md
"""

import asyncio
import json
import os
import statistics
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1] / "root"
sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")
API_KEY = os.getenv("JOBAGENT_OPENROUTER_API_KEY", "")
BASE = "https://openrouter.ai/api/v1"

# Resume text from the DB (extracted from Basil's uploaded .docx)
con = sqlite3.connect(ROOT / "data" / "jobagent.db")
RESUME_TEXT = con.execute("SELECT resume_text FROM resumes LIMIT 1").fetchone()[0]
con.close()

ANALYSIS_PROMPT = f"""Analyze this resume for a job-search system. Respond with ONLY valid JSON:
{{"search_terms": ["..."], "job_titles": ["..."], "key_skills": ["..."], "seniority": "...", "summary": "..."}}
Rules: 5-10 search_terms, 3-6 job_titles, 8-15 key_skills, seniority is junior/mid/senior/lead, one-sentence summary.

RESUME:
{RESUME_TEXT[:3500]}
"""


def get_free_models() -> list[str]:
    req = urllib.request.Request(f"{BASE}/models")
    with urllib.request.urlopen(req, timeout=30) as r:
        models = json.load(r)["data"]
    return sorted(m["id"] for m in models if m["id"].endswith(":free"))


async def chat(model: str, prompt: str, max_tokens: int, timeout_s: float = 60.0):
    """Raw call — returns (ok, content, latency, error)."""
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.post(
                f"{BASE}/chat/completions",
                headers={"Authorization": f"Bearer {API_KEY}"},
                json={"model": model, "max_tokens": max_tokens,
                      "messages": [{"role": "user", "content": prompt}]},
            )
            latency = time.monotonic() - t0
            if resp.status_code != 200:
                return False, "", latency, f"HTTP {resp.status_code}: {resp.text[:120]}"
            content = resp.json()["choices"][0]["message"]["content"] or ""
            return True, content, latency, ""
    except Exception as e:
        return False, "", time.monotonic() - t0, f"{type(e).__name__}: {e}"[:120]


def score_analysis(content: str) -> tuple[dict, int, str]:
    """Parse + score analysis output. Returns (parsed, quality_points, note)."""
    txt = content.strip()
    if txt.startswith("```"):
        txt = txt.split("```")[1]
        if txt.startswith("json"):
            txt = txt[4:]
    try:
        d = json.loads(txt)
    except json.JSONDecodeError:
        # try to find the JSON object inside the text
        i, j = txt.find("{"), txt.rfind("}")
        if 0 <= i < j:
            try:
                d = json.loads(txt[i:j + 1])
            except json.JSONDecodeError:
                return {}, 0, "invalid JSON"
        else:
            return {}, 0, "invalid JSON"

    pts, notes = 0, []
    st, jt, ks = d.get("search_terms") or [], d.get("job_titles") or [], d.get("key_skills") or []
    if isinstance(st, list) and 5 <= len(st) <= 12: pts += 1
    elif isinstance(st, list) and st: pts += 0.5; notes.append(f"only {len(st)} search_terms")
    if isinstance(jt, list) and 3 <= len(jt) <= 8: pts += 1
    elif isinstance(jt, list) and jt: pts += 0.5
    if isinstance(ks, list) and 8 <= len(ks) <= 18: pts += 1
    elif isinstance(ks, list) and ks: pts += 0.5
    if str(d.get("seniority", "")).strip(): pts += 1
    if str(d.get("summary", "")).strip(): pts += 1
    if notes: return d, pts, "; ".join(notes)
    return d, pts, ""


async def bench_one(model: str) -> dict:
    r = {"model": model}
    ok, content, lat, err = await chat(model, "Reply with exactly: OK", 10, 45)
    r["sanity"] = "ok" if ok else f"FAIL ({err})"
    r["sanity_latency"] = round(lat, 1) if ok else None
    if not ok:
        r["analysis"] = "skipped"
        r["quality"] = 0
        r["analysis_latency"] = None
        return r

    ok, content, lat, err = await chat(model, ANALYSIS_PROMPT, 900, 90)
    if not ok:
        r["analysis"] = f"FAIL ({err})"
        r["quality"] = 0
        r["analysis_latency"] = round(lat, 1)
        return r
    parsed, pts, note = score_analysis(content)
    r["analysis"] = "ok" + (f" ({note})" if note else "")
    r["quality"] = pts
    r["analysis_latency"] = round(lat, 1)
    r["sample_terms"] = (parsed.get("search_terms") or [])[:3]
    return r


async def main():
    models = get_free_models()
    print(f"Testing {len(models)} free models against the real resume-analysis task...\n")
    results = []
    BATCH = 5
    for i in range(0, len(models), BATCH):
        batch = models[i:i + BATCH]
        print(f"  batch {i // BATCH + 1}: {', '.join(m.split('/')[0] for m in batch)}")
        results.extend(await asyncio.gather(*(bench_one(m) for m in batch)))

    # ---- report ----
    ok_results = [r for r in results if r["sanity"] == "ok" and str(r["analysis"]).startswith("ok")]
    ok_results.sort(key=lambda r: (-r["quality"], r["analysis_latency"] or 999))
    lines = [
        "# MODEL BENCHMARK REPORT — free OpenRouter models vs jobagent's real workload",
        "",
        f"**Date:** {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}  ",
        "**Task:** the app's actual production prompt — Basil's real stored resume → "
        "JSON {search_terms, job_titles, key_skills, seniority, summary} (the resume-analysis step).  ",
        f"**Models tested:** {len(models)} (all models currently flagged `:free` on OpenRouter)  ",
        "**Quality score:** 0–5 points (search_terms 1 + job_titles 1 + key_skills 1 + seniority 1 + summary 1; "
        "0.5 if present but out of target range).",
        "",
        "## Rankings (working models, best first)",
        "",
        "| # | Model | Quality | Analysis latency | Sample search_terms |",
        "|---|-------|--------:|-----------------:|---------------------|",
    ]
    for i, r in enumerate(ok_results, 1):
        terms = ", ".join(r.get("sample_terms", [])[:3]) or "—"
        lines.append(f"| {i} | `{r['model']}` | {r['quality']}/5 | "
                     f"{r['analysis_latency']}s | {terms[:60]} |")

    lines += ["", "## Failures / skipped", "", "| Model | Result |", "|-------|--------|"]
    for r in results:
        if r not in ok_results:
            detail = r["analysis"] if r["analysis"] != "skipped" else r["sanity"]
            lines.append(f"| `{r['model']}` | {detail} |")

    lat_ok = [r["analysis_latency"] for r in ok_results if r["analysis_latency"]]
    lines += [
        "",
        "## Summary",
        "",
        f"- Working models: **{len(ok_results)}/{len(models)}**",
        f"- Perfect 5/5 quality: **{sum(1 for r in ok_results if r['quality'] == 5)}**",
        f"- Median analysis latency: **{statistics.median(lat_ok):.1f}s**" if lat_ok else "- no latency data",
        "",
        "## Recommendation",
        "",
    ]
    if ok_results:
        best = ok_results[0]
        lines.append(f"Set the app's default model to **`{best['model']}`** "
                     f"(quality {best['quality']}/5, {best['analysis_latency']}s) — it is free, "
                     "so job scoring/tailoring will not drain the $0.13 paid credit balance.")

    report = "\n".join(lines) + "\n"
    out = Path(__file__).resolve().parents[1] / "docs" / "MODEL_BENCHMARK_REPORT.md"
    out.write_text(report)
    print("\n" + "=" * 70)
    print(report)
    print(f"Report saved -> {out}")


if __name__ == "__main__":
    asyncio.run(main())
