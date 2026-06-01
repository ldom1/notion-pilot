"""Telegram /setup wizard state machine."""

from __future__ import annotations

import httpx
from loguru import logger

from notion_pilot.crm.conv_state import ConvState
from notion_pilot.shared.config import Settings
from notion_pilot.shared.utils.notion_urls import page_id_from_url
from notion_pilot.shared.workspace import create_crm_workspace, create_inbox_workspace

SETUP_STATE_ASK_TOKEN = "ask_token"
SETUP_STATE_ASK_SCOPE = "ask_scope"
SETUP_STATE_ASK_PARENT = "ask_parent"

_MAX_TOKEN_ATTEMPTS = 3
_NOTION_VERSION = "2022-06-28"

_SCOPE_ALIASES = {
    "crm": "crm",
    "1": "crm",
    "inbox": "inbox",
    "knowledge": "inbox",
    "2": "inbox",
    "both": "both",
    "3": "both",
}


async def _validate_notion_token(token: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://api.notion.com/v1/users/me",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Notion-Version": _NOTION_VERSION,
                },
            )
        return r.status_code == 200  # noqa: PLR2004
    except Exception:  # noqa: BLE001
        return False


async def start_setup(chat_id: int, settings: Settings) -> tuple[ConvState, str]:
    """Initiate /setup. Returns the initial ConvState and the first message to send."""
    if settings.notion_token:
        state = ConvState(
            chat_id=chat_id, command="setup", collected={}, pending_field=SETUP_STATE_ASK_SCOPE
        )
        return state, "What do you want to set up?\nReply with: crm, inbox, or both"
    state = ConvState(
        chat_id=chat_id, command="setup", collected={}, pending_field=SETUP_STATE_ASK_TOKEN
    )
    return state, (
        "Please paste your Notion integration token.\n"
        "(Create one at notion.so → Settings → Connections → New integration)"
    )


async def advance_setup(
    state: ConvState, user_text: str, settings: Settings
) -> tuple[ConvState | None, str]:
    """Process a user reply in the /setup flow.

    Returns (new_state, reply). new_state is None when the wizard is done or aborted.
    """
    pending = state.pending_field

    if pending == SETUP_STATE_ASK_TOKEN:
        attempts = int(state.collected.get("attempts", "0")) + 1
        if not await _validate_notion_token(user_text):
            if attempts >= _MAX_TOKEN_ATTEMPTS:
                return None, "❌ Too many failed attempts. /setup aborted."
            state.collected["attempts"] = str(attempts)
            return (
                state,
                f"❌ Invalid token (attempt {attempts}/{_MAX_TOKEN_ATTEMPTS}). Please try again:",
            )
        state.collected["token"] = user_text
        state.collected.pop("attempts", None)
        state.pending_field = SETUP_STATE_ASK_SCOPE
        return (
            state,
            "✅ Token valid!\n\nWhat do you want to set up?\nReply with: crm, inbox, or both",
        )

    if pending == SETUP_STATE_ASK_SCOPE:
        scope = _SCOPE_ALIASES.get(user_text.strip().lower())
        if scope is None:
            return state, "Please reply with crm, inbox, or both:"
        state.collected["scope"] = scope
        state.pending_field = SETUP_STATE_ASK_PARENT
        return state, "Paste your Notion parent page URL or ID:"

    if pending == SETUP_STATE_ASK_PARENT:
        try:
            parent_id = page_id_from_url(user_text.strip())
        except Exception:  # noqa: BLE001
            return state, "❌ Could not parse that page ID. Please paste the URL or raw UUID:"

        token = state.collected.get("token") or (
            settings.notion_token.get_secret_value() if settings.notion_token else None
        )
        if not token:
            return None, "❌ No Notion token available. /setup aborted."

        scope = state.collected.get("scope", "both")
        headers = {
            "Authorization": f"Bearer {token}",
            "Notion-Version": _NOTION_VERSION,
            "Content-Type": "application/json",
        }
        lines: list[str] = ["✅ Done! Add to your .env:\n"]
        try:
            async with httpx.AsyncClient(headers=headers, timeout=60) as client:
                if scope in ("crm", "both"):
                    crm = await create_crm_workspace(client, parent_id)
                    lines += [
                        f"NOTION_COMPANIES_DATA_SOURCE_ID={crm.companies_id}",
                        f"NOTION_PEOPLE_DATA_SOURCE_ID={crm.people_id}",
                        f"NOTION_DEALS_DATABASE_ID={crm.deals_id}",
                    ]
                if scope in ("inbox", "both"):
                    inbox = await create_inbox_workspace(client, parent_id)
                    lines += [
                        f"NOTION_DATABASE_ID={inbox.notions_id}",
                        f"NOTION_IDEAS_DATABASE_ID={inbox.ideas_id}",
                        f"NOTION_TOOLS_DATABASE_ID={inbox.tools_id}",
                        f"NOTION_DATA_TECH_DATABASE_ID={inbox.data_tech_id}",
                    ]
        except Exception as e:  # noqa: BLE001
            logger.exception("setup_wizard: workspace creation failed")
            return None, f"❌ Failed to create workspace: {e}"

        if state.collected.get("token"):
            lines.append("\n⚠️ Don't forget to also add NOTION_TOKEN=<your token> to .env")

        return None, "\n".join(lines)

    return None, "❌ Unknown setup state. /setup aborted."
