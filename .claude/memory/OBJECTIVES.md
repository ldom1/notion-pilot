---
type: objectives
updated:
---

# Objectives

## Goal

**Notion Pilot** — a self-hosted platform that turns Notion into an active business brain, piloted by Telegram (and future channels). Two independent products sharing a common core:

- **notion-crm**: CRM for small sales teams (2-10 people) — people, companies, deals, enrichment
- **notion-inbox**: Personal knowledge management — capture from Telegram/email/Discord, LLM enrichment

## Success Criteria

- Small sales teams can deploy a full Notion CRM in < 5 minutes via setup wizard
- Daily personal use for knowledge management without friction
- Distributable: installable via pip, deployable via website wizard
- Reliable enrichment pipeline: Apollo, Brave Search, OpenRouter

## Scope

- Telegram as primary interaction channel (long polling only)
- Email (IMAP) and Discord as secondary sources
- Notion as the sole output target
- Optional LLM enrichment via OpenRouter
- Single-user and small-team self-hosted deployment
- Website: landing page + Notion OAuth deploy wizard + chatbot

## Non-Goals

- Building or hosting an LLM
- Webhook server / always-on HTTP endpoint
- Supporting knowledge bases other than Notion
- Multi-tenant SaaS before single-user experience is solid
- Splitting into two repos (mono-repo until team requires it)
