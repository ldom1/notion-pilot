"""Enrich Dom Telegram Bot pages → meta-pages in 4 knowledge databases.

Process A (default): triage "Not analysed" source pages → find/create meta-pages → mark Analysed.
Process B (--dedup):  scan AI-authored pages in target DBs, auto-merge duplicates.
Process C (--purge):  archive Analysed source pages older than 14 days.

Usage:
    uv run python scripts/inbox/enrich_knowledge.py --dry-run --limit=5
    uv run python scripts/inbox/enrich_knowledge.py
    uv run python scripts/inbox/enrich_knowledge.py --dedup --dry-run
    uv run python scripts/inbox/enrich_knowledge.py --purge --dry-run
    uv run python scripts/inbox/enrich_knowledge.py --output=data/inbox/run.json
"""

import asyncio
import csv
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
from loguru import logger

from notion_pilot.shared.config import Settings, load_settings

# ── Constants ─────────────────────────────────────────────────────────────────

_STATUS_TODO = "Not analysed"
_STATUS_WIP  = "Analysing ..."
_STATUS_DONE = "Analysed"
_PURGE_DAYS  = 14
_BASE        = "https://api.notion.com/v1"
_NV          = "2022-06-28"
_OUTPUT_DIR  = Path("data/inbox")
_DEDUP_CSV   = _OUTPUT_DIR / "knowledge-dedup-review.csv"

_TITLE_PROP = {"notions": "Name", "ideas": "Nom", "tools": "Name", "data_tech": "Name"}
_DB_ATTR    = {
    "notions":   "notion_notions_database_id",
    "ideas":     "notion_ideas_database_id",
    "tools":     "notion_tools_database_id",
    "data_tech": "notion_data_tech_database_id",
}
_DB_LABEL = {
    "notions":   "Notions",
    "ideas":     "Idées",
    "tools":     "Tools",
    "data_tech": "Data & Technology",
}

# ── CLI helpers ───────────────────────────────────────────────────────────────

def _flag(name: str) -> bool:
    return name in sys.argv

def _arg(prefix: str) -> str | None:
    for a in sys.argv:
        if a.startswith(f"{prefix}="):
            return a.split("=", 1)[1]
    return None

# ── Notion API (raw httpx) ────────────────────────────────────────────────────

def _notion_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": _NV,
        "Content-Type": "application/json",
    }

async def _query_db(
    client: httpx.AsyncClient,
    db_id: str,
    h: dict,
    filter_body: dict | None = None,
    page_size: int = 100,
) -> list[dict]:
    results: list[dict] = []
    body: dict[str, Any] = {"page_size": page_size}
    if filter_body:
        body["filter"] = filter_body
    while True:
        r = await client.post(f"{_BASE}/databases/{db_id}/query", headers=h, json=body)
        r.raise_for_status()
        data = r.json()
        results.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        body["start_cursor"] = data["next_cursor"]
    return results

async def _get_blocks(client: httpx.AsyncClient, page_id: str, h: dict) -> list[dict]:
    blocks: list[dict] = []
    params: dict[str, Any] = {"page_size": 100}
    while True:
        r = await client.get(f"{_BASE}/blocks/{page_id}/children", headers=h, params=params)
        if r.status_code != 200:
            break
        data = r.json()
        blocks.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        params["start_cursor"] = data["next_cursor"]
    return blocks

async def _append_blocks(client: httpx.AsyncClient, page_id: str, children: list[dict], h: dict) -> None:
    r = await client.patch(f"{_BASE}/blocks/{page_id}/children", headers=h, json={"children": children})
    r.raise_for_status()

async def _update_page(client: httpx.AsyncClient, page_id: str, properties: dict, h: dict) -> None:
    r = await client.patch(f"{_BASE}/pages/{page_id}", headers=h, json={"properties": properties})
    r.raise_for_status()

async def _create_page(
    client: httpx.AsyncClient, db_id: str, properties: dict, children: list[dict], h: dict
) -> str:
    r = await client.post(
        f"{_BASE}/pages",
        headers=h,
        json={"parent": {"database_id": db_id}, "properties": properties, "children": children},
    )
    r.raise_for_status()
    return str(r.json()["id"])

