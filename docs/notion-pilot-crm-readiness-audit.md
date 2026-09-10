# Readiness audit — CRM deploy via the public Notion integration, and agent access

Audited 10 September 2026 against `main` (`5f350d4`). Every claim below cites the file and line
it came from, so this can be re-run when the code moves.

## Verdict in one line

**Deploying the CRM: works, but it is not the CRM this project markets — roughly 60% there.**
**An AI agent exploring Notion through the Notion Pilot connection: no, and it cannot today by
design.** Use Notion's official MCP server for that — setup at the end of this document.

---

## 1 · Deploying the CRM via the public integration

### What genuinely works end to end

| Step | Where | Status |
|---|---|---|
| OAuth authorize + callback | `web/oauth.py:14`, `web/server.py:255-300` | ✅ |
| Token exchange, workspace + user identity captured | `web/server.py:293-299` | ✅ |
| Root page created in the user's workspace | `web/server.py:352` | ✅ |
| CRM page + 3 databases created with demo rows | `notion_pilot/shared/workspace.py:768` | ✅ |
| Relations wired between them | `workspace.py:851` (People→Company), `:906-907` (Deals→Client/Contacts) | ✅ |
| Per-workspace DB ids persisted for the cockpit | `web/server.py:381`, `web/config.py:72` | ✅ |
| Live progress streamed to the wizard (SSE) | `web/server.py:344-395` | ✅ |

A first-time user can click **Deploy to Notion**, authorise, and land on a working CRM page. That
part is real and it is the strongest piece of the product.

### Gap 1 — three databases, not five

`create_crm_workspace` calls `_create_db` exactly three times: Companies (`workspace.py:777`),
People (`:845`), Deals (`:900`). There is **no Activities database and no Meetings database**
anywhere in the bootstrap path.

This matters more than it sounds, because Activities is a hard dependency elsewhere:

```
notion_pilot/mcp/tools.py:450
    if not settings.notion_activities_database_id:
        raise ValueError("NOTION_ACTIVITIES_DATABASE_ID is required to log activities")
```

So a freshly deployed workspace **cannot log a single activity** — the exact capability the pitch
leads with ("log the call, the follow-up stops living in your head"). The operator has to create
Activities by hand in Notion and paste its id into config.

### Gap 2 — `Companies.Activities` is a multi-select, not a relation

```
notion_pilot/shared/workspace.py:838
    "Activities": {"multi_select": {"options": []}},
```

The "one row related three ways" story — a logged call showing up on the deal, the contact and the
company — does not hold on a bootstrapped workspace. It is a tag list, not a relation. This is the
single most misleading gap between the marketing and the deployed artefact.

### Gap 3 — the bootstrapped schema is thinner than the real CRM

Comparing `workspace.py:900-950` against the live Artelys Leads database:

| Present in the real CRM | In bootstrap? |
|---|---|
| `Stage`, `Value (euros)`, `Probability (%)`, `Next Step`, `Next Step Date`, `Lead Source`, `Product` | ✅ |
| `Expected Close Date`, `Primary contact`, `Activities` (relation), `Projects` | ❌ |
| `Deal Age (days)`, `Days Since Last Activity`, `Last Activity Date` | ❌ formulas absent |
| `Stale Deal`, `Weighted Value (€)`, `Deal Temperature` | ❌ formulas absent |

The four missing formula properties are the ones the homepage names by title in its "who keeps this
up to date?" section. A deployed workspace does not have them.

Two vocabulary mismatches on top:

- **Stage options** — bootstrap omits `Discovery / First Meeting` and `Waiting for a Response`,
  both of which are in live use (`Discovery / First Meeting` is 3 of 30 open leads).
- **Lead Source** — bootstrap ships French options (`Prospection froide`, `Prospection tiède`, …)
  while the real CRM uses English (`Cold Outreach`, `Referral`, `Partner`, `Inbound`,
  `Conference / Event`).

Same for Companies: the real database carries `SIREN`, `CA`, `Résultat net`, `Marge nette %`,
`Année financière` and `Market Segment`; bootstrap creates none of them — yet the
`company-open-data-enrichment` skill writes to exactly those properties.

### Gap 4 — the OAuth token is never persisted

```
web/server.py:208   app.add_middleware(SessionMiddleware, secret_key=session_secret, …)
web/server.py:293   request.session["notion_token"] = token_data["access_token"]
```

The token lives **only in the signed session cookie**. Nothing writes it to disk or to a keystore.
Consequences:

- The Telegram bot and every background job read the static `NOTION_TOKEN` from settings, never the
  OAuth token. So automation for a workspace someone connected through the website **does not
  exist** — only the cockpit works, and only while that browser session lasts.
- Clear cookies and the workspace is orphaned: the databases stay in Notion, the cockpit config
  (`web/config.py:72`, keyed by `workspace_id`) survives, but nothing can authenticate to it again
  without re-running OAuth.

Notion access tokens do not expire, so there is no refresh-token problem — persisting the token
server-side (encrypted, keyed by `workspace_id`) is the whole fix.

### To get the deploy to 100%

1. Add Activities to `create_crm_workspace`, and convert `Companies.Activities` to a real relation.
2. Backfill the missing Leads properties, including the four formulas, and align Stage / Lead Source
   options with the live vocabulary.
3. Add the finance + SIREN properties to Companies so `company-open-data-enrichment` has somewhere
   to write on a fresh workspace.
