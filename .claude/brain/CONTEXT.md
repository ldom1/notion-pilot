# Context

<!-- Current state snapshot. Update at session end. -->

## What's Done

- v1.0.0 shipped: core Telegram → Notion pipeline, CI, LICENSE, CONTRIBUTING, CHANGELOG
- Full enrichment pipeline: text, photos, documents, video, GIFs, voice notes (faster-whisper)
- LLM enrichment via OpenRouter (heuristics fallback if no key)
- Deployed on devbox as systemd user service
- Notion agent (external, Notion-native) post-processes DB entries into structured meta-pages across 4 knowledge databases
- Source adapter abstraction: `SourceAdapter` / `SinkAdapter` protocols, IMAP email, Discord source+sink
- `crm/` package: fuzzy dedup (rapidfuzz), Brave enrichment, NotionPeopleSyncer, NotionCompanySyncer
- LinkedIn batch import: 1775 contacts loaded into Notion People DB (2026-05-21)
- Deals DB created in Notion (Projets page), id: `4890e1d6-178d-4a42-af06-7bbe0cef09fe`
- `scripts/setup_crm.py`: zero-friction setup — creates People + Companies + Deals with relations under any page

## In Progress

- `feat/mail-management` branch: full CRM pipeline design complete, ready for implementation
- Design spec: `$BRAIN_PATH/inbox/daily/specs/telegram-to-notion/2026-05-22-crm-pipeline-design.md`

## Open Questions

- Product direction: keep as personal tool vs. build sellable enrichment platform (deep research, customer DB, contacts, invoices)
- Project rename/rebranding: `telegram-to-notion` name is too narrow for multi-source vision

## Next Steps (implementation order)

1. **`utils/` package**: move `crm/dedup.py` → `utils/dedup.py`, create `utils/enrichment.py` (4-tier: Apollo → Brave → Perplexity → LLM)
2. **`crm/syncer.py`**: update imports + add `phone`, `seniority`, `role_type` to `PersonRecord`
3. **`crm/deals.py`**: `NotionDealsSyncer` (standard `database_id` API, not data_sources)
4. **`crm/prospection.py`**: `rank_contacts()` — OpenRouter-powered contact ranking for a pitch
5. **`scripts/setup_notion_crm.py`**: add new properties to existing People + Companies DBs (one-off, safe to re-run)
6. **`scripts/enrich_crm.py`**: batch enrichment CLI (`--people`, `--companies`, `--dry-run`, `--limit N`)
7. **`scripts/prospect.py`**: NL CLI — `uv run python scripts/prospect.py --pitch "I want to sell HPC-as-a-service"`
8. **Config**: add `APOLLO_API_KEY` to `config.py` (optional), `NOTION_DEALS_DATA_SOURCE_ID` to `.env`
