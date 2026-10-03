# STAGE-4 SCORE — TEST RESULTS

> ## ✅ EXECUTED — 2026-10-03
>
> ```
> uv run pytest tests/test_scoring.py -q                 → 23 passed in 0.22s
> uv run pytest tests/test_matcher.py tests/test_matcher_extended.py tests/test_scoring.py -q
>                                                        → 37 passed in 0.37s
> ```
>
> Stage-4 is **green**. One pre-existing matcher test had to be updated to the hardened contract —
> see "Test corrected during the run" below.

---

## Test corrected during the run

`tests/test_matcher_extended.py::test_parse_batch_response_missing_entry` asserted the *old*
behaviour — that a job with no usable batch entry receives a fabricated `score=0` fallback. That is
exactly defect **D1**, which the hardening removed: `_parse_batch_response` now omits the job and
logs `left unscored for the next cycle (not fabricated)`. The test was rewritten to assert the new
contract (only the scored job returns; nothing is invented). The test was wrong, not the code.

---

## Inventory — `tests/test_scoring.py` (23 tests)

### D1 — never fabricate a zero (3)
| Test | Asserts |
|---|---|
| `test_d1_missing_entry_is_omitted_not_scored_zero` | 2 entries for 3 jobs ⇒ 2 results; job 3 absent, not `score=0` |
| `test_d1_no_fabricated_zero_concern_is_ever_produced` | the string `"Missing from batch response"` never appears in output |
| `test_d1_batch_that_yields_nothing_usable_falls_back` | a batch that parses but has no usable score falls back to individual |

### D2 — never misattribute a score (5)
| Test | Asserts |
|---|---|
| `test_d2_out_of_order_job_index_still_aligns_correctly` | reordered entries map to the right jobs |
| `test_d2_positional_used_only_when_count_matches` | no index + exact count ⇒ positional order applies |
| `test_d2_count_mismatch_without_index_is_refused` | no index + count mismatch ⇒ `ValueError` |
| `test_d2_out_of_range_index_is_refused` | `job_index` outside range ⇒ `ValueError` |
| `test_d2_count_mismatch_falls_back_rather_than_guessing` | end-to-end: misaligned batch falls back, all 3 jobs scored individually |

### D5 — malformed entries are skipped, not zeroed (4)
| Test | Asserts |
|---|---|
| `test_d5_entry_without_score_is_skipped` | entry with no `score` is dropped |
| `test_d5_non_numeric_score_is_skipped` | `score="high"` is dropped |
| `test_d5_boolean_score_is_not_treated_as_a_number` | `score=True` is dropped, not recorded as 1 |
| `test_score_is_clamped_to_0_100` | `150 → 100`, `-20 → 0` |

### D3b — the cap, enforced in code (6)
| Test | Asserts |
|---|---|
| `test_d3b_explicit_role_mismatch_caps_score_at_50` | `role_match:false, score:80` ⇒ `50` |
| `test_d3b_matching_role_is_not_capped` | `role_match:true, score:88` ⇒ `88` |
| `test_d3_absent_role_match_does_not_invent_a_penalty` | missing `role_match` ⇒ `88` survives |
| `test_d3b_string_false_is_understood` | `"false"` caps; flag reads `False` |
| `test_d3b_cap_also_applies_on_the_single_job_path` | `score_job` caps too, not just batch |
| `test_single_job_path_rejects_response_without_a_score` | `score_job` returns `None` |

### Fallback + regression contracts (5)
| Test | Asserts |
|---|---|
| `test_batch_exception_falls_back_to_individual` | batch exception ⇒ per-job scoring |
| `test_individual_fallback_aborts_after_three_consecutive_failures` | exactly 3 attempts, then abort (not 10) |
| `test_empty_job_list_returns_empty_without_calling_ai` | no AI call for an empty batch |
| `test_fenced_json_is_still_parsed` | ```` ```json ```` fences still stripped |
| `test_batch_attaches_correct_job_ids` | `job_id` attached correctly |

## Regression surface that must stay green

| File | Why it matters |
|---|---|
| `tests/test_matcher.py` | its mock omits `role_match` and asserts `88` survives — the guard on the D3 reclassification |
| `tests/test_matcher_extended.py` | broader matcher behaviour |
| `tests/test_hybrid_matcher.py` | Stage-5 consumes Stage-4's scores; must not be disturbed |
| `tests/test_daily_run.py` | the stage order this stage sits in |
| `tests/test_classification.py`, `tests/test_eligibility.py` | Stages 2–3 must remain green |

## Actual totals (2026-10-03)

| Suite | Result |
|---|---|
| `tests/test_scoring.py` | **23 passed** |
| `tests/test_matcher.py` + `test_matcher_extended.py` + `test_scoring.py` | **37 passed** |
| full backend suite (`uv run pytest -q --timeout=300`) | **1171 passed, 0 failed** |

**Flaky, not a defect (fixed):** `tests/test_scrape_robust.py::test_scrape_heartbeat_updates` failed
once under full-suite load and passes in isolation. Windows' `time.monotonic()` is coarse (~15.6 ms),
so a fast fake scrape cycle can complete inside one tick and both heartbeat reads tie, failing `>`.
The test now waits for a real tick before running — the assertion stays strict. Unrelated to Stage-4.
