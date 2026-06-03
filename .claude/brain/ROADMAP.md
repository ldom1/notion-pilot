# Roadmap

## Phase 0 — Refactoring (current priority)

Rename and reorganize before adding features. No new behavior, just structural clarity.

- [x] Rename repo: `telegram-to-notion` → `notion-pilot`
- [x] Rename Python package: `telegram_to_notion` → `notion_pilot`
- [x] Reorganize into verticals: `crm/`, `inbox/` (from `pipelines/`), `shared/` (adapters, llm, utils, notion.py, config.py, models.py)
- [x] Organize scripts: `scripts/crm/` + `scripts/inbox/`
- [x] Unify People capture through `notion_people_data_source_id` and the central CRM syncer
- [x] Update README, CHANGELOG, brain vault note path

## Phase 1 — Setup Wizard (CLI)

One-command bootstrap on virgin Notion for both products.

- [x] `scripts/inbox/setup_workspace.py` — create Knowledge DBs (Notions, Ideas, Tools, Data & Technology)
- [x] Extend `scripts/crm/setup_workspace.py` to optionally create all 4 DBs in one shot
- [ ] `/setup` Telegram command — guided onboarding wizard that sets up the workspace and outputs `.env` values

## Phase 2 — Email "à relire"

- [ ] Email pipeline: scan inbox → classify (newsletter / contact / transactional) via LLM
- [ ] Auto-tag newsletters and unread knowledge as `À relire` in Knowledge DB
- [ ] Skip already-processed messages (idempotent)

## Phase 3 — Telegram Recap Commands

- [ ] `/recap` — daily/weekly summary: active deals, unread knowledge items, upcoming next actions
- [ ] `/leads` — list open deals with stage
- [ ] `/inbox` — list Knowledge items tagged `À relire`
- [ ] Scheduled recap (cron or Telegram command)

## Phase 4 — Website

- [ ] Landing page (Astro or Next.js): pitch for notion-crm + notion-inbox, screenshots, CTAs
- [ ] "Deploy to Notion" wizard: Notion OAuth → auto-create DBs → display `.env` values
- [ ] Chatbot endpoint (FastAPI): receive text → query Notion DBs → structured response
- [ ] Chatbot UI: embeddable on landing page

## Phase 5 — Enrichment & Prospection Polish

- [ ] Company enrichment: Apollo domain search + Brave fallback
- [ ] People enrichment: Apollo person search by name + company
- [ ] Prospection pipeline: batch enrich a list from CSV/LinkedIn export
- [ ] Dedup: merge duplicate People/Companies via LLM similarity

## Later / Won't Do Now

- WhatsApp adapter
- Web clipper (browser extension)
- RSS feeds
- Multi-tenant SaaS billing
- Support for knowledge bases other than Notion
