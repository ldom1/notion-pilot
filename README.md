# telegram-to-notion

[![CI](https://github.com/ldom1/telegram-to-notion/actions/workflows/ci.yml/badge.svg)](https://github.com/ldom1/telegram-to-notion/actions/workflows/ci.yml)
[![Latest tag](https://img.shields.io/github/v/tag/ldom1/telegram-to-notion?label=tag&sort=semver)](https://github.com/ldom1/telegram-to-notion/tags)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)

**Your Telegram bot is now your Notion inbox.** Send a link, a photo, or a voice note — it lands in your Notion database, fully structured, in seconds.

No webhooks. No third-party SaaS. No data leaving your server.

## Why you'll like it

- **Voice-to-Notion, offline.** Dictate an idea, get a transcribed, titled, categorized page. All on-device via [faster-whisper](https://github.com/SYSTRAN/faster-whisper).
- **LLM-powered enrichment (optional).** Point it at [OpenRouter](https://openrouter.ai/) and every message becomes a Notion row with a smart title, tags, summary, detected source (GitHub, YouTube, arXiv…), and interest level.
- **Heuristics fallback.** No API key, no problem — URLs, platforms, and basic categorization still just work.
- **One binary, zero infra.** Long polling only. Runs as a single systemd user service. Perfect for a home server.

## What goes in, what comes out

You send: `J'ai trouvé un outil sympa: https://github.com/ldom1/telegram-to-notion`

Notion receives:

| Name | Label | Type | Source | Link | Description | Interest |
|---|---|---|---|---|---|---|
| Telegram-to-Notion bridge | `[tool, dev, python]` | link | GitHub | github.com/… | Self-hosted pipeline from Telegram to Notion. | High |

Voice notes? Same thing — transcribed first, then enriched.

## Setup (2 minutes)

```bash
git clone https://github.com/ldom1/telegram-to-notion && cd telegram-to-notion
cp .env.example .env   # fill in TELEGRAM_BOT_TOKEN, NOTION_TOKEN, NOTION_DATABASE_ID
uv sync
uv run python -m telegram_to_notion
```

Send your bot a message on Telegram. Send `/ping` to confirm it's alive.

### What you need

- Python 3.12 + [uv](https://docs.astral.sh/uv/)
- A Telegram bot from [@BotFather](https://t.me/BotFather)
- A [Notion integration](https://www.notion.so/my-integrations) + a database shared with it, containing columns: `Name` (title), `Label` (multi-select), `Type` (select), `Link` (url), `Source` (select), `Description` (text), `Interest` (select), `Status` (status)
- *(Optional)* An [OpenRouter API key](https://openrouter.ai/keys) for LLM enrichment

### Optional adapters

```bash
uv sync --extra email     # IMAP email ingestion
uv sync --extra discord   # Discord source + notifications
```

Set the relevant env vars (see `.env.example`) — adapters activate automatically when their credentials are present.

## Try it without Telegram

```bash
uv run python examples/example.py
```

Builds a fake `IncomingMessage`, runs it through the same enrichment pipeline, writes to your Notion DB.

## Deploy (systemd user service)

```bash
ssh <your-server> 'cd ~/Lab/dom-telegram-to-notion && git pull && uv sync && systemctl --user restart telegram-to-notion.service'
ssh <your-server> 'journalctl --user -u telegram-to-notion.service -f'
```

## Develop

```bash
uv run pytest tests/unit -v              # fast, no network
uv run pytest tests/integration -v       # hits real Notion + OpenRouter + Whisper
uv run ruff check . && uv run mypy telegram_to_notion
```

## Under the hood

```
telegram_to_notion/
├── adapters/
│   ├── __init__.py    # SourceAdapter + SinkAdapter protocols
│   ├── telegram.py    # Telegram long-polling source
│   ├── email.py       # IMAP polling source (optional: uv sync --extra email)
│   └── discord.py     # Discord source + notification sink (optional: uv sync --extra discord)
├── bot.py             # Runner: activates adapters from env, asyncio.gather
├── config.py          # Pydantic settings from .env
├── models.py          # IncomingMessage + NotionDatabaseProperties
├── notion.py          # NotionDatabaseWriter
├── pipeline.py        # Shared: interpret_message → create_page
├── llm/
│   ├── openrouter.py  # Structured JSON extraction via chat completions
│   ├── prompt.py      # System prompt built from the Pydantic model
│   └── source_hints.py
└── media/             # Photo + voice download, on-device transcription
```

Contributions welcome. Short & sharp.
