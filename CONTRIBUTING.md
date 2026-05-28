# Contributing

Thanks for your interest! This project is small and opinionated — PRs that keep it that way are very welcome.

## Before you open a PR

1. **Open an issue first** for anything larger than a typo or one-liner. Saves rework.
2. Fork, branch off `main`, and keep commits focused.
3. Match the existing tone: short, direct, no speculative abstractions.

## Dev setup

```bash
git clone https://github.com/ldom1/notion-pilot && cd notion-pilot
cp .env.example .env   # fill in TELEGRAM_BOT_TOKEN, NOTION_TOKEN, NOTION_DATABASE_ID
uv sync
```

## The CI contract

Your PR must pass all of the following locally (CI runs the same set):

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy notion_pilot
uv run pylint notion_pilot --fail-under=9.5
uv run pytest tests/unit -v
```

Integration tests (`tests/integration/`) hit real Notion + OpenRouter + Whisper. They're not run in CI — run them locally before a release if you touched any I/O path:

```bash
uv run pytest tests/integration -v
```

## Commit style

Short conventional commits. Examples from the log:

```
feat(llm): structured prompt, source hints
fix(notion): data_source parent + Telegram replies
deps: ship faster-whisper in main dependencies
```

## Releasing

Versioning is derived from git tags via `hatch-vcs`. To ship a release:

```bash
git tag vX.Y.Z
git push --tags
./deploy.sh --tag vX.Y.Z       # deploys to devbox (maintainers only)
```

`__version__` and PyPI metadata update automatically.

## Style & scope

- Python 3.12, `uv`, Pydantic v2, `loguru`, `notion-client`, `python-telegram-bot`.
- No new top-level dependencies without a clear reason.
- New features behind opt-in env vars when possible.
- Docs: update `README.md` for user-facing changes, `CHANGELOG.md` for every release.
