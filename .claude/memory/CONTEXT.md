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


## What's New (2026-07-24)

- New skill `company-open-data-enrichment` (SIREN/BODACC/RNE enrichment via direct open-data API fallback, since Prosper MCP is early-stage/not reliably live) + a Finance section (`CA`/`Résultat net`/`Marge nette %`/`Année financière` as real Notion properties, sourced from RNE, gated on high-confidence SIREN). PR #25 open (`feat/add-skills` → `main`), 9 commits, doc-only, brainstorm→spec→plan→subagent-driven-development execution with per-task + final whole-branch review, not yet merged. See [[2026-07-24-companies-finance-section]].
- Live-tested the direct-API path on **RTE** (SIREN `444619258`): high-confidence match, BODACC clean (86 filings, no insolvency), RNE 2024 CA €5,558,953,000 / résultat net €171,258,000 / margin ≈3.08%, 19 dirigeants. Confirms the fallback path is solid — this is real data, not a fixture.
- **Blocker (root-caused this session, see DECISIONS.md 2026-07-24):** `notion-crm` MCP server crashed on startup because `INFISICAL_ENV` was unset (defaults to `"prod"` in `Settings()`'s OAuth validator, tripping on the default localhost redirect URI) — same class of failure as the 2026-07-17 note below, now understood precisely. Fixed via `"env": {"INFISICAL_ENV": "dev"}` in `.claude/settings.json`/`.cursor/mcp.json`'s `notion-crm` entries; a `/resume` did **not** pick this up (MCP servers spawn at process start) — needs a full quit-and-relaunch to verify.
- Second test company "LCH" (from a pasted `app.notion.com` link) stayed fully blocked — `WebFetch` can't authenticate to Notion (redirect loop), so no identity was ever established for it without MCP access.
- **`notion-crm` MCP confirmed still broken across three separate sessions**, including one the user confirmed was a genuine fresh terminal + direct `claude` launch — `claude mcp list`/`get`/`ToolSearch` all show nothing despite `~/.claude.json`'s project-scoped config being verified correct each time. Root cause still open; pivoted to a proven, now-documented workaround instead of chasing it further (see below).
- **Direct-Notion-API fallback proven and documented**: `notion_pilot`'s own `Settings()` + `notion_client.AsyncClient` used directly (same client the app's syncers already use), bypassing MCP entirely. Two gotchas found and worked around: `INFISICAL_ENV=dev` holds an **invalid placeholder Notion token** (the real one is under `prod`, which needs a one-off `NOTION_OAUTH_REDIRECT_URI` override to dodge the OAuth-localhost guard — client-side only, no real config touched); the real Companies data source uses the **legacy `data_sources` API**, not `databases` — `ensure_siren_property()`-style idempotent-create helpers in `syncer.py` only cover the `databases` path and silently no-op on this workspace. Now documented as an accepted MCP fallback in `skills/company-open-data-enrichment/SKILL.md` prerequisite #1.
- **RTE and LCH Finance writes completed live** (the two blocked test companies from the first entry): RTE got all 4 Finance properties created + written (CA €5.56B, margin 3.08%, 2024); LCH got real values with a genuine `ca=0`-blank-margin edge case (2017, only year on file).
- **Batch Finance run across all 22 open (non-Closed-Lost) leads**: 13 companies got real Finance data written; 4 had no RNE accounts filed (valid SKIP); Gasunie/ENNOH have no French SIREN (foreign entities, permanent SKIP for this French-only workflow); CRE's SIREN (`110000106`) was newly resolved. Followed by a full-enrichment pass (Sector/Size/Country/Website/Linkedin) on the same 22, using user-supplied corroboration (LinkedIn/registry pages pasted directly) for the genuinely thin rows (CRE, Gasunie) and 5 Linkedin-only gaps.
- **Two real code bugs found (not fixed this session):** (1) `notion_pilot/shared/siren_lookup.py::naf_section_to_sector()` produces Sector values (`"Public Sector"`, `"Energy"`, `"Finance"`, etc.) that don't match this workspace's actual live Sector select options (`"Government & Public Sector"`, `"Energy & Utilities"`, `"Financial Services"`, etc.) — would create stray new select options if ever run for real. (2) The Companies data source **has no `Notes` property at all**, contradicting the skill doc's assumption that BODACC/dirigeants get written there.
- See [[2026-07-24-companies-finance-section]] for the full multi-session writeup (4 continuation entries).

## What's New (2026-07-22)

- Cursor `.cursor/mcp.json` registers `notion-crm` over stdio (mirrors `.claude/settings.json`).
- Project skill `skills/notion-crm-ops/` (symlinks under `.cursor/skills/` + `.claude/skills/`): Artelys CRM ops via Notion MCP with mandatory FR preview table. See [[2026-07-22-session-capture]].
- Live CRM ops this session: Hexana/CRE/MAIF/Michelin/LCH/Air Liquide/Axa/MS4All leads + activities; people/companies enrichment (Massa, Lalaurette, MS4All, etc.).
- MS4All People enriched (LinkedIn/Position/Seniority/Role Type): Edouard Lété, Coralie Feillault, Zoheir Laguel — Phone still `needs_review`.
- **Blocker:** `NOTION_DEALS_DATABASE_ID` / `NOTION_ACTIVITIES_DATABASE_ID` often unset in local Settings — Leads/Activities writes went through Notion MCP OAuth, not stdio. Companies DS may 404 for the Lgiron API **dev** integration token.

