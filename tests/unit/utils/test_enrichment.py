"""Unit tests for utils/enrichment.py — all HTTP mocked."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

from notion_pilot.config import Settings
from notion_pilot.utils.enrichment import (
    PersonEnrichment,
    enrich_company,
    enrich_person,
)

_SETTINGS_BASE = dict(notion_token="t", notion_database_id="d")


def _mock_http_client(get_resp=None, post_resp=None):
    mock = AsyncMock()
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=None)
    if get_resp is not None:
        r = MagicMock()
        r.status_code = 200
        r.json.return_value = get_resp
        mock.get = AsyncMock(return_value=r)
    if post_resp is not None:
        r = MagicMock()
        r.status_code = 200
        r.json.return_value = post_resp
        mock.post = AsyncMock(return_value=r)
    return mock


async def test_no_keys_returns_empty():
    s = Settings(**_SETTINGS_BASE)
    with patch("notion_pilot.utils.enrichment.httpx.AsyncClient") as mock_cls:
        result = await enrich_person("Jean Dupont", "EDF", s)
    assert result == PersonEnrichment()
    mock_cls.assert_not_called()


async def test_brave_finds_email():
    s = Settings(**_SETTINGS_BASE, brave_api_key="bk")
    brave_resp = {
        "web": {
            "results": [
                {"description": "Contact at jean.dupont@edf.fr for info.", "url": "https://edf.fr"},
            ]
        }
    }
    with patch("notion_pilot.utils.enrichment.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _mock_http_client(get_resp=brave_resp)
        result = await enrich_person("Jean Dupont", "EDF", s)
    assert result.email == "jean.dupont@edf.fr"
    assert result.source == "brave"


async def test_brave_finds_linkedin():
    s = Settings(**_SETTINGS_BASE, brave_api_key="bk")
    brave_resp = {
        "web": {
            "results": [
                {"description": "See profile.", "url": "https://www.linkedin.com/in/jean-dupont/"},
            ]
        }
    }
    with patch("notion_pilot.utils.enrichment.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _mock_http_client(get_resp=brave_resp)
        result = await enrich_person("Jean Dupont", "EDF", s)
    assert "linkedin.com/in/jean-dupont" in result.linkedin_url


async def test_brave_returns_empty_triggers_perplexity():
    s = Settings(**_SETTINGS_BASE, brave_api_key="bk", openrouter_api_key="ok")
    brave_resp = {"web": {"results": [{"description": "no contact info", "url": "x"}]}}
    perp_payload = json.dumps(
        {
            "email": "j@edf.fr",
            "phone": "",
            "linkedin_url": "",
            "seniority": "",
            "role_type": [],
            "country": "FR",
        }
    )
    perp_resp = {"choices": [{"message": {"content": perp_payload}}]}
    call_count = {"n": 0}

    async def _side_effect_get(*a, **kw):
        r = MagicMock()
        r.status_code = 200
        r.json.return_value = brave_resp
        return r

    async def _side_effect_post(*a, **kw):
        call_count["n"] += 1
        r = MagicMock()
        r.status_code = 200
        r.json.return_value = perp_resp
        return r

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = _side_effect_get
    mock_client.post = _side_effect_post

    with patch("notion_pilot.utils.enrichment.httpx.AsyncClient", return_value=mock_client):
        result = await enrich_person("Jean Dupont", "EDF", s)

    assert result.email == "j@edf.fr"
    assert result.source == "perplexity"
    assert call_count["n"] >= 1


async def test_brave_found_something_skips_perplexity():
    s = Settings(**_SETTINGS_BASE, brave_api_key="bk", openrouter_api_key="ok")
    brave_resp = {
        "web": {
            "results": [
                {"description": "jean.dupont@edf.fr is the contact.", "url": "x"},
            ]
        }
    }
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = brave_resp
    mock_client.get = AsyncMock(return_value=r)
    mock_client.post = AsyncMock()  # should NOT be called

    with patch("notion_pilot.utils.enrichment.httpx.AsyncClient", return_value=mock_client):
        result = await enrich_person(
            "Jean Dupont", "EDF", s, perplexity_model="perplexity/sonar-pro"
        )

    assert result.email == "jean.dupont@edf.fr"
    mock_client.post.assert_not_called()


async def test_network_error_returns_empty():
    s = Settings(**_SETTINGS_BASE, brave_api_key="bk")
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(side_effect=Exception("timeout"))

    with patch("notion_pilot.utils.enrichment.httpx.AsyncClient", return_value=mock_client):
        result = await enrich_person("Jean Dupont", "EDF", s)

    assert result == PersonEnrichment()


async def test_enrich_company_brave_finds_linkedin():
    s = Settings(**_SETTINGS_BASE, brave_api_key="bk")
    brave_resp = {
        "web": {
            "results": [
                {"description": "official page", "url": "https://www.linkedin.com/company/edf/"},
            ]
        }
    }
    with patch("notion_pilot.utils.enrichment.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _mock_http_client(get_resp=brave_resp)
        result = await enrich_company("EDF", s)
    assert "linkedin.com/company/edf" in result.linkedin_url
