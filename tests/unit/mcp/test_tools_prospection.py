"""Unit tests for mcp/tools.py rank_contacts_for_pitch — mocked ranking call."""

from unittest.mock import AsyncMock

from pydantic import SecretStr

from notion_pilot.crm.prospection import RankedContact
from notion_pilot.mcp.session import SyncerSession
from notion_pilot.mcp.tools import rank_contacts_for_pitch
from notion_pilot.shared.config import Settings


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
        {"page_id": "p1", "name": "Jean Dupont", "company": "EDF", "seniority": "Director"},
        {"page_id": "p2", "name": "Alice Martin", "company": "Engie", "seniority": "Manager"},
    ]
    await session.ensure_loaded()
    return session


async def test_rank_contacts_for_pitch_returns_ranked_list(monkeypatch):
    session = await _loaded_session()
    rank_mock = AsyncMock(
        return_value=[
            RankedContact(
                page_id="p1",
                name="Jean Dupont",
                company="EDF",
                position="",
                score=0.9,
                reasoning="Director-level decision maker",
            )
        ]
    )
    monkeypatch.setattr("notion_pilot.mcp.tools.rank_contacts", rank_mock)

    ranked = await rank_contacts_for_pitch(session, _settings(), pitch="Crystal HPC for utilities")

    rank_mock.assert_awaited_once()
    assert ranked[0]["name"] == "Jean Dupont"
    assert ranked[0]["score"] == 0.9


async def test_rank_contacts_for_pitch_filters_by_company(monkeypatch):
    session = await _loaded_session()
    rank_mock = AsyncMock(return_value=[])
    monkeypatch.setattr("notion_pilot.mcp.tools.rank_contacts", rank_mock)

    await rank_contacts_for_pitch(session, _settings(), pitch="pitch", company="EDF")

    passed_candidates = rank_mock.await_args.args[1]
    assert len(passed_candidates) == 1
    assert passed_candidates[0]["company"] == "EDF"
