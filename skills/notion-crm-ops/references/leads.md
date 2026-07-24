# Leads (Deals)

Notion DB title: **💶 Leads**. Parent data source: see `crm-ids.md`. Model: `DealInput`.

## Naming

Prefer `{Company} / ACHPC` for Crystal HPC deals when that product applies (e.g. `Hexana / ACHPC`, `CRE / ACHPC`). Keep existing title on UPDATE (match is by exact title for `upsert_deal`).

## Stage enum

`Prospect` | `Qualified` | `Discovery / First Meeting` | `Proposal Sent` | `Negotiation` | `Waiting for a Response` | `Closed Won` | `Closed Lost` | `No Answer`

## Lead Source enum

`Cold Outreach` | `Referral` | `Inbound` | `Conference / Event` | `Partner` | `Existing Relationship` | `LinkedIn`

## Product

Usually `Artelys Crystal HPC` and/or `Service en Optimization`.

## Key properties to set on UPDATE

- `Stage`, `Next Step` (FR), `Next Step Date`
- `Notes` (append facts; source language OK)
- `Client` (company relation), `Primary contact`, `Contacts`
- `Probability (%)`, `Value (euros)`, `Expected Close Date` when known

**Probability scale differs by write path — 100× footgun:**
- `notion-crm` `upsert_deal` → `DealInput.probability_pct` expects a **percentage** (`60` = 60%).
- Notion MCP SQL layer often stores a **fraction** (`0.6` = 60%).

Use the right scale for the path you're on, and preserve the existing scale when patching an existing deal.

## Workflow tip

After logging Activities, still set Lead `Next Step` / date so pipeline views stay actionable.
