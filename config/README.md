# config/

Version-controlled, non-sensitive configuration files. Commit changes here freely — no secrets, no tokens.

---

## email-senders.yaml

**Used by:** `scripts/inbox/process_email.py`

Controls how the email pipeline routes incoming messages:

| Key | Purpose |
|-----|---------|
| `allowed` | Senders routed to the Notion knowledge DB. Pattern: `@domain.com` (suffix) or `user@domain.com` (exact). |
| `auto_archive` | Silently archived — no Notion entry created. Useful for newsletters you want out of inbox but not in Notion. |
| `people` | Senders treated as personal contacts and routed through the CRM People syncer instead of the knowledge DB. |

To add entries from the CLI: `--add-auto-archive=@domain.com`

---

## scripts.yaml

**Used by:** `web/server.py` (Cockpit Automation panel)

Declares which Python scripts are surfaced as one-click buttons in the `/cockpit` dashboard. Adding an entry here automatically creates a button — no server code changes needed.

Each entry:

```yaml
- id: unique_snake_case_id     # used internally; must be unique
  label: Human-readable name   # shown on the button
  description: One sentence    # shown below the label
  path: scripts/crm/foo.py     # relative to repo root
  args: ["--flag", "value"]    # optional CLI args
  category: CRM                # CRM | Inbox (used for filter tabs)
```

Scripts are run with the current Python interpreter. The Cockpit injects `NOTION_TOKEN` (from the OAuth session) and all configured DB IDs as environment variables before spawning the subprocess, so scripts pick them up via pydantic-settings without any changes.

### LinkedIn import — manual prerequisite

The `import_linkedin` script requires a `Connections.csv` downloaded manually from LinkedIn:

1. Go to [linkedin.com/mypreferences/d/download-my-data](https://www.linkedin.com/mypreferences/d/download-my-data)
2. Select **Connections** only, request the archive
3. LinkedIn emails a ZIP within ~10 minutes — unzip it
4. Copy `Connections.csv` to **`data/crm/linkedin/Connections.csv`** (create the folder if needed)
5. Run `import_linkedin` from the Cockpit (or `--dry-run` first to preview)
