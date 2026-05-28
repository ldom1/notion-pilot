# Architecture

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
- **LLM enrichment:** OpenRouter (`google/gemini-2.5-flash-lite` default) — optional, heuristics fallback

## Key Modules

| Module | Role |
|--------|------|
| `adapters/__init__.py` | `SourceAdapter` + `SinkAdapter` Protocols, `MessageHandler` type |
| `adapters/telegram.py` | Telegram long-polling source (async API) |
| `adapters/email.py` | IMAP polling source — sender allowlist, archive after ingest |
| `adapters/discord.py` | Discord source + notification sink |
| `bot.py` | Thin runner: activates adapters from env, `asyncio.gather` |
| `pipeline.py` | Shared: `interpret_message → create_page`; `build_pipeline()` returns handler |
| `config.py` | Pydantic settings from `.env`; all adapters optional except Notion |
| `models.py` | `IncomingMessage` (+ `source_adapter` field) + `NotionDatabaseProperties` |
| `notion.py` | `NotionDatabaseWriter` — create/update/delete Notion rows |
| `llm/openrouter.py` | Structured JSON extraction via chat completions |
| `llm/prompt.py` | System prompt built from the Pydantic model schema |
| `llm/source_hints.py` | URL → platform heuristics (GitHub, YouTube, arXiv…) |
| `media/` | Photo + voice download, on-device transcription via faster-whisper |

## Data Flow

```
Source adapter (telegram / email / discord)
  → IncomingMessage  [source_adapter="telegram"|"email"|"discord"]
  → pipeline.py
      → media download + transcription (media/)
      → LLM enrichment or heuristics (llm/)
      → NotionDatabaseProperties
      → NotionDatabaseWriter (notion.py)
      → Notion DB row
  → (optional) SinkAdapter.send() for notifications
```

## Planned Layers (sellable platform)

```
Layer 1 (now):   Multi-source ingestion  → Notion DB row (enriched)
Layer 2 (next):  Enrichment agent        → entity resolution → meta-pages across 4 Notion DBs
Layer 3 (later): Vertical use cases      → CRM enrichment, invoice alerts, contacts
Layer 4 (later): SaaS packaging          → multi-user, billing, Notion marketplace
```

## Architectural Notes

- Notion SDK is synchronous — all calls go through `asyncio.to_thread`
- Adapters activate by env var presence: no config file changes to add/remove a source
- `TELEGRAM_BOT_TOKEN` is now optional — the runner works with any combination of adapters
- `source_adapter` field on `IncomingMessage` drives the Notion `Label` via `from_incoming()`
- Check `animation` before `video` in Telegram handlers — Telegram sets both flags for GIFs
- Deploy: systemd user service on devbox (`~/Lab/dom-telegram-to-notion`)
- Optional dep groups: `uv sync --group email`, `uv sync --group discord`
