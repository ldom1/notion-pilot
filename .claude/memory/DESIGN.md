---
type: design
updated: 2026-07-08
---

# Design (original application intent)
<!-- keep this file under ~300 words -->

<!-- DESIGN.md records the product/application design that should remain reviewable
     over time: original intent, user experience, core workflows, and constraints.
     ARCHITECTURE.md is separate: it tracks the live technical structure, stack,
     module boundaries, data flow, and implementation trade-offs. -->

## Original Intent

Notion Pilot turns Notion into an active business brain, piloted primarily via Telegram. Two verticals share one core: **notion-crm** (small sales teams) and **notion-inbox** (personal knowledge capture). See [OBJECTIVES.md](OBJECTIVES.md) for full goal/scope.

## User Experience

Primary user today is Louis himself (dogfooding) — daily driver for both CRM and knowledge capture. The hosted wizard (`notion-pilot.com`) and multi-customer path ([DECISIONS.md](DECISIONS.md) 2026-06-03 ADR, [ROADMAP.md](ROADMAP.md) Phase 5) exist but external customers are not yet the primary usage mode.

## Core Workflows

Two flows must stay stable regardless of internal refactors:

1. **Capture → structured Notion row**: send a link, photo, or voice note to the Telegram bot → lands enriched (title, tags, summary, source) in the Knowledge DB. No user-side structuring effort.
2. **Telegram CRM commands**: `/lead /people /company /deal /enrich` — conversational, multi-turn (SQLite-backed state) data entry into People/Companies/Deals without leaving Telegram.

The web cockpit (DB linking, script runs, "ask your data" chat) and setup wizards are important but secondary surfaces layered on top of these two flows — see [ARCHITECTURE.md](ARCHITECTURE.md).

## Design Constraints

- **Privacy-first, self-hosted**: no data leaves the server by default (on-device transcription, no third-party SaaS dependency for core capture). This is a product principle, not just a technical convenience — it should bias future choices even when a hosted alternative is easier to build.
- **Zero-friction onboarding is non-negotiable**: setup must stay near the "< 5 minutes" bar in [OBJECTIVES.md](OBJECTIVES.md) even as features grow; trade features for simplicity if they conflict.
- **Single-developer, low-maintenance bias**: prefer low-ops choices (systemd over orchestration platforms, SQLite over a server DB) since the project is solo-maintained — consistent with existing stack choices in [ARCHITECTURE.md](ARCHITECTURE.md).

## Amendments
<!-- Dated changes to the original design intent; keep historical context reviewable -->
