# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- MCP server now optionally reachable over HTTP (`streamable-http` transport) at `/mcp` on the web service, gated by a static bearer token (`MCP_BEARER_TOKEN`) — in addition to the existing stdio transport. Mounted only when both `NOTION_TOKEN` and `MCP_BEARER_TOKEN` are set; acts on that single Notion workspace, not per-session OAuth workspaces.
- Cockpit MCP panel: tools grouped into collapsible "Write · confirm required" / "Read-only" sections with a kind badge per tool, based on actual `confirm`-gated write behavior in `notion_pilot/mcp/tools.py`.

### Fixed
- `upsert_people`/`upsert_companies` MCP tools: `PersonRecord.name`/`.company` and `CompanyRecord.name` now reject empty/whitespace-only strings (previously only required the key to be *present*, so an empty `name` could create a blank-titled Notion page). Same non-empty-if-provided constraint added to `PersonRecord.linkedin_url` and `CompanyRecord.website`/`.linkedin_url`/`.country`/`.sector`.

### Fixed
- Cockpit chat: resolve People → Company relation names when building CRM context; rehydrate lead names from `notion_id` when the LLM returns placeholders like `[PERSON_NAME]`; drop unresolvable placeholder leads.
- Local dev: `.infisical.json` project ID updated to dedicated `notion-pilot` project (`71e743d9-…`); `make dev` uses `--env dev --path /`.
- Cockpit: Notion status/chat queries fall back to `data_sources` API when `databases` returns 404; clearer access-denied message in UI.
- Local dev: `WEB_SECRET_KEY` accepted as alias for `WEB_SESSION_SECRET` (OAuth 500 when only the legacy name was set).

### Changed
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
