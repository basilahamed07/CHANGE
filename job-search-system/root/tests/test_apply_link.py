import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.apply_link_finder import find_apply_url


@pytest.mark.asyncio
async def test_find_apply_url_by_text():
    html = '<html><body><a href="https://company.com/apply/123">Apply Now</a></body></html>'
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = html

    with patch("httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client

        result = await find_apply_url("https://jobs.example.com/listing/456")
        assert result == "https://company.com/apply/123"


@pytest.mark.asyncio
async def test_find_apply_url_relative():
    html = '<html><body><a href="/apply/123">Apply for this job</a></body></html>'
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = html

    with patch("httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client

        result = await find_apply_url("https://jobs.example.com/listing/456")
        assert result == "https://jobs.example.com/apply/123"


@pytest.mark.asyncio
async def test_find_apply_url_none():
    html = '<html><body><p>No apply links here</p></body></html>'
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = html

    with patch("httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client

        result = await find_apply_url("https://jobs.example.com/listing/456")
        assert result is None
