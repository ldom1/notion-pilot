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

- [x] Email pipeline: scan inbox → classify (newsletter / contact / transactional) via LLM
- [x] Auto-tag newsletters and unread knowledge as `À relire` in Knowledge DB
- [x] Skip already-processed messages (idempotent)

## Phase 2b — Knowledge Triage (in progress)

Batch enrichment script that replicates the Notion agent logic locally (no Notion AI credits needed).

Source: Dom Telegram Bot DB (`NOTION_TELEGRAM_MSG_DATABASE_ID`) — pages with `Status = Not analysed`.
Target: 4 custom knowledge DBs — Notions, Ideas, Tools, Data & Technology.

**Flow:** read source page → LLM identifies subject entity + target DB → find or create meta-page → append dated note section → write summary back → mark `Analysed`.
**Lifecycle:** `--purge` archives `Analysed` source pages older than 14 days.

- [x] `scripts/inbox/enrich_knowledge.py` — batch triage script (dry-run, limit, dedup, purge, JSON output)
- [x] Add to `config/scripts.yaml` for cockpit visibility
- [x] Correct DB IDs in `.env` (page IDs → actual DB IDs for Notions, Tools, Data & Tech)
- [ ] E2E test with `--limit=5` (no dry-run) to validate Notion writes
- [ ] Tune LLM granularity: crypto roundup produces 7 entities — may need a `max_entities_per_page` guard

## Phase 3 — Telegram Recap Commands

- [ ] `/recap` — daily/weekly summary: active deals, unread knowledge items, upcoming next actions
- [ ] `/leads` — list open deals with stage
- [ ] `/inbox` — list Knowledge items tagged `À relire`
- [ ] Scheduled recap (cron or Telegram command)

## Phase 4 — Website & Cockpit (current)

- [ ] Landing page (Astro or Next.js): pitch for notion-crm + notion-inbox, screenshots, CTAs
- [x] "Deploy to Notion" wizard: Notion OAuth → auto-create DBs → display `.env` values
- [x] Cockpit (`/cockpit`): workspace overview, script launcher, LLM chat against CRM data
  - [x] DB cards with live record counts and inline pointer editing (cockpit_config.json)
  - [x] Automation panel: scripts.yaml manifest → one-click run with SSE log output
  - [x] "Ask your data" chat: query CRM → LLM leads → one-click "Add to Notion"
- [ ] Chatbot endpoint (FastAPI): receive text → query Notion DBs → structured response
- [ ] Chatbot UI: embeddable on landing page

## Phase 5 — Multi-customer deployment

> **Decision (2026-06-03):** Hosted wizard + shared Telegram bot + file-upload cockpit. See DECISIONS.md for the full ADR.

**How customers use Notion Pilot (target state):**
1. Customer visits `notion-pilot.com` → OAuth with Notion → workspace created in their account
2. Customer opens the cockpit → runs scripts, chats with data, uploads files
3. Customer clicks "Connect Telegram" → deep link → links their Telegram user ID to their workspace
4. One shared bot handles all customers, dispatches to the right workspace per user

**What needs to be built:**

- [ ] `data/` namespacing by Notion workspace_id — `data/{workspace_id}/crm/`, `data/{workspace_id}/conv_state.db`
- [ ] `/api/cockpit/upload` — file upload for LinkedIn CSV (and future files); stores to `data/{workspace_id}/`
- [ ] Encrypted Notion token storage per workspace (needed to run scripts on the customer's behalf)
- [ ] User registry: `{telegram_user_id → workspace_id}` SQLite table
- [ ] "Connect Telegram" flow in cockpit: generate one-time deep link token → bot maps user on `/start <token>`
- [ ] Bot dispatcher: look up workspace on each incoming message, route to correct Notion token + DB IDs
- [ ] Docker Compose for self-hosted customers who want full control or their own private bot

## Phase 6 — Enrichment & Prospection Polish

- [ ] Company enrichment: Apollo domain search + Brave fallback
- [ ] People enrichment: Apollo person search by name + company
- [ ] Prospection pipeline: batch enrich a list from CSV/LinkedIn export
- [ ] Dedup: merge duplicate People/Companies via LLM similarity
- [ ] Robustify enrichment for People and Companies: retry logic, partial-failure recovery, progress logging per record, idempotent runs (skip already-enriched records), dry-run mode that reports what would change

## Later / Won't Do Now

- WhatsApp adapter
- Web clipper (browser extension)
- RSS feeds
- Multi-tenant SaaS billing (hard multi-tenancy, billing, subscription management)
- Support for knowledge bases other than Notion
