# MULTI-USER ACCESS PLAN — Admin + User Workspaces

Date: 2026-09-23
Status: PLAN — awaiting Basil's approval to start M15a
Author: Generated from Basil's requirements + decisions on 2026-09-23

---

## 1. What Basil Asked For

> "User-based access: login as Admin and Users. Each user can add their own
> resume, choose their own country, and have their own API key."

## 2. Basil's Decisions (2026-09-23)

| Question | Decision |
|----------|----------|
| Scale | **Small: 2–10 users** (one machine, no Postgres needed) |
| Job pool | **Each user scrapes their own** (full isolation, no shared pool) |
| Admin rights | **Full access to everything** (admin can open any user's workspace) |

These three answers select **Option C — Per-User Workspace** as the architecture.

---

## 3. Architecture: Per-User Workspace (Option C)

### 3.1 The core idea

**One SQLite database per user. Same 46-table schema. Zero changes to the
existing tables.**

Today `Database(settings.db_path)` already opens an arbitrary path (the CLI
proves it). Multi-user becomes: *each authenticated request opens the DB that
belongs to the logged-in user.*

```
data/
├── system.db                  # NEW: users + sessions (auth only)
└── users/
    ├── 1-admin/               # Basil (migrated from current data/)
    │   ├── jobagent.db        # the SAME schema as today
    │   ├── profile/           # THEIR evidence YAMLs (resume, skills...)
    │   ├── applications/      # THEIR generated packages
    │   └── gmail_drafts/      # THEIR local-draft fallback
    ├── 2-sara/
    │   └── ...
    └── 3-omar/
        └── ...
```

### 3.2 Why this beats adding `user_id` to all 46 tables

| | Option A (`user_id` everywhere) | **Option C (workspace per user)** ✅ |
|---|---|---|
| DB schema changes | 46 tables + every query | **0 tables** |
| Risk of cross-user data leak in one query bug | High (one missing WHERE = leak) | **Structurally impossible** (process only opens your DB) |
| Migration of Basil's data | Rewrite every table | **Move folder, done** |
| "extend > rewrite" rule | Violated | **Honoured** |
| Effort | Very high | Medium |

### 3.3 How each requirement is satisfied

| Requirement | Mechanism |
|-------------|-----------|
| **Own resume** | Each workspace has its own `profile/*.yaml` evidence set + own resume upload + own `applications/` packages |
| **Own country selection** | Each workspace has its own `config` rows + country enabled-set (country *definitions* stay shared global YAML; the per-user *enabled/strategy state* lives in the user's DB) |
| **Own API key** | Each workspace has its own `ai_settings` row → their own OpenRouter/DeepSeek key, their own cost meter (`ai_usage`), their own quota |
| **Own scraper keys** | `scraper_keys` table already exists per-DB → per-user Hunter/Apollo/USAJobs keys |
| **Own Gmail** | Per-user Gmail token stored in workspace settings (encrypted, M15e) → drafts land in *their* Gmail; local-draft fallback stays |

### 3.4 Auth design (no new heavy dependencies)

- **`data/system.db`** — two tables:
  - `users(id, username UNIQUE, password_hash, role admin|user, is_active, created_at, last_login_at)`
  - `sessions(token_hash UNIQUE, user_id, created_at, expires_at)` — token = `secrets.token_urlsafe(32)`, only the SHA-256 is stored; HttpOnly + SameSite=Lax cookie; 7-day sliding expiry.
- **Password hashing:** `hashlib.scrypt` (Python stdlib — zero new deps, memory-hard, recommended).
- **First-run bootstrap:** if `users` is empty → setup screen creates the ADMIN account → admin workspace is created. No default password ever exists.
- **Admin "full access":** admin picks **"Act as user X"** → session carries `impersonated_user_id`; every action runs through the *same* code path as that user (no bypass = fewer bugs) and an event is written to an append-only `admin_actions` audit table. Admin panel also shows read-only usage/spend for all users.

### 3.5 Request flow (the one real refactor)

```
Browser ──cookie──▶ AuthMiddleware
                      │ verify session → load user
                      ▼
                    request.state.user      = user row
                    request.state.workspace = {db, profile_dir, apps_dir, ...}
                      ▼
                    Router (request.state.db instead of request.app.state.db)
                      ▼
                    DailyRun / scheduler loop iterates ACTIVE users,
                    each with their own workspace (staggered)
```

Mechanical change: routers switch `request.app.state.db` → `request.state.db`
(middleware injects it). `app.state.db` remains = admin workspace, used by the
scheduler/bootstrap only.

---

## 4. Milestones (each ends with tests + E2E + report, Golden Rule #11)

### M15a — Auth foundation
- `data/system.db` with `users` + `sessions`; scrypt hashing; login/logout/change-password endpoints.
- First-run bootstrap screen (create admin) — only shown when no users exist.
- Login page + frontend route guards (401 → `#/login`); `api.js` handles session expiry.
- Middleware rejects ALL API routes except `/api/system/health`, `/api/auth/*`.
- Tests: hash round-trip, wrong password, expired session, inactive user, unauthenticated 401 matrix across routers.
- **Done when:** you can log in as Admin and nobody can reach any data without a session.

### M15b — User workspaces (the core)
- Workspace factory: `data/users/{id}/` (db + dirs + evidence templates copied on create).
- Middleware binds session → workspace; routers read `request.state.db/workspace`.
- User self-registration option (config flag, default: admin creates users).
- User adds **own AI key** (Settings page now writes to their `ai_settings`), uploads **own resume**, verifies own evidence.
- Tests: two users, two DBs; every write lands in the right workspace.
- **Done when:** a second user completes setup → own resume → own scoring → own package, with their own key.

### M15c — Per-user pipeline features
- Per-user countries enabled-set, per-user scraper keys, per-user Gmail token, per-user daily-run state + analytics + cost meter.
- Scheduler loop: iterate active users, stagger discovery (per-IP rate limits), each user's `DailyRun` runs against their workspace.
- Per-user anti-spam caps unchanged (12/day etc. — already per-DB).
- **Done when:** 2 users each run a full daily cycle independently in the same process.

### M15d — Admin panel
- Admin page: create user, disable user, reset password, view per-user usage/spend/packages-today, **Act as user X** (audited).
- `admin_actions` audit table (append-only).
- **Done when:** admin manages a user end-to-end from the UI.

### M15e — Hardening + migration (Critical Test #5)
- **Critical Test #5 (new):** user A can NEVER read/write user B's jobs, packages, keys, or drafts — proven by attempting every cross-access vector through the live API.
- API-key encryption at rest: workspace keys encrypted with a server master key (`JOBAGENT_MASTER_KEY` env) — uses the `cryptography` (Fernet) library, the **one justified new dependency**; without the master key the app refuses to expose keys.
- Per-user rate limits on AI calls + login throttling (5 fails → 15-min lockout).
- **Migration script:** move current `root/data/` (jobagent.db, profile/, applications/) → `data/users/1-admin/` with a timestamped backup; old paths keep working read-only during transition.
- **Done when:** E2E report shows isolation tests passing and Basil's existing data intact under the admin workspace.

---

## 5. Concerns & Mitigations (honest list)

| # | Concern | Mitigation |
|---|---------|-----------|
| 1 | **You become responsible for other people's PII (resumes) + paid API keys** | Keys encrypted at rest (M15e); resume folders are per-user OS directories; recommend HTTPS reverse proxy before any exposure beyond localhost; document a data-deletion path per user |
| 2 | **Server is currently localhost-only, no auth** | M15a adds auth on every route; deployment doc (M14 gap) should include HTTPS guidance |
| 3 | **N users scraping from one IP** → rate-limit bans for everyone | Staggered per-user discovery windows; per-user budgets; small scale (≤10) keeps this manageable |
| 4 | **Admin full-access = trust** | All admin actions audit-logged, impersonation is explicit + visible; you can downgrade to "users + usage only" later by removing the impersonate route |
| 5 | **Session/cookie security** | HttpOnly + SameSite cookies, hashed tokens, expiry, login lockout |
| 6 | **Cost: whose bill?** | Each user pays with their OWN key by design — the app meters per user and shows spend per user; admin sees all |
| 7 | **Scope creep into rewrite** | Workspace model = zero schema changes; if a shared job pool is wanted later (Option B), it can be added ON TOP without redoing auth |

## 6. What Does NOT Change

- All 11 Golden Rules (evidence gate, DRAFT-ONLY outreach, deterministic-first, E2E-per-milestone…).
- All 46 table schemas, all existing tests (872 backend + 180 frontend stay green).
- All 4 existing Critical Tests — plus new **Critical Test #5** (user isolation).
- Per-user behaviour = today's single-user behaviour, multiplied.

## 7. Open Items for Basil (answer before M15a starts)

1. Can users self-register, or only admin creates accounts? (default plan: admin creates)
2. Keep username+password, or also want email magic-links later? (plan: username+password now)
3. Should disabled users' data be deleted or frozen? (plan: frozen — reversible)
4. Confirm the $2-cryptography dependency for key encryption (plan: yes, Fernet).
