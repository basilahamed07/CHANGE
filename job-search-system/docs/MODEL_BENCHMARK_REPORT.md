# MODEL BENCHMARK REPORT — free OpenRouter models vs jobagent's real workload

**Date:** 2026-09-21 16:23 UTC  
**Task:** the app's actual production prompt — Basil's real stored resume → JSON {search_terms, job_titles, key_skills, seniority, summary} (the resume-analysis step).  
**Models tested:** 21 (all models currently flagged `:free` on OpenRouter)  
**Quality score:** 0–5 points (search_terms 1 + job_titles 1 + key_skills 1 + seniority 1 + summary 1; 0.5 if present but out of target range).

## Rankings (working models, best first)

| # | Model | Quality | Analysis latency | Sample search_terms |
|---|-------|--------:|-----------------:|---------------------|
| 1 | `poolside/laguna-s-2.1:free` | 5/5 | 9.5s | AI Engineer, Machine Learning Engineer, LLM Engineer |
| 2 | `nex-agi/nex-n2.5-pro:free` | 5/5 | 11.9s | AI Engineer, Generative AI Engineer, LLM Engineer |
| 3 | `nex-agi/nex-n2.5-mini:free` | 5/5 | 13.2s | AI Engineer, GenAI Engineer, LLM Engineer |
| 4 | `inclusionai/ling-3.0-flash-vl:free` | 5/5 | 30.0s | AI Engineer, RAG, LangGraph |
| 5 | `nvidia/nemotron-3.5-content-safety:free` | 0/5 | 3.3s | — |
| 6 | `inclusionai/ling-3.0-flash-fin:free` | 0/5 | 4.3s | — |
| 7 | `inclusionai/ling-3.0-flash-sante:free` | 0/5 | 6.0s | — |
| 8 | `liquid/lfm-2.5-2.6b:free` | 0/5 | 10.2s | — |
| 9 | `cohere/north-mini-code:free` | 0/5 | 10.9s | — |
| 10 | `dots-studio/dots-3-note-preview:free` | 0/5 | 19.5s | — |
| 11 | `nvidia/nemotron-3-ultra-550b-a55b:free` | 0/5 | 120.2s | — |

## Failures / skipped

| Model | Result |
|-------|--------|
| `google/gemma-4-26b-a4b-it:free` | FAIL (HTTP 429: {"error":{"message":"Provider returned error","code":429,"metadata":{"raw":"google/gemma-4-26b-a4b-it:free is temporaril) |
| `google/gemma-4-31b-it:free` | FAIL (HTTP 429: {"error":{"message":"Provider returned error","code":429,"metadata":{"raw":"google/gemma-4-31b-it:free is temporarily ra) |
| `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` | FAIL (KeyError: 'choices') |
| `nvidia/nemotron-3-super-120b-a12b:free` | FAIL (KeyError: 'choices') |
| `nvidia/nemotron-3.5-lightning:free` | FAIL (ReadTimeout: ) |
| `poolside/laguna-xs-2.1:free` | FAIL (HTTP 429: {"error":{"message":"Provider returned error","code":429,"metadata":{"raw":"poolside/laguna-xs-2.1:free is temporarily r) |
| `qwen/qwen3.8-27b:free` | FAIL (HTTP 429: {"error":{"message":"Provider returned error","code":429,"metadata":{"raw":"qwen/qwen3.8-27b:free is temporarily rate-li) |
| `thinkingmachines/inkling-small:free` | FAIL (HTTP 403: {"error":{"message":"thinkingmachines/inkling-small:free is only available on agentic harnesses. Try plugging it into a ) |
| `thinkingmachines/inkling:free` | FAIL (HTTP 403: {"error":{"message":"thinkingmachines/inkling:free is only available on agentic harnesses. Try plugging it into a coding) |
| `z-ai/glm-5.2:free` | FAIL (HTTP 429: {"error":{"message":"Provider returned error","code":429,"metadata":{"raw":"z-ai/glm-5.2:free is temporarily rate-limite) |

## Summary

- Working models: **11/21**
- Perfect 5/5 quality: **4**
- Median analysis latency: **10.9s**

## Recommendation

Set the app's default model to **`poolside/laguna-s-2.1:free`** (quality 5/5, 9.5s) — it is free, so job scoring/tailoring will not drain the $0.13 paid credit balance.
