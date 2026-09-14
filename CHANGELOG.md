# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- **P6 copy + docs:** Landing hero/meta/JSON-LD drop EU and “self-hosted” claims outside the canonical **Where your data goes** disclosure (D15/D19/D22). README is customer-path only (deploy → notion-pilot-powers → Data & EU); Options A/B, inbox bot, systemd, Docker, and CLI detail moved to the GitHub Wiki (Self-host / Capture-channels / CLI-scripts); Artelys skills and MCP server sections removed from README. **Breaking for install docs:** customer install is the two-line `notion-pilot-powers` plugin (see P5), not `notion-crm@notion-pilot`.
- **P5 handoff:** Customer plugin install is now `notion-pilot-powers` (two commands). CRM home + cockpit assistant panel updated; old `notion-crm@notion-pilot` three-line install kept in `LEGACY_TEMPLATE_TEXTS` so CRM refresh rewrites it. Cockpit: copy buttons for the four `userConfig` IDs, least-privilege integration note, Disconnect (T1–T3), heading clarifies the assistant runs on the machine. MCP panel lists the 12 always-on tools (no `uv --directory` clone path). Old marketplace (`.claude-plugin/`, `skills/`) **moved to [notion-pilot-powers](https://github.com/ldom1/notion-pilot-powers)**; Artelys specifics live in `.claude/skills/artelys-crm/`. Local MCP configs use `artelys-crm` + Infisical.
- **P4 cockpit cleanup:** Removed unused hosted surfaces — chat/conversations/memory, deal/lead wizard, scripts runner, workflows, Telegram status/ping UI+API, and `crm_chat.py`. Session cookie uses `https_only` + `max_age=3600` in production; SPA catch-all returns 404 for `api/`/`auth/`/`mcp` (not HTML). `docker-compose.yml` persists `./data/workspaces` → `/app/web/workspaces`.
- **P3 vendor split:** CRM core + stdio MCP live in `vendor/notion-pilot-powers` (editable path dep). `Settings` subclasses `CRMSettings`. HTTP `/mcp` mount removed from the web server (use local `python -m notion_pilot_powers.mcp.server`). Docker/CI fetch the submodule. Lock resolves `notion-client` to 2.x (powers `~=2.2`).
- Messaging aligned on CRM-you-own / AI assistant (HITL): README lead and setup no longer require Telegram; Telegram/email/Discord are optional adapters. Canonical public URL is `https://notion-pilot.com/` (`notion-pilot.dombot.tech` 301s there).
- Landing SEO: canonical, Open Graph/Twitter, JSON-LD, self-hosted Archivo/IBM Plex (no Google Fonts), `<main>` landmark, schema heading order, `.lp-who` contrast; unused agent/collab films removed from the web build (sources stay under `promotion/video/`).
- Web server: serves `/robots.txt`, `/sitemap.xml`, `/og-image.jpg`, `/film/*`, `/fonts/*` before the SPA catch-all; long-cache for assets/fonts/film; security headers (HSTS, nosniff, Referrer-Policy, Permissions-Policy, X-Frame-Options).

### Added
- `web/frontend/public/robots.txt`, `sitemap.xml`, `og-image.jpg`, and self-hosted `fonts/`.
- GitHub Wiki: Home, Setup, Capture-channels, FAQ (Telegram optional).
- Sitemap `<lastmod>`, `og:site_name` / `og:locale`, and a CI guard that `/sitemap.xml` is XML (not the SPA).

### Added
- CRM home page shows this week's pipeline first: 📊 Pipeline, ⚠️ Needs attention, 📅 Closing in the next 30 days and 🕘 Recent activity, created as linked views during deploy.
- A ready-to-paste assistant prompt and a "Sources & documentation" section on the CRM home, mirrored in a new cockpit panel.
- `scripts/crm/crm_upgrade_home.py` refreshes an existing CRM home in place, keeping databases, rows and your own blocks.
- `NOTION_VIEWS_VERSION` (default `2025-09-03`) selects the Notion API version for views.
- Homepage films (`promotion/video/`): three silent 16:9 clips authored as HyperFrames HTML compositions on the site's own token layer (`_shared/np.css` mirrors `web/frontend/src/styles/tokens.css`) and rendered to MP4. `notion-pilot-pipeline` (21s) walks one real email through the whole loop — the agent searching before it writes, the four-record diff, the approval, the Leads/Activities rows moving, the pipeline formulas recomputing; `notion-pilot-agent` (16s) shows the actual `confirm=false` tool call and the preview it returns, then the four rules; `notion-pilot-collab` (19s) shows three people dictating from chat into one shared workspace and the board that is current by 14:21. Each project carries a `BRIEF.md` (intent + beat sheet); every figure, stage and record in them also appears in `Landing.tsx`. Localised Archivo/IBM Plex Mono (`_shared/fetch-fonts.sh`) because a render must not fetch anything at frame time. See `promotion/video/README.md` for the authoring and publishing loop.
- Landing page: new `#film` section (`Film` component + `.lp-film*` in `landing.css`) playing `notion-pilot-pipeline` from `/film/<slug>.mp4` as a muted autoplay loop at the full 1180px measure — half-width columns halve the type inside the frame and the tables stop being readable. It sits directly after the pipeline-decay beat, so it answers the question that section raises; the other two films stay in the catalog rather than on the page, since agent HITL and collaboration are already told by the surfaces and EU/Enterprise sections. A reader whose OS asks for reduced motion gets the poster frame and real controls instead of autoplay. MP4s are remuxed with `+faststart` so playback begins before the file finishes downloading.
- Marketing deck for the Notion CRM story: `docs/notion-pilot-crm-executive-deck.pptx` (15 executive slides + 4 appendix), generated by `scripts/marketing/generate_crm_deck.py` from `docs/marketing/brand-palette.json`, plus a speaker sheet `docs/notion-pilot-crm-deck-talk-track.md` (per-slide talk track, timings, appendix triggers, objection handling, and a "never say" list covering data-residency and metric claims).
- Deck: new Part 1 slides on automated pipeline KPIs (rollups/formulas/grouped views, with an explicit "dashboards are configuration, not defaults" caveat) and on Notion Enterprise governance (storage region — EU residency framed as an Enterprise option to confirm with Notion, never a guarantee — plus SSO/SCIM/audit log and teamspaces).
- Deck: removed the on-screen "Slide purpose — …" band from every slide (it read as internal scaffolding left in a client-facing deck); the purpose text is now the first line of each slide's PowerPoint speaker notes, and the reclaimed space raises the hero/body zones (body grows 3.85" → 4.3"). Headlines and support lines rewritten for punch — same verifiable claims, no new promises.
- Deck: design system rebuilt in `scripts/marketing/generate_crm_deck.py`. The brand mark from `docs/marketing/notion-pilot-promo/assets/logo.svg` is now drawn from native PowerPoint shapes (rounded square + glyph + accent dot), so it appears on every slide and in the title lockup while staying vector and editable — python-pptx cannot embed SVG and no rasterizer is available. PowerPoint tables were dropped entirely in favour of shape-based row cards (no theme grid lines, controlled spacing and fills), and three slides that were carrying their content badly were rebuilt: the ASCII-art architecture diagram became a real 4-stage flow with arrow connectors and a highlighted middle stage (S8), the thin timeline beside an empty grey box became a chevron journey plus input/output panels and a Won/Lost outcome strip (S11), and the pilot-plan table became three numbered step cards with week badges under a filled ask callout (S13). S9's screenshot placeholder is now a stylised capture-conversation illustration (labelled as an illustration), S12 became a two-panel IS / IS-NOT comparison using new `positive`/`negative` palette accents, and remaining appendix placeholders are dashed-outline. Every slide gained a top phase rule, an accent bar over the hero, and a footer rule with wordmark and page number.
- Deck: two new slides — a CRM schema slide showing the four real databases (Companies and People → Leads/Deals → Activities) with labelled relations, plus an Activity-types card that answers "where are meetings?" (a meeting is an Activity type; there is no Meetings database, per `skills/notion-crm-ops/references/activities.md`) — and a closing call-to-action slide pairing "what we need from you" against "what you have in four weeks" over a booking-call band with a dashed fill-in-before-sending placeholder.
- Deck: all copy extracted to `docs/marketing/crm-deck-content.json` so marketing can edit text without touching Python; the generator now holds layout only. Slide numbers are computed from position, so slides can be added, removed or reordered without renumbering (this previously had to be done by hand). Also sets PPTX core properties (title/author/subject/keywords/category), names the significant shapes for the PowerPoint Selection pane, stamps `meta.version` into every footer so a stale deck is visible at a glance, and reads the font from the content file. New `docs/marketing/README.md` documents the edit/rebuild loop, the pre-send checklist, and the known constraints (Segoe UI is Windows-only, no PDF export on the build machine, alt text unset).
- Homepage rewritten as a full marketing narrative (`web/frontend/src/pages/Landing.tsx` + new `web/frontend/src/styles/landing.css`): Claudeforce hook → why Notion is the system of record → the five-database schema with automation badges → a dark "but who keeps this up to date?" band naming the formula properties that decay → Telegram vs AI-agent capture → a worked email-to-pipeline agent transcript → EU data residency (Frankfurt, free on Enterprise) → deploy and MCP setup. Replaces the single-screen three-bullet hero. Mock CRM rows are fictional; the column names and stage vocabulary mirror the live schema.
- `docs/notion-pilot-crm-readiness-audit.md`: audit of the public-integration deploy path and agent access. Findings: the deploy creates 3 of 5 databases (no Activities, so `log_activity` raises on a fresh workspace — `mcp/tools.py:450`), `Companies.Activities` is a multi-select rather than a relation (`workspace.py:838`), the bootstrapped Leads schema is missing the four formula properties plus two live Stage options, and the OAuth token is held only in the signed cookie session (`web/server.py:293`) so no background job can act on a connected workspace. Also documents that the `notion-crm` MCP server is bound to a single static workspace at import (`mcp/server.py:31`) and therefore cannot serve per-user OAuth workspaces — with official Notion MCP setup for Claude Code and Cursor as the agent-exploration path.
- Deck correction: the schema slide said "a meeting is an Activity type, not a separate database". The Notion export disproves it — Meetings is a real database related from both `Activities.Meeting` and `People.Meetings`. Slide 4 is now five entities with AUTOMATED/MANUAL badges, and appendix A4 distinguishes what the deploy creates from what exists in Notion.
- Project skill `company-open-data-enrichment` (`skills/company-open-data-enrichment/`) to enrich/create Artelys CRM Companies from French open data (SIREN, NAF/APE, BODACC, RNE, dirigeants): Prosper MCP preferred (early-stage, not always live) with a direct-API fallback documented step-by-step — SIREN via `recherche-entreprises.api.gouv.fr/search?q=`, BODACC via `bodacc-datadila.opendatasoft.com` `/records` filtered by `registre`, RNE dirigeants/finances via the same `recherche-entreprises` endpoint queried by SIREN — French validation table + `go` before write, `[open-data]` Notes replace-not-append; symlinked into `.cursor/skills/` and `.claude/skills/`.
- `company-open-data-enrichment`: adds a Finance section to Companies — `CA`, `Résultat net`, `Marge nette %`, `Année financière` as real Notion properties (Number/Euro, Number/Euro, Number/Percent, Number), sourced from RNE `finances` (same `recherche-entreprises.api.gouv.fr` SIREN query used for dirigeants), gated on a high-confidence SIREN, written directly via Notion MCP (not `upsert_companies`/`enrich_companies`, since financials must refresh annually and neither tool's create-only/fill-empty-only contract fits that) with guards against stale RNE years and mismatched existing property types; `[open-data]` Notes block no longer repeats the RNE financial summary now that it's a real property. Grouping the 4 properties into a "Finance" section in Notion is a manual one-time step (not exposed by the API).
- Project skill `notion-crm-ops` (`skills/notion-crm-ops/`) for Artelys CRM ops via Notion MCP (Leads / Activities / People / Companies): always French validation table before write; symlinked into `.cursor/skills/` and `.claude/skills/`.
- Cursor project MCP config (`.cursor/mcp.json`) registers `notion-crm` over stdio (`uv run python -m notion_pilot.mcp.server`), matching `.claude/settings.json`.
- MCP server now optionally reachable over HTTP (`streamable-http` transport) at `/mcp` on the web service, gated by a static bearer token (`MCP_BEARER_TOKEN`) — in addition to the existing stdio transport. Mounted only when both `NOTION_TOKEN` and `MCP_BEARER_TOKEN` are set; acts on that single Notion workspace, not per-session OAuth workspaces.
- Cockpit MCP panel: tools grouped into collapsible "Write · confirm required" / "Read-only" sections with a kind badge per tool, based on actual `confirm`-gated write behavior in `notion_pilot/mcp/tools.py`.
- MCP: Deals ("Leads") and Activities databases now accessible — `upsert_deal` (matched by exact title, reuses the existing `NotionDealsSyncer`, now also covering `Lead Source`/`Primary contact`/`Expected Close Date`), `log_activity` (append-only, no dedup — new `notion_pilot/crm/activities.py`), and `get_activities` (recent activities, optionally scoped to one Deal). `get_open_leads` now includes `page_id` for linking Activities to a specific deal. Requires `NOTION_DEALS_DATABASE_ID`/`NOTION_ACTIVITIES_DATABASE_ID` (the latter setting was previously undocumented in `Settings` despite being in `.env.example`).

### Changed
- Cockpit assistant setup now leads with the non-technical path (Notion Settings → Connections → Notion MCP, Help + Claude connector; skill guides as project instructions) and tucks CLI / `mcp.json` under a “For the dev” disclosure. Doc links stack on two rows; Claude, Mistral, ChatGPT and Cursor named in both steps. MCP panel lede cut to two lines.

### Fixed
- Cockpit “Your AI assistant” panel was unstyled: `setup-*` classes were used in `AssistantSetupPanel` (and the sources lede) but never defined, so headings, default-blue links and raw `<pre>` collapsed into one wall of text. Now a two-column card layout with the same code block, type, and link treatment as the rest of the cockpit.
- Cockpit was still rendering the old "Ask your data" chat panel — `AssistantSetupPanel` existed but `Cockpit.tsx` had never been switched over to it. Swapped it in and removed the now-dead `ChatPanel`/`ConversationSidebar`/`MemoryEditor`.
- MCP Server panel's Write/Read-only tool lists were `<details open>`, so both sections rendered fully expanded (14 tool cards) regardless of the collapsible markup — the panel took most of the page. They now start collapsed.
- Header had no mobile layout: the badge, workspace name, user name and buttons overflowed the viewport horizontally below ~640px instead of wrapping. Drops the redundant "COCKPIT" badge and gives the workspace name its own row on narrow screens.
- Header logo rendered the new SVG mark at browser-default intrinsic size (no CSS constrained it) — oversized and misaligned next to the wordmark. Fixed at 22×22px.
- Landing footer tagline forced `white-space: nowrap`, pushing the whole page 38px past the viewport width on mobile (the only element actually overflowing the page, as opposed to a scrollable container). Removed; it wraps normally now.
- Homepage films never rendered in production: `Landing.tsx`'s `<Film>` requests `/film/<slug>.mp4` and `.jpg` directly, but only `/assets` and `/static` were mounted — `/film/...` fell through to the SPA catch-all, which returned `index.html` with a 200, so the `<video>` element silently had an HTML document as its source. Added a dedicated `/film` static mount.
- Landing nav (`Notion Pilot` wordmark + `Deploy to Notion` + `Sign in`) was ~12px too tight below 420px — the wordmark and "Sign in" each broke onto two lines instead of overflowing visibly. Both are now `white-space: nowrap`, with nav padding/gaps trimmed slightly under 420px to make room.
- Frontend production build (and therefore the Coolify deploy) failed with `TS2580: Cannot find name 'process'` in `vite.config.ts` — `@types/node` is only an optional peer dependency of vite and was never installed. `loadEnv` now takes `'.'` as its env directory instead of `process.cwd()` (identical resolution, no node globals).
- CI now builds the frontend (`npm ci && npm run build`, the same command `docker/Dockerfile.web` runs), so a broken production build fails the PR instead of the deploy. The previous local check, `tsc --noEmit`, silently type-checked nothing: the root `tsconfig.json` is a solution-style config (`"files": []` + `references`), and only `tsc -b` walks into the referenced projects. Also available locally as `make check-frontend`.

### Fixed
- `upsert_people`/`upsert_companies` MCP tools: `PersonRecord.name`/`.company` and `CompanyRecord.name` now reject empty/whitespace-only strings (previously only required the key to be *present*, so an empty `name` could create a blank-titled Notion page). Same non-empty-if-provided constraint added to `PersonRecord.linkedin_url` and `CompanyRecord.website`/`.linkedin_url`/`.country`/`.sector`.

### Fixed
- Cockpit chat: resolve People → Company relation names when building CRM context; rehydrate lead names from `notion_id` when the LLM returns placeholders like `[PERSON_NAME]`; drop unresolvable placeholder leads.
- Local dev: `.infisical.json` project ID updated to dedicated `notion-pilot` project (`71e743d9-…`); `make dev` uses `--env dev --path /`.
- Cockpit: Notion status/chat queries fall back to `data_sources` API when `databases` returns 404; clearer access-denied message in UI.
- Local dev: `WEB_SECRET_KEY` accepted as alias for `WEB_SESSION_SECRET` (OAuth 500 when only the legacy name was set).

### Changed
- The CRM home no longer mentions Telegram commands.
- Demo data: two leads now have close dates and one has no next step, so every home view shows a row on day one.
- The wizard lists any view Notion refused, with the manual steps on the CRM page.
- Landing: one vertical rhythm — `2rem` on every section, `1.65rem` on inner stacks.
- Landing: dropped Telegram from the homepage — capture story is the AI assistant only (paste, preview, go).
- Landing: setup wizard is CRM-only (no knowledge inbox), names the Notion page, and matches the ready-to-use CRM pitch.
- Setup wizard: choose workspace root or an existing Notion page as the CRM parent (`parent_page` on `/api/setup`).
- Setup wizard: deploy-location picker is a workspace tree; faint grid/graph motion behind the deploy screen.
- Setup wizard: “Under an existing page” lists workspace-root Notion pages A–Z (`GET /api/setup/pages`), not subpages or a paste-URL field.
- Setup wizard: CRM page name hangs under the selected parent in the tree, not below the whole list.
- Setup wizard: deploy log is a dark instrument panel (status marks + live spinner), not a dump of monospace lines.
- Setup wizard: page-list loading shows a small spinner beside “Loading pages…”.
- Setup wizard page list paginates Notion Search to completion and keeps `parent.type=workspace` only (Notion has no list-root endpoint). The previous 3-page cap is why only a few sidebar titles appeared.

### Fixed
- Setup wizard page list: Notion search is time-boxed (was walking up to 1000 results and leaving “Loading pages…” stuck).
- Landing: database-section headline now reads “It is not a CRM yet.”
- Landing: the Notion-as-database intro copy spans the same wrap width as the Companies table below it.
- Landing `#film`: one pipeline clip (played at 0.85×), placed after the decay beat instead of three autoplay films under Claudeforce. Dropped the production lede and the caption bodies; the HITL story stays in the Telegram/assistant surfaces (a diagram, not a second film of `confirm=true`); Notion-native collaboration is named in the EU/Enterprise band rather than a third film. Agent and collab MP4s remain under `/film/` for reuse.
- Landing: moved the France-only enrichment scope note from the hero into the footer.
- Local dev: removed `.env` / `NOTION_PILOT_DEV` fallbacks — secrets come from Infisical per environment (`dev`, `staging`, `prod`). Override with `INFISICAL_ENV=staging make dev`.
- Infisical: all envs use secret path `/` (was `/notion-pilot` for prod); SDK source reads `/global` then `/`.
- Infisical: renamed `NOTION_DATABASE_ID` → `NOTION_TELEGRAM_MSG_DATABASE_ID`, `NOTION_TITLE_PROPERTY` → `NOTION_TELEGRAM_MSG_DATABASE_TITLE_PROPERTY`; removed unused `NOTION_OAUTH_AUTHORIZATION_URL` and `NOTION_COMMERCIAL_DATA_SOURCE_ID`.

### Added
- Multi-link Telegram messages (≥2 URLs) now produce a richer Notion knowledge page: each link
  gets a heading + factual bullets (description, language, stars, topics where available) in the
  page body, plus a set-level Description summarizing the links as a whole — instead of a one-line
  Description with a blank body. A "Processing…" reply is sent first since this path is slower.
- `/people`: pasting a markdown-formatted contact (`[Name](linkedin_url), Company :`, optionally
  followed by a repeated LinkedIn URL line) is now parsed deterministically, bypassing the LLM;
  falls through to the LLM (rather than guessing) if a second URL in the message disagrees with
  the markdown link's URL.

### Fixed
- Telegram CRM errors (both the immediate-dispatch and step-by-step field-filling paths) now show
  a consistent, sanitized message — always the exception class name, never a raw Notion SDK error
  (which could leak page/database IDs or schema internals) — instead of a generic
  "Failed to save to Notion" with no detail on one path and an unsanitized raw message on the other.

### Added
- **Infisical secret manager** — all app secrets now live in Infisical (`Dom Universe` project, `prod` env, `/global` + `/notion-pilot` folders); `.env` replaced by `.env.bootstrap` (4 vars: client_id, client_secret, project_id, env)
- `infisical.json` — project config for the Infisical CLI (`infisical run --` local dev workflow)
- `.env.bootstrap.example` — template for bootstrapping Docker/devbox deploys
- `InfisicalSettingsSource` (`notion_pilot/shared/config.py`) — pydantic-settings v2 custom source; SDK (Universal Auth) path for Docker, CLI-injected env vars for local dev; per-path errors are non-fatal (warns + continues)
- `deploy.sh` — rewritten for Docker Compose (`git fetch → reset --hard → docker compose up --build -d`); replaces the old tag-based systemd script
- MCP server (`notion_pilot/mcp/`) exposing the CRM vertical as tools: `upsert_people`, `upsert_companies`, `find_duplicates`, `enrich_people`, `enrich_companies`, `rank_contacts_for_pitch`, `search_people`, `search_companies`, `get_recent_people`, `get_open_leads`, `refresh_notion_snapshot`. Stdio transport, dry-run-by-default on all write tools.
- `notion_pilot/shared/siren_lookup.py` — SIREN-by-name lookup via the French government's free company registry API (no key required); wired into `upsert_companies`, which surfaces the candidate SIREN in the `confirm=false` preview and only writes it once the caller repeats the call with `confirm=true`.
- `notion_pilot/shared/utils/dedup.py`: `find_match()` now matches people on an exact email/LinkedIn
  URL first, ahead of fuzzy name+company scoring.
- `upsert_companies`/`upsert_people`: `needs_review` status with actionable `candidates` and a
  human-readable `reason`; a per-record `force=True` input bypasses a `needs_review` dedup block on
  `confirm=true` (status comes back as `created_with_override`) without bypassing the SIREN
  confidence gate.
- `upsert_companies` on creation now attempts prosper's `enrich_company` and, for anything prosper
  didn't fill, falls back to the French government registry data already being queried for SIREN:
  sector (from the NAF code), size (from the headcount bracket), country (`"FR"`), and — failing
  everything else — a website guessed from a supplied `contact_email`'s domain. Shown in the
  `confirm=false` preview as `enrichment_preview` before being written.

### Changed
- `Makefile`: `dev` and `dev-backend` targets now wrap `launch_webserver.sh` with `infisical run --`; `deploy` delegates to `./deploy.sh`
- `launch_webserver.sh`: removed `.env` file reading; secrets come from Infisical CLI injection (`infisical run -- ./launch_webserver.sh`)
- Docker Compose: `env_file` changed from `.env` to `.env.bootstrap` (4 Infisical bootstrap vars only)

### Removed
- `scripts/crm/crm_enrich.py` — superseded by the MCP server's `enrich_people`/`enrich_companies` tools, which replicate its dry-run-by-default batch enrichment logic
- `scripts/crm/crm_setup_deals_db.py` — one-off patch (hardcoded DB id) for a notion-client 3.x bug dropping DB properties on creation; `shared/workspace.py`'s DB-creation path already applies and verifies properties generically

### Fixed
- `notion_pilot/crm/syncer.py`: `NotionPeopleSyncer` now reads/writes the People DB's real title
  property (`"Name"`) instead of a stale `"Nom"` — every person-creation call (MCP, `/people`,
  `/lead`, email-import, LinkedIn-import) was silently failing against this workspace; dropped the
  nonexistent `"In my network"` property too.
- `upsert_companies`: replaced the single fuzzy-name threshold with a 4-signal dedup chain (contact
  email domain match, exact/near-exact name, acronym/subset name via `token_set_ratio`) so
  "Rte France" now gets flagged against the existing "RTE" company instead of creating a duplicate.
- `upsert_companies`: a SIREN candidate whose registry name diverges too far from the input name (e.g.
  "Rte France" → an unrelated "VCSP ROUTE FRANCE") is now rejected instead of silently attached.
- `upsert_companies`: `preview()` already downgraded a `would_create` record to `needs_review` on
  SIREN-name divergence, but `upsert()` only skipped the SIREN field and created the company anyway
  — live-tested against production Notion this created 2 unreviewed company pages. `upsert()` now
  blocks creation on the same divergence unless `force=True`.
- Telegram CRM writes (`/people`, infer-confirm yes, multi-step commands): call `_enrich_settings_from_cockpit()` before handlers so People/Companies DB IDs from `cockpit_config.json` are used when env vars are unset (fixes `data_sources//query` 400 on save)
- LinkedIn contact paste (`URL : Name, Company, Position`): deterministic parser in `contact_parse.py` bypasses LLM; rejects `[PERSON_NAME]` placeholders; fixes wrong name/company/position on infer-confirm save
- Comma contact lines: deterministic parse only on explicit `/people`; smart routing uses LLM
- LinkedIn URL routing: `/in/…` → People, `/company/…` → Companies (`parse_linkedin_deterministic`)
- infer_confirm: `cancel` / `skip` / `rien` / `/cancel` discards without writing to any Notion DB
- CI: remove unused `pytest` import in `tests/unit/crm/test_recap.py`

### Added
- **CRM schema redesign** — full 5-database rework (Deals/People/Companies/Meetings/Activities) via
  Notion API migration scripts in `scripts/crm/`: Deals gets Lead Source, 9 stages, Expected Close
  Date, Owner, Meetings relation; People renamed `Nom`→`Name` with Priority/Relationship/Lead Source;
  Companies gets Revenue Potential, Sector, Size, and a durable `SIREN` property for Prosper lookups;
  new Activities DB is the CRM's event log (Type, Outcome, Deal/Person/Company relations, Next Step).
- Deal formulas (Notion Formula 1.0 API, binary `or`/`and`): Days Since Last Activity, Deal Age,
  Deal Temperature (🔥/🌡/❄️), Stale Deal, Next Step Scheduled.
- `scripts/crm/crm_sync_meetings_activities.py` — polls Meetings for `Advanced Deal?` = checked and
  creates the corresponding Activity record; replaces the Notion UI automation (paid-plan only).

### Added
- Deploy workflow: `workflow_dispatch` trigger for manual re-deploys
- `scripts/inbox/process_promotions.py` — batch Promotions folder → DomTelegramBot DB (dry-run, CSV review, dedup, `--from-csv`)
- Config: `IMAP_PROMOTIONS_FOLDER`, `IMAP_SINCE_DAYS`; email bodies fall back to stripped HTML
- Promotions review CSV: one-line summaries; `decision` = `Untouched` | `Treated and archived` | `Auto archived`
- `IMAP_AUTO_ARCHIVE_SENDERS` — archive without Notion (defaults include Medium admin senders; add Vivino etc.)
- Promotions live run: archive immediately after each Notion write (exact `IMAP_ARCHIVE` folder name)
- `scripts/inbox/process_promotions.py --limit=N` — process only the N newest messages (smoke test)
- Landing page: full marketing page with hero, CRM pipeline examples, two-product section, and how-it-works
- Notion OAuth deploy wizard: 3-step wizard (Connect → Choose scope → Name workspace) accessed from "Deploy to Notion" button
- `create_workspace_root_page` in `workspace.py`: creates a named page at Notion workspace root
- New config fields: `NOTION_OAUTH_CLIENT_ID`, `NOTION_OAUTH_CLIENT_SECRET`, `NOTION_OAUTH_REDIRECT_URI`, `WEB_SESSION_SECRET`
- **Setup wizard** — bootstrap a full Notion workspace (CRM + Knowledge inbox) in 3 ways:
  - CLI: `scripts/crm/crm_setup_workspace.py --with-inbox` or `scripts/inbox/setup_workspace.py`
  - Telegram: `/setup` command — guided multi-turn wizard (token → scope → parent page → `.env` output)
  - Web UI: FastAPI server (`web/`) with Notion OAuth (3-step wizard) at `http://your-server:8080`
- `launch_webserver.sh` — start the web UI; reads `NOTION_OAUTH_CLIENT_ID`, `NOTION_OAUTH_CLIENT_SECRET`, `NOTION_OAUTH_REDIRECT_URI`, `WEB_SESSION_SECRET` from `.env`
- `notion_pilot/shared/workspace.py` — shared workspace creation module (CRM + 4 Knowledge DBs)
- `web/server.py`, `web/auth.py`, `web/static/index.html` — FastAPI setup server with Notion OAuth
- Config: `NOTION_IDEAS_DATABASE_ID`, `NOTION_TOOLS_DATABASE_ID`, `NOTION_DATA_TECH_DATABASE_ID`

### Changed
- Email People capture now uses the central CRM `NotionPeopleSyncer` with deduplication and company sync instead of the removed `PersonContactProperties` direct writer.
- Removed the old `NOTION_PEOPLE_DATABASE_ID` config surface; use `NOTION_PEOPLE_DATA_SOURCE_ID` plus `NOTION_COMPANIES_DATA_SOURCE_ID`.
- `NOTION_DATABASE_ID` renamed to `NOTION_TELEGRAM_MSG_DATABASE_ID` (`NOTION_DATABASE_ID` still accepted)
- README `🚀 Quick Start` section covering all three setup options
- `crm/` package: `NotionPeopleSyncer`, `NotionCompanySyncer`, fuzzy dedup (`rapidfuzz`), Brave Search email enrichment
- `scripts/import_linkedin.py`: batch import of LinkedIn `Connections.csv` into Notion People database
  - Fuzzy dedup on Name+Company (skip ≥ 85, review 75–84, create < 75)
  - Company resolution: fuzzy match against existing Notion companies, auto-creates new ones
  - Optional Brave Search email enrichment (`--no-enrich` to skip, rate-limited 1 req/s)
  - Borderline matches written to `data/import-review.csv` for manual review
  - `--dry-run` mode: counts only, no Notion writes
- Config: `NOTION_PEOPLE_DATA_SOURCE_ID`, `NOTION_COMPANIES_DATA_SOURCE_ID`, `BRAVE_API_KEY` (all optional)
- Source adapter abstraction: `SourceAdapter` and `SinkAdapter` protocols in `telegram_to_notion/adapters/`
- IMAP email adapter: polls unseen messages, filters by sender allowlist (`IMAP_ALLOWED_SENDERS`), archives processed emails (`uv sync --extra email`)
- Discord adapter: source (messages → Notion) + sink scaffolded for future pipeline notifications (`uv sync --extra discord`)
- `pipeline.py`: shared enrichment + Notion write logic extracted from `bot.py`
- Optional dep extras: `uv sync --extra email`, `uv sync --extra discord`

### Changed
- `NOTION_TOKEN` is now optional (only required when running the Telegram bot, not the deploy wizard)
- `/api/setup` now accepts `workspace_name` instead of `parent_page` URL/ID
- `/api/setup` returns `{notion_page_url}` instead of a list of env var IDs
- Removed JWT admin login from the deploy wizard flow; OAuth replaces it
- Renamed project to **Notion Pilot** (`notion-pilot` / `notion_pilot`)
- Reorganized package structure: `shared/` core, `inbox/` (formerly `pipelines/`), `crm/`, `scripts/crm/`
- GitHub repo renamed from `notion-pilot` to `notion-pilot`
- `TELEGRAM_BOT_TOKEN` is now optional — bot starts with any configured adapter
- `IncomingMessage` has a new required field `source_adapter` (label in Notion reflects the source)

## [1.0.0] - 2026-04-18

First stable release. Consolidates the v0.1 → v0.3 iterations into a production-ready
pipeline: Telegram → local Whisper → OpenRouter → Notion, with CI, tagged releases, and
a tagged-deploy script.

### Added

- **Telegram → Notion core**: long-polling bot that forwards **text**, **photos**, and
  **voice notes** to a Notion database row.
- **On-device voice transcription** via `faster-whisper>=1.2.1` (model downloaded on first use;
  defaults to `base`, French). Configurable via `WHISPER_LANGUAGE` / `WHISPER_MODEL_SIZE`.
- **OpenRouter LLM enrichment** of each row (default model `google/gemini-2.5-flash-lite`):
  populates `Name`, `Label` (multi-select), `Type`, `Link`, `Source`, `Description`, `Interest`.
  Graceful heuristic fallback when `OPENROUTER_API_KEY` is unset.
- **Heuristic source detection** via `llm/source_hints.py` — GitHub, YouTube, arXiv, LinkedIn,
  Instagram, X, Substack, Medium, Figma, Spotify, TikTok, Reddit, Notion.
- **Prompt generated from the Pydantic model**: `llm/prompt.py` enumerates
  `NotionDatabaseProperties` fields so prompt keys always match Notion column names.
- **`NotionDatabaseWriter`** with async `create_page`, `update_page`, and **`delete_page`**
  (soft-delete via `archived=True`).
- **`/ping`** Telegram command for health checks.
- **Reply after each save**: bot replies with Notion page id, or a formatted error detail.
- **Runnable example** at `examples/example.py` — builds an `IncomingMessage`, enriches it,
  writes and archives a Notion page.
- **Unit test suite** (35 tests, ~0.5 s, no network) covering models, prompt, OpenRouter
  fallback paths, and source-hint heuristics.
- **Integration test suite** (5 tests) hitting real Notion / Whisper / OpenRouter:
  text + voice end-to-end with teardown archive, direct create/delete, example-mirroring,
  and an audio-fixture flow that **persists the transcript** to `tests/data/` for
  inspection.
- **GitHub Actions CI** (`.github/workflows/ci.yml`): `ruff check`, `ruff format --check`,
  `mypy --strict`, `pylint --fail-under=9.5`, unit tests.
- **Tagged deploy** — `deploy.sh` (uncommitted) with required `--tag <vX.Y.Z>` flag:
  fetches tags, detaches HEAD at the tag, `uv sync`, restarts the systemd user service on
  devbox. Optional `--env` (scp `.env`) and `--logs` (tail journalctl).
- **Dynamic versioning** via `hatch-vcs` — `__version__` (and package metadata) comes
  from the latest git tag. `importlib.metadata.version(...)` in `__init__.py`.
- **MIT `LICENSE`**, **`CONTRIBUTING.md`**, professional README banner
  (CI / tag / license / Python / uv badges).
- **Improved `.gitignore`** — grouped with comments; ignores `.env`, `deploy.sh`, `PLAN.md`,
  `tests/data/audio_example_transcript.txt`, Whisper weights, and the hatch-vcs
  `_version.py`.

### Changed

- **Drastically simplified `bot.py`**: from 7 private helpers to 4 public functions —
  `handle_telegram_message`, `health_check`, `build_application`, `run`.
- **OpenRouter call hardened**: posts to `/chat/completions` (was posting to the base URL),
  forces `response_format={"type": "json_object"}`, single `except Exception` fallback path,
  parses directly into `NotionDatabaseProperties.model_validate(...)`.
- **Notion payload fixed**: `to_notion_properties()` now emits typed Notion objects
  (`{"title": [...]}`, `{"multi_select": [...]}`, etc.) instead of raw strings.
  Empty optional fields are omitted to avoid 400s.
- **Async Notion client**: `NotionDatabaseWriter` uses `notion_client.AsyncClient`
  (the synchronous `Client` was returning dicts to `await`).
- **Media surface reduced** to photo + voice (removed document, video, animation).
- **Logging**: single loguru configuration to stderr, version embedded in the format
  (`v1.0.0`), no double-registration.
- **Docs**: new marketing-oriented README with a concrete before/after table and a
  4-command quickstart.

### Fixed

- `bot.py` bug where `writer.create_page(incoming, properties)` passed 2 args to a
  1-arg method (would crash on the first message).
- Stale `telegram_to_notion/media/__init__.py` still importing deleted modules
  (`animation`, `document`, `video`).
- `Settings` missing `whisper_language` / `whisper_model_size` — re-added.
- Prompt used lowercase JSON keys (`"title"`, `"type"`) that Pydantic silently dropped
  — now uses the Notion-aligned aliases (`"Name"`, `"Type"`, …) and marks `"Label"` as
  a required JSON array.
- Strict `mypy` now passes (added `pydantic.mypy` plugin; fixed `Any`→`str` return in
  `notion.py`; parameterised `Application[Any, …]`).
