# STAGE-9 OUTREACH — AUDIT

> Static audit from reading the code. **Not executed** — the environment's command classifier was
> unavailable throughout, so nothing below was reproduced live. Every finding cites `file:line`.
>
> Stage 9 of `app/daily_run.py:29` (`STAGES`). Upstream: Stage-8 PACKAGES. Downstream: Stage-10 DIGEST.
>
> **M9 itself has no send path — verified.** The finding that matters is that a *sibling* router does
> send, ungated (O1).

---

## 1. What the stage does today

| Piece | Location |
|---|---|
| Service (the only entry point) | `OutreachService` — `app/outreach.py:206` |
| Sequences / limits / identity | `load_sequences` — `outreach.py:64`; `config/outreach_sequences.yaml` |
| Deterministic rendering | `render_message` — `outreach.py:102` |
| Gmail **draft-only** provider | `GmailProvider` — `outreach.py:128` (`create_draft:148`, `find_existing_draft:183`) |
| Idempotency (Critical Test #4) | service check `outreach.py:262` + DB `UNIQUE(job_id, audience)` `database.py:568` |
| Caps | `max_outreach_per_day=12`, `per_company_daily_cap=2`, `followup_wait_days=6` — `outreach.py:52-56` |
| Per-user credential | `_gmail_credential` — `app/routers/outreach.py:22` |
| Router surface | `app/routers/outreach.py` |

## 2. Contract vs reality

| Claimed | Actual |
|---|---|
| "There is no code path in M9 that sends" (`outreach.py:6`) | **True** — `GmailProvider` exposes only `create_draft` / `find_existing_draft` |
| Critical Test #4: creating twice ⇒ one draft | **True, two layers** — service check *and* DB `UNIQUE(job_id, audience)` |
| Gmail token is the requesting user's (`routers/outreach.py:23`) | **True in the router** — workspace token, env only as fallback (`:35-39`) |
| …but the service default still reaches env | **True** — `gmail or GmailProvider()` (`outreach.py:213`) |
| Follow-up waits 6 days | True — but measured from the *first* outreach only (O9) |
| "one outreach per (job, audience)" | True — and audience is derived from the contact, so a job can legitimately hold several |
| Sending is gated by `JOBAGENT_ALLOW_SEND` | **False elsewhere** — `pipeline.py:112` sends via SMTP with no gate (O1) |

---

## 3. Defects found

### O1 — an ungated SMTP send endpoint exists outside M9 and bypasses the approval matrix
**✅ FIXED — the send capability was removed entirely. See the resolution note at the end of O1.**
`app/routers/pipeline.py:112-127`, `app/crm.py:182`

```python
# routers/pipeline.py:112
@router.post("/jobs/{job_id}/send-email")
async def send_job_email(request: Request, job_id: int):
    from app.emailer import send_application_email
    ...
    success = await send_application_email(email_settings, email_draft)   # ← actually sends
    await db.add_event(job_id, "email_sent", f"Email sent to {email_draft.get('to', '')}")
```

This endpoint takes a stored `email_draft` and **sends it over SMTP**. There is:

- **no** check of `JOBAGENT_ALLOW_SEND`,
- **no** call into `approval_required(...)`, even though the approval matrix explicitly registers
  `"outreach_send": {"risk": "high", "approval": "explicit"}` (`crm.py:182`),
- no confirmation parameter.

It sits in a different router from M9, so the M9 "never sends" guarantee is true of `app/outreach.py`
and false of the application. Any authenticated user can send mail through the configured SMTP account
with one POST.

**Why it matters:** the project's stated posture (Golden Rule 6, `CLAUDE.md` "Gmail outreach creates
drafts by default. Do not add sending behavior unless explicitly requested and covered by tests") is
enforced in the module the docs point at and unchecked in the endpoint that actually sends.

**Resolution (2026-10-03):** the endpoint and every path to it were **deleted**, not gated — jobagent
is draft-only, so a dormant-but-present sender is a standing risk. Removed:

| Removed | Where |
|---|---|
| `POST /api/jobs/{job_id}/send-email` route | `app/routers/pipeline.py` |
| `send_application_email()` helper | `app/emailer.py` (dead once the route was gone) |
| `wireSendEmailBtn()` + its two call sites | `app/static/js/views/detail.js` |
| the "Send Email" button in the email-draft preview | `app/static/js/views/detail.js` (`renderEmailPreview`) |

The **Draft Email** and **Copy Email** affordances remain — drafting still works, the user copies the
text and sends it themselves from their own client. Two guards now prevent regression:
`test_send_job_email_endpoint_is_removed` (the route 404s) and `test_no_send_email_route_is_registered`
(scans every registered route for a `send-email` path under any HTTP method).

SMTP itself is untouched: `app/emailer.send_email` still powers the opt-in **digest** email and the
`/api/settings/email/test` connection test. Those are the user's own report/test features and are not
application sends — nothing in them can email a recruiter.

### O2 — Gmail draft dedup matches on subject across the whole mailbox, so one job can adopt another's draft
`app/outreach.py:183-199`, `:289-293`

```python
resp = await client.get(self.DRAFTS_URL,
                        params={"q": f"subject:{subject}"}, ...)   # :192
drafts = resp.json().get("drafts", []) or []
return drafts[0] if drafts else None                               # :196
```

`find_existing_draft` searches **every draft in the mailbox** by subject substring and returns the first
hit. It is not scoped by recipient, company, job, or thread. If two jobs render the same subject — a
template like `Quick question about {company}` collides whenever the company name is shared, and any
template that omits `{company}` collides always — then for job B the service finds job A's draft and:

```python
draft_id = existing_gmail.get("id", "")   # :291  → A's draft id
provider = "gmail"
```

so B's `outreach_messages` row records **A's draft id** and **no draft is created for B**. The job is
then marked as having outreach, and `already_exists` on the next call hides the problem.

**Why it matters:** the dedup layer turns a correctness guarantee (one draft per job) into a
cross-job mislink, and the symptom is silent — outreach appears done for a job that has no draft.

### O3 — the service-level default re-opens the env-token path the router carefully closes
`app/outreach.py:213`, `:144-146`

```python
self.gmail = gmail or GmailProvider()          # :213 → token="" → os.getenv("JOBAGENT_GMAIL_TOKEN")
```

The router does the right thing (`routers/outreach.py:42-47` passes a per-user token, and
`_gmail_credential:35-39` reads the workspace `email_settings` first). But `OutreachService`'s own
default constructs `GmailProvider()` with no token, which falls through to `os.getenv`
(`outreach.py:145`). Any future caller that constructs the service directly — the scheduler, a new
router, a test — silently uses the process-wide token. The project's own rule is "env fallback only
when **no workspace token exists**", which the default cannot know.

### O4 — the daily cap is a rolling 24h window, not a calendar day
`app/outreach.py:217-223`

```python
return await self.db.count_outreach_since(_iso(_now_utc() - timedelta(days=1)))
```

`max_outreach_per_day` and `per_company_daily_cap` are counted over `now − 24h`. This is defensible (it
is stricter than a calendar day) but the names say "per day", and `count_outreach_since` (`database.py:1408`)
compares ISO timestamps lexicographically against a UTC string — correct, provided every writer stores
UTC ISO (it does). Worth documenting the window explicitly so the limit is predictable.

### O5 — the "capped" result is honest, but the pipeline has no caller to consume it
`app/routers/outreach.py:72-73`, `app/outreach.py:269-275`

The router maps `capped` → HTTP 429 (`:73`), and the service returns a reason string. Good. But
**`OutreachService` is constructed in exactly two places** — `routers/outreach.py:47` and
`tests/test_outreach.py:26`. There is **no pipeline/scheduler caller**, so Stage-9 in `STAGES` is not
wired to anything that runs automatically; `daily-run/run` passes `"outreach": None`
(`crm.py:191`), which `DailyRun` records as `status="skipped", reason="not_implemented"`
(`daily_run.py:158-161`). The stage exists in the list and does not execute.

### O6 — `classify_role` is fed an email address
`app/outreach.py:236-242`

```python
role = classify_role(title or email)
```

Same shape as Stage-7's R6: when no contact title exists, the *email address* is classified as a role.
A local part like `hr-team@…` matches the recruiter regex by luck; `j.smith@…` yields `other`. The
audience then defaults to `recruiter` (`:242`), so a hiring-manager contact with no title is treated as
a recruiter. Low impact, wrong input.

### O7 — `force_audience=False` silently discards an explicitly requested audience
`app/outreach.py:248`, `:259`

```python
audience = self._pick_audience(job, audience if force_audience else None)
```

With the default `force_audience=True` the requested audience is honoured. But a caller passing
`audience="hiring_manager", force_audience=False` gets `_pick_audience(job, None)` — the explicit
audience is thrown away and recomputed from the contact. The flag's name suggests the opposite of what
it does in that branch.

### O8 — the raw RFC2822 message is built by f-string with no CRLF sanitisation
`app/outreach.py:163-167`

```python
raw_msg = (f"To: {to}\r\nSubject: {subject}\r\n"
           f"Content-Type: text/plain; charset=\"UTF-8\"\r\n\r\n{body}")
```

`to_email` ultimately comes from `job.hiring_manager_email` or the request body's `contact_email`
(`routers/outreach.py:67`). A value containing `\r\n` injects additional headers into the draft. Impact
is low — this creates a **draft**, never sends, and the user controls the input — but the construction
is the fragility, and the same `raw` is what Gmail will send if a human later hits send in the Gmail UI.
Strip `\r`/`\n` from `to` and `subject`.

### O9 — the follow-up wait is measured only from the first outreach, and prefers `recruiter`
`app/outreach.py:312-322`

```python
first = await self.db.get_outreach(job_id, "recruiter") or \
        await self.db.get_outreach(job_id, "hiring_manager")
```

If both a recruiter and a hiring-manager outreach exist, the wait is measured from the **recruiter's**
timestamp (the `or` short-circuits). And because the follow-up's own dedup key is `(job_id, "followup")`,
only one follow-up is ever possible per job regardless of how many audiences were contacted — so a
job with two live threads gets one follow-up, timed against an arbitrary one of them.

### O10 — rendered content has no length or content guard
`app/outreach.py:102-121`

`render_message` fills placeholders and collapses blank lines, then returns. Job titles and company
names come from scraped listings (`job.get("title")`, `job.get("company")`) — attacker-influenced text
that is interpolated straight into the subject and body. There is no length cap and no strip of control
characters beyond the `\n{3,}` collapse. A listing title containing a newline and long text lands
verbatim in a draft addressed to a real person.

---

## 4. What holds (verified, not assumed)

- **Critical Test #4 is enforced at two layers.** Service: `get_outreach(job_id, audience)` returns
  early with `status="already_exists"` (`outreach.py:262-265`). DB:
  `UNIQUE(job_id, audience)` (`database.py:568`), and `insert_outreach` (`:1373`) does a plain `INSERT`,
  so a race raises rather than duplicating.
- **No send in M9.** A repository-wide search for send paths returns `outreach.py` only in its own
  docstrings; `GmailProvider` has exactly two methods, both draft-side.
- **Rendering is deterministic and LLM-free** — `render_message` is a regex substitution over the YAML
  template (`:114-116`); no AI import in the module.
- **The router resolves the per-user credential correctly** — workspace `email_settings.gmail_token`
  first, env only as a labelled fallback, and the raw token is never returned (`routers/outreach.py:22-39`,
  `:110-113`).
- **Caps are real and honest** — enforced before any draft is created (`outreach.py:268-275`), and the
  refusal is returned with its count and limit rather than silently skipped.

---

## 5. What hardening should do

1. **Close or gate the send endpoint (O1).** Either remove `POST /jobs/{job_id}/send-email` or route it
   through `approval_required("outreach_send")` **and** the `JOBAGENT_ALLOW_SEND` check that M9's
   docstring promises. This is the highest-value change in the stage.
2. **Scope draft dedup (O2).** Search by subject **and** recipient (`q=f"subject:{s} to:{to}"`), and
   verify the found draft's company/job before adopting it; when in doubt, create rather than adopt.
3. **Remove the env fallback from the service default (O3)** — require an explicit token, so the
   workspace-first rule cannot be bypassed by a new caller.
4. **Sanitise the raw message (O8).** Strip `\r`/`\n` from `to` and `subject`; build the header block
   with a library or an explicit encoder.
5. **Document the cap window (O4)** as rolling 24h, or switch to calendar-day.
6. **Wire or drop the stage (O5).** If Stage-9 is meant to run in the pipeline, give it a caller; if not,
   say so in `STAGES` so the `not_implemented` skip is expected rather than surprising.
7. **Classify from titles only (O6)**; cap and sanitise rendered fields (O10).
8. **Tests:**
   - `create_outreach` twice, same args ⇒ one row, one draft, `already_exists` (Critical Test #4).
   - A mailbox where job A and job B share a subject ⇒ B does **not** adopt A's draft (guards O2).
   - Exceeding `max_outreach_per_day` ⇒ `status="capped"`, **zero** Gmail calls.
   - A contact email containing `\r\n` ⇒ no second header line in the raw message (guards O8).
   - `/jobs/{id}/send-email` ⇒ refused unless the approval gate and `ALLOW_SEND` both pass (guards O1).

---

## 6. Open questions

- Is `POST /jobs/{id}/send-email` intentional and documented, or a leftover legacy surface? It is the
  only code in the app that can send mail on the user's behalf, and it is not mentioned in `CLAUDE.md`.
- Should the follow-up be per-audience (one per thread) rather than one per job (O9)?
- `load_sequences` raises `ValueError` when the YAML is missing a required sequence (`outreach.py:94`) but
  the router does not catch it — a broken config becomes a 500 on every outreach call. Fail-loud is
  right; a clean 503 would be better.
