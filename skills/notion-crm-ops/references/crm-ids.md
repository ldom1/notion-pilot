# Artelys CRM identifiers (notion-pilot)

Update this file if databases are recreated. Prefer resolving via Notion MCP search (`Leads`, `Activities`) when unsure.

## Databases / data sources

| Entity | Notion title | Database / page ID | Data source (`collection://`) |
|--------|--------------|--------------------|-------------------------------|
| Leads (Deals UI) | 💶 Leads | `4890e1d6-178d-4a42-af06-7bbe0cef09fe` | `e4aa9077-08d2-4e65-95e2-feff12b5d415` |
| Activities | ⚡ Activities | `38f6c451-9465-814d-a383-ce59038b6e8d` | `38f6c451-9465-819b-9462-000be3eab530` |
| People | People | (resolve via search / settings) | `866ce33a-cf5b-47d4-85db-7cd932915dc8` |
| Companies | Companies | (resolve via search / settings) | `fe2b97ac-6d33-4626-890b-62b25a02e1cb` |

Pipeline hub page: `36d6c451-9465-80b7-af00-d80250f0974c` (Leads pipeline).

## Env (local stdio / scripts)

When using `notion_pilot` code path:

- `NOTION_TOKEN` (or Infisical)
- `NOTION_PEOPLE_DATA_SOURCE_ID` / `NOTION_COMPANIES_DATA_SOURCE_ID`
- `NOTION_DEALS_DATABASE_ID` / `NOTION_ACTIVITIES_DATABASE_ID` (often unset in `.env` — then use Notion MCP for Leads/Activities)

`INFISICAL_ENV=dev` when loading Settings from a localhost OAuth redirect URI.
