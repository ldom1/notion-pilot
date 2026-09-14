# CLI scripts

Replaces the removed cockpit script runner. Run from the repo root with `uv` after `git clone --recurse-submodules` and `uv sync`.

## CRM

| Script | Purpose |
|--------|---------|
| `scripts/crm/crm_setup_workspace.py` | Bootstrap CRM databases under a parent page (`--with-inbox` optional) |
| `scripts/crm/crm_upgrade_home.py` | Refresh an existing CRM home in place (`--crm-page-id`) |
| `scripts/crm/crm_setup_deals_db.py` | Deals / Leads database helpers |
| `scripts/crm/crm_setup_properties.py` | Property patches |
| `scripts/crm/crm_create_activities_db.py` | Activities database |
| `scripts/crm/crm_add_activity_rollups.py` | Activity rollups |
| `scripts/crm/crm_patch_*.py` | Schema patches (companies, people, meetings, commercial) |
| `scripts/crm/crm_sync_meetings_activities.py` | Meetings ↔ activities sync |
| `scripts/crm/crm_refresh_companies.py` / `crm_refresh_people.py` | Refresh rows |
| `scripts/crm/crm_import_linkedin.py` | LinkedIn CSV import |
| `scripts/crm/crm_prospect.py` / `crm_dedup.py` / `dump_leads.py` | Prospecting / dedup / dump |

Examples:

```bash
uv run python scripts/crm/crm_setup_workspace.py --parent-id <PAGE_URL> --with-inbox
uv run python scripts/crm/crm_upgrade_home.py --crm-page-id <page id or URL>
```

UI notes for manual Notion steps: `scripts/crm/NOTION_UI_STEPS.md`.

## Inbox / knowledge

| Script | Purpose |
|--------|---------|
| `scripts/inbox/setup_workspace.py` | Knowledge inbox databases under a parent page |
| `scripts/inbox/process_email.py` | Process email into inbox |
| `scripts/inbox/enrich_knowledge.py` | Enrich knowledge rows |
| `scripts/inbox/analyze_email_review.py` | Email review analysis |

```bash
uv run python scripts/inbox/setup_workspace.py --parent-id <PAGE_URL>
```

## See also

- [[Self-host]] — Docker, env, Coolify
- [[Capture-channels]] — Telegram / email / Discord
