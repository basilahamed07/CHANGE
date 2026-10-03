# STAGE-4 SCORE — LIVE SAMPLE RESULTS

> ## ✅ RUN — 2026-10-03, on a COPY of the live DB
>
> `analysis/verify_score_live.py` was executed against a temp copy of the real database. The live
> file was never opened for writing. Raw output: `results/score_summary.json`.
>
> ```
> cd job-search-system/root
> uv run python -u ../analysis/verify_score_live.py            # free, 0 AI calls
> uv run python -u ../analysis/verify_score_live.py --score 3  # 1 batch AI call
> ```

---

## Where the live rows actually are

The deployment is **split across two databases**, which is why the first run reported an empty pool:

| DB | jobs | resumes | ai_settings |
|---|---|---|---|
| `root/data/jobagent.db` | **1245** | 0 | 0 |
| `root/data/users/1-basil/jobagent.db` | 0 | 2 | 1 (deepseek) |

The verifier now picks the DB that actually holds jobs, runs the deterministic **Stage-2 + Stage-3**
passes on the copy (zero AI calls), and borrows the real resume + AI settings from the workspace DB —
so Stage-4 is exercised on real jobs with the real resume.

---

## Result — gate chain and pool

```
Stage-2 classified 42 newly-unclassified jobs; Stage-3 evaluated 1244 jobs
eligible pool: 26   already scored: 0   awaiting score: 26
```

| Field | Value | Question it answers |
|---|---|---|
| `eligible_total` | **26** | real Stage-4 workload after the Stage-3 gate |
| `stage4_input_pool` | **26** | every eligible job is still unscored |
| `already_scored` | 0 | nothing has been scored in this DB yet |
| `stage3_leaked_scores` | **0** ✅ | Stage-3 containment holds — no non-ELIGIBLE job holds a score |
| `d1_fabricated_zero_total` | **0** ✅ | the old padding marker never reached this data |
| `transient_zero_total` | 0 | no `score=0` rows for `clear_failed_scores()` to purge |
| `role_match_false_over_cap` | 0 ✅ | no pre-fix row escaped the 50 cap |

## Result — live scoring against a real model (`--score 3`)

```
scoring 3 real jobs via deepseek/deepseek-flash ...
requested: 3   scored: 3   skipped: 0
scores: #259 → 35 (role_match=false)
        #260 → 63 (role_match=true)
        #295 → 72 (role_match=true)
```

- `scored + skipped == requested` — **the new "omit, never pad" parser held against a real model**:
  every job got a real score, so nothing needed omitting, and nothing was fabricated.
- Scores span a genuine range and `role_match` discriminates (false at 35, true at 63/72) — the
  role-match rule is not trivially `True` on live data.
- **A real resilience path fired live:** the first DeepSeek response returned
  `finish=length, chars=0, reasoning_tokens=1536` (the whole output budget consumed by reasoning).
  `app/ai_client.py` logged `Unusable AI response … escalating output budget`, retried, and the
  second attempt succeeded. This is the first time that escalation has been observed against a real
  provider.

## Duration

30.9 s total (gate chain ≈ 2 s; the single DeepSeek batch call, including the budget escalation, ≈ 29 s).

## The three questions this run had to answer

1. **Is Stage-3 containment holding?** ✅ `stage3_leaked_scores = 0`.
2. **Did D1 fire on real data?** ✅ No — `d1_fabricated_zero_total = 0`.
3. **Does the new parser hold against a real model?** ✅ 3/3 accounted for, 0 fabricated.
