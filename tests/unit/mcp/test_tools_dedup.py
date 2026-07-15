"""Unit tests for mcp/tools.py find_duplicates — mocked Notion client."""

from unittest.mock import AsyncMock

from pydantic import SecretStr

from notion_pilot.mcp.session import SyncerSession
from notion_pilot.mcp.tools import find_duplicates
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
    # "Acme Corp." (trailing period only) reliably scores >=85 against "Acme Corp"
    # under the existing plain token_sort_ratio matcher; "EDF"/"EDF S.A." does not (~55).
    session.company_syncer._id_to_name = {
        "id-acme": "Acme Corp",
        "id-acme2": "Acme Corp.",
        "id-rte": "RTE",
    }
    session.people_syncer._existing = [
        {"page_id": "p1", "name": "Jean Dupont", "company": "EDF"},
        {"page_id": "p2", "name": "Jean Dupont", "company": "EDF"},
    ]
    await session.ensure_loaded()
    return session


async def test_find_duplicates_companies_only():
    session = await _loaded_session()
    pairs = await find_duplicates(session, target="companies", threshold=85)
    assert len(pairs) == 1
    assert {pairs[0]["name_a"], pairs[0]["name_b"]} == {"Acme Corp", "Acme Corp."}
    assert pairs[0]["notion_url_a"].startswith("https://www.notion.so/")


async def test_find_duplicates_people_only():
    session = await _loaded_session()
    pairs = await find_duplicates(session, target="people", threshold=85)
    assert len(pairs) == 1
    assert {pairs[0]["page_id_a"], pairs[0]["page_id_b"]} == {"p1", "p2"}


async def test_find_duplicates_both():
    session = await _loaded_session()
    pairs = await find_duplicates(session, target="both", threshold=85)
    assert len(pairs) == 2


async def test_find_duplicates_invalid_target_raises():
    session = await _loaded_session()
    try:
        await find_duplicates(session, target="bogus")
        raised = False
    except ValueError:
        raised = True
    assert raised
