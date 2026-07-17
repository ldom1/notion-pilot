"""Unit tests for mcp/tools.py enrich_people/enrich_companies — mocked enrichment calls."""

from unittest.mock import AsyncMock

from pydantic import SecretStr

from notion_pilot.mcp.session import SyncerSession
from notion_pilot.mcp.tools import enrich_companies, enrich_people
from notion_pilot.shared.config import Settings
from notion_pilot.shared.prosper_client import CompanyEnrichment, PersonEnrichment


def _settings() -> Settings:
    return Settings(
        notion_token=SecretStr("fake-token"),
        notion_telegram_msg_database_id="fake-db",
        notion_people_data_source_id="fake-people-ds",
        notion_companies_data_source_id="fake-companies-ds",
    )


async def _loaded_session() -> SyncerSession:
    session = SyncerSession(_settings())
    session.company_syncer.load_notion_snapshot = AsyncMock()
    session.people_syncer.load_notion_snapshot = AsyncMock()
    session.people_syncer._existing = [
        {"page_id": "p1", "name": "Jean Dupont", "company": "EDF"},
    ]
    session.company_syncer._id_to_name = {"c1": "EDF"}
    session.company_syncer.details = {"c1": {}}
    await session.ensure_loaded()
    return session


async def test_enrich_people_dry_run_does_not_write(monkeypatch):
    session = await _loaded_session()
    enrich_mock = AsyncMock(return_value=PersonEnrichment(email="jean@edf.fr", source="apollo"))
    monkeypatch.setattr("notion_pilot.mcp.tools.enrich_person", enrich_mock)
    pages_update = AsyncMock()
    monkeypatch.setattr(session.people_syncer._client.pages, "update", pages_update)

    result = await enrich_people(session, _settings(), page_ids=["p1"], confirm=False)

    pages_update.assert_not_called()
    assert result.results[0].status == "would_enrich"


async def test_enrich_people_confirm_true_writes(monkeypatch):
    session = await _loaded_session()
    enrich_mock = AsyncMock(return_value=PersonEnrichment(email="jean@edf.fr", source="apollo"))
    monkeypatch.setattr("notion_pilot.mcp.tools.enrich_person", enrich_mock)
    pages_update = AsyncMock()
    monkeypatch.setattr(session.people_syncer._client.pages, "update", pages_update)

    result = await enrich_people(session, _settings(), page_ids=["p1"], confirm=True)

    pages_update.assert_awaited_once()
    assert result.results[0].status == "ok"


async def test_enrich_people_no_data_found(monkeypatch):
    session = await _loaded_session()
    enrich_mock = AsyncMock(return_value=PersonEnrichment())
    monkeypatch.setattr("notion_pilot.mcp.tools.enrich_person", enrich_mock)

    result = await enrich_people(session, _settings(), page_ids=["p1"], confirm=True)

    assert result.results[0].status == "no_data"


async def test_enrich_companies_confirm_true_writes(monkeypatch):
    session = await _loaded_session()
    enrich_mock = AsyncMock(return_value=CompanyEnrichment(sector="Utilities", source="apollo"))
    monkeypatch.setattr("notion_pilot.mcp.tools.enrich_company", enrich_mock)
    pages_update = AsyncMock()
    monkeypatch.setattr(session.company_syncer._client.pages, "update", pages_update)

    result = await enrich_companies(session, _settings(), page_ids=["c1"], confirm=True)

    pages_update.assert_awaited_once()
    assert result.results[0].status == "ok"
