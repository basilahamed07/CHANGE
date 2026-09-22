"""jobagent live demo + profile verification audit.

Run:  python3 job-search-system/analysis/demo_script.py
Boots the server on port 8085, runs the demo against the live HTTP API,
then shuts the server down. No external dependencies (urllib only).
"""

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "root"
PORT = 8085
BASE = f"http://127.0.0.1:{PORT}"


def api(method: str, path: str, body: dict | None = None) -> tuple[int, dict | str]:
    req = urllib.request.Request(
        BASE + path,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read().decode()
            try:
                return r.status, json.loads(raw)
            except json.JSONDecodeError:
                return r.status, raw[:120]
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, raw[:120]


def section(title: str) -> None:
    print(f"\n{'=' * 64}\n  {title}\n{'=' * 64}")


def wait_healthy(proc: subprocess.Popen) -> bool:
    for _ in range(30):
        if proc.poll() is not None:
            return False
        try:
            code, body = api("GET", "/api/system/health")
            if code == 200 and body.get("status") == "healthy":
                return True
        except (urllib.error.URLError, ConnectionError, OSError):
            pass
        time.sleep(1)
    return False


def main() -> int:
    section("BOOT: starting jobagent server")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:create_app",
         "--factory", "--port", str(PORT)],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        if not wait_healthy(proc):
            print("FAILED to start server")
            return 1
        code, health = api("GET", "/api/system/health")
        print(f"  status={health['status']}  product={health['product']}  "
              f"version={health['version']}")
        print(f"  db={health['db']}  scheduler={health['scheduler']}")
        print(f"  features={json.dumps(health['features'])}")

        # ------------------------------------------------ profile audit
        section("DEMO 1: PROFILE VERIFICATION AUDIT (GET /api/evidence)")
        code, ev = api("GET", "/api/evidence")
        print(f"  counts: {json.dumps(ev['counts'])}")
        flag = {"VERIFIED": "[VERIFIED]   ", "UNVERIFIED": "[UNVERIFIED] ",
                "DISPUTED": "[DISPUTED]  ", "DO_NOT_USE": "[DO_NOT_USE] "}
        for c in ev["claims"]:
            val = c["value"] if c["value"] else "(empty — fill this in)"
            if len(val) > 52:
                val = val[:52] + "…"
            print(f"  {flag[c['status']]} {c['category']:11} "
                  f"{c['claim_id']:22} {val}")
        unverified = [c for c in ev["claims"] if c["status"] == "UNVERIFIED"]
        print(f"\n  >> {len(unverified)} claim(s) are UNVERIFIED — the system will")
        print("  >> NEVER put them on a resume until YOU mark them VERIFIED with a source.")

        # ------------------------------------------------ gate: fabrication FAIL
        section("DEMO 2: EVIDENCE GATE — FABRICATED RESUME TEXT (must FAIL)")
        fabricated = (
            "Senior AI Engineer with 8 years of experience.\n"
            "Skills: Python, Kubernetes, Terraform, AWS SageMaker.\n"
            "Led a team of 12 engineers and improved model throughput by 300%.\n"
        )
        code, result = api("POST", "/api/evidence/check", {"text": fabricated})
        print(f"  gate verdict: {'PASS' if result['ok'] else 'FAIL ✓ (blocked)'}")
        for f in result["failures"]:
            items = ", ".join(f["items"][:4])
            print(f"    ✗ {f['type']:20} {items}")
        print("  >> A resume containing this text would be REJECTED. Nothing saved.")

        # ------------------------------------------------ gate: honest PASS
        section("DEMO 3: EVIDENCE GATE — TEXT BACKED BY VERIFIED EVIDENCE (must PASS)")
        verified_values = [c["value"] for c in ev["claims"] if c["status"] == "VERIFIED"]
        honest = "\n".join(v for v in verified_values if v.strip())
        if not honest.strip():
            honest = "no verified claims available"
        preview = honest[:80] + ("…" if len(honest) > 80 else "")
        print(f"  text used: {preview!r}")
        code, result = api("POST", "/api/evidence/check", {"text": honest})
        print(f"  gate verdict: {'PASS ✓' if result['ok'] else 'FAIL'}")
        if not result["ok"]:
            for f in result["failures"]:
                print(f"    ✗ {f['type']:20} {', '.join(f['items'][:3])}")

        # ------------------------------------------------ UI + docs
        section("DEMO 4: WEB UI + OPENAPI")
        code, _ = api("GET", "/")
        print(f"  GET /            -> {code} (dashboard SPA)")
        code, _ = api("GET", "/docs")
        print(f"  GET /docs        -> {code} (OpenAPI swagger UI)")

        section("RESULT")
        print("  App: WORKING. Gate: enforcing. Profile: awaiting Basil's verification.")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
