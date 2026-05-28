# Context

<!-- Current state snapshot. Update at session end. -->

## What's Done

- v1.0.0 shipped: core Telegram → Notion pipeline, CI, LICENSE, CONTRIBUTING, CHANGELOG
- Full enrichment pipeline: text, photos, documents, video, GIFs, voice notes (faster-whisper)
- LLM enrichment via OpenRouter (heuristics fallback if no key)
- Deployed on devbox as systemd user service
- Notion agent (external, Notion-native) post-processes DB entries into structured meta-pages across 4 knowledge databases

## In Progress

- `feat/mail-management`: email as a second source adapter (design TBD)
- Brain init (this session): documenting project context

## Open Questions

- Adapter abstraction: what interface should source adapters expose? `bot.py` is the reference but no formal contract yet
- Product direction: keep as personal tool vs. build sellable enrichment platform (deep research, customer DB, contacts, invoices)
- Project rename/rebranding: `telegram-to-notion` name is too narrow for multi-source vision

## Next Steps

- Design the source adapter abstraction (interface/protocol) before adding email
- Decide: evolve this repo vs. create a new `notion-inbox` / platform repo
- Architect the deep research / enrichment layer (separate service vs. embedded)
