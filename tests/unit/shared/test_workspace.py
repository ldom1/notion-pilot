# tests/unit/shared/test_workspace.py
from unittest.mock import AsyncMock, MagicMock

import pytest

from notion_pilot.shared.workspace import (
    CRMWorkspaceResult,
    InboxWorkspaceResult,
    create_crm_workspace,
    create_inbox_workspace,
)


@pytest.mark.asyncio
async def test_create_crm_workspace_returns_ids():
    ids = ["crm-page", "companies-db", "people-db", "deals-db"]
    call_count = 0

    async def fake_post(url, **kwargs):
        nonlocal call_count
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"id": ids[call_count]}
        call_count += 1
        return resp

    async def fake_patch(url, **kwargs):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"id": url.split("/")[-1]}
        return resp

    mock_client = AsyncMock()
    mock_client.post = fake_post
    mock_client.patch = fake_patch

    result = await create_crm_workspace(mock_client, "parent-page-id")
    assert isinstance(result, CRMWorkspaceResult)
    assert result.companies_id == "companies-db"
    assert result.people_id == "people-db"
    assert result.deals_id == "deals-db"


@pytest.mark.asyncio
async def test_create_inbox_workspace_returns_ids():
    ids = ["inbox-page", "notions-db", "ideas-db", "tools-db", "data-tech-db"]
    call_count = 0

    async def fake_post(url, **kwargs):
        nonlocal call_count
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"id": ids[call_count]}
        call_count += 1
        return resp

    async def fake_patch(url, **kwargs):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"id": url.split("/")[-1]}
        return resp

    mock_client = AsyncMock()
    mock_client.post = fake_post
    mock_client.patch = fake_patch

    result = await create_inbox_workspace(mock_client, "parent-page-id")
    assert isinstance(result, InboxWorkspaceResult)
    assert result.notions_id == "notions-db"
    assert result.ideas_id == "ideas-db"
    assert result.tools_id == "tools-db"
    assert result.data_tech_id == "data-tech-db"
