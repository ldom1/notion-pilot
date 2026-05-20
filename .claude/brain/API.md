# API

## External Services Consumed

| Service | Purpose | Auth |
|---------|---------|------|
| Telegram Bot API | Long-polling message ingestion | `TELEGRAM_BOT_TOKEN` in `.env` |
| Notion API | Read/write database rows, file upload | `NOTION_TOKEN` + `NOTION_DATABASE_ID` in `.env` |
| OpenRouter | LLM enrichment (structured JSON extraction) | `OPENROUTER_API_KEY` in `.env` (optional) |
| faster-whisper | On-device voice transcription | Local model, no key |
| Email / IMAP | Planned: email ingestion adapter | TBD (`feat/mail-management`) |

## Authentication

All secrets in `.env` (see `.env.example`). Loaded via Pydantic settings in `config.py`.

## Notion DB Schema

Required columns: `Name` (title), `Label` (multi-select), `Type` (select), `Link` (url), `Source` (select), `Description` (text), `Interest` (select), `Status` (status)

`NOTION_TITLE_COLUMN` env var overrides the title column name (default: `Name`).
