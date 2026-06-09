# tests/unit/test_telegram_inference.py
"""Unit tests for smart routing inference in TelegramAdapter."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from notion_pilot.shared.config import Settings

_BASE = dict(
    notion_telegram_msg_database_id="kb-db",
    notion_token="tok",
    telegram_bot_token="tg-tok",
    openrouter_api_key="or-key",
)


_OLIVIER_MSG = (
    "https://www.linkedin.com/in/ocoussau/ : "
    "Olivier Coussau, Veolia, Chapter Lead Appel d'Offres et Développement"
)


_LISA_MSG = "Lisa Schwob, Responsable d'affaires Digital pour Veolia Eau France, Veolia"


@pytest.mark.asyncio
async def test_infer_comma_contact_uses_llm():
    from notion_pilot.shared.adapters.telegram import infer_and_confirm

    s = Settings(**_BASE)
    llm_payload = json.dumps(
        {
            "type": "people",
            "name": "Lisa Schwob",
            "company": "Veolia",
            "position": "Responsable d'affaires Digital pour Veolia Eau France",
        }
    )
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"choices": [{"message": {"content": llm_payload}}]}
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("notion_pilot.shared.adapters.telegram.httpx.AsyncClient", return_value=mock_client):
        result = await infer_and_confirm(_LISA_MSG, s)

    mock_client.post.assert_called_once()
    assert result is not None
    inferred_type, confirmation_text, extracted = result
    assert inferred_type == "people"
    assert "Lisa Schwob" in confirmation_text
    assert extracted["name"] == "Lisa Schwob"


@pytest.mark.asyncio
async def test_infer_linkedin_company_url_bypasses_llm():
    from notion_pilot.shared.adapters.telegram import infer_and_confirm

    s = Settings(**_BASE)
    with patch("notion_pilot.shared.adapters.telegram.httpx.AsyncClient") as mock_client_cls:
        result = await infer_and_confirm("https://www.linkedin.com/company/altotrain/", s)

    mock_client_cls.assert_not_called()
    assert result is not None
    inferred_type, confirmation_text, extracted = result
    assert inferred_type == "company"
    assert "Altotrain" in confirmation_text
    assert extracted["name"] == "Altotrain"


@pytest.mark.asyncio
async def test_infer_linkedin_paste_bypasses_llm():
    from notion_pilot.shared.adapters.telegram import infer_and_confirm

    s = Settings(**_BASE)
    with patch("notion_pilot.shared.adapters.telegram.httpx.AsyncClient") as mock_client_cls:
        result = await infer_and_confirm(_OLIVIER_MSG, s)

    mock_client_cls.assert_not_called()
    assert result is not None
    inferred_type, confirmation_text, extracted = result
    assert inferred_type == "people"
    assert "Olivier Coussau" in confirmation_text
    assert "Veolia" in confirmation_text
    assert "Chapter Lead Appel d'Offres et Développement" in confirmation_text
    assert extracted["name"] == "Olivier Coussau"
    assert extracted["company"] == "Veolia"


@pytest.mark.asyncio
async def test_infer_people_placeholder_name_returns_none():
    from notion_pilot.shared.adapters.telegram import infer_and_confirm

    s = Settings(**_BASE)
    llm_payload = json.dumps(
        {"type": "people", "name": "[PERSON_NAME]", "company": "Veolia", "position": "CTO"}
    )
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"choices": [{"message": {"content": llm_payload}}]}
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("notion_pilot.shared.adapters.telegram.httpx.AsyncClient", return_value=mock_client):
        result = await infer_and_confirm("Contact at Veolia", s)

    assert result is None


@pytest.mark.asyncio
async def test_infer_type_people_returns_confirmation():
    from notion_pilot.shared.adapters.telegram import infer_and_confirm

    s = Settings(**_BASE)
    llm_payload = json.dumps(
        {"type": "people", "name": "Jean Dupont", "company": "Artelys", "position": "CTO"}
    )
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"choices": [{"message": {"content": llm_payload}}]}
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("notion_pilot.shared.adapters.telegram.httpx.AsyncClient", return_value=mock_client):
        result = await infer_and_confirm("Met Jean Dupont from Artelys, CTO", s)

    assert result is not None
    inferred_type, confirmation_text, extracted = result
    assert inferred_type == "people"
    assert "Jean Dupont" in confirmation_text
    assert extracted["name"] == "Jean Dupont"


@pytest.mark.asyncio
async def test_infer_type_knowledge_returns_none():
    from notion_pilot.shared.adapters.telegram import infer_and_confirm

    s = Settings(**_BASE)
    llm_payload = json.dumps({"type": "knowledge", "name": ""})
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"choices": [{"message": {"content": llm_payload}}]}
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("notion_pilot.shared.adapters.telegram.httpx.AsyncClient", return_value=mock_client):
        result = await infer_and_confirm("Interesting article about embeddings", s)

    assert result is None


@pytest.mark.asyncio
async def test_infer_no_llm_key_returns_none():
    from notion_pilot.shared.adapters.telegram import infer_and_confirm

    s = Settings(**{**_BASE, "openrouter_api_key": None})
    result = await infer_and_confirm("Some text", s)
    assert result is None


def test_handle_confirm_yes():
    from notion_pilot.shared.adapters.telegram import _resolve_confirmation

    assert _resolve_confirmation("yes") == "yes"
    assert _resolve_confirmation("oui") == "yes"
    assert _resolve_confirmation("YES") == "yes"


def test_handle_confirm_no():
    from notion_pilot.shared.adapters.telegram import _resolve_confirmation

    assert _resolve_confirmation("no") == "no"
    assert _resolve_confirmation("non") == "no"
    assert _resolve_confirmation("/knowledge") == "no"


def test_handle_confirm_cancel():
    from notion_pilot.shared.adapters.telegram import _resolve_confirmation

    assert _resolve_confirmation("cancel") == "cancel"
    assert _resolve_confirmation("skip") == "cancel"
    assert _resolve_confirmation("rien") == "cancel"
    assert _resolve_confirmation("/cancel") == "cancel"


def test_handle_confirm_unknown():
    from notion_pilot.shared.adapters.telegram import _resolve_confirmation

    assert _resolve_confirmation("maybe") == "unknown"
