# STAGE-7 RESEARCH — AUDIT

> Static audit from reading the code. **Not executed** — the environment's command classifier was
> unavailable throughout, so nothing below was reproduced live. Every finding cites `file:line`.
>
> Stage 7 of `app/daily_run.py:29` (`STAGES`). Upstream: Stage-6 SELECT. Downstream: Stage-8 PACKAGES.
>
> The never-raise provider contract holds. The serious findings are a **cached transient failure**, an
> **SSRF-shaped fetch**, and **provider keys read from process env instead of the per-user workspace**.

---

## 1. What the stage does today

| Piece | Location |
|---|---|
| Contact provider interface + adapters | `app/contact_providers.py:152` (`ContactProvider`), `:174` Hunter, `:217` Apollo, `:252` WebSearch, `:276` Manual |
| Fallback chain | `default_provider_chain` — `contact_providers.py:303` |
| Deterministic role/confidence/rank | `classify_role:53`, `score_confidence:86`, `rank_candidates:127` |
| Research service (cache-first) | `ContactResearchService` — `contact_providers.py:322`; TTL `CACHE_TTL_DAYS = 7` (`:319`) |
| Company enrichment | `app/company_enrichment.py:53`; TTL `COMPANY_CACHE_TTL_DAYS = 30` (`:21`) |
| Router surface | `app/routers/research.py` |
| Persistence | `db.save_contact_research` / `db.get_contact_research`; `db.save_company` / `db.get_company` |

## 2. Contract vs reality

| Claimed | Actual |
|---|---|
| "NEVER raises from find()" (`contact_providers.py:153`) | **True** — the base `find` wraps `_find` in try/except and returns `[]` (`:163-168`) |
| "No paid key ⇒ still works" (`plan`) | **True** — `manual` + `web_search` are always `available`; the chain filters on `.available` (`:346-347`) |
| "Deterministic … no LLM" (`:5-7`) | **True** — role/confidence/rank and all company parsing are pure Python |
| "Cache-first … no re-research within TTL" | **True — and that is the defect** for a transient failure (R4) |
| Provider keys come from workspace settings | **False** — read from `os.getenv` (R1) |
| Company research fetches the company's own site | **False** — it fetches any URL the caller supplies (R9) |

---

## 3. Defects found

### R1 — provider API keys are read from process env, not the per-user workspace
`app/contact_providers.py:182`, `:225`

```python
self.api_key = api_key or os.getenv("JOBAGENT_HUNTER_API_KEY", "")   # :182
self.api_key = api_key or os.getenv("JOBAGENT_APOLLO_API_KEY", "")   # :225
```

`default_provider_chain(db)` (`:303`) builds `HunterProvider()` and `ApolloProvider()` with **no**
arguments, so their keys come from `os.getenv` on the server process. The workspace's own
`scraper_keys` table is never consulted, and `ContactResearchService` (`research.py:29`) passes only the
DB.

**Why it matters:** in a multi-user deployment every user's research runs on one process-wide key (or
none), and a key a user configured in their own settings is ignored. This is the same class of issue the
project treats as critical elsewhere — per-user credentials must resolve per-user.

### R2 — a transient provider failure is cached as a definitive "not_found" for 7 days
`app/contact_providers.py:353-363`, `:398-403`

```python
ranked = rank_candidates(candidates, job.get("title", ""))
status = "found" if ranked else "not_found"
await self.db.save_contact_research(job["id"], job.get("company", ""), status,
                                    used_provider or "none", [...])   # :355
```

Because `find()` swallows every exception and returns `[]` (`:166-168`), a **network error, a 429, a
timeout, or a bad key is indistinguishable from "this company genuinely has no findable contact"**. Both
paths write `status="not_found"` and both are then treated as fresh for `CACHE_TTL_DAYS = 7`
(`_fresh:398`).

**Effect:** one transient failure during a run freezes the job as un-researchable for a week, and the
next six daily runs will happily "succeed" using the cached negative. Only `force=True` clears it, and
nothing in the pipeline passes it.

### R3 — company research will fetch an arbitrary caller-supplied URL (SSRF-shaped)
`app/routers/research.py:78-80`, `app/company_enrichment.py:75-92`

```python
# routers/research.py:78
async def research_company(request: Request, company_name: str,
                           website: str = "", force: bool = False):   # ← caller-controlled
...
# company_enrichment.py:75
base = website_hint or info["website"] or f"https://{_domain_guess(company_name)}"
if base and base.startswith("http"):
    resp = await client.get(base)                                     # server-side fetch
```

`website` is an unvalidated query parameter, and the server performs a `GET` on it. `startswith("http")`
admits `http://localhost:…`, `http://169.254.169.254/…` (cloud metadata), and any internal host the
server can reach. `follow_redirects=True` (`:81`) extends this to any redirect target.

**Why it matters:** an authenticated user can use the server as a request proxy against internal
services and read the response body back through the parsed `description`/`careers_url`/`ai_clues`
fields. Should be restricted to an allowlist/scheme+host policy, or the hint should be dropped.

### R4 — the domain guess can cache a wrong site's links for 30 days
`app/company_enrichment.py:33-35`, `:89-90`, `:21`

```python
def _domain_guess(company: str) -> str:
    slug = re.sub(r"[^a-z0-9]", "", (company or "").lower())
    return f"{slug}.com" if slug else ""
```

