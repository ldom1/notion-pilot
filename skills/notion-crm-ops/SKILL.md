---
name: notion-crm-ops
description: >-
  Operate the Artelys Notion CRM (Leads, Activities, People, Companies) for the
  notion-pilot project. Use whenever the user pastes sales emails, asks to
  create/update a lead/deal, log an activity, add or enrich a person or company,
  fill LinkedIn/SIREN/sector/seniority, or sync CRM state after a call/meeting.
  Requires Notion MCP (workspace plugin) connected to the Artelys CRM; prefer
  notion-crm stdio MCP for People/Companies dry-runs when available. Always
  show a French validation table and wait for explicit go before writing.
---

# notion-crm-ops — Artelys CRM via Notion MCP

Project-only skill for **Artelys CRM** in this repo. Do not use against other Notion workspaces.

## Prerequisites

1. **Notion MCP** (`plugin-notion-workspace-notion` or equivalent) must be ready and authenticated to the Artelys CRM workspace. If missing/unauthenticated → stop and tell the user to connect it.
2. Optionally **`notion-crm`** stdio MCP (`python -m notion_pilot.mcp.server`) for People/Companies upsert dry-runs (`confirm=false`).
3. Ground field shapes in repo models: `notion_pilot/mcp/models.py` (`PersonRecord`, `CompanyRecord`, `DealInput`, `ActivityInput`) and CRM property setup under `scripts/crm/` / `notion_pilot/shared/workspace.py`.

Read `references/crm-ids.md` for database / data-source IDs. Read the entity reference only for the entities you touch:
- `references/people.md`
- `references/companies.md`
- `references/leads.md`
- `references/activities.md`

## Hard rules

- **Artelys CRM only** — Leads / Activities / People / Companies listed in `crm-ids.md`.
- **Always preview** — French validation table(s) before any create/update. Write only after explicit user go (`ok`, `go`, `parfait`, …). Exception: user message already contains an explicit skip like `écris sans preview` / `confirm=true` with no table requested.
- **Never invent** LinkedIn, SIREN, email, or titles. Research (web / SIREN registry) then propose with `source=web|siren|user|repo`. Low confidence → `needs_review` row; leave field empty on write.
- **Language:** Next Step + activity titles in **French**. Notes follow the source language (usually FR).
- Prefer **one multi-entity plan** when the user pastes a thread (People + Company + Lead + Activities together).

## Tooling preference

| Entity | Prefer | Fallback |
|--------|--------|----------|
| People / Companies | `notion-crm` tools (`upsert_*` dry-run then confirm) | Notion MCP search/fetch/create/update + manual dedup checklist |
| Leads / Activities | Notion MCP (query/search + create/update pages) | `notion-crm` `upsert_deal` / `log_activity` if IDs configured in env |

If Companies data-source is not shared with a local Notion token, use Notion MCP (OAuth workspace) for company writes.

## Workflow

1. **Parse intent** — which of People / Companies / Leads / Activities to touch.
2. **Resolve existing** — search by name/email/domain/title; fetch current properties.
3. **Fill gaps** — for Companies and People, research missing strongly-expected fields (see references). Tag each proposed value with `source=…`.
4. **Build validation tables (FR)** — separate or combined sections: Leads updates, Activities creates, People, Companies. Include action (`CREATE`/`UPDATE`/`SKIP`), key fields, `needs_review`, sources.
5. **Ask precise questions** only for true blockers (ambiguous person match, wrong company string, missing required `name`+`company`).
6. **On go** — write in dependency order: Company → People → Lead → Activities. Link relations (`Client`, `Primary contact`, `Contacts`, `Deal`, `Person`, `Company`).
7. **Report** — short FR summary with what was written and what remained `needs_review`.

## Completeness gates

### Company (strongly expected — always attempt)

`country`, `sector`, `SIREN`, `Website`, `Linkedin`  
(+ `Size` when known). Missing after research → still allow related Lead/People/Activity writes if user validated; leave company fields empty + `needs_review` (never fake SIREN/LinkedIn).

### People

- **Required:** `name`, `company`
- **Strongly expected (search hard):** `email`, `linkedin_url`, `position`, `seniority`, `role_type`, `phone`

Map to Notion properties / `PersonRecord` as in `references/people.md`. Seniority must be one of: `founder`, `c_suite`, `vp`, `director`, `manager`, `senior`, `mid`, `junior` (plus `unknown` only if already used in DB).

### Leads / Activities

See `references/leads.md` and `references/activities.md` for Stage / Type / Outcome enums and naming (`{Company} / ACHPC` pattern when relevant).

## Validation table template

```markdown
### Plan CRM (à valider)

| Entité | Action | Clé | Champs | Source | needs_review |
|--------|--------|-----|--------|--------|--------------|
| Company | CREATE/UPDATE | … | country=…; sector=…; … | web/siren | … |
| People | … | … | … | … | … |
| Lead | … | … | Stage=…; Next Step=… | user | … |
| Activity | CREATE | … | Type=…; Date=… | user | … |

Réponds **go** pour écrire, ou corrige les lignes.
```
