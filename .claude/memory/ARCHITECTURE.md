---
type: architecture
updated:
---

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
- Deploy: Coolify-managed containers on hp-elite-server (migrated off the devbox systemd service, 2026-07-20)

## Planned Layers

```
Layer 1 (done):   Multi-source ingestion  → Notion DB row (enriched)
Layer 2 (now):    CRM vertical            → People/Companies/Deals + Telegram commands
Layer 3 (next):   Setup wizard            → virgin Notion bootstrap (CRM + Knowledge)
Layer 4 (later):  Email recap             → "à relire" tagging + Telegram summary
Layer 5 (later):  Website                 → landing + Notion OAuth deploy wizard + chatbot
```

## Key Modules
<!-- added by ai-dotfiles upgrade -->

- **`notion_pilot/mcp/`** (2026-07-13) — exposes the CRM vertical as MCP tools over stdio (`FastMCP`), for any MCP-aware client (not just Telegram). `session.py` caches a `SyncerSession` (People/Companies snapshot) per process with a background pre-warm at startup (via FastMCP's `lifespan` hook — pre-warm must NOT start at bare module-import time, since `asyncio.create_task` requires a running event loop). `tools.py` are thin wrappers calling straight into `crm/syncer.py`, `shared/utils/dedup.py`, `shared/prosper_client.py` (updated 2026-07-14 — was `shared/utils/enrichment.py` until that module was deleted in favor of prosper's MCP-based enrichment), `crm/prospection.py`, `crm/queries.py` — no duplicated business logic. `server.py` registers 11 tools: `upsert_people`, `upsert_companies`, `find_duplicates`, `enrich_people`, `enrich_companies`, `rank_contacts_for_pitch`, `search_people`, `search_companies`, `get_recent_people`, `get_open_leads`, `refresh_notion_snapshot`.
- **`notion_pilot/mcp/server.py::build_http_app()`** (2026-07-22) — same `mcp` FastMCP instance, additionally reachable over `streamable-http` at `/mcp` when `web/server.py` mounts it (only if both `NOTION_TOKEN` and `MCP_BEARER_TOKEN` are set). Gated by a static bearer token (`_BearerTokenMiddleware`), not FastMCP's built-in OAuth resource-server auth — there's no real authorization server behind this, just a shared secret. `web/server.py` combines `mcp.session_manager.run()` into its own FastAPI lifespan via `AsyncExitStack` (Starlette does not run a mounted sub-app's lifespan automatically) and redirects bare `/mcp` → `/mcp/` (Starlette's `Mount` only matches with a trailing slash). This HTTP surface acts on the single global `NOTION_TOKEN` workspace — not the per-session OAuth workspaces the cockpit UI uses.

## Non-Obvious Decisions
<!-- added by ai-dotfiles upgrade -->

- **MCP write tools default to `confirm=false` (dry-run preview)** — every tool that writes to Notion (`upsert_people`, `upsert_companies`, `enrich_people`, `enrich_companies`) computes and returns what *would* happen without calling any Notion write endpoint unless the caller passes `confirm=true`. Mirrors `crm_enrich.py`'s existing `--dry-run` flag, generalized to every write tool.
- **Company dedup fuzzy matching does not catch legal-suffix variants** (e.g. "EDF" vs "EDF S.A." scores ~55, well under the 85 threshold) — the existing `token_sort_ratio`-based algorithm in `shared/utils/dedup.py` has no legal-suffix-stripping. Confirmed while implementing the MCP `find_duplicates`/`upsert_companies` tools (2026-07-13): don't assume near-miss company-name pairs will dedup — verify empirically before writing tests/fixtures around this matcher.
- **People DB title property is `"Name"`, not `"Nom"`** (2026-07-16 fix, PR #19) — `NotionPeopleSyncer` and `shared/workspace.py`'s People DB template both use `"Name"`; there is no `"In my network"` property. Company dedup in `upsert_companies` is now a strict 4-signal chain (domain match → `token_sort_ratio>=85` → `token_set_ratio>=90` acronym/subset containment → create), enforced identically in preview and on write. SIREN lookup returns top-3 candidates gated by a `token_sort_ratio>=85` name-divergence check against the candidate's matched name; `force=True` bypasses only the Notion-dedup review, never this SIREN gate. See DECISIONS.md 2026-07-16 entries.
- **`str = Field(...)` in a Pydantic model only requires the key be present, not non-empty** (2026-07-22) — `PersonRecord.name`/`.company` were already "required" but an MCP client could still pass `name=""` and create a blank-titled Notion page. Fixed with a `NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]` alias, applied to `name`/`company` on both records plus `PersonRecord.linkedin_url` and `CompanyRecord.website`/`.linkedin_url`/`.country`/`.sector` (user's explicit choice — `size`/`contact_email`/`position`/`email`/`phone`/`seniority` intentionally left unconstrained). `crm/syncer.py` already guards every optional field with a truthy check before writing to Notion, so this was purely a required-field gap, not a broader pattern.
- **`StreamableHTTPSessionManager.run()` can only be entered once per process, ever** (2026-07-22) — since `mcp` (`notion_pilot/mcp/server.py`) is a module-level singleton, a second `with TestClient(...)` context that re-enters its lifespan raises `RuntimeError`. Constrains test structure (tests/unit/mcp/test_server.py's bearer-auth test owns the one live-lifespan assertion; tests/unit/web/test_server.py's mount test checks 401s without entering the app as a context manager, since the bearer middleware rejects before touching session state). Also means uvicorn `--reload` re-executing code does NOT re-read env vars — adding `MCP_BEARER_TOKEN` required a full `make dev` restart, not just a reload, before the mount activated.
