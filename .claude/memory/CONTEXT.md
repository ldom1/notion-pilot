---
type: context
updated:
---

# Context

## What's Done

- v1.0.0 shipped: core Telegram → Notion pipeline, CI, LICENSE, CONTRIBUTING, CHANGELOG
- Full enrichment pipeline: text, photos, documents, video, GIFs, voice notes (faster-whisper)
- LLM enrichment via OpenRouter (heuristics fallback if no key)
- Multi-adapter architecture: Telegram, Email (IMAP), Discord
- CRM module fully functional: `/lead`, `/people`, `/company`, `/deal`, `/enrich`, `/knowledge`
- Deployed on devbox as systemd user service

## Current Branch

`develop` (2026-07-15) — PR #16 (thin CRM sync layer: SIREN auto-population + enrichment migration to prosper, squash `0d22d45`) and PR #18 (MCP server, squash `8e705b7`) both merged. See [[2026-07-14-crm-rationalization-execution]] and `[[2026-07-15-mcp-server-test]]` for details.

**PR #19 open, not yet merged** (`mcp-crm-fixes` → `develop`): fixes all four bugs found in the live test above — People DB schema mismatch, "Rte France"/"RTE" duplicate creation, wrong-SIREN attachment, no fallback enrichment. See [[2026-07-16-mcp-crm-fixes]].

## What's New (2026-06-04, UX polish)

### Cockpit layout
- Panel order: Chat → Workspace → Automation
- Workspace panel moved above Automation for discoverability

### Ask your data (ChatPanel)
- Chat input anchored to bottom of fixed-height (280px) card via `historyRef.scrollTop` (no page scroll hijack)
- Example prompt buttons (light violet chips) shown when chat is empty; clicking auto-sends
- "Deal" renamed to "Lead" throughout visible UI
- Lead creation modal rewritten: single form showing all fields at once (no step-by-step wizard)
- On lead creation: last assistant message written as purple 🤖 callout block on Notion page
- On lead creation: company auto-linked via relation (exact title match in Companies DB + auto-detected relation property in Deals DB)
- Success screen shows "Open in Notion ↗" link

### Workspace panel
- Linking a DB shows per-card loading state (dim + spinner + "loading" label) while single-key refresh runs
- After re-link, only the changed DB is re-fetched (`/api/cockpit/status/{key}`) — not all 8
- Error footer shows "⚠ check access" when Notion API returns error

### Backend fixes
- `filter_properties: []` removed from Notion query pagination (was causing 400 on all DBs)
- `CreateDealRequest` gains `summary` and `company_name` fields
- DB_DEFS: `"Deals"` label renamed to `"Leads"`
- New endpoint: `GET /api/cockpit/status/{key}` — single-DB status refresh

## Open Decisions

- Notion conversation history persistence (log chat to a Notion page) — not yet implemented
- Notion OAuth: currently using public integration (client_id + secret from env)
- Company linking uses exact title match — fuzzy match not implemented

## Next Steps

1. Fix Telegram conflict error (two getUpdates pollers running simultaneously)
2. Improve LLM prompt to prevent fictional/unknown contacts in lead suggestions
3. End-to-end test: sign-out → OAuth → cockpit → run script → compose workflow → save → run from list
4. Add `crm_prospect.py` to `config/scripts.yaml` once CLI args confirmed
5. Phase 5: `data/{workspace_id}/` namespacing, LinkedIn upload endpoint, shared bot dispatcher
6. Notion conversation history (log chat sessions to Notion — roadmap item)
7. Phase 2: email "à relire" pipeline

## Web module layout

```
web/
  config.py          ← constants, DB helpers, workflow helpers; DB_DEFS label "Leads" (was "Deals")
  server.py          ← FastAPI router (21 routes incl. /api/cockpit/status/{key})
  models.py          ← Pydantic models; CreateDealRequest has summary + company_name
  utils.py           ← load_scripts, extract_*_prop, notion_page_url
  oauth.py           ← Notion OAuth helpers
  workspaces/        ← gitignored, per-workspace runtime data
    {workspace_id}/
      cockpit_config.json   ← DB ID pointers + workspace_url
      workflows.json        ← user-composed automation workflows
  static/            ← Vite build output (index.html + assets/)
  frontend/
    src/
      pages/Cockpit.tsx          ← panel layout, savingDbId state
      features/chat/ChatPanel.tsx ← Ask your data, example prompts, lead modal
      features/workspace/WorkspacePanel.tsx ← per-card save loading state
      features/automation/AutomationPanel.tsx ← scripts + graph view
      styles/globals.css         ← all UI styles
```

## In Progress
<!-- added by ai-dotfiles upgrade -->

- MCP server (`notion_pilot/mcp/`) merged to `develop` 2026-07-15 (PR #18, squash `8e705b7`) — 11 tools (upsert/dedup/enrich/rank/search/read), registered in this repo's `.claude/settings.json` as `notion-crm` (needs a Claude Code restart to connect for real via stdio).
- **Resolved (2026-07-16), shipped in open PR #19, not yet merged:** the live-test blocker above (People DB schema mismatch) plus the "Rte France"/"RTE" duplicate, wrong-SIREN-attachment, and no-fallback-enrichment bugs from `[[2026-07-15-mcp-server-test]]` are all fixed. See `[[2026-07-16-mcp-crm-fixes]]` and DECISIONS.md 2026-07-16 entry.

## Open Questions
<!-- added by ai-dotfiles upgrade -->

- Both prior open questions here are resolved (schema fix: changed the code, not the live DB; SIREN lookup: now returns top-3 candidates with a name-divergence gate) — see DECISIONS.md 2026-07-16 entry.
- **New:** `web/server.py`'s `/lead` and web-cockpit person-create path independently writes to the same wrong `"Nom"` property — same root cause as the fixed bug, different code path, not covered by PR #19. Needs its own fix.
- **New:** archive the stale, empty "Rte France" duplicate Notion page (`39e6c451-9465-81d1-ad4e-f80e58fc3070`) — deferred until PR #19 is merged and the original live test is re-run to confirm it now resolves to `needs_review` against "RTE" instead of creating a duplicate.
