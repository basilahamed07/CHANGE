"""Stage-4 SCORE — parser hardening tests.

One regression test per defect recorded in docs/score/SCORE_AUDIT.md:

- D1  a job the model did not score must be OMITTED, never padded with a
      fabricated score of 0 (`clear_failed_scores` does not clean these up,
      because its LIKE patterns do not match "Missing from batch response").
- D2  scores must never be attributed to the wrong job when `job_index` is
      missing or the response length does not match.
- D3b the "role_match false ⇒ score ≤ 50" rule is enforced in code, not only
      asked for in the prompt.
- D5  a malformed entry (no usable score) is skipped, not recorded as 0.

Plus the contracts that must not regress: batch→individual fallback, the
3-consecutive-failure abort, and fence stripping.
"""
import json

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.matcher import JobMatcher, ROLE_MATCH_SCORE_CAP

RESUME = "AI engineer. Python, RAG, LangChain, FastAPI, vector databases."


def _client(response) -> MagicMock:
    """AI client returning `response`, or raising it when it is an Exception."""
    client = MagicMock()
    if isinstance(response, Exception):
        client.chat = AsyncMock(side_effect=response)
    else:
        client.chat = AsyncMock(return_value=response)
    return client


def _matcher(response) -> JobMatcher:
    return JobMatcher(client=_client(response), resume_text=RESUME)


def _parser() -> JobMatcher:
    """A matcher used only for the (sync, AI-free) parser."""
    return JobMatcher(client=MagicMock(), resume_text=RESUME)


def _jobs(n: int) -> list[dict]:
    return [{"id": i + 1, "description": f"job description {i}"} for i in range(n)]


def _entry(idx=None, **over) -> dict:
    base = {"score": 70, "role_match": True, "reasons": ["r"], "concerns": [],
            "keywords": ["k"]}
    if idx is not None:
        base["job_index"] = idx
    base.update(over)
    return base


def _batch_json(*entries) -> str:
    return json.dumps(list(entries))


# --------------------------- D1: never fabricate a zero ---------------------------

def test_d1_missing_entry_is_omitted_not_scored_zero():
    """THE D1 regression: 2 entries for 3 jobs ⇒ 2 results, not a padded third."""
    results = _parser()._parse_batch_response(
        _batch_json(_entry(0), _entry(1)), _jobs(3))

    assert len(results) == 2
    assert {r["job_id"] for r in results} == {1, 2}
    # The un-scored job 3 must be absent entirely — not present with score 0.
    assert all(r["score"] != 0 for r in results)


def test_d1_no_fabricated_zero_concern_is_ever_produced():
    results = _parser()._parse_batch_response(_batch_json(_entry(0)), _jobs(4))
    assert "Missing from batch response" not in json.dumps(results)
    assert len(results) == 1


@pytest.mark.asyncio
async def test_d1_batch_that_yields_nothing_usable_falls_back():
    """A batch that parses but produces no usable score must not look successful."""
    individual = json.dumps({"score": 61, "role_match": True, "reasons": [],
                             "concerns": [], "keywords": []})
    client = _client("")  # replaced below
    client.chat = AsyncMock(side_effect=[
        _batch_json(_entry(0, score=None)),   # parses, but has no usable score
        individual,                           # the fallback's per-job call
    ])
    m = JobMatcher(client=client, resume_text=RESUME)
    results = await m.score_batch(_jobs(1))
    assert len(results) == 1 and results[0]["score"] == 61
    assert client.chat.await_count == 2  # batch + exactly one fallback


# ------------------------- D2: never misattribute a score -------------------------

def test_d2_out_of_order_job_index_still_aligns_correctly():
    """Entries returned in a different order must map to the right job."""
    raw = _batch_json(_entry(2, score=90), _entry(0, score=10), _entry(1, score=50))
    results = _parser()._parse_batch_response(raw, _jobs(3))
    assert {r["job_id"]: r["score"] for r in results} == {1: 10, 2: 50, 3: 90}


def test_d2_positional_used_only_when_count_matches():
    """No job_index, but exact count ⇒ the prompt's promised order applies."""
    results = _parser()._parse_batch_response(
        _batch_json(_entry(score=11), _entry(score=22)), _jobs(2))
    assert [r["score"] for r in results] == [11, 22]
    assert [r["job_id"] for r in results] == [1, 2]


def test_d2_count_mismatch_without_index_is_refused():
    """No job_index and a count mismatch ⇒ raise, so the caller can fall back."""
    with pytest.raises(ValueError):
        _parser()._parse_batch_response(_batch_json(_entry(), _entry()), _jobs(3))


def test_d2_out_of_range_index_is_refused():
    with pytest.raises(ValueError):
        _parser()._parse_batch_response(_batch_json(_entry(7)), _jobs(2))


