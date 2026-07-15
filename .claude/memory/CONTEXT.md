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

`feat/crm-rationalization-notion-pilot` (2026-07-14) — thin CRM sync layer migration, PR [#16](https://github.com/ldom1/notion-pilot/pull/16) open against `develop`, not merged. See [[2026-07-14-crm-rationalization-execution]] for details. (This line was stale — previously pointed at `feat/notion-pilot-cockpit`, several branches/sessions behind.)

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

- MCP server (`notion_pilot/mcp/`) fully implemented (2026-07-13) on branch `feat/mcp-crm-server`, in an isolated worktree at `.claude/worktrees/feat-mcp-crm-server` — **uncommitted**, per explicit no-commit instruction for that session. Needs: review diff → commit → merge.
- **Merge hazard resolved (2026-07-14):** `feat/mcp-crm-server` has been rebased onto the current tip of `feat/crm-rationalization-notion-pilot` (`1befdb4`) and its `tools.py`/`test_tools_enrich.py` import updated from the deleted `shared.utils.enrichment` to `shared.prosper_client` (mechanical fix — identical signatures/dataclass shapes). 293/293 unit tests pass, ruff + mypy strict clean, stdio smoke check clean, both before and after. The branch is now current and mergeable; see [[2026-07-14-crm-rationalization-execution]] for the rebase log.

## Open Questions
<!-- added by ai-dotfiles upgrade -->

- Should the `feat/mcp-crm-server` branch merge into `feat/crm-rationalization-notion-pilot`/PR #16 before that PR merges to `develop`, or wait until after? (No longer a hazard either way — the import fix is already applied — this is now purely a merge-ordering/PR-hygiene question.)
