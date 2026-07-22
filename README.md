# Notion Pilot

[![CI](https://github.com/ldom1/notion-pilot/actions/workflows/ci.yml/badge.svg)](https://github.com/ldom1/notion-pilot/actions/workflows/ci.yml)
[![Latest tag](https://img.shields.io/github/v/tag/ldom1/notion-pilot?label=tag&sort=semver)](https://github.com/ldom1/notion-pilot/tags)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)

**Self-hosted Notion automation platform — CRM and knowledge inbox, piloted by Telegram.** Send a link, a photo, or a voice note — it lands in your Notion database, fully structured, in seconds.

No webhooks. No third-party SaaS. No data leaving your server.

## 🚀 Quick Start

### Prerequisites
- Python 3.12+, [uv](https://docs.astral.sh/uv/)
- A Notion account with an [integration token](https://www.notion.so/my-integrations) (`secret_...`)
- A Notion page where the integration has access (open the page → ··· → Connections → add your integration)

### Option A — CLI (one command)

```bash
# CRM + Knowledge inbox in one shot:
uv run python scripts/crm/crm_setup_workspace.py --parent-id <YOUR_PAGE_URL> --with-inbox

# CRM only:
uv run python scripts/crm/crm_setup_workspace.py --parent-id <YOUR_PAGE_URL>

# Knowledge inbox only:
uv run python scripts/inbox/setup_workspace.py --parent-id <YOUR_PAGE_URL>
```

Copy the printed IDs into your `.env` file.

### Option B — Telegram `/setup` wizard

Start the bot with at least `NOTION_TOKEN` set in `.env`, then send `/setup` to your bot.
The wizard walks you through token validation, scope selection, and parent page — then prints the `.env` values.

### Option C — Web UI (deploy wizard)

Register a public Notion integration at [notion.so/my-integrations](https://www.notion.so/profile/integrations), then add to your `.env`:

```env
NOTION_OAUTH_CLIENT_ID=your_client_id
NOTION_OAUTH_CLIENT_SECRET=your_client_secret
NOTION_OAUTH_REDIRECT_URI=https://yourhost/auth/notion/callback
WEB_SESSION_SECRET=a-long-random-key
```

Then launch:

```bash
uv sync --group web
./launch_webserver.sh
```

Open `http://localhost:8080`, click **Deploy to Notion**, authorize with your Notion account, choose your scope, and name your workspace. Done.

**Advanced / self-hosted without OAuth:** Click "Have an integration token?" in the wizard and paste a `secret_...` token from [notion.so/my-integrations](https://www.notion.so/profile/integrations). The integration must have workspace-level create permissions.

### Generated `.env` variables

| Variable | Description |
|----------|-------------|
| `NOTION_TOKEN` | Your Notion integration token |
| `NOTION_TELEGRAM_MSG_DATABASE_ID` | DomTelegramBot / Notions (knowledge) database |
| `NOTION_IDEAS_DATABASE_ID` | Ideas database |
| `NOTION_TOOLS_DATABASE_ID` | Tools database |
| `NOTION_DATA_TECH_DATABASE_ID` | Data & Technology database |
| `NOTION_COMPANIES_DATA_SOURCE_ID` | Companies CRM database |
| `NOTION_PEOPLE_DATA_SOURCE_ID` | People CRM database |
| `NOTION_DEALS_DATABASE_ID` | Deals CRM database |

## Why you'll like it

- **Voice-to-Notion, offline.** Dictate an idea, get a transcribed, titled, categorized page. All on-device via [faster-whisper](https://github.com/SYSTRAN/faster-whisper).
- **LLM-powered enrichment (optional).** Point it at [OpenRouter](https://openrouter.ai/) and every message becomes a Notion row with a smart title, tags, summary, detected source (GitHub, YouTube, arXiv…), and interest level.
- **Heuristics fallback.** No API key, no problem — URLs, platforms, and basic categorization still just work.
- **One binary, zero infra.** Long polling only. Runs as a single systemd user service. Perfect for a home server.

## What goes in, what comes out

You send: `J'ai trouvé un outil sympa: https://github.com/ldom1/notion-pilot`

Notion receives:

| Name | Label | Type | Source | Link | Description | Interest |
|---|---|---|---|---|---|---|
| Notion Pilot | `[tool, dev, python]` | link | GitHub | github.com/… | Self-hosted Notion automation platform. | High |

Voice notes? Same thing — transcribed first, then enriched.

## Setup (2 minutes)

```bash
git clone https://github.com/ldom1/notion-pilot && cd notion-pilot
cp .env.example .env   # fill in TELEGRAM_BOT_TOKEN, NOTION_TOKEN, NOTION_TELEGRAM_MSG_DATABASE_ID
uv sync
uv run python -m notion_pilot
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
For email senders routed to People, set `NOTION_PEOPLE_DATA_SOURCE_ID` and `NOTION_COMPANIES_DATA_SOURCE_ID`;
the adapter uses the central CRM syncer with deduplication instead of a separate contacts table.

## Try it without Telegram

```bash
uv run python examples/example.py
```

Builds a fake `IncomingMessage`, runs it through the same enrichment pipeline, writes to your Notion DB.

## Deploy (systemd user service)

```bash
ssh <your-server> 'cd ~/Lab/notion-pilot && git pull && uv sync && systemctl --user restart notion-pilot.service'
ssh <your-server> 'journalctl --user -u notion-pilot.service -f'
```

## Develop

```bash
uv run pytest tests/unit -v              # fast, no network
uv run pytest tests/integration -v       # hits real Notion + OpenRouter + Whisper
uv run ruff check . && uv run mypy notion_pilot
```

## Under the hood

Two verticals, one platform:

- **Knowledge inbox** — captures anything you send (links, photos, voice notes) into a structured Notion database.
- **CRM** — syncs people, companies, and deals into Notion; enriches contacts via Apollo/Brave Search.

```
notion_pilot/
├── shared/            # Core shared across verticals
│   ├── adapters/
│   │   ├── __init__.py    # SourceAdapter + SinkAdapter protocols
│   │   ├── telegram.py    # Telegram long-polling source
│   │   ├── email.py       # IMAP polling source (optional: uv sync --extra email)
│   │   └── discord.py     # Discord source + notification sink (optional: uv sync --extra discord)
│   ├── config.py          # Pydantic settings from .env
│   ├── models.py          # IncomingMessage + NotionDatabaseProperties
│   └── notion.py          # NotionDatabaseWriter
├── inbox/             # Knowledge inbox vertical (formerly pipelines/)
│   ├── bot.py         # Runner: activates adapters from env, asyncio.gather
│   ├── pipeline.py    # interpret_message → create_page
│   └── llm/
│       ├── openrouter.py  # Structured JSON extraction via chat completions
│       ├── prompt.py      # System prompt built from the Pydantic model
│       └── source_hints.py
├── crm/               # CRM vertical
│   ├── people.py      # NotionPeopleSyncer
│   ├── companies.py   # NotionCompanySyncer
│   └── deals.py       # Deal tracking
└── media/             # Photo + voice download, on-device transcription
```

## MCP server

`notion_pilot/mcp/` exposes the CRM vertical's existing capabilities (fuzzy-dedup'd upsert, enrichment, duplicate scan, pitch-based ranking, read queries) as MCP tools over stdio, so any MCP-aware client (e.g. Claude Code, from this project or another) can ingest, dedup, enrich, and query Notion CRM data directly — without reinventing any of the matching/enrichment logic already proven in `crm/` and `shared/utils/`. It's a thin wrapper: `session.py` caches a `NotionCompanySyncer`/`NotionPeopleSyncer` snapshot for the process lifetime (background pre-warm at startup), and `tools.py` calls straight into the existing syncer/dedup/enrichment/prospection/queries functions.

Register it as an MCP server (e.g. in a project's `.claude/settings.json`):

```json
{
  "mcpServers": {
    "notion-crm": {
      "command": "uv",
      "args": ["--directory", "/home/lgiron/lab_perso/notion-pilot", "run", "python", "-m", "notion_pilot.mcp.server"]
    }
  }
}
```

Tools:

| Tool | Description |
|---|---|
| `upsert_people` | Upsert people into the Notion People database, dedup-checked (exact email/LinkedIn match, then fuzzy name+company). Defaults to a dry-run preview (`confirm=false`) — pass `confirm=true` to actually write. A `needs_review` result can be created anyway with `force=true`. |
| `upsert_companies` | Upsert companies into the Notion Companies database, dedup-checked (contact-email domain, exact name, acronym/subset name). New companies get SIREN + sector/size/country enriched — prosper first, falling back to the French government company registry — shown in the preview for approval and written on `confirm=true`. A `needs_review` result can be created anyway with `force=true`. |
| `find_duplicates` | Find likely-duplicate People/Companies pairs already in Notion via fuzzy name matching. `target`: `people`, `companies`, or `both`. |
| `enrich_people` | Enrich People records missing seniority/role/email via prosper's `enrich_person` MCP tool. Defaults to a dry-run preview. |
| `enrich_companies` | Enrich Company records missing sector/size/country/LinkedIn via prosper's `enrich_company` MCP tool. Defaults to a dry-run preview. |
| `rank_contacts_for_pitch` | Rank existing CRM contacts by relevance to a B2B sales pitch (LLM-powered). |
| `search_people` | Fuzzy-search existing People by name/company — read-only, no write. |
| `search_companies` | Fuzzy-search existing Companies by name — read-only, no write. |
| `get_recent_people` | People added to Notion in the last 7 days. |
| `get_open_leads` | Open (non-closed) deals from the Deals database. |
| `refresh_notion_snapshot` | Force-reload the cached People/Companies snapshot from Notion (use if the Telegram bot or web cockpit may have written since this session started). |

All write tools default to `confirm=false` (dry-run preview, no Notion write) and require an explicit `confirm=true` to actually write.

### Remote access (HTTP)

The same tools are also reachable over HTTP — mounted at `/mcp` on the deployed web service, gated by a static bearer token — for MCP clients that can't spawn a local subprocess. Set `NOTION_TOKEN` and `MCP_BEARER_TOKEN` (see `.env.example`); the mount is skipped entirely if either is unset. Note this endpoint always acts on that single `NOTION_TOKEN` workspace, not any per-session OAuth workspace connected through the cockpit UI.

```json
{
  "mcpServers": {
    "notion-crm": {
      "url": "https://notion-pilot.dombot.tech/mcp",
      "headers": { "Authorization": "Bearer <MCP_BEARER_TOKEN>" }
    }
  }
}
```

Contributions welcome. Short & sharp.
