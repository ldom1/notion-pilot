"""Unit tests for crm/enrichment.py — mocked HTTP."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from telegram_to_notion.crm.enrichment import find_email


@pytest.fixture
def brave_response():
    return {
        "web": {
            "results": [
                {
                    "description": "Contact Jean Dupont at jean.dupont@edf.fr for more info.",
                    "url": "https://edf.fr/contact",
                },
                {
                    "description": "No email here.",
                    "url": "https://edf.fr/about",
                },
            ]
        }
    }


async def test_find_email_returns_first_match(brave_response):
    mock_resp = MagicMock()
    mock_resp.json.return_value = brave_response
    mock_resp.raise_for_status = MagicMock()

    with patch("telegram_to_notion.crm.enrichment.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        result = await find_email("Jean Dupont", "EDF", "fake-key")

    assert result == "jean.dupont@edf.fr"


async def test_find_email_returns_none_when_no_email():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"web": {"results": [{"description": "No contact info", "url": "x"}]}}
    mock_resp.raise_for_status = MagicMock()

    with patch("telegram_to_notion.crm.enrichment.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        result = await find_email("No One", "Nowhere", "fake-key")

    assert result is None


async def test_find_email_returns_none_on_http_error():
    with patch("telegram_to_notion.crm.enrichment.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(side_effect=Exception("network error"))
        mock_client_cls.return_value = mock_client

        result = await find_email("Jean Dupont", "EDF", "fake-key")

    assert result is None
