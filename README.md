# Notion Pilot

[![CI](https://github.com/ldom1/notion-pilot/actions/workflows/ci.yml/badge.svg)](https://github.com/ldom1/notion-pilot/actions/workflows/ci.yml)
[![Latest tag](https://img.shields.io/github/v/tag/ldom1/notion-pilot?label=tag&sort=semver)](https://github.com/ldom1/notion-pilot/tags)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)

**Self-hosted Notion CRM you actually own** — deploy a relational CRM into your workspace, then keep it current with your AI assistant (human-in-the-loop by default). Optional capture channels: Telegram, email, Discord.

No third-party CRM SaaS. Your data stays in your Notion.

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

The wizard asks where to put the workspace: the top level of your Notion, or
inside a page you pick. **With an internal integration token, a parent page is
required** — Notion rejects workspace-level page creation for integrations that
aren't owned by a single user ("Internal integrations aren't owned by a single
user, so creating workspace-level private pages is not supported"). The wizard
detects this and only offers placements your token can actually use. Share the
page with your integration first: open it in Notion → `···` → **Connections**.

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

Open `http://localhost:8080`, click **Deploy the CRM to Notion**, authorize with your Notion account, name the CRM page, and choose workspace root or a page from the workspace. Done.

The CRM page opens on your pipeline: four views under **This week**, a prompt to paste into your assistant, and **Sources & documentation**. To refresh an older CRM page in place:

```bash
uv run python scripts/crm/crm_upgrade_home.py --crm-page-id <page id or URL>
```

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
- **One binary, zero infra.** Optional Telegram long polling (no webhook). Runs as a single systemd user service. Perfect for a home server.

## What goes in, what comes out

You send: `J'ai trouvé un outil sympa: https://github.com/ldom1/notion-pilot`

Notion receives:

| Name | Label | Type | Source | Link | Description | Interest |
|---|---|---|---|---|---|---|
| Notion Pilot | `[tool, dev, python]` | link | GitHub | github.com/… | Self-hosted Notion automation platform. | High |

Voice notes? Same thing — transcribed first, then enriched.

## Setup (inbox bot, optional Telegram)

```bash
git clone https://github.com/ldom1/notion-pilot && cd notion-pilot
cp .env.example .env   # NOTION_TOKEN + database IDs; TELEGRAM_BOT_TOKEN only if using Telegram
uv sync
uv run python -m notion_pilot
```

Prefer the **Web UI deploy wizard** (Option C above) for the CRM. For the knowledge inbox over Telegram: create a bot with [@BotFather](https://t.me/BotFather), set `TELEGRAM_BOT_TOKEN`, then `/ping`.

### What you need

- Python 3.12 + [uv](https://docs.astral.sh/uv/)
- A [Notion integration](https://www.notion.so/my-integrations) + databases shared with it
- *(Optional)* Telegram bot token, email/Discord extras, [OpenRouter](https://openrouter.ai/keys) for LLM enrichment

### Optional adapters

```bash
uv sync --extra email     # IMAP email ingestion
uv sync --extra discord   # Discord source + notifications
```

Set the relevant env vars (see `.env.example`) — adapters activate automatically when their credentials are present.
For email senders routed to People, set `NOTION_PEOPLE_DATA_SOURCE_ID` and `NOTION_COMPANIES_DATA_SOURCE_ID`;
the adapter uses the central CRM syncer with deduplication instead of a separate contacts table.

## Try the inbox pipeline without a chat adapter

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

## Homepage films

The landing page embeds one silent clip — the email → approved diff → Notion → KPI loop —
after the “who keeps this up to date?” beat. The other two HyperFrames compositions
(HITL gate, team dictation) stay in `promotion/video/` and `/film/`; on the page those
jobs are the assistant preview and the EU/Enterprise band (collaboration is
native Notion). All three are HTML compositions on the site's own design tokens, rendered
to MP4.

```bash
cd promotion/video && npm install                 # once — installs the hyperframes CLI
./hyperframes/sync-shared.sh                      # after editing _shared/np.css
cd hyperframes/notion-pilot-pipeline
../../node_modules/.bin/hyperframes check         # must be 0 errors before rendering
../../node_modules/.bin/hyperframes render --quality high --output out.mp4
```

Delivered files live in `web/frontend/public/film/` (served at `/film/<slug>.mp4`).
Sources, briefs and the publishing loop: [`promotion/video/README.md`](promotion/video/README.md).

## Under the hood

Two verticals, one platform:

- **Knowledge inbox** — captures anything you send (links, photos, voice notes) into a structured Notion database.
- **CRM** — syncs people, companies, and deals into Notion; enriches contacts via Apollo/Brave Search.

```
notion_pilot/
├── bot.py                 # Runner: activates adapters from env
├── shared/                # Core shared across verticals
│   ├── adapters/          # Telegram / email / Discord (optional extras)
│   ├── llm/               # OpenRouter synthesis, prompts, CRM chat
│   ├── media/             # Photo + voice; on-device transcription
│   ├── config.py          # Settings(CRMSettings) + Infisical / Telegram / web
│   ├── models.py          # IncomingMessage + Notion properties
│   └── notion.py          # NotionDatabaseWriter
├── inbox/                 # Knowledge inbox vertical
│   ├── pipeline.py        # interpret_message → create_page
│   ├── knowledge.py
│   └── people.py
├── crm/                   # Platform CRM (Telegram commands, inbox queries)
│   ├── queries.py         # get_inbox_items (CRM reads live in powers)
│   └── commands.py        # Optional Telegram CRM commands
vendor/notion-pilot-powers/  # Path submodule: CRM core + stdio MCP
```

## Agent skills: Artelys CRM

Canonical skills under `skills/` (symlinked into `.cursor/skills/` and `.claude/skills/`):

- **`notion-crm-ops`** — add/update Leads, Activities, People, or Companies via Notion MCP; always French preview table before writes. See `references/` for DB IDs and field enums.
- **`company-open-data-enrichment`** — enrich or create a Companies row from French open data (SIREN, NAF/APE, BODACC, RNE financials, dirigeants); Prosper MCP preferred, registry fallback; same preview + `go` write discipline as `notion-crm-ops`.

## MCP server

CRM tools live in the **`notion-pilot-powers`** submodule (`vendor/notion-pilot-powers`), installed as an editable path dependency. Run over stdio:

```json
{
  "mcpServers": {
    "notion-crm": {
      "command": "uv",
      "args": ["--directory", "/path/to/notion-pilot", "run", "python", "-m", "notion_pilot_powers.mcp.server"]
    }
  }
}
```

Tools (same surface as before the split): `upsert_people`, `upsert_companies`, `find_duplicates`, `enrich_people`, `enrich_companies`, `rank_contacts_for_pitch`, `search_people`, `search_companies`, `get_recent_people`, `get_open_leads`, `get_activities`, `refresh_notion_snapshot`, `upsert_deal`, `log_activity`. Write tools default to `confirm=false`.

The former HTTP `/mcp` mount on the web service was removed — use local stdio (or Notion’s official MCP) instead.

Contributions welcome. Short & sharp.
