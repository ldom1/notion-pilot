"""Unit tests for crm/prospection.py."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

from notion_pilot.crm.prospection import rank_contacts
from notion_pilot.shared.config import Settings

_SETTINGS = dict(notion_token="t", notion_database_id="d", openrouter_api_key="ok")

_CANDIDATES = [
    {
        "name": "Alice Martin",
        "company": "EDF",
        "page_id": "p1",
        "position": "CEO",
        "seniority": "c_suite",
    },
    {"name": "Bob Bernard", "company": "OVHcloud", "page_id": "p2", "position": "Engineer"},
]


async def test_returns_empty_without_api_key():
    s = Settings(notion_token="t", notion_database_id="d")
    result = await rank_contacts("sell HPC", _CANDIDATES, s)
    assert result == []


async def test_returns_empty_with_no_candidates():
    s = Settings(**_SETTINGS)
    result = await rank_contacts("sell HPC", [], s)
    assert result == []


async def test_ranks_and_sorts_by_score():
    s = Settings(**_SETTINGS)
    llm_payload = json.dumps(
        {
            "rankings": [
                {"index": 1, "score": 0.9, "reasoning": "CEO decision maker"},
                {"index": 2, "score": 0.3, "reasoning": "engineer, not a buyer"},
            ]
        }
    )
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"choices": [{"message": {"content": llm_payload}}]}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("notion_pilot.crm.prospection.httpx.AsyncClient", return_value=mock_client):
        result = await rank_contacts("sell HPC", _CANDIDATES, s)

    assert len(result) == 2
    assert result[0].score == 0.9
    assert result[0].name == "Alice Martin"
    assert result[1].score == 0.3


async def test_rank_respects_top_k():
    s = Settings(**_SETTINGS)
    llm_payload = json.dumps(
        {
            "rankings": [
                {"index": 1, "score": 0.9, "reasoning": "top"},
                {"index": 2, "score": 0.3, "reasoning": "bottom"},
            ]
        }
    )
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"choices": [{"message": {"content": llm_payload}}]}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("notion_pilot.crm.prospection.httpx.AsyncClient", return_value=mock_client):
        result = await rank_contacts("sell HPC", _CANDIDATES, s, top_k=1)

    assert len(result) == 1
    assert result[0].name == "Alice Martin"
