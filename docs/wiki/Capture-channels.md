# Capture channels

## Primary — Claude Code + Notion MCP (HITL)

Deploy the CRM, install [notion-pilot-powers](https://github.com/ldom1/notion-pilot-powers), connect [Notion's hosted MCP](https://developers.notion.com/guides/mcp/get-started-with-mcp). Paste a thread into Claude Code; the assistant searches, shows a preview, and writes only after you approve.

## Optional — Telegram

Long-polling bot (`TELEGRAM_BOT_TOKEN` from [@BotFather](https://t.me/BotFather)). Links, photos, voice notes → structured Notion rows. Useful for capture on the go; not required for the CRM product story.

```bash
uv sync
# set TELEGRAM_BOT_TOKEN (+ Notion IDs) in .env
uv run python -m notion_pilot
```

## Optional — Email / Discord

```bash
uv sync --extra email     # IMAP
uv sync --extra discord
```

Credentials in `.env` activate adapters automatically (see `.env.example`). For email senders routed to People, set `NOTION_PEOPLE_DATA_SOURCE_ID` and `NOTION_COMPANIES_DATA_SOURCE_ID`.

## Try the inbox pipeline without a chat adapter

```bash
uv run python examples/example.py
```

Builds a fake `IncomingMessage`, runs enrichment, writes to your Notion DB.
