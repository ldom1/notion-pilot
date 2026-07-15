"""Unit tests for mcp/tools.py search_people/search_companies — cached-snapshot lookup."""

from unittest.mock import AsyncMock

from pydantic import SecretStr

from notion_pilot.mcp.session import SyncerSession
from notion_pilot.mcp.tools import search_companies, search_people
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
    session.company_syncer.load_snapshot = AsyncMock()
    session.people_syncer.load_snapshot = AsyncMock()
    # "Acme" and "Acme Corp" both score >=60 (the search min-score) against the
    # query "acme" under plain token_sort_ratio, so both appear in an unlimited
    # search — needed to meaningfully exercise the `limit` truncation below.
    # "RTE" scores far lower and is excluded either way.
    session.company_syncer._id_to_name = {"c1": "Acme", "c2": "Acme Corp", "c3": "RTE"}
    session.people_syncer._existing = [
        {"page_id": "p1", "name": "Jean Dupont", "company": "EDF"},
        {"page_id": "p2", "name": "Alice Martin", "company": "Engie"},
    ]
    await session.ensure_loaded()
    return session


async def test_search_companies_fuzzy_match():
    session = await _loaded_session()
    results = await search_companies(session, query="acme", limit=10)
    assert results[0]["name"] == "Acme"
    assert results[0]["page_id"] == "c1"
    assert results[0]["score"] > 80


async def test_search_companies_respects_limit():
    session = await _loaded_session()
    results = await search_companies(session, query="acme", limit=1)
    assert len(results) == 1


async def test_search_people_fuzzy_match():
    session = await _loaded_session()
    results = await search_people(session, query="jean dupont", limit=10)
    assert results[0]["name"] == "Jean Dupont"
    assert results[0]["company"] == "EDF"
    assert results[0]["page_id"] == "p1"


async def test_search_people_no_match_returns_empty():
    session = await _loaded_session()
    results = await search_people(session, query="zzzzzzz nobody", limit=10)
    assert results == []
