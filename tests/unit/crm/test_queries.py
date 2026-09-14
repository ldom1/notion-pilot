"""Unit tests for crm/queries.py (inbox only)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from notion_pilot.crm.queries import get_inbox_items
from notion_pilot.shared.config import Settings

_BASE = dict(notion_telegram_msg_database_id="kb-db", notion_token="tok")


def _make_httpx_mock(json_data: dict) -> MagicMock:
    """Return a mock httpx.AsyncClient context manager returning json_data."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = json_data
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=mock_resp)
    return mock_client


@pytest.mark.asyncio
async def test_get_inbox_items_filters_not_analysed():
    s = Settings(**_BASE)
    mock_client = _make_httpx_mock(
        {
            "results": [
                {
                    "id": "p2",
                    "properties": {
                        "Name": {"type": "title", "title": [{"plain_text": "Article on RAG"}]},
                        "Status": {"status": {"name": "Not analysed"}},
                    },
                }
            ]
        }
    )
    with patch("notion_pilot.crm.queries.httpx.AsyncClient", return_value=mock_client):
        result = await get_inbox_items(s)
    assert len(result) == 1
    assert result[0]["title"] == "Article on RAG"
