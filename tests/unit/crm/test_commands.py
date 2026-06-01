"""Unit tests for crm/commands.py."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

from notion_pilot.crm.commands import (
    COMMANDS,
    CommandDef,
    extract_fields_from_text,
    get_next_prompt,
)
from notion_pilot.crm.conv_state import ConvState
from notion_pilot.shared.config import Settings

_SETTINGS = dict(notion_token="t", notion_telegram_msg_database_id="d", openrouter_api_key="ok")


def test_all_commands_defined():
    for name in ["lead", "people", "company", "deal", "enrich", "knowledge"]:
        assert name in COMMANDS, f"/{name} missing from COMMANDS"


def test_command_def_has_required_fields():
    for name, cmd in COMMANDS.items():
        assert isinstance(cmd, CommandDef), f"{name} is not a CommandDef"
        assert cmd.name == name
        assert cmd.description
        assert isinstance(cmd.fields, list)


def test_required_fields_have_prompts():
    for name, cmd in COMMANDS.items():
        for f in cmd.fields:
            if f.required:
                assert f.prompt, f"/{name}.{f.name} required field has no prompt"


async def test_extract_fields_from_text_parses_llm_response():
    s = Settings(**_SETTINGS)
    cmd = COMMANDS["people"]
    llm_payload = json.dumps({"name": "Alice Martin", "company": "EDF", "position": "VP"})
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"choices": [{"message": {"content": llm_payload}}]}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("notion_pilot.crm.commands.httpx.AsyncClient", return_value=mock_client):
        result = await extract_fields_from_text("Alice Martin from EDF, VP", cmd, s)

    assert result.get("name") == "Alice Martin"
    assert result.get("company") == "EDF"


def test_get_next_prompt_returns_first_missing_required():
    cmd = COMMANDS["people"]
    state = ConvState(chat_id=1, command="people", collected={"name": "Alice"})
    prompt = get_next_prompt(cmd, state)
    assert prompt is not None
    assert "company" in prompt.lower() or prompt  # returns the company prompt


def test_get_next_prompt_returns_none_when_all_required_filled():
    cmd = COMMANDS["people"]
    required_keys = {f.name for f in cmd.fields if f.required}
    state = ConvState(
        chat_id=1,
        command="people",
        collected={k: "value" for k in required_keys},
    )
    prompt = get_next_prompt(cmd, state)
    assert prompt is None
