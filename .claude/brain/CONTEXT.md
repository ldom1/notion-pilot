# Context

## What's Done

- v1.0.0 shipped: core Telegram → Notion pipeline, CI, LICENSE, CONTRIBUTING, CHANGELOG
- Full enrichment pipeline: text, photos, documents, video, GIFs, voice notes (faster-whisper)
- LLM enrichment via OpenRouter (heuristics fallback if no key)
- Multi-adapter architecture: Telegram, Email (IMAP), Discord
- CRM module fully functional: `/lead`, `/people`, `/company`, `/deal`, `/enrich`, `/knowledge`
- Deployed on devbox as systemd user service
- Cockpit (Phase 4): chat panel, workspace panel, automation panel — UX polished

## CRM Schema Redesign (2026-06-29/30)

Full 5-database CRM redesign executed via Notion API migration scripts. All scripts in `scripts/crm/`.

**Live DB IDs:**
- Deals (Commercial): `4890e1d6-178d-4a42-af06-7bbe0cef09fe`
- People: `11b5f43c-a19a-4bec-9489-7c6897ed30fb`
- Companies: `cfc21198-9684-47ef-98ae-fc5657511998`
- Meetings: `e94cc98f-2f66-4c53-ac6d-62b9d8f7d5aa`
- Activities: `38f6c451-9465-814d-a383-ce59038b6e8d` (⚠️ the original ID `38f6c451-9465-8166-a862-e531d15f467f` was accidentally trashed in Notion UI ~2026-06-30/07-02; there were two Activities DBs — always verify `in_trash`/`archived` before trusting a cached ID)

**Key schema changes applied:**
- Deals: Lead Source (7 options), 9 Stages (incl. Discovery/First Meeting, No Answer, Waiting for Response), Expected Close Date, Owner (person), Created time, Meetings relation, Weighted Value formula fixed
- People: Name (was Nom), Priority (🔥/🌡/🧊), Relationship (Close/Warm/Cold/None), Lead Source
- Companies: Revenue Potential, Sector (11 options), Size (7 buckets), Market Segment (was Activities)
- Meetings: Name (was Nom), Tags (was Étiquettes), Deal relation ↔ Deals, Company relation, Meeting Objective, Advanced Deal? checkbox
- Activities: new DB — Type (8 options), Outcome (4 options), Deal/Person/Company relations, Owner (person), Next Step, Next Step Date

**Formulas on Deals (Notion Formula 1.0 API — binary or/and, no cross-formula refs):**
- Days Since Last Activity: terminal→0, no activity→999, else dateBetween
- Deal Age (days): dateBetween(now(), Created time, "days")
- Deal Temperature: terminal→"—", ≤7→🔥 Hot, ≤21→🌡 Warm, else ❄️ Cold
- Stale Deal: open + empty Next Step + >14 days since activity
- Next Step Scheduled: not(empty(Next Step Date))

**Pending manual steps:** follow `scripts/crm/NOTION_UI_STEPS.md` in Notion UI (views, dashboard, automation, People option remapping)

**Env var (set):** `NOTION_ACTIVITIES_DATABASE_ID=38f6c451-9465-814d-a383-ce59038b6e8d`

## CRM Deal List Review + Prosper Enrichment (2026-07-02)

Full pass over all 29 leads in the Deal Board: backfilled 18 Activities from the Meetings backlog, filled Notes/Next Step/Primary contact per-deal based on live conversation with Louis, enriched 27/29 linked Companies via the Prosper MCP server (SIREN, Website, Country, Sector, Size, Clearbit logo as page icon — no dedicated Logo property).

**New Companies property:** `SIREN` (rich_text) — added for durable Prosper lookups, avoids re-searching every enrichment pass.

**Prosper MCP details:** runs locally at `http://localhost:8090`, SSE transport only (no native Claude Code tool registered — must hand-roll the MCP `initialize`/`tools/call` handshake over SSE each session). Covers ~23M French SIREN entities (`gold.companies`) + curated ~93k layer; has no logo/website/non-French data. Large public entities (EDF, Veolia, RTE, MAIF) often show `is_active: false` on their well-known parent SIREN — appears to be stale registry data in Prosper's build, not real status.

**Reusable prompt** for repeating this workflow (mapping tables, gotchas, cold-prospect default template) written to session scratchpad — not yet copied into the repo. Consider moving it into `scripts/crm/` if this becomes a recurring task.

## Current Branch

`main` — CRM redesign complete (10 commits, 8370168→81dcb93).

## Open Decisions

- Notion conversation history persistence (log chat to a Notion page) — not yet implemented
- Notion OAuth: currently using public integration (client_id + secret from env)
- Company linking uses exact title match — fuzzy match not implemented
- Meetings→Activities automation: the built-in Notion agent ran out of credits (as of 2026-07-02) — treat as unavailable; Activities must be created manually/via Claude Code until re-funded

## Next Steps

1. Run `scripts/crm/NOTION_UI_STEPS.md` checklist in Notion UI
2. Remap existing People records (Priority and Relationship old option values) in Notion UI
3. Add `NOTION_ACTIVITIES_DATABASE_ID` to `.env` and devbox infisical
4. Fix Telegram conflict error (two getUpdates pollers running simultaneously)
5. Add `crm_prospect.py` to `config/scripts.yaml` once CLI args confirmed
6. Phase 5: `data/{workspace_id}/` namespacing, LinkedIn upload endpoint, shared bot dispatcher
7. Notion conversation history (log chat sessions to Notion — roadmap item)
8. Phase 2: email "à relire" pipeline

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