async def _archive_page(client: httpx.AsyncClient, page_id: str, h: dict) -> None:
    r = await client.patch(f"{_BASE}/pages/{page_id}", headers=h, json={"archived": True})
    r.raise_for_status()

# ── Block builders ────────────────────────────────────────────────────────────

def _rt(text: str) -> list[dict]:
    return [{"type": "text", "text": {"content": text[:2000]}}]

def _h2(text: str) -> dict:
    return {"object": "block", "type": "heading_2", "heading_2": {"rich_text": _rt(text)}}

def _h3(text: str) -> dict:
    return {"object": "block", "type": "heading_3", "heading_3": {"rich_text": _rt(text)}}

def _p(text: str) -> dict:
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": _rt(text)}}

def _divider() -> dict:
    return {"object": "block", "type": "divider", "divider": {}}

def _blocks_to_text(blocks: list[dict]) -> str:
    lines = []
    for b in blocks:
        btype = b.get("type", "")
        rich = b.get(btype, {}).get("rich_text", [])
        text = "".join(rt.get("plain_text", "") for rt in rich)
        if text.strip():
            lines.append(text)
    return "\n".join(lines)

def _count_text_blocks(blocks: list[dict]) -> int:
    return sum(1 for b in blocks if b.get(b.get("type", ""), {}).get("rich_text"))

def _meta_page_blocks(overview: str, note: str, date: str, refs: list[str]) -> list[dict]:
    blocks = [_h2("Overview"), _p(overview), _divider(), _h2("Notes & Insights"), _h3(f"{date} — from Telegram"), _p(note)]
    if refs:
        blocks += [_divider(), _h2("References")] + [_p(ref) for ref in refs[:5]]
    return blocks

def _note_blocks(note: str, date: str, refs: list[str]) -> list[dict]:
    blocks = [_divider(), _h3(f"{date} — from Telegram"), _p(note)]
    if refs:
        blocks += [_p(f"→ {ref}") for ref in refs[:3]]
    return blocks

def _consolidation_blocks(loser_title: str, loser_text: str, date: str) -> list[dict]:
    return [_divider(), _h3(f"Consolidated from: {loser_title} ({date})"), _p(loser_text[:4000])]

# ── Page property helpers ─────────────────────────────────────────────────────

def _page_title(page: dict) -> str:
    for pdata in page.get("properties", {}).values():
        if pdata.get("type") == "title":
            return "".join(t.get("plain_text", "") for t in pdata.get("title", []))
    return ""

def _page_author(page: dict) -> str:
    prop = page.get("properties", {}).get("Author", {})
    if prop.get("type") == "select" and prop.get("select"):
        return prop["select"].get("name", "")
    return ""

def _page_to_context(page: dict, blocks: list[dict]) -> str:
    props = page.get("properties", {})
    lines = [f"Title: {_page_title(page)}"]
    for pname, pdata in props.items():
        ptype = pdata.get("type", "")
        if ptype == "title":
            continue
        if ptype == "rich_text":
            text = "".join(t.get("plain_text", "") for t in pdata.get("rich_text", []))
            if text:
                lines.append(f"{pname}: {text}")
        elif ptype == "select" and pdata.get("select"):
            lines.append(f"{pname}: {pdata['select']['name']}")
        elif ptype == "multi_select":
            opts = [o["name"] for o in pdata.get("multi_select", [])]
            if opts:
                lines.append(f"{pname}: {', '.join(opts)}")
        elif ptype == "url" and pdata.get("url"):
            lines.append(f"Link: {pdata['url']}")
    body = _blocks_to_text(blocks)
    if body:
        lines.append(f"\nBody:\n{body[:3000]}")
    return "\n".join(lines)

# ── Notion property builders per DB ──────────────────────────────────────────

