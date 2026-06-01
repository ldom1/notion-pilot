# tests/unit/crm/test_setup_wizard.py
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from notion_pilot.crm.conv_state import ConvState
from notion_pilot.crm.setup_wizard import (
    SETUP_STATE_ASK_PARENT,
    SETUP_STATE_ASK_SCOPE,
    SETUP_STATE_ASK_TOKEN,
    advance_setup,
    start_setup,
)


def _settings(has_token: bool = True):
    s = MagicMock()
    if has_token:
        s.notion_token = MagicMock()
        s.notion_token.get_secret_value.return_value = "secret_test"
    else:
        s.notion_token = None
    return s


@pytest.mark.asyncio
async def test_start_setup_skips_token_if_configured():
    state, msg = await start_setup(42, _settings(has_token=True))
    assert state.pending_field == SETUP_STATE_ASK_SCOPE
    assert any(word in msg.lower() for word in ["crm", "inbox", "setup", "what"])


@pytest.mark.asyncio
async def test_start_setup_asks_token_if_missing():
    state, msg = await start_setup(42, _settings(has_token=False))
    assert state.pending_field == SETUP_STATE_ASK_TOKEN
    assert "token" in msg.lower()


@pytest.mark.asyncio
async def test_advance_token_step_valid():
    state = ConvState(
        chat_id=42, command="setup", collected={}, pending_field=SETUP_STATE_ASK_TOKEN
    )
    with patch("notion_pilot.crm.setup_wizard._validate_notion_token", return_value=True):
        new_state, msg = await advance_setup(state, "secret_valid", _settings(has_token=False))
    assert new_state is not None
    assert new_state.pending_field == SETUP_STATE_ASK_SCOPE


@pytest.mark.asyncio
async def test_advance_token_step_invalid_increments_attempts():
    state = ConvState(
        chat_id=42,
        command="setup",
        collected={"attempts": "1"},
        pending_field=SETUP_STATE_ASK_TOKEN,
    )
    with patch("notion_pilot.crm.setup_wizard._validate_notion_token", return_value=False):
        new_state, msg = await advance_setup(state, "bad_token", _settings(has_token=False))
    assert new_state is not None
    assert new_state.collected.get("attempts") == "2"
    assert any(c in msg for c in ["❌", "invalid", "Invalid"])


@pytest.mark.asyncio
async def test_advance_token_step_max_retries_aborts():
    state = ConvState(
        chat_id=42,
        command="setup",
        collected={"attempts": "3"},
        pending_field=SETUP_STATE_ASK_TOKEN,
    )
    with patch("notion_pilot.crm.setup_wizard._validate_notion_token", return_value=False):
        new_state, msg = await advance_setup(state, "bad_token", _settings(has_token=False))
    assert new_state is None


@pytest.mark.asyncio
async def test_advance_scope_step():
    state = ConvState(
        chat_id=42, command="setup", collected={}, pending_field=SETUP_STATE_ASK_SCOPE
    )
    new_state, msg = await advance_setup(state, "both", _settings())
    assert new_state is not None
    assert new_state.collected.get("scope") == "both"
    assert new_state.pending_field == SETUP_STATE_ASK_PARENT


@pytest.mark.asyncio
async def test_advance_scope_invalid():
    state = ConvState(
        chat_id=42, command="setup", collected={}, pending_field=SETUP_STATE_ASK_SCOPE
    )
    new_state, msg = await advance_setup(state, "foobar", _settings())
    assert new_state is not None
    assert new_state.pending_field == SETUP_STATE_ASK_SCOPE


@pytest.mark.asyncio
async def test_advance_parent_triggers_creation():
    state = ConvState(
        chat_id=42,
        command="setup",
        collected={"scope": "crm", "token": "secret_test"},
        pending_field=SETUP_STATE_ASK_PARENT,
    )
    mock_crm = MagicMock(companies_id="c1", people_id="p1", deals_id="d1", crm_page_id="pg1")
    with patch(
        "notion_pilot.crm.setup_wizard.create_crm_workspace",
        new_callable=AsyncMock,
        return_value=mock_crm,
    ):
        new_state, msg = await advance_setup(
            state, "https://notion.so/My-Page-550e8400e29b41d4a716446655440000", _settings()
        )
    assert new_state is None
    assert any(s in msg for s in ["NOTION_COMPANIES", "✅"])
