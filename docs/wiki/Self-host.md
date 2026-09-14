# Self-host

Developer path: run the web wizard and optional inbox bot on your own machine or server. Customers use [notion-pilot.com](https://notion-pilot.com/) instead.

## Clone (with submodule)

CRM core + stdio MCP live in `vendor/notion-pilot-powers`. Always recurse submodules:

```bash
git clone --recurse-submodules https://github.com/ldom1/notion-pilot
cd notion-pilot
# if you already cloned without submodules:
git submodule update --init --recursive
```

## Env

```bash
cp .env.example .env
# Fill NOTION_TOKEN and OAuth / session vars as needed.
# Docker Compose expects .env.bootstrap (Infisical machine identity) — see comments in .env.example.
```

- **Without Infisical:** set app secrets directly in `.env` (leave `INFISICAL_CLIENT_ID` unset).
- **With Infisical:** fill `INFISICAL_CLIENT_ID` / `SECRET` / `PROJECT_ID` in `.env.bootstrap`; app secrets come from Infisical at runtime.

Public Notion OAuth (web wizard) also needs:

```env
NOTION_OAUTH_CLIENT_ID=…
NOTION_OAUTH_CLIENT_SECRET=…
NOTION_OAUTH_REDIRECT_URI=https://yourhost/auth/notion/callback
WEB_SESSION_SECRET=a-long-random-key
```

## Docker Compose (web + bot)

```bash
cp .env.example .env.bootstrap   # at least Infisical fields, or fall back to plain .env
docker compose build
docker compose up -d
```

- **web** — landing, deploy wizard, cockpit (`:8080` exposed internally)
- **bot** — Telegram long-polling; comment out the service if unused

Persist cockpit configs: `./data/workspaces` → `/app/web/workspaces` (already in `docker-compose.yml`).

## Local web without Docker

```bash
uv sync --group web
./launch_webserver.sh
# open http://localhost:8080
```

## Inbox bot (optional adapters)

```bash
uv sync
uv run python -m notion_pilot
```

Adapters activate when their credentials are present (`TELEGRAM_BOT_TOKEN`, IMAP_*, `DISCORD_*`). See [[Capture-channels]].

## systemd (example)

```bash
# after installing a user unit that runs `uv run python -m notion_pilot`
systemctl --user restart notion-pilot.service
journalctl --user -u notion-pilot.service -f
```

## Coolify notes

- Register every public hostname on the Coolify app (Traefik matches `Host`).
- Ensure the deploy does a **recursive** submodule checkout.
- Map a persistent volume for `web/workspaces` (cockpit configs) across deploys.

## CLI setup (no web)

```bash
# CRM + knowledge inbox:
uv run python scripts/crm/crm_setup_workspace.py --parent-id <PAGE_URL> --with-inbox
# CRM only / inbox only — see [[CLI-scripts]]
```

Copy printed IDs into `.env`.
