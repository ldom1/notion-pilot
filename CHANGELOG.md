# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Renamed project to **Notion Pilot** (`notion-pilot` / `notion_pilot`)
- Reorganized package structure: `shared/` core, `inbox/` (formerly `pipelines/`), `crm/`, `scripts/crm/`
- GitHub repo renamed from `telegram-to-notion` to `notion-pilot`

### Added
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
