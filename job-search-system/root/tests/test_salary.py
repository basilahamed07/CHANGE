import pytest
from unittest.mock import AsyncMock
from app.salary_estimator import estimate_salary


@pytest.mark.asyncio
async def test_estimate_salary():
    mock_client = AsyncMock()
    mock_client.chat = AsyncMock(return_value='{"min": 120000, "max": 160000, "confidence": "medium", "reasoning": "Standard SWE range"}')

    job = {"title": "Senior Engineer", "company": "Acme", "location": "Remote", "description": "Build stuff"}
    result = await estimate_salary(mock_client, job)
    assert result["min"] == 120000
    assert result["max"] == 160000
    assert result["confidence"] == "medium"


@pytest.mark.asyncio
async def test_estimate_salary_no_estimate():
    mock_client = AsyncMock()
    mock_client.chat = AsyncMock(return_value='{"min": 0, "max": 0, "confidence": "none", "reasoning": "Not enough info"}')

    job = {"title": "Mystery Job", "company": "?", "location": "", "description": ""}
    result = await estimate_salary(mock_client, job)
    assert result["min"] == 0
    assert result["confidence"] == "none"
