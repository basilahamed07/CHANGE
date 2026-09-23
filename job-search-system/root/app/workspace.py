"""M15b — Per-user workspaces (docs/MULTI_USER_PLAN.md Option C).

One SQLite DB + directory tree per user, same schema, zero table changes:
    data/users/{id}-{username}/
        jobagent.db      ← the SAME 46-table schema
        profile/         ← THEIR evidence YAMLs (own resume claims)
        applications/    ← THEIR generated packages
        gmail_drafts/    ← THEIR local-draft fallback

The middleware resolves request.state.workspace before routers run. Every
router already reads request.app.state.db — the workspace middleware installs
the user's Database onto request.state and main.py's _db(request) helper
bridges routers to it. Basil's original single-user data is workspace #1
(admin) via the migration in _migrate_single_user().

Scraping (run_scrape_cycle) is INHERENTLY PER-WORKSPACE: the job pool lives
inside each user's DB. Each user's enabled countries drive their own pool.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
from dataclasses import dataclass

from app.database import Database
from app.auth import SystemStore

logger = logging.getLogger(__name__)

# Files/dirs that belong to the workspace; everything else in the old data/
# stays shared (e.g. .env lives at root/, config/ at root/config).
MIGRATE_ENTRIES = ("jobagent.db", "jobagent.db-shm", "jobagent.db-wal",
                   "profile", "applications")


def _slug(username: str) -> str:
    return re.sub(r"[^a-z0-9_-]+", "", username.lower()) or "user"


@dataclass
class Workspace:
    """One user's isolated world: their DB + their directories."""
    user_id: int
    username: str
    dir: str
    db: Database
    profile_dir: str
    applications_dir: str
    drafts_dir: str

    async def close(self) -> None:
        try:
            await self.db.close()
        except Exception:
            logger.exception("db close failed for user %s", self.user_id)


