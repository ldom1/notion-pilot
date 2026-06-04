# Context

## What's Done

- v1.0.0 shipped: core Telegram → Notion pipeline, CI, LICENSE, CONTRIBUTING, CHANGELOG
- Full enrichment pipeline: text, photos, documents, video, GIFs, voice notes (faster-whisper)
- LLM enrichment via OpenRouter (heuristics fallback if no key)
- Multi-adapter architecture: Telegram, Email (IMAP), Discord
- CRM module fully functional: `/lead`, `/people`, `/company`, `/deal`, `/enrich`, `/knowledge`
- Deployed on devbox as systemd user service

## Current Branch

`feat/notion-pilot-cockpit` — Phase 4 complete.

## What's New (2026-06-03, iteration 2)

### Automation panel (React Flow)
- `web/static/cockpit.html` — Automation section rebuilt: **List view** (default, Operations + Workflows tabs) and **Graph view** (React Flow canvas, connectable nodes, workflow composition)
- `web/server.py` — 20 routes total; new: stop-script, deals-properties, create-deal (wizard fields), workflows CRUD, run-workflow (topological SSE)
- `_running_procs` dict enables stop-script from cockpit

### Chat ("Ask your data")
- `notion_pilot/shared/llm/crm_chat.py` — NEW: `chat_crm()` with multi-turn history + intent detection (`suggest`|`create`|`info`)
- Deal creation is now a **client-side wizard**: fetches Deals DB schema → asks Product/Type/Stage/etc. as clickable options → creates deal on confirm
- Bug fixed: false "✓ created" badge replaced with "📋 confirm below"
- Chat history persisted in `localStorage`; sent to LLM for context on follow-ups

### Config/layout
- `web/config.py` (was `web/cfg.py`) — restored natural name
- `web/workspaces/{workspace_id}/` (was `web/creds/`) — avoids name collision; stores `cockpit_config.json` + `workflows.json`
- `web/models.py` — `ChatMessage`, `CreateDealRequest(extra_fields)`, workflow models

### Tests
- `tests/unit/web/test_cockpit.py` — 30 new tests; 172 total unit tests passing

## Open Decisions

- Notion conversation history persistence (log chat to a Notion page) — not yet implemented
- Notion OAuth: currently using public integration (client_id + secret from env)

## Next Steps

1. End-to-end test: sign-out → OAuth → cockpit → run script → compose workflow → save → run from list
2. Add `crm_prospect.py` to `config/scripts.yaml` once CLI args confirmed
3. Phase 5: `data/{workspace_id}/` namespacing, LinkedIn upload endpoint, shared bot dispatcher
4. Notion conversation history (log chat sessions to Notion — roadmap item)
5. Phase 2: email "à relire" pipeline

## Web module layout

```
web/
  config.py          ← constants, DB helpers, workflow helpers
  server.py          ← FastAPI router (20 routes)
  models.py          ← Pydantic models
  utils.py           ← load_scripts, extract_*_prop, notion_page_url
  oauth.py           ← Notion OAuth helpers
  workspaces/        ← gitignored, per-workspace runtime data
    {workspace_id}/
      cockpit_config.json   ← DB ID pointers + workspace_url
      workflows.json        ← user-composed automation workflows
  static/
    index.html        ← landing + deploy wizard
    cockpit.html      ← cockpit UI (React Flow, chat, workspace panel)
```
