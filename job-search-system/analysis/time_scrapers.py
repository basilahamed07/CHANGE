"""Time each scraper's FETCH phase (no DB writes).

The UI calls a scrape "stalled" after 30s without a progress heartbeat and shows
an error toast after 120s; the server also kills a source at
`PER_SCRAPER_TIMEOUT = 120s` and records it as a failure. Both thresholds apply
to the FETCH phase, where `run_scrape_cycle` emits no heartbeat. This script
measures that phase per source so the false positives are visible.

Usage:  .venv/bin/python ../analysis/time_scrapers.py
"""
import asyncio
import os
import sys
import time

ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "root")
sys.path.insert(0, ROOT)

from app.database import Database          # noqa: E402
from app.scrapers import ALL_SCRAPERS      # noqa: E402

DB_PATH = os.path.join(ROOT, "data", "users", "1-basil", "jobagent.db")
CAP = 130          # just past PER_SCRAPER_TIMEOUT (120s)
STALL_WARN = 30    # frontend STALL_WARN_SEC
STALL_CRITICAL = 120
HEARTBEAT_INTERVAL = 5.0   # what the fix emits


async def main() -> int:
    db = Database(DB_PATH)
    await db.init()
    cfg = await db.get_search_config() or {}
    terms = cfg.get("search_terms") or []
    keys = await db.get_scraper_keys() or {}

    print(f"{len(ALL_SCRAPERS)} scrapers | UI warns >{STALL_WARN}s, errors >{STALL_CRITICAL}s "
          f"| server kills >{CAP}s", flush=True)
    print("-" * 92, flush=True)

    slow, killed, errored = [], [], []
    for cls in ALL_SCRAPERS:
        try:
            s = cls(search_terms=terms, scraper_keys=keys)
        except Exception as e:
            print(f"INIT   {cls.__name__:<22} {type(e).__name__}: {e}", flush=True)
            errored.append(cls.__name__)
            continue
        name = s.source_name
        t0 = time.monotonic()
        try:
            listings = await asyncio.wait_for(s.scrape(), timeout=CAP)
            dur = time.monotonic() - t0
            if dur > STALL_CRITICAL:
                verdict = "FALSE-ERROR (would show 'appears stuck')"
                slow.append((name, dur))
            elif dur > STALL_WARN:
                verdict = "FALSE-STALL (would show 'Stalled')"
                slow.append((name, dur))
            else:
                verdict = ""
            print(f"ok     {name:<22} {dur:6.1f}s  {len(listings):>5} listings  {verdict}",
                  flush=True)
        except asyncio.TimeoutError:
            dur = time.monotonic() - t0
            killed.append((name, dur))
            print(f"KILLED {name:<22} {dur:6.1f}s  server records status=timeout "
                  f"error='exceeded {CAP - 10}s'", flush=True)
        except Exception as e:
            dur = time.monotonic() - t0
            errored.append((name, str(e)))
            print(f"ERROR  {name:<22} {dur:6.1f}s  {type(e).__name__}: {str(e)[:60]}",
                  flush=True)

    print("\n" + "=" * 92)
    print("SUMMARY")
    print("=" * 92)
    print(f"sources above the UI stall threshold ({STALL_WARN}s): {slow or 'none'}")
    print(f"sources KILLED at the {CAP}s cap:                     {killed or 'none'}")
    print(f"sources that raised:                                {errored or 'none'}")
    await db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