When an ATS reports the company as "Acme GmbH" the guess is `acmegmbh.com`; when it is "Acme, Inc." it
is `acmeinc.com`. If the guessed domain resolves to a parked page, a squatter, or an unrelated company,
`extract_links` returns that page's careers/LinkedIn URLs and `research_status` becomes `"complete"`
(`:89-90`) — then `save_company` caches it for **30 days** (`research.py:101`, `:21`).

### R5 — contacts with no email are duplicated on every selection
`app/contact_providers.py:378-390`

```python
dup = next((x for x in existing
            if x.get("email") and c.get("email")
            and x["email"].lower() == c["email"].lower()), None)
if dup: contact_id = dup["id"]
else:   contact_id = await self.db.create_contact(...)   # ← runs when email is ""
```

Dedup is **only** by exact lowercased email. Apollo frequently returns contacts with no email
(`:244` `p.get("email") or ""`), and WebSearch's `find_hiring_contact` may return a name without a
usable address. For those, `c.get("email")` is `""`, the `dup` predicate is short-circuited to `None`,
and **a new `contacts` row is created every time the candidate is selected** — the same person, repeated.

### R6 — `classify_role` is called on the contact's NAME when the title is empty
`app/contact_providers.py:130`

```python
c.role_type = classify_role(c.title or c.name)
```

When a provider supplies no title, the person's *name* is fed to the role regexes. Names are not roles;
this is a deterministic-but-wrong classification. Low impact today (the regexes are role-word-specific),
but it is the wrong input, and it runs before confidence scoring, which weights `role_type` (`:105-107`).

### R7 — `score_confidence`'s `base_by_provider` parameter is dead
`app/contact_providers.py:86-96`, `:131`

`score_confidence(candidate, job_title, base_by_provider=None)` advertises per-provider base overrides,
but the only caller — `rank_candidates:131` — passes two arguments. Per-provider bases are always the
hardcoded `{"hunter": 70, "apollo": 65, "web_search": 40, "manual": 90}`. Either wire it or drop it.

### R8 — a new `httpx.AsyncClient` per provider call
`app/contact_providers.py:199`, `:231`; `app/company_enrichment.py:80`

Each `_find` opens a fresh client inside `async with`. No connection reuse, no retry. Correctness is
unaffected (`find()` catches), but it interacts with R2: a single failed connect becomes a cached
negative.

---

## 4. What holds (verified, not assumed)

- **The never-raise contract is real.** `ContactProvider.find` (`:162-168`) is the only entry, and it
  catches `Exception`, logs at warning, and returns `[]`. Every adapter inherits it.
- **Determinism is real.** `classify_role`, `score_confidence`, `rank_candidates`, `extract_ai_clues`,
  and `extract_links` are pure functions of their inputs. No LLM import in either module.
- **No paid key ⇒ still functional.** `ManualResearchProvider.available = True` (`:284`) and
  `WebSearchProvider.available = True` (`:259`); the chain filters unavailable providers (`:346`).
- **Manual-first ordering is intentional and implemented** — `default_provider_chain` puts Basil's own
  contacts first (`:305`) and `research` breaks on the first provider with results (`:352`).
- **Per-user data isolation is correct** — `ManualResearchProvider` reads `db.get_contacts()` and the
  router passes the workspace DB (`research.py:29`); contact research is cached per job in the workspace.
- **The cache TTL is genuinely enforced** — `_fresh:398` parses `researched_at` and compares against
  `now - 7d`, and a malformed timestamp fails closed (`except … return False`).

---

## 5. What hardening should do

1. **Resolve provider keys per workspace (R1).** Build the chain from the workspace's `scraper_keys`,
   exactly as the scraping path does, and fall back to env only when the workspace has none — mirroring
   the Gmail-token rule already in the project.
2. **Distinguish "provider failed" from "no contact" (R2).** Let `find()` return an error signal (or have
   the service track which providers *errored*), and **do not persist a fresh `not_found`** when any
   provider errored. Cache only a clean negative.
3. **Constrain the company fetch (R3).** Validate `website` against an allowlist or drop the parameter;
   disable redirects or re-validate the final URL; refuse private/link-local hosts.
4. **Only cache a domain guess when it proves out (R4)** — e.g. require the page to actually mention the
   company name before trusting its links, and record `website_source: "hint" | "legacy" | "guess"`.
5. **Dedup contacts by more than email (R5)** — fall back to (lowercased name, company) when the email
   is empty.
6. **Classify from the title only (R6)**; leave `role_type` as `other` when no title exists.
7. **Wire or delete `base_by_provider` (R7).**
8. **Tests:**
   - A provider that raises ⇒ the job is **not** cached as `not_found` (guards R2).
   - `website="http://169.254.169.254/"` ⇒ rejected, zero fetch (guards R3).
   - Select the same emailless candidate twice ⇒ exactly **one** `contacts` row (guards R5).
   - Every provider raising ⇒ `research()` returns `status="not_found"` and never raises (the plan's
     critical test — verifies the existing contract).
   - Two runs, same inputs ⇒ identical `confidence` and identical candidate order (determinism).

---

## 6. Open questions

- Should a `not_found` be cached at all, or only a `found`? Re-researching every job daily is cheap for
  `manual` (local DB) but not for Hunter/Apollo (paid quota) — the TTL exists for a reason. A shorter
  negative TTL (e.g. 1 day) may be the honest compromise.
- `enrich_company` never records **which** source produced each field. Combined with R4, a 30-day cache
  entry cannot be audited after the fact.
- `WebSearchProvider` depends on `app/contact_finder.find_hiring_contact`, whose own failure mode was not
  audited here — its `[]`/exception behavior feeds directly into R2.
