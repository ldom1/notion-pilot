"""Web-layer constants and per-workspace config helpers.

Per-workspace files live under  web/workspaces/<workspace_id>/
  cockpit_config.json        — DB ID pointers + workspace_url (+ crm_page_id / crm_views)
"""

from __future__ import annotations

import json
import pathlib

from notion_pilot.shared.config import Settings

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

_WEB_DIR = pathlib.Path(__file__).parent

DB_DEFS: list[dict] = [
    {"key": "notion_people_data_source_id", "label": "People", "icon": "👥", "category": "crm"},
    {
        "key": "notion_companies_data_source_id",
        "label": "Companies",
        "icon": "🏭",
        "category": "crm",
    },
    {"key": "notion_deals_database_id", "label": "Leads", "icon": "💼", "category": "crm"},
    {
        "key": "notion_activities_database_id",
        "label": "Activities",
        "icon": "⚡",
        "category": "crm",
    },
    {"key": "notion_meetings_database_id", "label": "Meetings", "icon": "🤝", "category": "crm"},
    {
        "key": "notion_telegram_msg_database_id",
        "label": "Messages",
        "icon": "💬",
        "category": "inbox",
    },
    {"key": "notion_notions_database_id", "label": "Notions", "icon": "💡", "category": "inbox"},
    {"key": "notion_ideas_database_id", "label": "Ideas", "icon": "🧠", "category": "inbox"},
    {"key": "notion_tools_database_id", "label": "Tools", "icon": "🔧", "category": "inbox"},
    {
        "key": "notion_data_tech_database_id",
        "label": "Data & Tech",
        "icon": "📊",
        "category": "inbox",
    },
]


# ── Per-workspace config directory ────────────────────────────────────────────


def _workspace_dir(workspace_id: str) -> pathlib.Path:
    return _WEB_DIR / "workspaces" / workspace_id


# ── Cockpit config (DB pointers + workspace_url) ──────────────────────────────


def _cockpit_cfg_path(workspace_id: str) -> pathlib.Path:
    return _workspace_dir(workspace_id) / "cockpit_config.json"


def load_cockpit_cfg(workspace_id: str) -> dict:
    path = _cockpit_cfg_path(workspace_id)
    if path.exists():
        return json.loads(path.read_text())
    return {"databases": {}}


def save_cockpit_cfg(workspace_id: str, cfg: dict) -> None:
    path = _cockpit_cfg_path(workspace_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, indent=2))


def resolve_db_ids(
    settings: Settings,
    workspace_id: str,
    *,
    cockpit_only: bool = False,
) -> dict:
    """Cockpit overrides Infisical/env. Web UI passes cockpit_only=True (linked DBs only)."""
    base: dict[str, str | None] = {
        "notion_people_data_source_id": settings.notion_people_data_source_id,
        "notion_companies_data_source_id": settings.notion_companies_data_source_id,
        "notion_deals_database_id": settings.notion_deals_database_id,
        "notion_telegram_msg_database_id": settings.notion_telegram_msg_database_id,
        "notion_notions_database_id": settings.notion_notions_database_id,
        "notion_ideas_database_id": settings.notion_ideas_database_id,
        "notion_tools_database_id": settings.notion_tools_database_id,
        "notion_data_tech_database_id": settings.notion_data_tech_database_id,
        "notion_activities_database_id": settings.notion_activities_database_id,
        "notion_meetings_database_id": settings.notion_meetings_database_id,
    }
    overrides = load_cockpit_cfg(workspace_id).get("databases", {})
    if cockpit_only:
        return {k: overrides.get(k) for k in base}
    return {k: overrides.get(k) or v for k, v in base.items()}


# ── Notion API helpers ────────────────────────────────────────────────────────


def notion_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }
