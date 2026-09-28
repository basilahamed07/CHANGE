# DOCS SERVER — jobagent's documentation behind login, on 0.0.0.0

> **What this is:** a tiny FastAPI app (`docs_server.py` at the
> `job-search-system/` level) that serves every `.md` file in `docs/` as a
> readable web page — **only to logged-in users**, on `0.0.0.0:8090`.

---

## 1. Quick start

```bash
cd job-search-system

# A) Standalone (fresh machine, no users yet): create the admin first
root/.venv/bin/python docs_server.py --port 8090 --create-user basil 'a-strong-password'

# B) Normal case: reuse the accounts from the main app (same system.db)
root/.venv/bin/python docs_server.py --port 8090
```

Then open `http://<server-ip>:8090` — you get a **Sign in** screen. Only
existing usernames + passwords work (the main app's users, since both read the
same `root/data/system.db`).

| Flag | Default | Meaning |
|---|---|---|
| `--host` | `0.0.0.0` | reachable from the network (use `127.0.0.1` for local-only) |
| `--port` | `8090` | any free port |
| `--db` | `root/data/jobagent.db` | whose **system.db** provides the users |
| `--create-user U P` | — | one-time: create an admin account (refuses duplicates) |

## 2. Auth model — "only my users can read my docs"

- **Same store as the app:** users + sessions live in `root/data/system.db`
  (`app/auth.py#SystemStore`), scrypt-hashed passwords, SHA-256-stored session
  tokens, 7-day cookie (`jobagent_session`, HttpOnly, SameSite=Lax).
- **No anonymous access:** every path except the login page/POST requires a
  valid session. Anonymous browsers get the login page; anonymous API clients
  get `401 {"detail": "Authentication required"}`.
- **No bootstrap hole:** unlike the main app there is **no first-run bootstrap**
  here — this server can never create the first account implicitly; only
  `--create-user` (run by the person who owns the machine) adds users.
- **Login throttling:** 5 wrong passwords for one username → 15-minute lock.
- **Disabled users are locked out immediately** (their sessions stop resolving).

## 3. What it serves

| URL | Auth? | Content |
|---|---|---|
| `GET /` | session | index of every `docs/*.md` |
| `GET /docs/USER_PROCESS.md` | session | that file rendered as HTML (headings, tables, code) |
| `GET /raw/USER_PROCESS.md` | session | the raw markdown text |
| `GET /logout` | session | destroys the session, shows login |
| `POST /login` | public | form endpoint the login page posts to |
| anything else | **401 / login page** | defence in depth |

## 4. Security notes (honest limits)

- Path traversal is blocked: only plain `*.md` filenames **directly inside
  `docs/`** are servable (`..`, `/`, `\` rejected; resolved path must stay in
  `docs/`).
- No HTTPS (same as the main app) — put it behind a TLS reverse proxy if this
  faces the internet, not just a LAN.
- Docs contain **no secrets** (keys/resume text are gitignored elsewhere), but
  the reports describe your infrastructure — that is exactly why it is gated.

## 5. How it was verified (2026-09-27)

Live run on `0.0.0.0:8090`:
anonymous `GET /docs/FULL_SUITE_TEST_REPORT.md` → **401 JSON** ·
anonymous browser `GET /` → **login page** ·
`POST /login` with a real user → **303 + session cookie** ·
then `GET /` (file index), `GET /docs/...` (rendered HTML),
`GET /raw/...` (markdown), **bad password → 401**, `/logout` → session dead
(all verified with curl).
