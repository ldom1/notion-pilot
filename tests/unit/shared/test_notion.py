"""Unit tests for shared/notion.py — mocked Notion client."""

from unittest.mock import AsyncMock

import pytest

from notion_pilot.shared.notion import NotionDatabaseWriter


class _FakeProps:
    name = "Test Page"

    def to_notion_properties(self):
        return {"Name": {"title": [{"text": {"content": "Test Page"}}]}}


@pytest.mark.asyncio
async def test_create_page_without_children_omits_children_kwarg():
    client = AsyncMock()
    client.pages.create.return_value = {"id": "page-1"}
    writer = NotionDatabaseWriter(client=client, database_id="db-1")

    page_id = await writer.create_page(_FakeProps())

    assert page_id == "page-1"
    assert "children" not in client.pages.create.call_args.kwargs


@pytest.mark.asyncio
async def test_create_page_with_children_passes_them_through():
    client = AsyncMock()
    client.pages.create.return_value = {"id": "page-2"}
    writer = NotionDatabaseWriter(client=client, database_id="db-1")
    blocks = [{"object": "block", "type": "heading_2", "heading_2": {"rich_text": []}}]

    page_id = await writer.create_page(_FakeProps(), children=blocks)

    assert page_id == "page-2"
    assert client.pages.create.call_args.kwargs["children"] == blocks