def _build_properties(db_key: str, canonical_title: str, db_props: dict) -> dict[str, Any]:
    title_key = _TITLE_PROP[db_key]
    props: dict[str, Any] = {
        title_key: {"title": _rt(canonical_title)},
        "Author": {"select": {"name": "IA"}},
    }
    if db_key == "notions":
        if db_props.get("Description"):
            props["Description"] = {"rich_text": _rt(db_props["Description"])}
        if db_props.get("Domain"):
            props["Domain"] = {"select": {"name": db_props["Domain"]}}
        props["Status"] = {"status": {"name": "A compléter"}}
    elif db_key == "ideas":
        tags = db_props.get("Tags", [])
        if isinstance(tags, str):
            tags = [tags]
        if tags:
            props["Tags"] = {"multi_select": [{"name": t} for t in tags[:5]]}
        if db_props.get("Topic"):
            props["Topic"] = {"select": {"name": db_props["Topic"]}}
        props["Priority"] = {"select": {"name": db_props.get("Priority", "🍃 P2")}}
    elif db_key == "data_tech":
        if db_props.get("Type"):
            props["Type"] = {"select": {"name": db_props["Type"]}}
        tags = db_props.get("Tags", [])
        if isinstance(tags, str):
            tags = [tags]
        if tags:
            props["Tags"] = {"multi_select": [{"name": t} for t in tags[:5]]}
        if db_props.get("URL"):
            props["URL"] = {"url": db_props["URL"]}
        props["Priority Level"] = {"select": {"name": db_props.get("Priority Level", "🍃 P2")}}
    # tools: only Name + Author
    return props

# ── LLM helpers ───────────────────────────────────────────────────────────────

def _or_headers(settings: Settings) -> dict[str, str]:
    key = settings.openrouter_api_key.get_secret_value()  # type: ignore[union-attr]
    h = {"Authorization": f"Bearer {key}", "Content-Type": "application/json", "X-Title": settings.openrouter_app_title}
    if settings.openrouter_http_referer:
        h["HTTP-Referer"] = settings.openrouter_http_referer
    return h

def _strip_json(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    text = text.strip()
    arr_s, obj_s = text.find("["), text.find("{")
    if arr_s != -1 and (obj_s == -1 or arr_s < obj_s):
        end = text.rfind("]")
        if end > arr_s:
            return text[arr_s:end + 1]
    obj_s = text.find("{")
    end = text.rfind("}")
    if obj_s != -1 and end > obj_s:
        return text[obj_s:end + 1]
    return text

_TRIAGE_SYSTEM = """\
You are a knowledge triage agent. Analyze a Notion page created from a Telegram message and \
identify ALL distinct subject entities it refers to.

A subject entity is what the message is fundamentally ABOUT — not its content, but its SUBJECT.
Examples:
  "Claude ↔ Obsidian: sessions + lesson.md" → "Claude Code" (data_tech)
  "Tried n8n for automation pipelines"       → "n8n" (tools)
  "Idea: build a habit tracker"              → "Habit Tracker" (ideas)
  "Always document API contracts"            → "Engineering Practices" (notions)

Target databases:
  "notions"   — Personal reflections, methodologies, principles, mental models, practices
  "ideas"     — Project ideas, product concepts, features, experiments
  "tools"     — Software tools, apps, services, APIs, SaaS products, developer utilities
  "data_tech" — Technical concepts, AI/ML, engineering, infrastructure, programming, research

DB-specific properties (fill only what applies):
  notions:
    Description: str (1 sentence)
    Domain: one of ["Les marchés de l'électricité","IT technologies","Climat","Développement","Finance","Energie","Ecriture"]
  ideas:
    Tags: list from ["Perso","Ecriture","Technologies","Formation","Finance","Cinema","Légal","IA","Article","Analyse & étude","Famille","Poésie","Engagement"]
    Topic: one of ["Écriture","Formation","Finance","Cinéma","Légal","Énergie","Social network","Politique","Parentalité","Commercial"]
    Priority: one of ["📛 P0","🔥 P1","🍃 P2","🥐 P3"]
  tools:
    (no additional properties)
  data_tech:
    Type: one of ["Data","Cloud","Product","IA","Web","SaaS Product","SaaS Product DataViz"]
    Tags: list from ["Cloud","Data","Security","Classification","Thalès","Kubernetes","Intelligence Artificielle","Design patterns","Architecture","Scalability","Network","BDD"]
    URL: str (only if a URL is present in the message)
    Priority Level: one of ["📛 P0","🔥 P1","🍃 P2","🥐 P3"]

Return ONLY a JSON array. One object per distinct entity found. Schema:
[{
  "subject_entity": "human-readable entity name",
  "canonical_title": "Short Title (2-5 words, title case)",
  "target_db": "notions|ideas|tools|data_tech",
  "db_properties": {},
  "overview": "1-2 sentence description of what this entity IS",
  "note": "2-4 sentence summary of what this message specifically says about the entity",
  "references": ["url"],
  "needs_review": false
}]"""


async def _llm_triage(context: str, settings: Settings) -> list[dict]:
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{settings.openrouter_url}/chat/completions",
            headers=_or_headers(settings),
            json={
                "model": settings.openrouter_model,
                "messages": [
                    {"role": "system", "content": _TRIAGE_SYSTEM},
                    {"role": "user", "content": f"Page content:\n\n{context[:8000]}"},
                ],
            },
        )
        resp.raise_for_status()
    raw = resp.json()["choices"][0]["message"]["content"]
    data = json.loads(_strip_json(raw))
    return data if isinstance(data, list) else [data]


