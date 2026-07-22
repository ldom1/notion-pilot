"""Web-layer constants and per-workspace config helpers.

Per-workspace files live under  web/workspaces/<workspace_id>/
  cockpit_config.json        — DB ID pointers + workspace_url
  workflows.json             — user-composed automation workflows
  conversations/<id>.json   — one file per chat session
  memory.txt                 — workspace context injected into every LLM call
"""

from __future__ import annotations

import json
import pathlib

from notion_pilot.shared.config import Settings

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

_REPO_ROOT = pathlib.Path(__file__).parent.parent
_WEB_DIR = pathlib.Path(__file__).parent
SCRIPTS_YAML_PATH = _REPO_ROOT / "config" / "scripts.yaml"

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
    }
    overrides = load_cockpit_cfg(workspace_id).get("databases", {})
    if cockpit_only:
        return {k: overrides.get(k) for k in base}
    return {k: overrides.get(k) or v for k, v in base.items()}


# ── Workflows (user-composed pipelines) ───────────────────────────────────────


def _workflows_path(workspace_id: str) -> pathlib.Path:
    return _workspace_dir(workspace_id) / "workflows.json"


def load_workflows(workspace_id: str) -> list[dict]:
    path = _workflows_path(workspace_id)
    if path.exists():
        return json.loads(path.read_text())
    return []


def save_workflows(workspace_id: str, workflows: list[dict]) -> None:
    path = _workflows_path(workspace_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(workflows, indent=2))


# ── Conversations (chat session persistence) ──────────────────────────────────


def _conversations_dir(workspace_id: str) -> pathlib.Path:
    return _workspace_dir(workspace_id) / "conversations"


def list_conversations(workspace_id: str) -> list[dict]:
    d = _conversations_dir(workspace_id)
    if not d.exists():
        return []
    sessions = []
    for f in sorted(d.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(f.read_text())
            messages = data.get("messages", [])
            # First user message as context preview
            preview = next(
                (m["content"][:80] for m in messages if m.get("role") == "user"),
                "",
            )
            sessions.append(
                {
                    "id": data["id"],
                    "title": data.get("title", "Conversation"),
                    "created_at": data.get("created_at", ""),
                    "updated_at": data.get("updated_at", ""),
                    "message_count": len(messages),
                    "preview": preview,
                }
            )
        except Exception:
            pass
    return sessions


def load_conversation(workspace_id: str, session_id: str) -> dict | None:
    path = _conversations_dir(workspace_id) / f"{session_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def save_conversation(workspace_id: str, session: dict) -> None:
    d = _conversations_dir(workspace_id)
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{session['id']}.json").write_text(json.dumps(session, indent=2))


def delete_conversation(workspace_id: str, session_id: str) -> bool:
    path = _conversations_dir(workspace_id) / f"{session_id}.json"
    if path.exists():
        path.unlink()
        return True
    return False


# ── Workspace memory (injected into every LLM chat call) ─────────────────────


def _memory_path(workspace_id: str) -> pathlib.Path:
    return _workspace_dir(workspace_id) / "memory.txt"


def load_memory(workspace_id: str) -> str:
    path = _memory_path(workspace_id)
    return path.read_text().strip() if path.exists() else ""


def save_memory(workspace_id: str, text: str) -> None:
    path = _memory_path(workspace_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


# ── Notion API helpers ────────────────────────────────────────────────────────


def notion_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }
