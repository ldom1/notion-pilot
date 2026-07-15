---
type: architecture
updated:
---

# Architecture

## Product Structure

Two products, one mono-repo, shared core:

```
notion-pilot/            ← repo name (rename from notion-pilot)
├── notion_pilot/        ← Python package (rename from telegram_to_notion)
│   ├── shared/          ← core used by both products
│   │   ├── adapters/    ← SourceAdapter/SinkAdapter protocols + Telegram/Email/Discord impls
│   │   ├── llm/         ← OpenRouter, prompt, source_hints
│   │   ├── utils/       ← enrichment (Apollo, Brave), dedup
│   │   ├── notion.py    ← NotionDatabaseWriter
│   │   ├── config.py    ← unified Pydantic settings
│   │   └── models.py    ← IncomingMessage + DB property models
│   ├── crm/             ← notion-crm vertical
│   │   ├── commands.py  ← /lead /people /company /deal /enrich Telegram commands
│   │   ├── conv_state.py← SQLite conversation state machine
│   │   ├── syncer.py    ← NotionPeopleSyncer, NotionCompanySyncer
│   │   ├── deals.py     ← NotionDealsSyncer
│   │   └── prospection.py
│   ├── inbox/           ← notion-inbox vertical (rename from pipelines/)
│   │   ├── knowledge.py ← knowledge pipeline → Notion Knowledge DB
│   │   └── people.py    ← people pipeline (email contacts → People DB)
│   ├── media/           ← photo/voice download, faster-whisper transcription
│   └── bot.py           ← thin runner: activates adapters, routes commands
├── scripts/
│   ├── crm/             ← crm_setup_workspace.py, crm_enrich.py, crm_dedup.py, etc.
│   └── inbox/           ← (future) inbox_setup.py for Knowledge DBs
└── web/                 ← (future) landing + deploy wizard + chatbot
```

## Stack

- **Runtime:** Python 3.12, uv
- **Telegram:** `python-telegram-bot` (long polling, no webhook)
- **Email:** `imapclient` (optional, IMAP polling)
- **Discord:** `discord.py` (optional, source + sink)
- **Notion:** `notion-client` (sync SDK, always wrapped in `asyncio.to_thread`)
- **Config:** Pydantic settings from `.env`
- **HTTP:** httpx
- **Logging:** loguru
- **Transcription:** `faster-whisper` (optional, on-device)
- **LLM enrichment:** OpenRouter (`google/gemini-2.5-flash-lite` default)
- **Enrichment:** Apollo.io (people/company), Brave Search (web)
- **State:** SQLite via `aiosqlite` (conversation state for CRM commands)

## Data Flow

```
Source adapter (telegram / email / discord)
  → IncomingMessage  [source_adapter field]
  → router (bot.py)
      ├── CRM command (/lead /people /company /deal /enrich)
      │     → crm/commands.py → conv_state → syncer → Notion CRM DBs
      └── Knowledge message (default)
            → media download + transcription (media/)
            → LLM enrichment (llm/)
            → NotionDatabaseWriter → Notion Knowledge DB
```

## Key Config IDs

| Env var | Purpose |
|---------|---------|
| `NOTION_DATABASE_ID` | Knowledge / inbox DB |
| `NOTION_COMPANIES_DATA_SOURCE_ID` | Companies DB (inline DS API) |
| `NOTION_PEOPLE_DATA_SOURCE_ID` | People DB (central CRM syncer: dedup + upsert) |
| `NOTION_DEALS_DATABASE_ID` | Deals DB |

> Email people capture uses the same CRM syncer path as `/people` commands instead of a separate contacts writer.

## Architectural Notes

- Notion SDK is synchronous — all calls go through `asyncio.to_thread`
- Adapters activate by env var presence: no config file changes to add/remove a source
- `source_adapter` field on `IncomingMessage` drives the Notion `Label` via `from_incoming()`
- Check `animation` before `video` in Telegram handlers — Telegram sets both flags for GIFs
- CRM commands use an LLM extraction step to parse free-form text → structured fields
- Conversation state (SQLite) tracks multi-turn CRM interactions per Telegram chat_id
- Deploy: systemd user service on devbox

## Planned Layers

```
Layer 1 (done):   Multi-source ingestion  → Notion DB row (enriched)
Layer 2 (now):    CRM vertical            → People/Companies/Deals + Telegram commands
Layer 3 (next):   Setup wizard            → virgin Notion bootstrap (CRM + Knowledge)
Layer 4 (later):  Email recap             → "à relire" tagging + Telegram summary
Layer 5 (later):  Website                 → landing + Notion OAuth deploy wizard + chatbot
```

## Key Modules
<!-- added by ai-dotfiles upgrade -->

- **`notion_pilot/mcp/`** (2026-07-13) — exposes the CRM vertical as MCP tools over stdio (`FastMCP`), for any MCP-aware client (not just Telegram). `session.py` caches a `SyncerSession` (People/Companies snapshot) per process with a background pre-warm at startup (via FastMCP's `lifespan` hook — pre-warm must NOT start at bare module-import time, since `asyncio.create_task` requires a running event loop). `tools.py` are thin wrappers calling straight into `crm/syncer.py`, `shared/utils/dedup.py`, `shared/prosper_client.py` (updated 2026-07-14 — was `shared/utils/enrichment.py` until that module was deleted in favor of prosper's MCP-based enrichment), `crm/prospection.py`, `crm/queries.py` — no duplicated business logic. `server.py` registers 11 tools: `upsert_people`, `upsert_companies`, `find_duplicates`, `enrich_people`, `enrich_companies`, `rank_contacts_for_pitch`, `search_people`, `search_companies`, `get_recent_people`, `get_open_leads`, `refresh_notion_snapshot`.

## Non-Obvious Decisions
<!-- added by ai-dotfiles upgrade -->

- **MCP write tools default to `confirm=false` (dry-run preview)** — every tool that writes to Notion (`upsert_people`, `upsert_companies`, `enrich_people`, `enrich_companies`) computes and returns what *would* happen without calling any Notion write endpoint unless the caller passes `confirm=true`. Mirrors `crm_enrich.py`'s existing `--dry-run` flag, generalized to every write tool.
- **Company dedup fuzzy matching does not catch legal-suffix variants** (e.g. "EDF" vs "EDF S.A." scores ~55, well under the 85 threshold) — the existing `token_sort_ratio`-based algorithm in `shared/utils/dedup.py` has no legal-suffix-stripping. Confirmed while implementing the MCP `find_duplicates`/`upsert_companies` tools (2026-07-13): don't assume near-miss company-name pairs will dedup — verify empirically before writing tests/fixtures around this matcher.