@pytest.mark.asyncio
async def test_d2_count_mismatch_falls_back_rather_than_guessing():
    """End to end: a misaligned batch must not silently mis-score; it falls back."""
    individual = json.dumps({"score": 61, "role_match": True, "reasons": [],
                             "concerns": [], "keywords": []})
    client = MagicMock()
    client.chat = AsyncMock(side_effect=[
        _batch_json(_entry(), _entry()),      # 2 entries for 3 jobs, no indices
        individual, individual, individual,
    ])
    m = JobMatcher(client=client, resume_text=RESUME)
    results = await m.score_batch(_jobs(3))
    assert [r["job_id"] for r in results] == [1, 2, 3]
    assert all(r["score"] == 61 for r in results)


# --------------------------- D5 / robustness: unusable entries --------------------

def test_d5_entry_without_score_is_skipped():
    raw = _batch_json({"job_index": 0, "role_match": True}, _entry(1, score=80))
    results = _parser()._parse_batch_response(raw, _jobs(2))
    assert len(results) == 1
    assert results[0]["job_id"] == 2 and results[0]["score"] == 80


def test_d5_non_numeric_score_is_skipped():
    raw = _batch_json(_entry(0, score="high"), _entry(1, score=80))
    results = _parser()._parse_batch_response(raw, _jobs(2))
    assert len(results) == 1 and results[0]["job_id"] == 2


def test_d5_boolean_score_is_not_treated_as_a_number():
    """`True` is an int in Python — it must not silently become score 1."""
    raw = _batch_json(_entry(0, score=True), _entry(1, score=70))
    results = _parser()._parse_batch_response(raw, _jobs(2))
    assert len(results) == 1 and results[0]["job_id"] == 2


def test_score_is_clamped_to_0_100():
    raw = _batch_json(_entry(0, score=150), _entry(1, score=-20))
    results = _parser()._parse_batch_response(raw, _jobs(2))
    assert [r["score"] for r in results] == [100, 0]


# --------------------------- D3b: the cap is enforced in code ---------------------

def test_d3b_explicit_role_mismatch_caps_score_at_50():
    results = _parser()._parse_batch_response(
        _batch_json(_entry(0, score=80, role_match=False)), _jobs(1))
    assert ROLE_MATCH_SCORE_CAP == 50
    assert results[0]["score"] == 50
    assert results[0]["role_match"] is False


def test_d3b_matching_role_is_not_capped():
    results = _parser()._parse_batch_response(
        _batch_json(_entry(0, score=88, role_match=True)), _jobs(1))
    assert results[0]["score"] == 88


def test_d3_absent_role_match_does_not_invent_a_penalty():
    """Regression guard for the reclassified D3: absence ≠ mismatch."""
    raw = _batch_json({"job_index": 0, "score": 88, "reasons": [],
                       "concerns": [], "keywords": []})
    results = _parser()._parse_batch_response(raw, _jobs(1))
    assert results[0]["score"] == 88
    assert results[0]["role_match"] is True


def test_d3b_string_false_is_understood():
    results = _parser()._parse_batch_response(
        _batch_json(_entry(0, score=90, role_match="false")), _jobs(1))
    assert results[0]["score"] == 50 and results[0]["role_match"] is False


@pytest.mark.asyncio
async def test_d3b_cap_also_applies_on_the_single_job_path():
    m = _matcher(json.dumps({"score": 95, "role_match": False, "reasons": [],
                             "concerns": [], "keywords": []}))
    result = await m.score_job("some job")
    assert result["score"] == 50 and result["role_match"] is False


@pytest.mark.asyncio
async def test_single_job_path_rejects_response_without_a_score():
    m = _matcher(json.dumps({"role_match": True, "reasons": []}))
    assert await m.score_job("some job") is None


# --------------------------- fallback contracts -----------------------------------

@pytest.mark.asyncio
async def test_batch_exception_falls_back_to_individual():
    individual = json.dumps({"score": 55, "role_match": True, "reasons": [],
                             "concerns": [], "keywords": []})
    client = MagicMock()
    client.chat = AsyncMock(side_effect=[Exception("AI down"), individual, individual])
    m = JobMatcher(client=client, resume_text=RESUME)
    results = await m.score_batch(_jobs(2))
    assert len(results) == 2 and all(r["score"] == 55 for r in results)


@pytest.mark.asyncio
async def test_individual_fallback_aborts_after_three_consecutive_failures():
    client = _client(Exception("AI down"))
    m = JobMatcher(client=client, resume_text=RESUME)
    assert await m._fallback_individual(_jobs(10)) == []
    assert client.chat.await_count == 3  # 3 attempts, then abort — not 10


@pytest.mark.asyncio
async def test_empty_job_list_returns_empty_without_calling_ai():
    client = _client("[]")
    m = JobMatcher(client=client, resume_text=RESUME)
    assert await m.score_batch([]) == []
    client.chat.assert_not_awaited()


@pytest.mark.asyncio
async def test_fenced_json_is_still_parsed():
    m = _matcher(f"```json\n{_batch_json(_entry(0, score=77))}\n```")
    results = await m.score_batch(_jobs(1))
    assert results[0]["score"] == 77


@pytest.mark.asyncio
async def test_batch_attaches_correct_job_ids():
    m = _matcher(_batch_json(_entry(0, score=10), _entry(1, score=20)))
    results = await m.score_batch(_jobs(2))
    assert [r["job_id"] for r in results] == [1, 2]
