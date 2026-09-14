# Notion Pilot

[![CI](https://github.com/ldom1/notion-pilot/actions/workflows/ci.yml/badge.svg)](https://github.com/ldom1/notion-pilot/actions/workflows/ci.yml)
[![Latest tag](https://img.shields.io/github/v/tag/ldom1/notion-pilot?label=tag&sort=semver)](https://github.com/ldom1/notion-pilot/tags)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://astral.sh/uv)

**Deploy the CRM into your Notion workspace in minutes. Run it from Claude Code with our skills and an optional local MCP, on your own machine. Your CRM records are stored in your Notion workspace; what your assistant reads is processed by your assistant's provider.**

Developers: self-host capture channels (Telegram, email, Discord) → [Wiki: Self-host](https://github.com/ldom1/notion-pilot/wiki/Self-host).

## 1. Deploy the CRM

1. Open [notion-pilot.com](https://notion-pilot.com/).
2. Click **Deploy the CRM to Notion** and authorize with your Notion account (or paste an internal integration token).
3. Name the CRM page and choose where it should live. Share that page with the integration if Notion asks.

The CRM page opens on your pipeline: views under **This week**, a prompt to paste into your assistant, and **Sources & documentation**.

## 2. Run it from your assistant

Install the **[notion-pilot-powers](https://github.com/ldom1/notion-pilot-powers)** plugin (Claude Code):

```
/plugin marketplace add ldom1/notion-pilot-powers
/plugin install notion-pilot-powers@notion-pilot-powers
```

Skills + optional local MCP ship from that repo. Connect Notion's hosted MCP so the assistant can reach the CRM pages you just deployed — see [Notion MCP setup](https://developers.notion.com/guides/mcp/get-started-with-mcp).

## 3. Data & EU

**Where your data goes.** Your CRM records are stored in your Notion workspace. On the **Notion Enterprise plan**, Notion can host that workspace in the EU (Frankfurt); on other plans, Notion stores it in its default region (US). Region and terms are set by your agreement with Notion ([details](https://www.notion.com/help/data-residency)). EU hosting covers CRM data stored in Notion, not AI processing. When your assistant reads CRM records, that content is processed by your assistant's provider (e.g. Anthropic for Claude), under the provider's data processing terms; Notion's residency does not cover it. Notion states that some of its own AI processing can also happen outside the residency region. notion-pilot.com deploys the CRM structure and keeps no CRM records and no Notion access token.

## Developers

Self-host the web wizard, optional inbox bot, Docker, systemd, and CLI scripts:

- [Wiki: Self-host](https://github.com/ldom1/notion-pilot/wiki/Self-host) — Docker Compose, `.env` / Infisical, Coolify notes, submodule checkout
- [Wiki: Capture-channels](https://github.com/ldom1/notion-pilot/wiki/Capture-channels) — Telegram, email, Discord
- [Wiki: CLI-scripts](https://github.com/ldom1/notion-pilot/wiki/CLI-scripts) — `scripts/crm/*`, `scripts/inbox/*`

## Develop (contributors)

```bash
git clone --recurse-submodules https://github.com/ldom1/notion-pilot && cd notion-pilot
uv sync
uv run pytest tests/unit -v
uv run ruff check . && uv run mypy notion_pilot
```

Frontend: `cd web/frontend && npm ci && npm run build` (also `make check-frontend`).

Contributions welcome. Short & sharp.
