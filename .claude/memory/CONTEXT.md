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

## What's New (2026-09-13)

- **CRM home dashboard (spec rev 6)** implemented via SDD (Tasks 1–9 + review harden). Branch `feat/crm-home-dashboard`, [PR #30](https://github.com/ldom1/notion-pilot/pull/30) → `develop`, CI green. See [[2026-09-13-crm-home-dashboard]].
- Stack #28 → #29 → #27 already on `develop` earlier the same day.
- Live gate: linked views list as `child_database` / `Untitled` on Notion-Version `2022-06-28`. Scratch parent remains `3d76c451-9465-80f3-9ee8-dd9f840f31bf`.
- **Uncommitted WIP (do not mix into #30):** landing/cockpit dogfood (Logo, SceneBg, Header, AssistantSetupPanel, SetupWizard deploy UX, static assets). Stash may include `dogfood-cockpit-globals`.

## Current Branch

`feat/crm-home-dashboard` (2026-09-13) — PR #30 open against `develop`. Local `develop` pointer may still sit on the same tip until merge; prefer the feature branch for the CRM home work.

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
- **New (2026-09-10):** two PRs open against `develop`, both CI-green, awaiting review — **#27** (landing page redesign + cockpit on the shared design system + CRM readiness audit + marketing deck) and **#28** (CRM v1 schema: Activities + Meetings in the deploy wizard). Neither is merged.
- **Resolved (2026-09-10, was blocking #28):** the back-relation behaviour is now **proven against the real Notion API**, not assumed. `dual_property: {}` does create a reverse property; Notion names it `Related to <child db> (<property>)`, **not** the target's name; the rename to `Activities` succeeds; and a rollup keyed on the resolved name is accepted. Hardcoding `"Activities"` would have keyed a rollup on a nonexistent property → 400 → aborted deploy, so `_resolve_back_relation` is load-bearing rather than defensive.
- **New (2026-09-10):** `.env.example` still lacks `NOTION_MEETINGS_DATABASE_ID`. A permission rule blocks Bash access to that file, so it was left alone; the `Settings` field exists, so the variable already works.
- **Resolved (2026-09-10):** the readiness audit (`docs/notion-pilot-crm-readiness-audit.md`) answered "is the public integration end-to-end ready" — no, and #28 closes the schema half of it. Still open from that audit: OAuth tokens live only in the signed cookie (`web/server.py`), so no background job can act on a workspace connected through the wizard, and the `notion-crm` MCP server binds one static workspace at import so it cannot serve per-user OAuth.

## Where the work stands (2026-09-13)

**PR stack merged into `develop`.** Tip `c38aea0`.

| PR | Status |
|---|---|
| #27 landing + cockpit design system | merged |
| #28 CRM v1 schema (Activities + Meetings) | merged |
| #29 wizard parent page | merged (closed; base was stacked on #28) |

**Next:** polish the Notion-side CRM template (views / dashboard / readiness), validate live, then prod cut for communication.

Conflict resolution note: develop keeps #29 `parent_page_id` + capabilities + bounded search, with #27 monochrome tokens and tree wizard UI; `_setup_host` nests a named CRM under a chosen page.

## Where the work stands (2026-09-11)

**Three PRs open, stacked. Nothing merged yet.**

| PR | Branch → base | Contents |
|---|---|---|
| [#27](https://github.com/ldom1/notion-pilot/pull/27) | `feat/landing-and-cockpit-redesign` → `develop` | Landing page rewrite, cockpit on the shared token layer, readiness audit, executive deck, `.claude-plugin` manifests, product-marketing doc, **this project brain** |
| [#28](https://github.com/ldom1/notion-pilot/pull/28) | `feat/crm-v1-schema` → `develop` | CRM v1 schema (Activities + Meetings in the wizard, rollups, SIREN/finance, English vocabulary), cockpit `log-activity`, Notion contract integration tests, Playwright suite |
| [#29](https://github.com/ldom1/notion-pilot/pull/29) | `feat/wizard-parent-page` → **`feat/crm-v1-schema`** | Deploy wizard can target a parent page; capability probe; searchable page picker |

**Merge order matters.** #29 is stacked on #28, so land #28 first (or merge #29 into #28 and land them together), then #27. Only #27 touches `.claude/memory/` — deliberately, so the other two cannot conflict on it.

`develop` was published this session as the remote integration base (it had existed only locally, 60 commits behind `main` with zero unique commits, so refreshing it to `main` discarded nothing). CI already gates its integration-test job on that branch name.

**Uncommitted on `feat/landing-and-cockpit-redesign` (2026-09-11):** the three landing-page films — `promotion/video/` (sources + briefs + shared design system), `web/frontend/public/film/` (3 MP4s + posters, 6.7 MB), the `#film` section in `Landing.tsx`, `.lp-film*` in `landing.css`, `.gitignore`, `README.md`, `CHANGELOG.md`. `hyperframes check` is 0 errors on all three; `tsc -b` and `npm run build` pass. Not committed, so PR #27 does not show them yet. See [[2026-09-11-landing-page-films]].

## Verified against the live Notion API (do not re-litigate)

- **Views (2026-09-13):** board on select Stage without nested `group_by.group_by`; `formula.checkbox`, `next_month`, `past_month` accepted; reverse insertion after **This week** yields §1 order; `parent.database_id` is the linked block id; `DELETE /v1/blocks/{id}` on `2022-06-28` removes a linked view; append returns only new blocks in order. Linked views list as `child_database` titled `Untitled` (×4) — not Leads/Activities.
- A dual relation's reverse property is auto-named `Related to <db> (<prop>)`; `synced_property_name` is read-only on create. Renaming it afterwards works, and a rollup on the resolved name is accepted.
- `parent: {"workspace": true}` is **rejected for internal integrations**: *"Internal integrations aren't owned by a single user, so creating workspace-level private pages is not supported."* Only a public-integration OAuth token can create top-level pages.
- `GET /v1/users/me` → `bot.owner.type == "workspace"` for an internal integration. (The `"user"` value for an OAuth token is **still unverified** — only an internal token was available.)
- With a parent page, an internal-integration token completes a full five-database wizard deploy in ~30s. Both test deploys were archived.
- The live CRM's People and Companies are on the legacy `data_sources` API, so `GET /databases/{id}` 404s on them. A wizard-deployed workspace creates all five as real `databases`, so this only affects tooling pointed at the Artelys workspace.
- `/v1/search` returns pages **and** database rows together. One call is ~0.8s; walking a real CRM to collect container pages took 45s, which is why the pages endpoint is bounded by requests and accepts a query.

## Active blockers / unknowns

- **`bot.owner.type == "user"` unverified.** The capability probe fails soft (assumes top level is allowed), so a wrong answer degrades to previous behaviour rather than blocking. Confirm with one real OAuth token; the parent-page spec names a probe-free fallback if it is ambiguous.
- **`.env.example` still lacks `NOTION_MEETINGS_DATABASE_ID`.** A permission rule blocks Bash on that file. The `Settings` field exists, so the variable works — this is a docs gap only.
- **`.claude-plugin` manifests unverified.** Schema-correct but `/plugin` cannot be invoked non-interactively. Run `/plugin marketplace add ldom1/notion-pilot` once before advertising it.
- **Cockpit is visually unverified.** It needs a live Notion session to render; only compilation and token resolution were checked. Wants eyes on selected-tab contrast and the dark log panel after `make dev`.
- **`make dev` cannot be driven by an agent (2026-09-11).** `infisical` is `Permission denied` under the agent sandbox, so the FastAPI half never binds :8080 and every `/api/*` call 502s through the Vite proxy; the `make dev` wrapper then exits on its own a few minutes later, taking Vite with it. Anything needing the backend — the cockpit check above included — has to be run by a human shell (`! make dev`). Vite alone is enough for the landing page and the films, which are static.

## Resuming: the commands that matter

```bash
# full CI gate locally
uv run ruff check . && uv run ruff format --check . \
  && uv run mypy notion_pilot && uv run pylint notion_pilot --fail-under=9.5 \
  && uv run pytest tests/unit -q
cd web/frontend && npm run build && npm run e2e      # 436 unit + 10 hermetic e2e

# real-Notion tests (prod Infisical trips an OAuth-localhost guard, hence the override)
export INFISICAL_ENV=prod \
  NOTION_OAUTH_REDIRECT_URI="https://notion-pilot.dombot.tech/auth/notion/callback"
uv run pytest tests/integration/test_notion_schema_contract.py -v -s   # needs the scratch page shared

# live wizard deploy (creates and archives a real page under the scratch parent)
uv run uvicorn web.server:app_factory --factory --port 8099            # note: app_factory, not create_app
uv run python scripts/e2e/mint_session.py --base-url http://127.0.0.1:8099
cd web/frontend && E2E_LIVE_BASE_URL=http://127.0.0.1:8099 \
  E2E_NOTION_PARENT_PAGE_ID=3d76c451-9465-80f3-9ee8-dd9f840f31bf \
  E2E_NOTION_TOKEN=<token> npm run e2e:live
```

Scratch page for real-API tests: **99 - Integration** (`3d76c451-9465-80f3-9ee8-dd9f840f31bf`), shared with the integration. Delete `web/frontend/e2e/.auth/state.json` when done — it holds a real token.

