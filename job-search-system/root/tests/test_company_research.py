import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.company_research import research_company


@pytest.mark.asyncio
async def test_research_company_with_abstract():
    mock_json_resp = MagicMock()
    mock_json_resp.status_code = 200
    mock_json_resp.json.return_value = {
        "Abstract": "Acme Corp is a technology company.",
        "AbstractURL": "https://acme.com",
    }

    mock_search_resp = MagicMock()
    mock_search_resp.status_code = 200
    mock_search_resp.text = "<html>3.8 out of 5 stars on Glassdoor</html>"

    with patch("httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[mock_json_resp, mock_search_resp])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client

        result = await research_company("Acme Corp")
        assert result["description"] == "Acme Corp is a technology company."
        assert result["website"] == "https://acme.com"
        assert result["glassdoor_rating"] == 3.8


@pytest.mark.asyncio
async def test_research_company_no_data():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {}
    mock_resp.text = "<html>nothing</html>"

    with patch("httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client

        result = await research_company("Unknown Co")
        assert result["name"] == "Unknown Co"
        assert "description" not in result
