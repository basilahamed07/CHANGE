# STAGE-8 PACKAGES — AUDIT

> Static audit from reading the code. **Not executed** — the environment's command classifier was
> unavailable throughout, so nothing below was reproduced live. Every finding cites `file:line`.
>
> Stage 8 of `app/daily_run.py:29` (`STAGES`). Upstream: Stage-7 RESEARCH. Downstream: Stage-9 OUTREACH.
> **This stage carries the two known live defects** proven in run `2026-09-24_125119`.

---

## 1. What the stage does today

| Piece | Location |
|---|---|
| Build endpoint | `POST /api/packages/jobs/{job_id}/build?refresh=` — `app/routers/packages.py:37` |
| Read one package | `GET /api/packages/jobs/{job_id}` — `packages.py:133` |
| List packages | `GET /api/packages` — `packages.py:145` |
| Download (allowlist) | `GET /api/packages/jobs/{job_id}/download/{filename}` — `packages.py:156` |
| Builder | `ApplicationBuilder.build` — `app/application_builder.py:102` |
| Idempotency key | `PackageInputs.fingerprint()` — `application_builder.py:63` |
| Hard evidence gate | `EvidenceChecker.check` — `app/evidence_checker.py:173` |
| Builder-side backstop | `application_builder.py:107` — raises `EvidenceViolationError` if `evidence_check_ok` is false |

**Two paths exist**, chosen at `packages.py:54` / `packages.py:61`:

- `refresh=true` **and** stored text exists → reuse `app_row["tailored_resume"]` (no AI).
- otherwise → run `tailor.prepare(...)` (AI), then check, then regenerate once on failure.

## 2. Contract vs reality

| Claimed | Actual |
|---|---|
| `refresh=true` is the zero-AI path (`packages.py:6`) | True — but it is **not the default**, and the default destroys reviewed text (D1) |
| "EvidenceChecker gates every generated resume" (Golden Rule 5) | True for skills/numbers/similarity. **False for personal facts** (D2) |
| Same inputs ⇒ no rewrite | True — `fingerprint()` comparison at `application_builder.py:121` |
| Never materialize unverified claims | True — the 422 at `packages.py:95` fires **before** `builder.build` at `packages.py:119` |
| Download is path-safe | True — a literal 5-name allowlist at `packages.py:158` |

---

## 3. Defects found

### D1 — the default build OVERWRITES human-reviewed text, and `refresh` reads backwards
**✅ FIXED 2026-10-03** — see the resolution note at the end of this section.
`app/routers/packages.py:38`, `:54`, `:61-93`

```python
async def build_package(request: Request, job_id: int, refresh: bool = False):
...
    if refresh and app_row and app_row.get("tailored_resume"):
        tailored = app_row["tailored_resume"]          # the reviewed text — the SAFE path
...
    else:
        result = await tailor.prepare(...)             # AI regenerates from scratch
        ...
        await db.update_application(app_id, status="prepared",
                                    tailored_resume=tailored, cover_letter=cover)  # OVERWRITES
```

`refresh` defaults to `False`, so a plain `POST .../build` takes the `else` branch, calls the AI, and
writes the freshly generated text over whatever the human had reviewed and possibly edited
(`packages.py:92-93`). The flag that preserves reviewed work is the one you have to *opt into*.

The name is also inverted: `refresh=true` does the **least** work (reuse stored text). The 503 message at
`packages.py:62` — "run /prepare first or use refresh=true" — shows the author intended `refresh` as the
no-AI path, which is exactly why the endpoint reads backwards to a caller.

**Why it matters:** the packaged resume can differ from what a human approved, and the fingerprint no-ops
on the *new* text, so the divergence is stable rather than self-correcting. This defeats the human review
gate that Golden Rule 6 exists to protect.

**Resolution:** the default was inverted exactly as recommended. `POST /build` with no parameters now
packages the **stored reviewed text, unchanged, at zero AI cost**. Regeneration happens only when the
caller asks for it with an explicit `regenerate=true`, and `refresh=true` is retained as a legacy alias
that maps to the safe default. The duplicate generation block was removed, so there is now exactly one
place that can rewrite the reviewed text. UI: "Build Package (AI)" sends `regenerate=true` (and says so
in its tooltip); "Repackage (free)" packages the stored text. Regression tests:
`test_default_build_packages_stored_text_without_ai`, `test_regenerate_true_overwrites_and_records_provenance`.

### D2 — the evidence gate does not validate PERSONAL FACTS
`app/evidence_checker.py:181-185` (the whole rule set), `:97-170` (the three rules)

`EvidenceChecker.check` enforces exactly three rules:

```python
self._check_numbers(generated_text, failures)       # fabricated_number
self._check_similarity(generated_text, failures)    # unsupported_claim
self._check_thin_lines(generated_text, warnings)    # warning only
if candidate_skill_values:
    self._check_skills(...)                         # unsupported_skill
```

