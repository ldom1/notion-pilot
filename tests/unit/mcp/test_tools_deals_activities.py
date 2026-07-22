"""Unit tests for mcp/tools.py upsert_deal/log_activity/get_activities_tool."""

from datetime import date
from unittest.mock import AsyncMock

import pytest
from pydantic import SecretStr

from notion_pilot.mcp.models import ActivityInput, DealInput
from notion_pilot.mcp.session import SyncerSession
from notion_pilot.mcp.tools import get_activities_tool, log_activity, upsert_deal
from notion_pilot.shared.config import Settings


def _settings(**overrides) -> Settings:
    fields = {
        "notion_token": SecretStr("fake-token"),
        "notion_telegram_msg_database_id": "fake-db",
        "notion_people_data_source_id": "fake-people-ds",
        "notion_companies_data_source_id": "fake-companies-ds",
        "notion_deals_database_id": "fake-deals-db",
        "notion_activities_database_id": "fake-activities-db",
        **overrides,
    }
    return Settings(**fields)


async def _loaded_session(
    settings: Settings, existing_deal_titles=None, existing_companies=None
) -> SyncerSession:
    session = SyncerSession(settings)
    load_mock = AsyncMock()
    session.company_syncer.load_notion_snapshot = load_mock
    session.people_syncer.load_notion_snapshot = load_mock
    session.deals_syncer.load_notion_snapshot = load_mock
    session.deals_syncer._snapshot = dict(existing_deal_titles or {})
    session.company_syncer._name_to_id = {
        v.lower(): k for k, v in (existing_companies or {}).items()
    }
    session.company_syncer._id_to_name = dict(existing_companies or {})
    await session.ensure_loaded()
    return session


# ── upsert_deal ──────────────────────────────────────────────────────────────


async def test_upsert_deal_requires_database_id():
    session = await _loaded_session(_settings(notion_deals_database_id=None))
    with pytest.raises(ValueError, match="NOTION_DEALS_DATABASE_ID"):
        await upsert_deal(session, _settings(notion_deals_database_id=None), DealInput(name="X"))


async def test_upsert_deal_dry_run_would_create_defaults_stage():
    session = await _loaded_session(_settings())
    result = await upsert_deal(session, _settings(), DealInput(name="New Deal"))
    assert result == {
        "status": "would_create",
        "title": "New Deal",
        "stage": "Prospect",
        "company_resolution": None,
    }


async def test_upsert_deal_dry_run_would_update_when_title_matches():
    session = await _loaded_session(_settings(), existing_deal_titles={"Existing Deal": "deal-1"})
    result = await upsert_deal(session, _settings(), DealInput(name="Existing Deal"))
    assert result["status"] == "would_update"


async def test_upsert_deal_dry_run_previews_company_resolution_without_writing():
    session = await _loaded_session(_settings(), existing_companies={"c1": "EDF"})
    get_or_create_mock = AsyncMock()
    session.company_syncer.get_or_create = get_or_create_mock

    result = await upsert_deal(session, _settings(), DealInput(name="New Deal", company_name="EDF"))

    get_or_create_mock.assert_not_called()
    assert result["company_resolution"] == "would_match_existing_company"


async def test_upsert_deal_dry_run_previews_new_company():
    session = await _loaded_session(_settings(), existing_companies={"c1": "EDF"})
    result = await upsert_deal(
        session, _settings(), DealInput(name="New Deal", company_name="Totally Unrelated Corp")
    )
    assert result["company_resolution"] == "would_create_new_company"


async def test_upsert_deal_confirm_creates_and_resolves_company(monkeypatch):
    session = await _loaded_session(_settings())
    session.company_syncer.get_or_create = AsyncMock(return_value="company-1")
    session.deals_syncer.upsert = AsyncMock(return_value=("deal-99", True))

    result = await upsert_deal(
        session,
        _settings(),
        DealInput(
            name="New Deal",
            company_name="EDF",
            contact_page_id="person-1",
            stage="Qualified",
            confirm=True,
        ),
    )

    session.company_syncer.get_or_create.assert_awaited_once()
    record = session.deals_syncer.upsert.call_args[0][0]
    assert record.title == "New Deal"
    assert record.stage == "Qualified"
    assert record.company_ids == ["company-1"]
    assert record.people_ids == ["person-1"]
    assert result == {
        "status": "created",
        "page_id": "deal-99",
        "url": "https://www.notion.so/deal99",
    }


# ── log_activity ─────────────────────────────────────────────────────────────


async def test_log_activity_requires_database_id():
    session = await _loaded_session(_settings(notion_activities_database_id=None))
    with pytest.raises(ValueError, match="NOTION_ACTIVITIES_DATABASE_ID"):
        await log_activity(
            session,
            _settings(notion_activities_database_id=None),
            ActivityInput(type="📞 Call"),
        )


async def test_log_activity_dry_run_defaults_title_to_type():
    session = await _loaded_session(_settings())
    result = await log_activity(session, _settings(), ActivityInput(type="📞 Call"))
    assert result == {"status": "would_create", "type": "📞 Call", "title": "📞 Call"}


async def test_log_activity_confirm_creates_with_default_date():
    session = await _loaded_session(_settings())
    session.activities.create = AsyncMock(return_value="activity-1")

    result = await log_activity(
        session, _settings(), ActivityInput(type="📞 Call", deal_page_id="deal-1", confirm=True)
    )

    record = session.activities.create.call_args[0][0]
    assert record.type == "📞 Call"
    assert record.deal_id == "deal-1"
    assert record.date == date.today().isoformat()
    assert result == {
        "status": "created",
        "page_id": "activity-1",
        "url": "https://www.notion.so/activity1",
    }


# ── get_activities_tool ──────────────────────────────────────────────────────


async def test_get_activities_tool_delegates():
    session = await _loaded_session(_settings())
    session.activities.list_recent = AsyncMock(return_value=[{"page_id": "a1"}])

    result = await get_activities_tool(session, _settings(), deal_page_id="deal-1", limit=5)

    session.activities.list_recent.assert_awaited_once_with(deal_id="deal-1", limit=5)
    assert result == [{"page_id": "a1"}]


async def test_get_activities_tool_returns_empty_without_database_id():
    session = await _loaded_session(_settings(notion_activities_database_id=None))
    session.activities.list_recent = AsyncMock()

    result = await get_activities_tool(session, _settings(notion_activities_database_id=None))

    session.activities.list_recent.assert_not_called()
    assert result == []
