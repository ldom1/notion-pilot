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
