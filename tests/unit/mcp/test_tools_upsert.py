"""Unit tests for mcp/tools.py upsert_people/upsert_companies — mocked Notion client."""

from unittest.mock import AsyncMock

from pydantic import SecretStr

from notion_pilot.mcp.models import CompanyRecord, PersonRecord
from notion_pilot.mcp.session import SyncerSession
from notion_pilot.mcp.tools import upsert_companies, upsert_people
from notion_pilot.shared.config import Settings


def _settings() -> Settings:
    return Settings(
        notion_token=SecretStr("fake-token"),
        notion_telegram_msg_database_id="fake-db",
        notion_people_data_source_id="fake-people-ds",
        notion_companies_data_source_id="fake-companies-ds",
    )


async def _loaded_session(existing_people=None, existing_companies=None) -> SyncerSession:
    session = SyncerSession(_settings())
    monkeypatch_load = AsyncMock()
    session.company_syncer.load_snapshot = monkeypatch_load
    session.people_syncer.load_snapshot = monkeypatch_load
    session.company_syncer._id_to_name = dict(existing_companies or {})
    session.company_syncer._name_to_id = {
        v.lower(): k for k, v in (existing_companies or {}).items()
    }
    session.people_syncer._existing = list(existing_people or [])
    await session.ensure_loaded()
    return session


async def test_upsert_people_dry_run_does_not_write(monkeypatch):
    session = await _loaded_session()
    upsert_mock = AsyncMock()
    monkeypatch.setattr(session.people_syncer, "upsert", upsert_mock)

    result = await upsert_people(
        session, [PersonRecord(name="Jean Dupont", company="EDF")], confirm=False
    )

    upsert_mock.assert_not_called()
    assert result.results[0].status == "would_create"
    assert result.summary == {"would_create": 1}


async def test_upsert_people_dry_run_reports_existing_match():
    session = await _loaded_session(
        existing_people=[{"name": "Jean Dupont", "company": "EDF", "page_id": "p1"}]
    )

    result = await upsert_people(
        session, [PersonRecord(name="Jean Dupont", company="EDF")], confirm=False
    )

    assert result.results[0].status == "would_skip"
    assert result.results[0].matched_name == "Jean Dupont"


async def test_upsert_people_confirm_true_writes(monkeypatch):
    session = await _loaded_session()
    from notion_pilot.crm.syncer import UpsertResult

    upsert_mock = AsyncMock(return_value=UpsertResult(status="created", page_id="new-id"))
    monkeypatch.setattr(session.people_syncer, "upsert", upsert_mock)

    result = await upsert_people(
        session, [PersonRecord(name="Jean Dupont", company="EDF")], confirm=True
    )

    upsert_mock.assert_awaited_once()
    assert result.results[0].status == "created"
    assert result.results[0].page_id == "new-id"
    assert result.success_count == 1
    assert result.fail_count == 0


async def test_upsert_people_batch_continues_after_one_error(monkeypatch):
    session = await _loaded_session()
    from notion_pilot.crm.syncer import UpsertResult

    async def flaky_upsert(person):
        if person.name == "Broken Record":
            raise RuntimeError("Notion API timeout")
        return UpsertResult(status="created", page_id="ok-id")

    monkeypatch.setattr(session.people_syncer, "upsert", flaky_upsert)

    result = await upsert_people(
        session,
        [
            PersonRecord(name="Broken Record", company="EDF"),
            PersonRecord(name="Fine Record", company="EDF"),
        ],
        confirm=True,
    )

    assert result.fail_count == 1
    assert result.success_count == 1
    assert result.results[0].status == "error"
    assert "Notion API timeout" in result.results[0].error_message
    assert result.results[1].status == "created"


async def test_upsert_companies_dry_run_reports_would_create():
    session = await _loaded_session(existing_companies={"id-edf": "EDF"})

    result = await upsert_companies(session, [CompanyRecord(name="OVHcloud")], confirm=False)

    assert result.results[0].status == "would_create"


async def test_upsert_companies_dry_run_reports_matched():
    # "Acme Corp." (trailing period only) reliably scores >=85 against "Acme Corp"
    # under the existing plain token_sort_ratio matcher; "EDF SA" vs "EDF" does not
    # (~67), so it isn't a valid fixture for the >=85 threshold.
    session = await _loaded_session(existing_companies={"id-acme": "Acme Corp"})

    result = await upsert_companies(session, [CompanyRecord(name="Acme Corp.")], confirm=False)

    assert result.results[0].status == "matched"
    assert result.results[0].matched_name == "Acme Corp"


async def test_upsert_companies_confirm_true_writes(monkeypatch):
    session = await _loaded_session()
    get_or_create_mock = AsyncMock(return_value="new-company-id")
    monkeypatch.setattr(session.company_syncer, "get_or_create", get_or_create_mock)

    result = await upsert_companies(session, [CompanyRecord(name="OVHcloud")], confirm=True)

    get_or_create_mock.assert_awaited_once_with("OVHcloud")
    assert result.results[0].status == "created"
    assert result.results[0].page_id == "new-company-id"
