"""Unit tests for the email people pipeline."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from notion_pilot.inbox.people import build_people_pipeline
from notion_pilot.shared.models import IncomingMessage, MediaType


def _settings() -> SimpleNamespace:
    token = MagicMock()
    token.get_secret_value.return_value = "notion-token"
    return SimpleNamespace(
        notion_token=token,
        notion_people_data_source_id="people-ds",
        notion_companies_data_source_id="companies-ds",
    )


def _incoming() -> IncomingMessage:
    return IncomingMessage(
        text="Follow up next week",
        caption=None,
        sender="alice.martin@example.com",
        sent_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        media_type=MediaType.TEXT,
        media=None,
        source_adapter="email",
    )


@pytest.mark.asyncio
async def test_people_pipeline_upserts_through_central_syncer() -> None:
    company_syncer = AsyncMock()
    people_syncer = AsyncMock()
    people_syncer.upsert.return_value.page_id = "person-page"

    with (
        patch("notion_pilot.inbox.people.NotionClient", create=True) as client_cls,
        patch(
            "notion_pilot.inbox.people.NotionCompanySyncer",
            return_value=company_syncer,
            create=True,
        ),
        patch(
            "notion_pilot.inbox.people.NotionPeopleSyncer",
            return_value=people_syncer,
            create=True,
        ),
    ):
        handler = build_people_pipeline(_settings())
        assert handler is not None
        result = await handler(_incoming())
        second = await handler(_incoming())

    assert result == "person-page"
    assert second == "person-page"
    client_cls.assert_called_once_with(auth="notion-token")
    company_syncer.load_snapshot.assert_awaited_once()
    people_syncer.load_snapshot.assert_awaited_once()
    assert people_syncer.upsert.await_count == 2
    person = people_syncer.upsert.await_args_list[0].args[0]
    assert person.name == "Alice Martin"
    assert person.email == "alice.martin@example.com"


def test_people_pipeline_disabled_without_people_data_source() -> None:
    settings = _settings()
    settings.notion_people_data_source_id = None

    assert build_people_pipeline(settings) is None
