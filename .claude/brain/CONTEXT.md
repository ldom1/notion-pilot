# Context

## What's Done

- v1.0.0 shipped: core Telegram → Notion pipeline, CI, LICENSE, CONTRIBUTING, CHANGELOG
- Full enrichment pipeline: text, photos, documents, video, GIFs, voice notes (faster-whisper)
- LLM enrichment via OpenRouter (heuristics fallback if no key)
- Multi-adapter architecture: Telegram, Email (IMAP), Discord
- CRM module fully functional on `feat/refactor`:
  - Telegram commands: `/lead`, `/people`, `/company`, `/deal`, `/enrich`, `/knowledge`
  - LLM field extraction from free-form messages
  - Conversation state machine (SQLite)
  - NotionPeopleSyncer, NotionCompanySyncer, NotionDealsSyncer
  - Apollo.io enrichment, Brave Search fallback
  - `scripts/crm_setup_workspace.py`: bootstraps Companies + People + Deals in Notion
- Deployed on devbox as systemd user service

## Current Branch

`feat/refactor` — CRM pipeline complete. Phase 0 refactoring (rename to notion-pilot) is the next step.

## Open Decisions

- Config unification: `notion_people_database_id` vs `notion_people_data_source_id` — two IDs for same table, to be merged
- Notion OAuth approach for deploy wizard (Phase 4): internal integration vs public OAuth app

## Next Steps

1. Phase 0: rename repo + package → `notion-pilot` / `notion_pilot`, reorganize into `crm/` `inbox/` `shared/`
2. Phase 1: setup wizard for Knowledge DBs (`scripts/inbox/setup_workspace.py`)
3. Phase 2: email "à relire" pipeline

## Product Vision (validated 2026-05-28)

**Notion Pilot** — two products, one mono-repo:
- `notion-crm`: small sales teams (2-10 people), People/Companies/Deals + Telegram commands
- `notion-inbox`: personal knowledge management, multi-source capture + LLM enrichment
- Website: landing + Notion OAuth deploy wizard + chatbot
