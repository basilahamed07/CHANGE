import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.contact_finder import find_hiring_contact


@pytest.mark.asyncio
async def test_find_contact_from_search():
    """Test finding email from DuckDuckGo search results."""
    mock_html = '<div class="result__body">Contact john@acme.com for engineering positions at Acme Corp</div>'

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = mock_html

    with patch("httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client

        result = await find_hiring_contact("Acme Corp", "Engineer")
        assert result.get("email") == "john@acme.com"
        assert result.get("source") == "web_search"


@pytest.mark.asyncio
async def test_find_contact_filters_noreply():
    """Test that noreply emails are filtered out."""
    mock_html = '<div class="result__body">noreply@acme.com and jobs@acme.com</div>'

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = mock_html

    with patch("httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client

        result = await find_hiring_contact("Acme Corp", "Engineer")
        assert result.get("email") == "jobs@acme.com"


@pytest.mark.asyncio
async def test_find_contact_no_results():
    """Test returns empty dict when nothing found."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "<html><body>nothing here</body></html>"

    with patch("httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client

        result = await find_hiring_contact("NoCompany", "NoJob")
        assert "email" not in result
