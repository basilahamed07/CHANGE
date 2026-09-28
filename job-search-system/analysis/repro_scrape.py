"""Reproduce what "Scrape now" does, and report every source's error.

Runs the same cycle the live server's background task runs
(`app.scheduler.run_scrape_cycle` with the same scrapers/terms/keys), against the
admin workspace DB, and prints per-source results plus every logged traceback.

Usage:  .venv/bin/python ../analysis/repro_scrape.py
"""
import asyncio
import logging
import os
import sys
import time

ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "root")
sys.path.insert(0, ROOT)

from app.database import Database                      # noqa: E402
from app.scrapers import ALL_SCRAPERS                  # noqa: E402
from app.scheduler import run_scrape_cycle             # noqa: E402

DB_PATH = os.path.join(ROOT, "data", "users", "1-basil", "jobagent.db")


async def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(levelname)-7s %(name)s: %(message)s")

    db = Database(DB_PATH)
    await db.init()

    config = await db.get_search_config()
    terms = (config or {}).get("search_terms") or []
    keys = await db.get_scraper_keys() or {}
    print(f"search terms ({len(terms)}): {terms[:8]}")
    print(f"scraper keys set: {sorted(keys) or 'none'}")
    print(f"scrapers registered: {len(ALL_SCRAPERS)}")
    print("-" * 78, flush=True)

    progress = {
        "phase": "scraping", "active": True, "current": None,
        "completed": 0, "total": len(ALL_SCRAPERS), "new_jobs": 0,
        "sources": [], "errors": [], "task_id": "repro",
        "last_updated_at": time.monotonic(),
    }
    scrapers = [s(search_terms=terms, scraper_keys=keys) for s in ALL_SCRAPERS]

    started = time.monotonic()
    try:
        total_new = await run_scrape_cycle(
            db, scrapers, search_terms=terms, progress=progress,
            scraper_keys=keys, force=True)
    except Exception:
        logging.exception("run_scrape_cycle raised")
        total_new = -1
    elapsed = round(time.monotonic() - started, 1)

    print("\n" + "=" * 78)
    print(f"PER SOURCE  (total new jobs: {total_new}, {elapsed}s)")
    print("=" * 78)
    bad = []
    for s in progress["sources"]:
        err = s.get("error")
        flag = "FAIL" if err else "ok  "
        if err:
            bad.append((s.get("name"), err))
        print(f'{flag} {str(s.get("name")):<20} status={str(s.get("status")):<9} '
              f'found={s.get("listings_found"):<5} new={s.get("new_jobs"):<5} '
              f'{s.get("duration_ms")}ms  {err or ""}')

    print("\n" + "=" * 78)
    if bad:
        print(f"FAILING SOURCES ({len(bad)} of {len(progress['sources'])})")
        for name, err in bad:
            print(f"  - {name}: {err}")
    else:
        print("No per-source errors reported.")
    print("=" * 78)

    await db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