async def _llm_dedup_confirm(
    title_a: str, text_a: str, title_b: str, text_b: str, settings: Settings
) -> bool:
    prompt = (
        f'Are these two knowledge pages about the SAME subject entity?\n\n'
        f'Page A: "{title_a}"\n{text_a[:800]}\n\nPage B: "{title_b}"\n{text_b[:800]}\n\n'
        'Return ONLY JSON: {"same_entity": true/false}'
    )
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{settings.openrouter_url}/chat/completions",
                headers=_or_headers(settings),
                json={
                    "model": settings.openrouter_model,
                    "response_format": {"type": "json_object"},
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            resp.raise_for_status()
        return bool(json.loads(_strip_json(resp.json()["choices"][0]["message"]["content"])).get("same_entity"))
    except Exception:
        return False


async def _llm_smart_description(current: str, new_note: str, settings: Settings) -> str | None:
    prompt = (
        f"Current description: {current[:400]}\nNew information: {new_note[:400]}\n\n"
        "Does the new information materially change the description? "
        'Return ONLY JSON: {"update": true/false, "new_description": "..."}'
    )
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{settings.openrouter_url}/chat/completions",
                headers=_or_headers(settings),
                json={
                    "model": settings.openrouter_model,
                    "response_format": {"type": "json_object"},
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            resp.raise_for_status()
        data = json.loads(_strip_json(resp.json()["choices"][0]["message"]["content"]))
        return data.get("new_description") if data.get("update") else None
    except Exception:
        return None


async def _llm_cluster_titles(titles: list[str], db_label: str, settings: Settings) -> list[list[str]]:
    titles_text = "\n".join(f"- {t}" for t in titles)
    prompt = (
        f"These are page titles from a '{db_label}' knowledge database.\n"
        f"Group titles that clearly refer to the SAME subject entity (2+ per group only).\n\n"
        f"Titles:\n{titles_text}\n\n"
        'Return ONLY JSON: {"clusters": [["Title A", "Title B"]]}'
    )
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(
                f"{settings.openrouter_url}/chat/completions",
                headers=_or_headers(settings),
                json={
                    "model": settings.openrouter_model,
                    "response_format": {"type": "json_object"},
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            resp.raise_for_status()
        return json.loads(_strip_json(resp.json()["choices"][0]["message"]["content"])).get("clusters", [])
    except Exception:
        return []

# ── Core: handle one entity ───────────────────────────────────────────────────

async def _handle_entity(
    client: httpx.AsyncClient,
    entity: dict,
    db_id: str,
    db_key: str,
    h: dict,
    settings: Settings,
    dry_run: bool,
    csv_rows: list[dict],
    today: str,
) -> dict:
    canonical = entity.get("canonical_title") or entity.get("subject_entity", "?")
    overview  = entity.get("overview", "")
    note      = entity.get("note", "")
    refs      = entity.get("references") or []
    db_props  = entity.get("db_properties") or {}
    title_prop = _TITLE_PROP[db_key]
    search_word = canonical.split()[0]

    # Search target DB
    try:
        candidates = await _query_db(
            client, db_id, h,
            filter_body={"property": title_prop, "title": {"contains": search_word}},
            page_size=10,
        )
    except Exception:
        candidates = []

    ai_pages    = [p for p in candidates if _page_author(p) == "IA"]
    human_pages = [p for p in candidates if _page_author(p) == "Me"]

    # Find surviving AI page ──────────────────────────────────────────────────
    surviving_ai: dict | None = None

    # Exact title match first
    for p in ai_pages:
        if _page_title(p).lower() == canonical.lower():
            surviving_ai = p
            break

    # LLM confirm on first candidate if no exact match
    if surviving_ai is None and ai_pages:
        cand = ai_pages[0]
        cand_blocks = await _get_blocks(client, cand["id"], h)
        if await _llm_dedup_confirm(_page_title(cand), _blocks_to_text(cand_blocks), canonical, note, settings):
            surviving_ai = cand

    # Merge any additional AI duplicates into surviving page
    for extra in [p for p in ai_pages if surviving_ai and p["id"] != surviving_ai["id"]]:
        extra_title  = _page_title(extra)
        extra_blocks = await _get_blocks(client, extra["id"], h)
        if not await _llm_dedup_confirm(_page_title(surviving_ai), "", extra_title, _blocks_to_text(extra_blocks), settings):
            continue
        logger.info("{}MERGE {} → {}", "[DRY] " if dry_run else "", extra_title, _page_title(surviving_ai))
        if not dry_run:
            # Winner = most content
            win_blocks = await _get_blocks(client, surviving_ai["id"], h)
            if _count_text_blocks(extra_blocks) > _count_text_blocks(win_blocks):
                surviving_ai, extra = extra, surviving_ai
                extra_blocks = win_blocks
            loser_text = _blocks_to_text(extra_blocks)
            await _append_blocks(client, surviving_ai["id"], _consolidation_blocks(extra_title, loser_text, today), h)
            await _archive_page(client, extra["id"], h)

    # Flag human page conflicts
    for hp in human_pages:
        hp_url = f"https://notion.so/{hp['id'].replace('-', '')}"
        csv_rows.append({
            "db": _DB_LABEL[db_key],
            "ai_page_title": canonical,
            "ai_page_url": "",
            "human_page_title": _page_title(hp),
            "human_page_url": hp_url,
            "suggested_action": "merge_into_human",
        })
        logger.warning("CONFLICT {} (IA) ↔ {} (Me) → CSV", canonical, _page_title(hp))

    # Create or enrich ────────────────────────────────────────────────────────
    notion_props = _build_properties(db_key, canonical, db_props)
    meta_id: str

    if surviving_ai:
        action  = "enriched"
        meta_id = surviving_ai["id"]
        logger.info("{}ENRICH '{}' in {}", "[DRY] " if dry_run else "", canonical, _DB_LABEL[db_key])
        if not dry_run:
            await _append_blocks(client, meta_id, _note_blocks(note, today, refs), h)
            # Smart description update (notions DB only)
            if db_key == "notions":
                existing_desc = db_props.get("Description", "")
                new_desc = await _llm_smart_description(existing_desc, note, settings)
                if new_desc:
                    await _update_page(client, meta_id, {"Description": {"rich_text": _rt(new_desc)}}, h)
    else:
        action = "created"
        logger.info("{}CREATE '{}' in {}", "[DRY] " if dry_run else "", canonical, _DB_LABEL[db_key])
        if not dry_run:
            meta_id = await _create_page(client, db_id, notion_props, _meta_page_blocks(overview, note, today, refs), h)
        else:
            meta_id = "(dry-run)"

    # Backfill AI URL in last CSV conflict row
    if csv_rows and not csv_rows[-1].get("ai_page_url") and meta_id != "(dry-run)":
        csv_rows[-1]["ai_page_url"] = f"https://notion.so/{meta_id.replace('-', '')}"

    return {
        "subject_entity": entity.get("subject_entity", canonical),
        "canonical_title": canonical,
        "target_db": db_key,
        "meta_page_action": action,
        "meta_page_id": meta_id,
    }

# ── Core: process one source page ────────────────────────────────────────────

async def _process_source_page(
    client: httpx.AsyncClient,
    page: dict,
    settings: Settings,
    h: dict,
    dry_run: bool,
    csv_rows: list[dict],
    today: str,
) -> dict:
    page_id = page["id"]
    title   = _page_title(page)
    result: dict[str, Any] = {"source_page_id": page_id, "source_title": title, "entities": [], "status": "ok"}

    if not dry_run:
        try:
            await _update_page(client, page_id, {"Status": {"status": {"name": _STATUS_WIP}}}, h)
        except Exception as e:
            logger.warning("Could not set WIP on '{}': {}", title, e)

    blocks = []
    try:
        blocks = await _get_blocks(client, page_id, h)
    except Exception:
        pass

    context = _page_to_context(page, blocks)

    try:
        entities = await _llm_triage(context, settings)
    except Exception as e:
        logger.error("Triage failed for '{}': {}", title, e)
        if not dry_run:
            await _update_page(client, page_id, {"Status": {"status": {"name": _STATUS_TODO}}}, h)
        result["status"] = "error"
        result["error"]  = str(e)
        return result

    entity_results = []
    for entity in entities:
        db_key = entity.get("target_db", "data_tech")
        db_id  = getattr(settings, _DB_ATTR.get(db_key, "notion_data_tech_database_id"), None)
        if not db_id:
            logger.warning("DB '{}' not configured, skipping entity '{}'", db_key, entity.get("canonical_title"))
            continue
        try:
            er = await _handle_entity(client, entity, db_id, db_key, h, settings, dry_run, csv_rows, today)
            entity_results.append(er)
        except Exception as e:
            logger.error("Entity '{}' failed: {}", entity.get("canonical_title"), e)
            entity_results.append({"canonical_title": entity.get("canonical_title", "?"), "status": "error", "error": str(e)})

    result["entities"] = entity_results

    # Write summary back to source page
    if entity_results and not dry_run:
        summary = "\n".join(
            f"Subject: {er.get('subject_entity', er.get('canonical_title', '?'))} → "
            f"{er.get('meta_page_action', '?')} meta-page in {_DB_LABEL.get(er.get('target_db', ''), '?')}."
            for er in entity_results
        )
        try:
            await _append_blocks(client, page_id, [_h2("Summary"), _p(summary)], h)
        except Exception as e:
            logger.warning("Could not write summary to '{}': {}", title, e)

    if not dry_run:
        try:
            await _update_page(client, page_id, {"Status": {"status": {"name": _STATUS_DONE}}}, h)
        except Exception as e:
            logger.error("Could not mark '{}' as Analysed: {}", title, e)
            result["status"] = "partial"

    return result

# ── Run modes ─────────────────────────────────────────────────────────────────

async def run_enrich(settings: Settings, h: dict, dry_run: bool, limit: int) -> list[dict]:
    today    = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    csv_rows: list[dict] = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        pages = await _query_db(
            client,
            settings.notion_telegram_msg_database_id,
            h,
            filter_body={"property": "Status", "status": {"equals": _STATUS_TODO}},
        )
        if limit > 0:
            pages = pages[:limit]
        logger.info("Found {} page(s) to enrich{}", len(pages), " (capped)" if limit and len(pages) == limit else "")

        results = []
        for page in pages:
            logger.info("── {!r}", _page_title(page))
            r = await _process_source_page(client, page, settings, h, dry_run, csv_rows, today)
            results.append(r)

    if csv_rows:
        _write_dedup_csv(csv_rows)
    return results


async def run_dedup(settings: Settings, h: dict, dry_run: bool) -> list[dict]:
    today  = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    merges: list[dict] = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        for db_key, attr in _DB_ATTR.items():
            db_id = getattr(settings, attr, None)
            if not db_id:
                continue
            ai_pages = await _query_db(
                client, db_id, h,
                filter_body={"property": "Author", "select": {"equals": "IA"}},
            )
            if len(ai_pages) < 2:
                logger.info("[{}] {} IA page(s) — nothing to dedup", _DB_LABEL[db_key], len(ai_pages))
                continue

            titles         = [_page_title(p) for p in ai_pages]
            title_to_page  = {_page_title(p): p for p in ai_pages}
            logger.info("[{}] {} IA pages — clustering...", _DB_LABEL[db_key], len(titles))

            clusters = await _llm_cluster_titles(titles, _DB_LABEL[db_key], settings)
            for cluster in clusters:
                cluster_pages = [title_to_page[t] for t in cluster if t in title_to_page]
                if len(cluster_pages) < 2:
                    continue

                # Rank by block count; winner = most content
                ranked = []
                for p in cluster_pages:
                    blocks = await _get_blocks(client, p["id"], h)
                    ranked.append((p, blocks, _count_text_blocks(blocks)))
                ranked.sort(key=lambda x: x[2], reverse=True)
                winner, _, _ = ranked[0]

                for loser, loser_blocks, _ in ranked[1:]:
                    loser_title = _page_title(loser)
                    loser_text  = _blocks_to_text(loser_blocks)
                    logger.info("{}DEDUP MERGE {} → {}", "[DRY] " if dry_run else "", loser_title, _page_title(winner))
                    if not dry_run:
                        await _append_blocks(client, winner["id"], _consolidation_blocks(loser_title, loser_text, today), h)
                        await _archive_page(client, loser["id"], h)
                    merges.append({
                        "db": _DB_LABEL[db_key],
                        "winner": _page_title(winner),
                        "loser": loser_title,
                        "action": "merged" if not dry_run else "would-merge",
                    })

    return merges


async def run_purge(settings: Settings, h: dict, dry_run: bool) -> int:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=_PURGE_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    count  = 0
    async with httpx.AsyncClient(timeout=30.0) as client:
        pages = await _query_db(
            client,
            settings.notion_telegram_msg_database_id,
            h,
            filter_body={
                "and": [
                    {"property": "Status", "status": {"equals": _STATUS_DONE}},
                    {"timestamp": "last_edited_time", "last_edited_time": {"before": cutoff}},
                ]
            },
        )
        logger.info("Purge: {} page(s) eligible (Analysed + > {} days)", len(pages), _PURGE_DAYS)
        for page in pages:
            title = _page_title(page)
            logger.info("{} {!r}", "[DRY] would archive" if dry_run else "ARCHIVE", title)
            if not dry_run:
                await _archive_page(client, page["id"], h)
            count += 1
    return count

# ── CSV output ────────────────────────────────────────────────────────────────

def _write_dedup_csv(rows: list[dict]) -> None:
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fields = ["db", "ai_page_title", "ai_page_url", "human_page_title", "human_page_url", "suggested_action"]
    with _DEDUP_CSV.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    logger.info("Wrote {} conflict(s) → {}", len(rows), _DEDUP_CSV)

# ── Entry point ───────────────────────────────────────────────────────────────

async def main() -> None:
    dry_run = _flag("--dry-run")
    dedup   = _flag("--dedup")
    purge   = _flag("--purge")
    limit   = int(_arg("--limit") or "0")
    out_raw = _arg("--output")
    today   = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out     = Path(out_raw) if out_raw else _OUTPUT_DIR / f"knowledge-enrichment-{today}.json"

    settings = load_settings()
    if not settings.notion_token:
        logger.error("NOTION_TOKEN required")
        sys.exit(1)
    if not settings.openrouter_api_key:
        logger.error("OPENROUTER_API_KEY required")
        sys.exit(1)

    h = _notion_headers(settings.notion_token.get_secret_value())

    logger.info("── Knowledge Enrichment ────────────────────────────────────")
    logger.info("  Mode    : {}", "DRY RUN" if dry_run else "LIVE")
    logger.info("  Process : {}", "dedup" if dedup else "purge" if purge else f"enrich (limit={limit or '∞'})")
    logger.info("────────────────────────────────────────────────────────────")

    if dedup:
        results = await run_dedup(settings, h, dry_run)
        mode    = "dedup"
    elif purge:
        count   = await run_purge(settings, h, dry_run)
        results = [{"purged": count}]
        mode    = "purge"
    else:
        results = await run_enrich(settings, h, dry_run, limit)
        mode    = "enrich"

    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"run_date": today, "mode": mode, "dry_run": dry_run, "results": results}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("Report → {}", out)


if __name__ == "__main__":
    asyncio.run(main())
