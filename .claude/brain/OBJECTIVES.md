# Objectives

## Goal

Self-hosted messaging → Notion bridge: capture messages, media, and voice notes from Telegram (and future messaging apps) into a structured Notion database with optional LLM enrichment.

## Success Criteria

- Daily personal use for knowledge management without friction
- Sellable/distributable on the Notion ecosystem (clean setup, good docs, MIT license)
- Reliable enrichment pipeline: title, tags, type, source, description, interest level auto-filled

## Scope

- Telegram as first-class input source
- Text, photos, documents, video, GIFs, voice notes (with on-device transcription)
- Notion as the sole output target
- Optional LLM enrichment via OpenRouter (heuristics fallback if no key)
- Long-polling only (no webhook server)
- Single-user, self-hosted deployment (systemd user service)

## Non-Goals

- Building or hosting an LLM
- Webhook server / always-on HTTP endpoint
- Multi-user SaaS
- Storing media long-term outside Notion
- Supporting other knowledge bases (100% Notion-focused output)
- Other messaging apps *now* — but the architecture should not preclude adding them later
