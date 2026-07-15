from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from notion_pilot.shared.config import Settings
from notion_pilot.shared.prosper_client import (
    CompanyEnrichment,
    PersonEnrichment,
    enrich_company,
    enrich_person,
    resolve_company,
)


@pytest.mark.asyncio
async def test_enrich_person_calls_prosper_tool_and_returns_dataclass():
    settings = Settings(
        notion_telegram_msg_database_id="db", prosper_mcp_url="http://fake:8090/sse"
    )
    fake_result = {
        "email": "jean@artelys.com",
        "phone": "",
        "linkedin_url": "",
        "seniority": "",
        "role_type": [],
        "country": "",
        "source": "apollo",
    }

    with patch(
        "notion_pilot.shared.prosper_client._call_prosper_tool",
        new=AsyncMock(return_value=fake_result),
    ) as mock_call:
        result = await enrich_person("Jean Dupont", "Artelys", settings)

    assert isinstance(result, PersonEnrichment)
    assert result.email == "jean@artelys.com"
    assert result.source == "apollo"
    mock_call.assert_awaited_once_with(
        settings, "enrich_person", name="Jean Dupont", company_context="Artelys"
    )


@pytest.mark.asyncio
async def test_enrich_company_calls_prosper_tool_and_returns_dataclass():
    settings = Settings(
        notion_telegram_msg_database_id="db", prosper_mcp_url="http://fake:8090/sse"
    )
    fake_result = {
        "website": "https://artelys.com",
        "linkedin_url": "",
        "size": "",
        "country": "",
        "sector": "",
        "tech_stack": [],
        "crm_status": "",
        "logo_url": "",
        "source": "apollo",
    }

    with patch(
        "notion_pilot.shared.prosper_client._call_prosper_tool",
        new=AsyncMock(return_value=fake_result),
    ):
        result = await enrich_company("Artelys", settings, domain="artelys.com")

    assert isinstance(result, CompanyEnrichment)
    assert result.website == "https://artelys.com"


@pytest.mark.asyncio
async def test_resolve_company_passes_through_raw_dict():
    settings = Settings(
        notion_telegram_msg_database_id="db", prosper_mcp_url="http://fake:8090/sse"
    )
    fake_result = {"matches": [], "best_match": None, "confidence_level": "low"}

    with patch(
        "notion_pilot.shared.prosper_client._call_prosper_tool",
        new=AsyncMock(return_value=fake_result),
    ):
        result = await resolve_company("Nonexistent Corp", settings)

    assert result["confidence_level"] == "low"
