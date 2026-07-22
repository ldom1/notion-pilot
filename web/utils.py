"""Shared helpers for the web layer."""

from __future__ import annotations

import yaml

from web.config import SCRIPTS_YAML_PATH


def notion_page_url(page_id: str) -> str:
    return f"https://notion.so/{page_id.replace('-', '')}"


def load_scripts() -> list:
    if not SCRIPTS_YAML_PATH.exists():
        return []
    with SCRIPTS_YAML_PATH.open() as f:
        data = yaml.safe_load(f)
    return data.get("scripts", []) if data else []


def extract_title_prop(props: dict) -> str:
    for p in props.values():
        if p.get("type") == "title":
            return "".join(t.get("plain_text", "") for t in p.get("title", []))
    return ""


def extract_text_prop(props: dict, key: str) -> str:
    p = props.get(key, {})
    if p.get("type") == "rich_text":
        return "".join(t.get("plain_text", "") for t in p.get("rich_text", []))
    if p.get("type") == "select" and p.get("select"):
        return str(p["select"]["name"])
    return ""


def extract_relation_ids(props: dict, key: str) -> list[str]:
    p = props.get(key, {})
    if p.get("type") != "relation":
        return []
    return [rel["id"] for rel in p.get("relation", []) if rel.get("id")]


def resolve_company_name(props: dict, company_names: dict[str, str], key: str = "Company") -> str:
    """Resolve a People → Company relation to a display name."""
    for rel_id in extract_relation_ids(props, key):
        if rel_id in company_names:
            return company_names[rel_id]
    return extract_text_prop(props, key)
