# NEXT 5 — execution plan

> Sequenced after the real user-journey E2E (26/26 green, 2026-09-24). Each item
> is **finished one at a time**: write code → run the real-scenario test → fix
> anything it finds → only then move to the next. Nothing counts as done until
> both the new scenario test **and** the repo suite are green.
>
> **Status board:** `docs/E2E_RUN_STATUS.md` · **guide:** `GUIDE.md` ·
> **branch:** `dev_users_based`

**Rule for every item here (Golden Rule #11):** a change is done when it is
proven by a *real-scenario* test — two logged-in users over live HTTP, or a real
server boot — not by a unit test alone.

---

## Backlog corrected by inspection (2026-09-24)

| Claim | Actual state after inspection |
|-------|-------------------------------|
| "per-user scraper keys" | ✅ **already per-user** — `get_scraper_keys()` reads the workspace `scraper_keys` table; discovery/scraping/settings all go through `_db(request)`. Only the *scheduled* cycle reads admin. |
| "per-user Gmail token" | ✅ **fixed 2026-09-27** — `_gmail_credential()` resolves the requesting user's workspace `email_settings` token first; env is only the legacy fallback. |
| "per-user discovery/scrape/score" | ✅ fixed 2026-09-24 (`_task_target`). |
| "per-user cost meter" | ✅ fixed 2026-09-24 (ContextVar sink). |
| "per-user run state" | ❌ **real gap** — `app.state.discovery_running` / `scrape_progress` / `scoring_progress` are process-global, so a second user gets `already_running` / 409 and **their run never starts**. |
| "per-user scheduled cycles" | ❌ **real gap** — `main.py` interval jobs operate on `app.state.bg_db` (admin workspace) only. |
| "build ships the reviewed resume" | ❌ **real bug** — `POST /build` re-generates with AI and overwrites the `/prepare` text (proven in run `2026-09-24_125119`: `visa welcomed` → `visa required`). |

---

## The five items

### N1 — Per-user Gmail token (M15c)

**Problem.** Every user's outreach drafts go through one shared
`JOBAGENT_GMAIL_TOKEN`. Two users each creating a draft for the same recruiter
produces two near-identical emails out of one mailbox.

**Do.**
- Store the token in the **workspace's own settings** (reuse the existing
  per-user `email_settings` table — no schema change), not the env var.
- `_service()` resolves the Gmail provider from `request.state.workspace`
  settings first, env only as the legacy/admin fallback.
- `GET /api/outreach/config` reports `gmail_connected` **and** whose it is;
  the token is never returned (mask like AI keys: `****`).
- `settings_dir` is currently computed and unused — either use it for the
  local-drafts dir or delete it.

**Acceptance.**
1. Two users, two tokens → user A's draft is created with A's token, B's with B's.
2. A's token never appears in any API response A *or* B can see.
3. No token → local-draft fallback still works (existing Critical Test #4 intact).
4. Existing 4-draft idempotency still holds.

**Real-scenario test:** `tests/test_multiuser_real_scenario.py::test_gmail_token_is_per_user`
— two logged-in `httpx` clients over live HTTP, distinct tokens, assert the
provider/token each draft is built from, plus a masked read-back.

**DONE 2026-09-27** (verified again 2026-09-28). All four acceptance criteria
proven by the 4 real-scenario tests (`testing=False`, auth + workspaces live):
two users → two tokens → two mailboxes; masked read-back (`****`-prefix, raw
token in no response either user can see); env only as legacy fallback with the
local-draft fallback still intact (Critical Test #4 path); masked value
round-trip never blanks the stored token (`clear_gmail_token` is the only
eraser). Repo suites green same day: multiuser-scenario 4/4, workspaces 12/12,
outreach/evidence/eligibility/digest 58/58.

---

### N2 — Per-user scheduled cycles (M15c remainder)

**Problem.** The interval jobs in `main.py` (`scheduled_scrape`, `scheduled_scoring`,
`scheduled_maintenance`, `scheduled_reminder_check`, `scheduled_embedding`) all
use `app.state.bg_db` = the admin workspace. A second user's pool never gets
background discovery/scoring/refresh.

**Do.**
- Add a scheduler pass that **iterates active users** and runs the cycle against
  each one's workspace DB + their own matcher (`_task_target`-style resolution).
- **Stagger** the per-user runs so N users scraping from one IP don't trip rate
  limits together (concern #3 in the multi-user plan).
- Keep a single shared cycle when there is only one user (no behaviour change).
- Log which workspace each run touched (`run_id` + `user_id`) for observability.

**Acceptance.**
1. With 2 active users, one scheduler tick touches **both** workspaces.
2. A disabled user is skipped.
3. Runs are staggered (start times differ), not simultaneous.
4. Each user's scoring uses **their** matcher/evidence, not the admin's.

**Real-scenario test:** `test_multiuser_real_scenario.py::test_scheduler_runs_per_user`
— 2 seeded workspaces, one tick, assert both DBs got rows and the scorer used the
right profile; disabled user untouched.

---

### N3 — Per-user background run state (concurrency)

**Problem.** One global `discovery_running` / `scrape_progress` / `scoring_progress`.
If user A starts discovery, user B's `POST /api/discovery/run` returns
`already_running` (and `/api/scrape` returns **409**) — B's run never happens, and
the progress bar B polls shows **A's** progress.

**Do.**
- Key the run state by `user_id` (a dict on `app.state`), not a single slot.
- `running`/`progress`/`task` are per user; `GET /status` and
  `GET /scrape/progress` answer for the *requesting* user.
- Keep a **per-IP advisory cap** so one host can't launch N concurrent scrape
  storms (configurable, default honest); a second user hitting the cap gets a
  clear `429`, not a silent no-op.

**Acceptance.**
1. A and B start discovery **at the same time** → both report `running`, both
   complete, both pools grow.
2. Each sees only their own progress.
3. Scrape same: A running does **not** make B get 409.
4. Progress polling by B never reports A's stage.

**Real-scenario test:** `test_multiuser_real_scenario.py::test_two_users_run_discovery_concurrently`
— two clients POST discovery simultaneously against a stubbed adapter, poll
their own status, assert independent completion.

---

### N4 — Ship what was reviewed + gate personal facts

**Problem (two proven defects from run `2026-09-24_125119`).**
1. `POST /api/packages/jobs/{id}/build` **re-generates** by default and overwrites
   the `/prepare` text a human reviewed — so the packaged resume is a *different*
   document (and costs another AI call). `refresh=true` is the zero-AI path, i.e.
   the flag reads backwards.
2. The evidence gate caught no fabrication, but DeepSeek rewrote a **personal
   fact**: `Open to relocation: Singapore` → `Amsterdam, Netherlands (visa
   sponsorship welcomed)`, and the second generation said `...required`. The two
   generations even contradict each other.

**Do.**
- `build` **defaults to the stored, reviewed text**; generation requires an
  explicit `regenerate=true`. Keep `refresh=true` as a documented alias.
- Add a **personal-facts guard** to the checker: relocation target, visa
  sponsorship, willingness and years must match the candidate's evidence, not
  the JD. Failure → regenerate once → then **422** (same contract as the
  existing gate).
- Record which generation the package came from in `metadata.json`
  (`generated_by: "stored" | "regenerated"`).

**Acceptance.**
1. `/prepare` then `/build` → packaged bytes are the reviewed bytes (hash equal).
2. `build?regenerate=true` → new generation, and it is recorded as such.
3. A generated resume that says a different relocation/visa than the evidence
   corpus is blocked with 422.
4. Two consecutive builds with unchanged inputs stay a `noop` (fingerprint).

**Real-scenario test:** `tests/test_package_and_personal_facts.py` — end-to-end
through the app: prepare → build (hash equality) → regenerate (hash differs) +
a fabricated relocation line rejected.

---

### N5 — Admin panel (M15d)

**Problem.** User management exists only as API endpoints + scattered UI; the
admin can't manage users or see what each is spending from one place, and the
promised **audited impersonation** ("Act as user X") isn't there.

**Do.** One admin-only page:
- create user · disable/enable · reset password (all already audit-logged)
- per-user usage: spend, calls, packages today, pool size
- **Act as user X** — explicit, banner-visible, every action logged to
  `admin_actions` (append-only); "Stop acting" returns to admin
- role-gated: non-admins get 403 (and the routes are 403, not hidden only)

**Acceptance.**
1. Admin creates a user from the UI and that user can log in immediately.
2. Non-admin hitting any admin route gets **403**.
3. Impersonation shows a banner, writes an `admin_actions` row, and the target's
   data is then visible — then reverses cleanly.
4. Per-user spend numbers match that user's own cost meter.

**Real-scenario test:** `test_multiuser_real_scenario.py::test_admin_panel_and_impersonation`.

---

## Order and definition of done

```
N1 Gmail token        → code → real-scenario test → repo suite → commit
N2 per-user scheduler → code → real-scenario test → repo suite → commit
N3 per-user run state → code → real-scenario test → repo suite → commit
N4 shipped text + gate→ code → real-scenario test → repo suite → commit
N5 admin panel        → code → real-scenario test → repo suite → commit
```

**Item done when all four are true:**
1. The feature works in code (no exceptions, no warnings).
2. Its **real-scenario** test passes (two logged-in users over live HTTP, or a
   real server boot — not a mocked unit test).
3. The **repo suite** passes: `pytest -q` (target ≥ 989 passed, 0 real failures).
4. Committed and pushed to `dev_users_based`, status board updated.

## Progress log

| # | Item | Code | Scenario test | Repo suite | Status |
|---|------|------|---------------|------------|--------|
| N1 | Per-user Gmail token | ✅ | ✅ 4/4 | ✅ 999 backend | **DONE 2026-09-27** (re-verified + committed 2026-09-28) |
| N2 | Per-user scheduled cycles | ⬜ | ⬜ | ⬜ | not started |
| N3 | Per-user background run state | ⬜ | ⬜ | ⬜ | not started |
| N4 | Ship reviewed text + personal-facts gate | ⬜ | ⬜ | ⬜ | not started |
| N5 | Admin panel | ⬜ | ⬜ | ⬜ | not started |

*(rows updated as each finishes; also mirrored in `docs/E2E_RUN_STATUS.md`)*