There is **no rule covering the candidate's own circumstances**: relocation target country, visa
sponsorship stance (`welcomed` vs `required`), willingness to relocate, or availability.

These slip through all three existing rules:

- **not a number** — "Amsterdam" and "welcomed" carry no digits;
- **not a skill** — they never appear in `candidate_skill_values`, so `_check_skills` is never consulted;
- **passes similarity** — `_check_similarity` (`:107`) computes containment of the *line's* tokens in the
  corpus. A line like "Open to relocation: Amsterdam, Netherlands (visa sponsorship welcomed)" shares
  nearly all its tokens with the verified "Open to relocation: Singapore (visa sponsorship welcomed)";
  only the country differs, and one differing token does not drop containment below the 0.18 floor.

This is exactly what run `2026-09-24_125119` recorded: the relocation country changed
Singapore → Amsterdam, and sponsorship flipped `welcomed` → `required` between two runs, and the gate
passed both times. A claim the candidate never made reaches a document that is otherwise "evidence-checked".

### D3 — `refresh=true` silently falls through to the AI path
**✅ FIXED 2026-10-03** — a build with no stored text now returns an honest **409**.
`app/routers/packages.py:54`, `:61-63`

The `if refresh and app_row and app_row.get("tailored_resume")` guard requires **stored text**. If
`refresh=true` is passed but no `tailored_resume` exists yet, control falls to the `elif not tailor` /
`else` at `:61-63` and the endpoint runs the full AI tailoring path anyway — spending an AI call on a
request that explicitly asked not to.

**Why it matters:** the flag's contract is "do not call the AI". Silently violating it is the same class
of error as D1 — a caller cannot predict cost or side effects from the parameter.

**Resolution:** there is no longer a fall-through. The default/stored path requires reviewed text and,
when it is absent, returns `409 no_reviewed_text` telling the caller to run `/prepare` or pass
`regenerate=true`. Nothing spends an AI call that was not explicitly requested. Regression tests:
`test_default_build_refuses_when_no_reviewed_text`, `test_regenerate_without_a_tailor_is_an_honest_503`.

### D4 — no `generated_by` provenance in `metadata.json`
**✅ FIXED 2026-10-03** — metadata now records `generated_by`.
`app/application_builder.py:149-170`

The metadata dict records `model`, `inputs_fingerprint`, hashes, and `status`, but not **how** the text
was produced (`stored` vs `regenerated` vs `ai`). Combined with D1, it is impossible to tell from a
package on disk whether its text is what a human reviewed or a fresh AI regeneration.

**Resolution:** `PackageInputs` gained `generated_by` (`"stored" | "regenerated"`) and the builder writes
it into `metadata.json`. It is deliberately **excluded from the fingerprint**, so recording provenance
cannot change package identity or force a rebuild. Asserted by both D1 regression tests.

---

## 4. What hardening should do

1. **Invert the default (D1).** `build` must default to the **stored reviewed text**; regeneration
   requires an explicit `regenerate=true`. Keep `refresh` as a deprecated alias that maps to the safe
   path so nothing already calling it changes meaning.
2. **Add a personal-facts guard (D2).** A new `_check_personal_facts(generated_text, evidence)` rule in
   `app/evidence_checker.py` covering **relocation target country, visa sponsorship stance, willingness
   to relocate, and years of experience**. Each must match the candidate's stored evidence — never the
   job description. On failure: regenerate once → if it fails again, **422**.
3. **Make `refresh=true` honest (D3).** If no stored text exists, return a clear error rather than
   silently spending an AI call.
4. **Record provenance (D4).** Add `generated_by: "stored" | "regenerated" | "ai"` to `metadata.json`.
5. **Regression tests:**
   - `/prepare` then `/build` ⇒ packaged bytes hash-equal the reviewed bytes (Critical test for D1).
   - A generated line swapping the relocation country ⇒ **422** (D2).
   - A generated line flipping sponsorship `welcomed` → `required` ⇒ **422** (D2).
   - `refresh=true` with no stored text ⇒ error, and **zero** AI calls (D3).
   - `metadata.json` carries a truthful `generated_by` (D4).

---

## 5. Open questions

- Is `tailor.prepare` itself idempotent for unchanged inputs, or does it always spend an AI call? Affects
  the cost of the D1 fix.
- Where do the candidate's relocation/visa facts actually live — profile YAML, `eeo_responses`,
  `custom_qa`, or `search_config`? The D2 guard needs an authoritative source to compare against.
- `fingerprint()` (`application_builder.py:63`) omits `company` and `job_title`. Harmless today because
  `_name_guess` returns `""` (`:188`), but worth confirming nothing else renders them.
