---
name: artelys-crm
description: >-
  Artelys-workspace overlay for notion-pilot. Use crm-ops / company-enrichment
  from notion-pilot-powers against this project's Artelys CRM (IDs in
  references/crm-ids.md). French preview tables; Infisical + Prosper notes for
  Louis. Prefer artelys-crm MCP when configured.
---

# artelys-crm — Artelys overlay

Thin project-local overlay. **Do not use against other Notion workspaces.**

## Skills to load

Use the generic skills from **notion-pilot-powers** (plugin or `vendor/notion-pilot-powers`):

- **`crm-ops`** — Leads, Activities, People, Companies; preview-then-go.
- **`company-enrichment`** — French open-data firmographics (SIREN, NAF/APE, BODACC, RNE).

This overlay only adds Artelys IDs, language, and Louis's local launch notes.

## Prerequisites

1. **Notion hosted MCP** authenticated to the Artelys CRM workspace (default path).
2. Optionally **`artelys-crm`** stdio MCP (see `.claude/settings.json` / `.cursor/mcp.json`) for dry-run People/Companies tools. Leave the plugin's `userConfig` empty on this machine so the plugin's own server does not clash — use `artelys-crm` instead.
3. Read `references/crm-ids.md` for database / data-source IDs.

## Artelys rules (Louis)

- **Language:** French validation tables; Next Step and activity titles in **French**. Notes follow the source language (usually FR).
- **Infisical:** `infisical run --env dev --path /` injects `Settings` / Notion token (see MCP launch below). Needs an active `infisical login`; if it expired, tools return 401 — check login first.
- **Prosper:** prefer Prosper MCP for enrichment when reachable; fall back to direct open-data APIs as in `company-enrichment`. Prosper/OpenRouter tools only register with `--with-external`.

## Local MCP (`artelys-crm`)

```json
"artelys-crm": {
  "command": "sh",
  "args": ["-c", "cd /home/lgiron/lab/notion-pilot && infisical run --env dev --path / -- uv --directory vendor/notion-pilot-powers run notion-pilot-powers --with-external"]
}
```

## Hard rules

- Artelys CRM only — IDs in `references/crm-ids.md`.
- Always French preview table before create/update; write only after explicit go.
- Never invent LinkedIn, SIREN, email, or titles.
