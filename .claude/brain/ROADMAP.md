# Roadmap

## Now

- `feat/mail-management` (this PR): source adapter abstraction + IMAP email + Discord (source+sink)
  - `SourceAdapter` / `SinkAdapter` protocols in `adapters/`
  - IMAP polling with sender allowlist + archive-after-ingest
  - `pipeline.py` extracted; `bot.py` becomes thin multi-adapter runner
- **CRM pipeline** (in progress, same branch):
  - `crm/` package: fuzzy dedup, Brave enrichment, People+Companies syncers — ✅ done
  - LinkedIn batch import (`scripts/import_linkedin.py`) — ✅ done, 1775 contacts loaded
  - Deals DB created in Notion (id: `4890e1d6-178d-4a42-af06-7bbe0cef09fe`) — ✅ done
  - `scripts/setup_crm.py` — zero-friction full CRM setup (People+Companies+Deals) — ✅ done
  - **Design complete** (spec: `2026-05-22-crm-pipeline-design.md`) — ✅ done
  - `utils/` package: `dedup.py` + `enrichment.py` (4-tier: Apollo→Brave→Perplexity→LLM) — 🔲 next
  - `crm/syncer.py` update: new `PersonRecord` fields (phone, seniority, role_type) — 🔲 next
  - `crm/deals.py`: `NotionDealsSyncer` + `DealRecord` — 🔲 next
  - `crm/prospection.py`: `rank_contacts()` — 🔲 next
  - `scripts/setup_notion_crm.py`: add enrichment properties to existing People+Companies DBs — 🔲 next
  - `scripts/enrich_crm.py`: batch enrichment CLI — 🔲 next
  - `scripts/prospect.py`: NL CLI ("I want to sell X" → ranked contacts) — 🔲 next

## Next

- **Deep research / enrichment agent** (spec: `2026-05-19-source-adapter-design.md`, layer 2)
  - Embed the Notion triage agent logic in the pipeline: identify subject entity → find/create meta-page → mark analyzed
  - This is the core differentiator vs. raw Telegram bots
- **Project rename / rebranding** — `telegram-to-notion` is too narrow; target name TBD (`notion-inbox`, `source-to-notion`, etc.)
- **Streamlined Notion onboarding** — shareable DB template, one-command setup, `/setup` wizard via Telegram

## Later (sellable product milestones)

### Product layer

- **Notion ecosystem listing** — publish on Notion marketplace with a template DB users can duplicate
- **Multi-user packaging** — per-user `.env` or config file, systemd template units, simple install script
- **SaaS option** — hosted version with auth, per-user billing (Stripe), managed infra

### Sellable use cases (vertical adapters)

| Use case | Source | Sink | Notes |
|----------|--------|------|-------|
| Knowledge management | Telegram, Email, Discord | Notion (4 DBs: Notions, Ideas, Tools, Data & Technology) | Personal — already built |
| Customer DB enrichment | CSV / CRM import | Notion CRM DB | Enrich contacts via LLM + web search — **in progress** |
| Prospection contacts | LinkedIn / email | Notion People+Deals DB | Build, enrich, and rank contacts for a pitch — **in progress** |
| Invoice management | Email (invoice parser) | Telegram / Discord alerts | Flag overdue invoices, remind by message |

### Additional sources

- WhatsApp (via unofficial API or Baileys bridge)
- Web clipper (browser extension → adapter)
- RSS feeds

## Won't Do

- Build or host an LLM
- Webhook server / always-on HTTP endpoint
- Support knowledge bases other than Notion (for now)
- Multi-tenant SaaS before the single-user experience is solid
