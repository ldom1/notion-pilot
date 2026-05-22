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
| `utils/dedup.py` | `CandidateRecord`, `DedupStatus`, `find_match()` — rapidfuzz fuzzy dedup (thresholds 85/75). Pure, no Notion. |
| `utils/enrichment.py` | Four-tier enrichment: Apollo.io → Brave Search → Perplexity (`sonar-pro`) → LLM inference. `enrich_person()`, `enrich_company()`. Never raises, 10s timeout per tier. |
| `crm/syncer.py` | `NotionPeopleSyncer`, `NotionCompanySyncer` — snapshot + fuzzy upsert. Imports from `utils/`. |
| `crm/deals.py` | `NotionDealsSyncer` — standard `database_id` API (not data_sources) |
| `crm/prospection.py` | `rank_contacts()` — OpenRouter-powered contact ranking for a pitch |
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

## CRM Notion IDs

| DB | Notion ID | API style |
|----|-----------|-----------|
| People | `866ce33a-cf5b-47d4-85db-7cd932915dc8` | `data_sources` (inline, created via UI) |
| Companies | `fe2b97ac-6d33-4626-890b-62b25a02e1cb` | `data_sources` (inline, created via UI) |
| Deals | `4890e1d6-178d-4a42-af06-7bbe0cef09fe` | `databases` (standard, created via API) |

People and Companies use `client.data_sources.query()` + `parent={"type": "data_source_id", ...}`.  
Deals uses `client.pages.create(parent={"database_id": ...})` and standard `databases` endpoints.

## Enrichment Pipeline

Four tiers, each skipped if its key is absent; never raises, partial results always returned:

| Tier | Source | Triggers when | Key |
|------|--------|--------------|-----|
| 1 | Apollo.io | Always | `APOLLO_API_KEY` |
| 2 | Brave Search | Apollo found nothing | `BRAVE_API_KEY` |
| 3 | Perplexity `sonar-pro` | Brave found nothing | `OPENROUTER_API_KEY` |
| 4 | LLM inference (Gemini) | Seniority/role_type/country missing | `OPENROUTER_API_KEY` |

Perplexity reuses `OPENROUTER_API_KEY` with model `perplexity/sonar-pro`. Override via `perplexity_model` param; set to `None` to skip.

## Architectural Notes

- Notion SDK is synchronous — all calls go through `asyncio.to_thread`
- Adapters activate by env var presence: no config file changes to add/remove a source
- `TELEGRAM_BOT_TOKEN` is now optional — the runner works with any combination of adapters
- `source_adapter` field on `IncomingMessage` drives the Notion `Label` via `from_incoming()`
- Check `animation` before `video` in Telegram handlers — Telegram sets both flags for GIFs
- Deploy: systemd user service on devbox (`~/Lab/dom-telegram-to-notion`)
- Optional dep groups: `uv sync --group email`, `uv sync --group discord`
