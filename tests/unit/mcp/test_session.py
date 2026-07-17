"""Unit tests for mcp/session.py — mocked Notion client, no network."""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pydantic import SecretStr

from notion_pilot.mcp.session import SyncerSession
from notion_pilot.shared.config import Settings


def _settings() -> Settings:
    return Settings(
        notion_token=SecretStr("fake-token"),
        notion_telegram_msg_database_id="fake-db",
        notion_people_data_source_id="fake-people-ds",
        notion_companies_data_source_id="fake-companies-ds",
    )


def test_missing_notion_token_raises():
    settings = Settings(notion_telegram_msg_database_id="fake-db")
    with pytest.raises(ValueError, match="NOTION_TOKEN"):
        SyncerSession(settings)


async def test_ensure_loaded_populates_syncers(monkeypatch):
    session = SyncerSession(_settings())

    company_load = AsyncMock()
    people_load = AsyncMock()
    monkeypatch.setattr(session.company_syncer, "load_notion_snapshot", company_load)
    monkeypatch.setattr(session.people_syncer, "load_notion_snapshot", people_load)

    await session.ensure_loaded()

    company_load.assert_awaited_once()
    people_load.assert_awaited_once()


async def test_ensure_loaded_only_loads_once(monkeypatch):
    session = SyncerSession(_settings())
    company_load = AsyncMock()
    people_load = AsyncMock()
    monkeypatch.setattr(session.company_syncer, "load_notion_snapshot", company_load)
    monkeypatch.setattr(session.people_syncer, "load_notion_snapshot", people_load)

    await session.ensure_loaded()
    await session.ensure_loaded()  # second call should not reload

    company_load.assert_awaited_once()
    people_load.assert_awaited_once()


async def test_start_prewarm_is_non_blocking(monkeypatch):
    session = SyncerSession(_settings())

    async def slow_load():
        await asyncio.sleep(0.05)

    monkeypatch.setattr(session.company_syncer, "load_notion_snapshot", slow_load)
    monkeypatch.setattr(session.people_syncer, "load_notion_snapshot", AsyncMock())

    session.start_prewarm()  # must return immediately, not block for 0.05s
    assert session._load_task is not None
    assert not session._load_task.done()
    await session.ensure_loaded()  # now wait for it to actually finish
    assert session._load_task.done()


async def test_refresh_forces_a_new_load(monkeypatch):
    session = SyncerSession(_settings())
    company_load = AsyncMock()
    people_load = AsyncMock()
    monkeypatch.setattr(session.company_syncer, "load_notion_snapshot", company_load)
    monkeypatch.setattr(session.people_syncer, "load_notion_snapshot", people_load)
    session.company_syncer._id_to_name = {"a": "A", "b": "B"}
    session.people_syncer._existing = [{"name": "X", "company": "A", "page_id": "p1"}]

    await session.ensure_loaded()
    people_count, companies_count = await session.refresh()

    assert company_load.await_count == 2  # once via ensure_loaded, once via refresh
    assert people_load.await_count == 2
    assert people_count == 1
    assert companies_count == 2


async def test_start_prewarm_failure_does_not_crash_or_raise(monkeypatch):
    session = SyncerSession(_settings())

    async def failing_load():
        raise RuntimeError("bad credentials")

    monkeypatch.setattr(session.company_syncer, "load_notion_snapshot", failing_load)
    monkeypatch.setattr(session.people_syncer, "load_notion_snapshot", AsyncMock())

    session.start_prewarm()
    await asyncio.sleep(0)  # let the task run and the done_callback fire
    assert session._load_task is not None
    assert session._load_task.done()
    # No exception propagates out here — the failure was logged, not raised.