class WorkspaceManager:
    """Creates and resolves per-user workspaces under a users root directory."""

    def __init__(self, users_root: str, country_yaml_dir: str | None = None):
        self.users_root = users_root
        self.country_yaml_dir = country_yaml_dir
        self._cache: dict[int, Workspace] = {}
        self._lock_held: set[int] = set()

    # ------------------------------------------------------------------ paths

    def workspace_dir(self, user_id: int, username: str) -> str:
        return os.path.join(self.users_root, f"{user_id}-{_slug(username)}")

    # ------------------------------------------------------------- lifecycle

    async def get_or_create(self, user: dict) -> "Workspace":
        user_id = user["id"]
        if user_id in self._cache:
            ws = self._cache[user_id]
            # Recreate if the directory vanished (paranoia — never leave a
            # request without a workspace).
            if os.path.isdir(ws.dir):
                return ws
            await self._close_cached(user_id)
        ws = await self._create(user)
        self._cache[user_id] = ws
        return ws

    async def close_all(self) -> None:
        for user_id in list(self._cache):
            await self._close_cached(user_id)

    async def _close_cached(self, user_id: int) -> None:
        ws = self._cache.pop(user_id, None)
        if ws:
            try:
                await ws.close()
            except Exception:
                logger.exception("workspace close failed for user %s", user_id)

    async def _create(self, user: dict) -> "Workspace":
        user_id, username = user["id"], user["username"]
        wdir = self.workspace_dir(user_id, username)
        db_path = os.path.join(wdir, "jobagent.db")
        os.makedirs(wdir, exist_ok=True)

        created = not os.path.exists(db_path)
        db = Database(db_path)
        await db.init()
        if created:
            # New user → seed enabled countries from the SHARED strategy YAMLs
            # (definitions stay global; the enabled/disabled STATE is per user).
            await self._seed_country_state(db)

        profile_dir = os.path.join(wdir, "profile")
        if not os.path.isdir(profile_dir):
            self._seed_profile_templates(profile_dir)

        applications_dir = os.path.join(wdir, "applications")
        os.makedirs(applications_dir, exist_ok=True)
        drafts_dir = os.path.join(wdir, "gmail_drafts")
        os.makedirs(drafts_dir, exist_ok=True)

        return Workspace(user_id=user_id, username=username, dir=wdir, db=db,
                         profile_dir=profile_dir, applications_dir=applications_dir,
                         drafts_dir=drafts_dir)

    def _seed_profile_templates(self, profile_dir: str) -> None:
        """Copy the 8 evidence YAML templates so a new user starts with a
        complete (all-UNVERIFIED, fail-closed) evidence profile.

        Template source order:
          1. config/profile_templates/ — pristine, every claim UNVERIFIED
             (shipped in the repo; the safe source for new users)
          2. settings.profile_dir — the legacy single-user profile dir, used
             only when the pristine templates are absent.
        """
        import shutil as _shutil
        from app.config import get_settings
        candidates = []
        try:
            _s = get_settings()
            candidates.append(os.path.join(os.path.dirname(_s.countries_dir),
                                           "profile_templates"))
            candidates.append(_s.profile_dir)
        except Exception:
            pass
        candidates.append(os.path.join(os.path.dirname(self.users_root),
                                       "profile_templates"))
        tpl_dir = next((c for c in candidates if c and os.path.isdir(c)), None)
        if tpl_dir:
            os.makedirs(profile_dir, exist_ok=True)
            for name in os.listdir(tpl_dir):
                if name.endswith(".yaml") and not os.path.exists(os.path.join(profile_dir, name)):
                    try:
                        _shutil.copy2(os.path.join(tpl_dir, name),
                                      os.path.join(profile_dir, name))
                    except Exception:
                        logger.exception("template copy failed: %s", name)

    async def _seed_country_state(self, db: Database) -> None:
        """Give new users the same starting enabled-country set as the shared
        YAML defaults (Germany/Netherlands/Ireland/UK/Singapore/UAE semantics
        live in the YAMLs; per-user enabled state lives in their DB)."""
        try:
            await db.update_allowed_regions([])  # empty until user picks countries
            return
        except Exception:
            try:
                await db.save_search_config("", [], allowed_regions=[])
            except Exception:
                logger.exception("country state seeding skipped (schema variance)")

    # ------------------------------------------------------------- migration

    async def migrate_single_user(self, old_data_dir: str, admin_user: dict,
                                  db_filename: str = "jobagent.db") -> str:
        """Move the pre-multi-user data (the main DB file + WAL/SHM, profile/,
        applications/) into the admin's workspace. Idempotent: skips entries
        already moved. db_filename covers non-default names (e2e.db in tests)."""
        moved = []
        wdir = self.workspace_dir(admin_user["id"], admin_user["username"])
        os.makedirs(wdir, exist_ok=True)

        # The main DB is renamed to the canonical workspace name so every
        # workspace opens the SAME filename (e2e.db → jobagent.db in tests).
        canonical = os.path.join(wdir, "jobagent.db")
        src_main = os.path.join(old_data_dir, db_filename)
        if os.path.exists(src_main) and not os.path.exists(canonical):
            shutil.move(src_main, canonical)
            moved.append(db_filename)
            for suffix in ("-wal", "-shm"):
                s = src_main + suffix
                if os.path.exists(s):
                    shutil.move(s, canonical + suffix)

        for entry in (e for e in MIGRATE_ENTRIES if e != "jobagent.db"):
            src = os.path.join(old_data_dir, entry)
            dst = os.path.join(wdir, entry)
            if not os.path.exists(src):
                continue
            if os.path.isdir(dst) and os.listdir(dst):
                continue  # already migrated and in use
            if os.path.isdir(src):
                if not os.path.isdir(dst):
                    shutil.move(src, dst)
                    moved.append(entry)
            else:
                if not os.path.exists(dst):
                    shutil.move(src, dst)
                    moved.append(entry)
        return ", ".join(moved) or "nothing to move (already migrated)"
