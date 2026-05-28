# Roadmap

## Now

- `feat/mail-management` (this PR): source adapter abstraction + IMAP email + Discord (source+sink)
  - `SourceAdapter` / `SinkAdapter` protocols in `adapters/`
  - IMAP polling with sender allowlist + archive-after-ingest
  - `pipeline.py` extracted; `bot.py` becomes thin multi-adapter runner

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
| Customer DB enrichment | CSV / CRM import | Notion CRM DB | Enrich contacts via LLM + web search |
| Prospection contacts | LinkedIn / email | Notion People DB | Build and enrich contact lists |
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
