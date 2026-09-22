# jobagent

**Personal International AI Job Search + Recruiter Outreach System** for Basil Ahamed H.

Target roles: AI Engineer · Generative AI Engineer · AI Application Developer ·
Python AI Developer · LLM Engineer · RAG Engineer · Agentic AI Engineer · Backend/AI Engineer.

Built on the [CareerPulse](https://github.com/tcpsyn/CareerPulse) (MIT) base,
extended with a candidate-evidence anti-hallucination layer, country strategy
engine, deterministic eligibility + hybrid matching, contact discovery with
confidence scoring, and draft-only Gmail outreach. See
`../docs/ARCHITECTURE_DECISION.md` for the full decision record.

## Status: M1 complete — foundation running

- ✅ FastAPI app + SQLite (WAL) + scheduler + vanilla-JS SPA (CareerPulse base)
- ✅ Unified `JOBAGENT_` config spine with feature flags
- ✅ OpenRouter as default AI provider (all 5 supported: OpenRouter/Anthropic/OpenAI/Gemini/Ollama)
- ✅ `/api/health` + `/api/system/health` (with feature-flag visibility)
- ✅ US-specific tools (salary/tax, offers, career advisor, predictor) behind feature flags, default OFF
- ✅ Gmail draft-only guard (`JOBAGENT_ALLOW_SEND=false` default) — M9 will build on this
- 🔜 M2: candidate evidence store + EvidenceChecker (anti-hallucination gate)

## Quick start

```bash
cp .env.example .env          # add JOBAGENT_OPENROUTER_API_KEY
uv sync                       # or: pip install -e ".[dev]"
uv run uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8085
```

Open http://localhost:8085 — Swagger UI at http://localhost:8085/docs

## Test

```bash
uv run pytest                       # backend
cd app/static && npx vitest run    # frontend (if Node available)
```

## Golden rules (enforced in code + review)

1. **Draft, never send.** Gmail integration creates drafts only; sending needs
   explicit config + per-draft approval.
2. **Never hallucinate.** Generated resumes are gated by the evidence store;
   UNVERIFIED claims never render as VERIFIED (M2+).
3. **Deterministic before LLM.** Filters/dedup/math in Python; LLM for semantics only.
4. **Packages ≠ scraped URLs.** daily_target counts qualifying application packages.
5. **Country = config.** Adding a country = adding one YAML file (M3+).
