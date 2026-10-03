# RESUME AI EVALUATION (Phase-0)

> One-off, **3 AI calls, hard-capped**, run 2026-10-03 against the candidate's own resume with
> DeepSeek (`deepseek-flash`). Script: `analysis/resume_ai_eval.py`. Raw output (private):
> `root/data/resume_ai_eval.json`.
>
> **This file contains no resume text** — only the model's assessments of it.

---

## Run summary

| | |
|---|---|
| Resume | *Basil Ahamed H - AI Engineer Resume.docx* (4,282 chars) |
| Calls | **3 / 3** (cap honoured) |
| 1 — `analyze_resume()` | ATS **90/100**, 12 search terms, 5 issues, 5 tips |
| 2 — critique | 5 strengths, **8 weaknesses**, 10 gaps, 5 rewrites |
| 3 — role fit | 8 target roles scored; **best: Agentic AI Engineer** |

---

## 1. ATS analysis — 90/100

**Issues the model found:**

1. No certifications section (some ATS templates expect one).
2. Overlapping project date ranges under one employer — can confuse chronological parsers.
3. Header carries relocation / work-pass sponsorship wording some ATS treat as non-standard.
4. Acronyms (`RAG`, `MCP`, `NLP-to-SQL`, `RBAC`) not spelled out on first use — weakens keyword match.
5. Only one clearly quantified metric across the experience section.

**Tips:** spell out acronyms on first use; clarify the overlapping dates; add a certifications
section; add more quantified business outcomes; lead the summary with the exact target job title.

## 2. Search terms the resume yields

`AI Engineer · Generative AI Engineer · Machine Learning Engineer · LLM Engineer · NLP Engineer ·
AI Software Engineer · Python Developer · Backend Engineer · AI Solutions Engineer · RAG Engineer ·
AI Application Developer · ML Engineer`

Seniority as read: **mid-level** (~2+ years production).

## 3. Role fit — against the project's target roles

| Rank | Role | Fit |
|---|---|---:|
| 1 | **Agentic AI Engineer** | **92** |
| 2 | AI Engineer | 90 |
| 3 | RAG Engineer | 89 |
| 4 | LLM Engineer | 87 |
| 5 | Generative AI Engineer | 85 |
| 6 | AI Application Developer | 84 |
| 7 | Python AI Developer | 82 |
| 8 | Backend/AI Engineer | 78 |

- **Recommended primary search term:** `Agentic AI Engineer LangGraph MCP`.
- **Roles to de-prioritise:** Backend/AI Engineer, Python AI Developer, Generative AI Engineer.
- Consistent gap across the top roles: little evidence of **cloud infra (AWS/GCP/Kubernetes/
  Terraform)**, **model fine-tuning**, and **agent observability/evaluation** — the areas the resume
  reads thinnest on despite strong agent + RAG depth.

---

## What this means for the roadmap

- The resume is **strongly aligned** with the project's target roles — Agentic AI Engineer and AI
  Engineer are near-ceiling fits. Search-term and scoring weights are well aimed.
- Two concrete, low-risk improvements worth doing: **spell out acronyms on first use** and **add
  quantified outcomes** — both raise ATS keyword match without inventing anything.
- The role-fit result supports keeping **Agentic AI Engineer** as a primary term in
  `config/countries/*.yaml` search expansion.

> ⚠️ **Key hygiene:** `JOBAGENT_DEEPSEEK_API_KEY` was pasted in chat earlier in this work and is now
> in `root/.env`. Treat it as exposed and rotate it.
