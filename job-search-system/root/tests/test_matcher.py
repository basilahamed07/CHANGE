import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from app.matcher import JobMatcher

SAMPLE_RESUME = """Senior Linux and Infrastructure Engineer with 20+ years...
AWS, Kubernetes, Terraform, Ansible, Python, Docker...
Salesforce Lead Infra Engineer, CVS Health Senior Infra Engineer..."""

SAMPLE_JOB_DESC = """Senior DevOps Engineer - Remote
Requirements: AWS, Kubernetes, Terraform, CI/CD, Python
Salary: $180,000 - $220,000"""

MOCK_CLAUDE_RESPONSE = {
    "score": 88,
    "reasons": ["Strong AWS and K8s match", "20+ years seniority aligns"],
    "concerns": ["No Go experience mentioned"],
    "keywords": ["kubernetes", "terraform", "CI/CD"]
}

@pytest.mark.asyncio
async def test_matcher_scores_job():
    mock_client = MagicMock()
    mock_client.chat = AsyncMock(return_value=json.dumps(MOCK_CLAUDE_RESPONSE))

    matcher = JobMatcher(client=mock_client, resume_text=SAMPLE_RESUME)
    result = await matcher.score_job(SAMPLE_JOB_DESC)
    assert result["score"] == 88
    assert len(result["reasons"]) > 0
    assert "concerns" in result
    assert "keywords" in result

@pytest.mark.asyncio
async def test_matcher_handles_bad_json():
    mock_client = MagicMock()
    mock_client.chat = AsyncMock(return_value="not json")

    matcher = JobMatcher(client=mock_client, resume_text=SAMPLE_RESUME)
    result = await matcher.score_job(SAMPLE_JOB_DESC)
    assert result is None  # Transient errors return None, not score=0

@pytest.mark.asyncio
async def test_matcher_handles_api_error():
    mock_client = MagicMock()
    mock_client.chat = AsyncMock(side_effect=Exception("API down"))

    matcher = JobMatcher(client=mock_client, resume_text=SAMPLE_RESUME)
    result = await matcher.score_job(SAMPLE_JOB_DESC)
    assert result is None  # Transient errors return None, not score=0

def test_matcher_batch_size_is_clamped_to_the_provider_cap():
    """A requested batch may never exceed what ONE completion can hold.

    Regression for the 2026-10-07 scoring redesign: asking for 200 jobs used to
    request `512 * 200` = 102,400 output tokens, which the client clamped to
    the provider cap. The response then truncated, parsing failed, and the batch
    degraded into one API call per job — the opposite of batching.
    """
    mock_client = MagicMock()
    mock_client.provider = "deepseek"
    mock_client._MAX_OUTPUT = {"deepseek": 16384}

    matcher = JobMatcher(client=mock_client, resume_text=SAMPLE_RESUME)
    per_call = matcher.jobs_per_call()
    assert per_call < 100                                   # 16,384 / 230 measured
    assert per_call >= 50                                   # not needlessly timid
    assert matcher.jobs_per_call(target=200) == per_call     # the cap wins
    assert matcher.jobs_per_call(target=5) == 5              # a small wish is honoured

    jobs = [{"id": i, "description": "job"} for i in range(250)]
    batches = matcher.plan_batches(jobs, target=200)
    assert all(len(b) <= per_call for b in batches)
    assert sum(len(b) for b in batches) == 250               # nothing dropped
    assert len(batches) > 1

@pytest.mark.asyncio
async def test_matcher_strips_markdown():
    mock_client = MagicMock()
    mock_client.chat = AsyncMock(return_value=f"```json\n{json.dumps(MOCK_CLAUDE_RESPONSE)}\n```")

    matcher = JobMatcher(client=mock_client, resume_text=SAMPLE_RESUME)
    result = await matcher.score_job(SAMPLE_JOB_DESC)
    assert result["score"] == 88