## Current Branch

`develop` (2026-07-17) — PR #16, #18, and #19 all merged (#19: `mcp-crm-fixes`, squash `af2d718` — People DB schema mismatch, "Rte France"/"RTE" duplicate creation, wrong-SIREN attachment, no fallback enrichment). See [[2026-07-14-crm-rationalization-execution]], `[[2026-07-15-mcp-server-test]]`, [[2026-07-16-mcp-crm-fixes]].

**3 PRs open, none yet merged** (all from `origin/develop`, split out of the [[2026-07-16-mcp-people-knowledge-fixes-plan]] implementation):
- PR #20 (`workstream-a-mcp-thin-wrapper`) — `upsert_companies` MCP thin-wrapper refactor + a live-test-discovered fix: `upsert()` now enforces the same SIREN-divergence `needs_review` gate `preview()` already had.
- PR #21 (`workstream-b-people-parsing`) — `/people` markdown-link paste parsing + sanitized Telegram errors.
- PR #22 (`workstream-c-knowledge-enrichment`) — richer multi-link Notion knowledge pages.

See [[2026-07-17-mcp-people-knowledge-fixes]] for the full implementation + live-test bug writeup.

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
- **Resolved (2026-07-16), shipped, PR #19 merged (`af2d718`):** the live-test blocker above (People DB schema mismatch) plus the "Rte France"/"RTE" duplicate, wrong-SIREN-attachment, and no-fallback-enrichment bugs from `[[2026-07-15-mcp-server-test]]` are all fixed. See `[[2026-07-16-mcp-crm-fixes]]` and DECISIONS.md 2026-07-16 entry.
- **New (2026-07-17), shipped in open PR #20, not yet merged:** Task A7's live retest against production Notion surfaced a second SIREN-gate gap — `upsert()` didn't enforce the same divergence block `preview()` already had, and created 2 real, unreviewed company pages. Fixed and both pages archived. See [[2026-07-17-mcp-people-knowledge-fixes]] and DECISIONS.md 2026-07-17 entry.

## Open Questions
<!-- added by ai-dotfiles upgrade -->

- Both prior open questions here are resolved (schema fix: changed the code, not the live DB; SIREN lookup: now returns top-3 candidates with a name-divergence gate) — see DECISIONS.md 2026-07-16 entry.
- **New:** `web/server.py`'s `/lead` and web-cockpit person-create path independently writes to the same wrong `"Nom"` property — same root cause as the fixed bug, different code path, not covered by PR #19. Needs its own fix.
- **Still open:** the stale, empty "Rte France" duplicate Notion page (`39e6c451-9465-81d1-ad4e-f80e58fc3070`) has not been archived yet — PR #19 merged 2026-07-16, so this can now be actioned (re-run the original live test first to confirm it resolves to `needs_review` against "RTE", then archive).
- **Resolved (2026-07-17):** the *separate* "Ugent"/"Sqli" pages created by this session's SIREN-gate `upsert()` bug (see DECISIONS.md 2026-07-17 entry) were archived after the fix shipped.
- **New (2026-07-17):** a Pydantic `ValidationError` on an unrelated sibling field (`NOTION_OAUTH_REDIRECT_URI`) dumped a partial real Notion OAuth token via its raw `input_value`. User explicitly chose not to rotate it — left as-is. Avoid printing raw `Settings` field values on validation errors going forward; print booleans/derived facts only.
- **Root-caused (2026-07-24):** the trigger for that same `NOTION_OAUTH_REDIRECT_URI` validator is `INFISICAL_ENV` defaulting to `"prod"` when unset — see DECISIONS.md 2026-07-24 entry. Fixed for the `notion-crm` MCP server specifically; still open whether other local entry points (scripts, other MCP configs) have the same gap.
- **Resolved via workaround (2026-07-24):** `notion-crm` MCP still does not connect even after a confirmed genuine fresh relaunch — root cause remains open, but no longer blocking, since the direct-Notion-API fallback (`Settings()` + `notion_client.AsyncClient`) is now proven and documented in the skill. RTE and LCH's Finance writes are done; a full batch (13 more companies, plus Sector/Size/Country/Website/Linkedin enrichment on all 22 open leads) is also done. See [[2026-07-24-companies-finance-section]].
- **New (2026-07-24):** `naf_section_to_sector()` in `siren_lookup.py` doesn't match the live Companies Sector select options — needs a fix (either update the hardcoded vocabulary or read the DB's actual options at runtime) before it's used for real again.
- **New (2026-07-24):** the Companies data source has no `Notes` property — the `company-open-data-enrichment` skill's BODACC/dirigeants `[open-data]` block plan doesn't apply to this real workspace as written; needs either a schema addition (with explicit `go`) or a skill-doc correction.