4. Persist the OAuth token server-side if multi-tenant is a goal; otherwise say plainly that the
   hosted wizard is a single-operator tool.
5. Optionally create Meetings, or state that Meetings stays manual (see below).

---

## 2 · Can an AI agent explore Notion through this connection?

**No.** The Notion Pilot MCP server is hard-bound to one static workspace:

```
notion_pilot/mcp/server.py:31-32
    _settings = load_settings()
    _session  = SyncerSession(_settings)          # ← module import time
```

```
web/server.py:188
    if settings.notion_token and settings.mcp_bearer_token:
        app.mount("/mcp", build_http_app(settings.mcp_bearer_token.get_secret_value()))
```

Three things follow:

- The session is built **once at import**, from environment settings. There is no per-request token,
  and no way to pass one — an MCP client cannot say "act on *my* workspace".
- `/mcp` is gated by a **static bearer token**, not by the caller's Notion OAuth session. Whoever
  holds that bearer acts on the operator's own workspace.
- Therefore the public integration and the MCP surface are **two unrelated authentication systems**.
  Connecting an agent to `https://notion-pilot.dombot.tech/mcp` explores *your* Artelys CRM,
  regardless of which workspace the agent's user authorised.

That is correct and useful for single-tenant use (your own CRM, your own agent). It would be a
cross-tenant data leak if the hosted wizard ever had real customers, so the bearer token must stay
private to you.

### What each MCP surface is actually for

| | Notion Pilot MCP (`notion-crm`) | Official Notion MCP |
|---|---|---|
| Scope | Your one configured workspace | Whichever workspace the user authorises |
| Auth | Static bearer / stdio subprocess | Per-user OAuth |
| Strength | Fuzzy dedup, French open-data enrichment, dry-run/`confirm` discipline, pitch ranking | Generic read/write, semantic search, **can create databases and views** |
| Use it to | Write CRM records safely | Explore, and build the schema in the first place |

They are complements, not substitutes. Notion's own server can `notion-create-database` and
`notion-create-view` — which means **an agent can build the full five-table CRM directly**, more
completely than `create_crm_workspace` does today. That is worth considering as the deploy path.

---

## 3 · Connecting the official Notion MCP server

Endpoint: **`https://mcp.notion.com/mcp`** — remote, hosted by Notion, authorised per user over
OAuth.

### Claude Code

```bash
claude mcp add --transport http notion https://mcp.notion.com/mcp
```

Then run `/mcp` inside Claude Code and complete the OAuth flow. Scope flags:
`--scope local` (default, this project), `--scope project` (team-shared via `.mcp.json`),
`--scope user` (all your projects).

### Cursor

`.cursor/mcp.json` in the project root (or `~/.cursor/mcp.json` for every project):

```json
{
  "mcpServers": {
    "notion": {
      "url": "https://mcp.notion.com/mcp"
    }
  }
}
```

Then open **Customize** in the Cursor sidebar, enable Notion, and complete the OAuth flow.

Note this repo already registers the *local* `notion-crm` server in `.cursor/mcp.json` over stdio —
add the `notion` entry alongside it rather than replacing it, so you get both surfaces.

### Tools it exposes

Search and read: `notion-search`, `notion-ai-search` (semantic, spans connected Slack/Mail/Calendar),
`notion-fetch`, `notion-query-data-sources` (SQL or rows mode), `notion-query-meeting-notes`.
Write: `notion-create-pages`, `notion-update-page`, `notion-move-pages`, `notion-duplicate-page`.
Schema: `notion-create-database`, `notion-update-data-source`, `notion-create-view`,
`notion-update-view`. Plus comments, users, teams, file uploads and async task polling.

`notion-query-meeting-notes` is worth flagging — it reads meeting notes directly, which is the
cheapest route to covering the Meetings gap without building anything.

---

## 4 · Correction to an earlier claim in this repo's docs

Earlier deck revisions asserted that "a meeting is an Activity type; there is no Meetings database".
**That is wrong for the live CRM.** The export shows a real Meetings database related from two
sides:

- `Activities.Meeting` → relation to Meetings pages (24 of 47 activity rows populated)
- `People.Meetings` → relation to Meetings pages (123 of 1859 people populated)

`Activities.Type` *also* has a `🤝 Meeting` option (27 of 47 rows), which is what caused the
confusion: meetings are recorded both as an activity type **and** as their own linked pages.

The accurate statement is:

- **Your Notion CRM has five databases**: Companies, People, Leads, Activities, Meetings.
- **Notion Pilot automates four of them** — Meetings is read-and-write by humans only.
- **The public deploy creates three of them** — see Gap 1.

The deck and the homepage have both been corrected to this.

---

## Sources

- [Notion MCP overview](https://developers.notion.com/docs/mcp) ·
  [Connect an MCP client](https://developers.notion.com/guides/mcp/get-started-with-mcp) ·
  [Supported tools](https://developers.notion.com/guides/mcp/mcp-supported-tools)
- [Notion data residency](https://www.notion.com/help/data-residency) ·
  [Multi-region data systems](https://www.notion.com/blog/enabling-multi-region-data-systems-at-notion)
- [Salesforce + Anthropic: Claudeforce](https://www.salesforce.com/news/press-releases/2026/08/26/salesforce-and-anthropic-announce-claudeforce/)
