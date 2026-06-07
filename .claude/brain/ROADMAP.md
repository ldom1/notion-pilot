# Roadmap

## Phase 0 — Refactoring ✅

- [x] Rename repo: `telegram-to-notion` → `notion-pilot`
- [x] Rename Python package: `telegram_to_notion` → `notion_pilot`
- [x] Reorganize into verticals: `crm/`, `inbox/`, `shared/`
- [x] Organize scripts: `scripts/crm/` + `scripts/inbox/`
- [x] Unify People capture through `notion_people_data_source_id`

## Phase 1 — Setup Wizard ✅

- [x] `scripts/inbox/setup_workspace.py` — create Knowledge DBs
- [x] `scripts/crm/setup_workspace.py` — create CRM DBs
- [x] `/setup` Telegram command — guided onboarding wizard

## Phase 2 — Email "à relire" ✅

- [x] Email pipeline: classify (newsletter / contact / transactional) via LLM
- [x] Auto-tag newsletters as `À relire` in Knowledge DB
- [x] Skip already-processed messages (idempotent)

## Phase 2b — Knowledge Triage (partial)

- [x] `scripts/inbox/enrich_knowledge.py` — batch triage (dry-run, limit, dedup, purge, JSON output)
- [x] Add to `config/scripts.yaml` for cockpit visibility
- [ ] E2E test with `--limit=5` (no dry-run) to validate Notion writes
- [ ] Tune LLM: `max_entities_per_page` guard (crypto roundups produce 7+ entities)

## Phase 3 — Telegram Recap Commands ✅

- [x] `/recap` — 7-day summary: active leads + stage, next actions, recent people, À relire
- [x] `/leads` — open deals list (cap 10 + overflow)
- [x] `/inbox` — knowledge items with status "Not analysed" (cap 10 + overflow)
- [x] Smart routing: plain-text → LLM infer → confirm before write (infer_confirm flow)
- [ ] Scheduled recap (deferred — manual `/recap` covers the use case for now)

## Phase 4 — Website & Cockpit ✅

- [x] Landing page: hero, feature list, "Deploy to Notion" CTA
- [x] "Deploy to Notion" wizard: Notion OAuth → auto-create DBs
- [x] Cockpit (`/cockpit`): workspace overview, script launcher, LLM chat
  - [x] DB cards with live record counts (single-page, `100+` for large DBs) and inline pointer editing
  - [x] Automation panel: scripts.yaml → one-click run with SSE log output
  - [x] "Ask your data" chat: query CRM → LLM → one-click "Add to Notion"
  - [x] Telegram Bot status card: connection dot, last seen, ping button
- [x] Deployed at `https://notion-pilot.dombot.tech` (Docker + nginx + Let's Encrypt)
- [x] GitHub Actions CI + auto-deploy on push to main
- [ ] Chatbot endpoint for embeddable landing page widget

## Phase 4b — Cockpit UX / Performance (in progress, branch: fix/deployment)

- [x] Remove BETA badge
- [x] SVG favicon (compass icon, Notion Pilot purple)
- [x] Centralized `<Spinner>` component — no more ad-hoc spinner definitions
- [x] Refresh Workspace: per-card dim + spinner instead of full-page reload
- [x] `_count_db` perf: single `page_size: 100` query, no pagination (5–10s → ~1–2s)
- [x] `make deploy BRANCH=<name>` — SSH deploy to devbox from local
- [ ] Server-side cache for `/api/cockpit/status` (TTL 60s) — avoid repeat Notion API calls on tab switch

## Phase 5 — Multi-customer deployment

> **Decision (2026-06-03):** Hosted wizard + shared Telegram bot + file-upload cockpit. See DECISIONS.md.

- [ ] `data/` namespacing by workspace_id — `data/{workspace_id}/crm/`, `data/{workspace_id}/conv_state.db`
- [ ] `/api/cockpit/upload` — file upload for LinkedIn CSV
- [ ] Encrypted Notion token storage per workspace
- [ ] User registry: `{telegram_user_id → workspace_id}` SQLite table
- [ ] "Connect Telegram" flow: one-time deep link token → bot maps user on `/start <token>`
- [ ] Bot dispatcher: look up workspace on each message, route to correct token + DB IDs

## Phase 6 — Enrichment & Prospection Polish

- [ ] Apollo domain search + Brave fallback for company enrichment
- [ ] Apollo person search by name + company for people enrichment
- [ ] Dedup: merge duplicate People/Companies via LLM similarity
- [ ] Batch enrich with retry logic, partial-failure recovery, idempotent runs

## Deferred / Won't Do Now

- WhatsApp adapter
- Browser extension / web clipper
- RSS feeds
- Multi-tenant SaaS billing
- Support for knowledge bases other than Notion
