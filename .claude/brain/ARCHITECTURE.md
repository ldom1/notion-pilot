# Architecture

## Product Structure

Two products, one mono-repo, shared core:

```
notion-pilot/            ← repo name (rename from notion-pilot)
├── notion_pilot/        ← Python package (rename from telegram_to_notion)
│   ├── shared/          ← core used by both products
│   │   ├── adapters/    ← SourceAdapter/SinkAdapter protocols + Telegram/Email/Discord impls
│   │   ├── llm/         ← OpenRouter, prompt, source_hints
│   │   ├── utils/       ← enrichment (Apollo, Brave), dedup
│   │   ├── notion.py    ← NotionDatabaseWriter
│   │   ├── config.py    ← unified Pydantic settings
│   │   └── models.py    ← IncomingMessage + DB property models
│   ├── crm/             ← notion-crm vertical
│   │   ├── commands.py  ← /lead /people /company /deal /enrich Telegram commands
│   │   ├── conv_state.py← SQLite conversation state machine
│   │   ├── syncer.py    ← NotionPeopleSyncer, NotionCompanySyncer
│   │   ├── deals.py     ← NotionDealsSyncer
│   │   └── prospection.py
│   ├── inbox/           ← notion-inbox vertical (rename from pipelines/)
│   │   ├── knowledge.py ← knowledge pipeline → Notion Knowledge DB
│   │   └── people.py    ← people pipeline (email contacts → People DB)
│   ├── media/           ← photo/voice download, faster-whisper transcription
│   └── bot.py           ← thin runner: activates adapters, routes commands
├── scripts/
│   ├── crm/             ← crm_setup_workspace.py, crm_enrich.py, crm_dedup.py, etc.
│   └── inbox/           ← (future) inbox_setup.py for Knowledge DBs
└── web/                 ← (future) landing + deploy wizard + chatbot
```

## Stack

- **Runtime:** Python 3.12, uv
- **Telegram:** `python-telegram-bot` (long polling, no webhook)
- **Email:** `imapclient` (optional, IMAP polling)
- **Discord:** `discord.py` (optional, source + sink)
- **Notion:** `notion-client` (sync SDK, always wrapped in `asyncio.to_thread`)
- **Config:** Pydantic settings from `.env`
- **HTTP:** httpx
- **Logging:** loguru
- **Transcription:** `faster-whisper` (optional, on-device)
- **LLM enrichment:** OpenRouter (`google/gemini-2.5-flash-lite` default)
- **Enrichment:** Apollo.io (people/company), Brave Search (web)
- **State:** SQLite via `aiosqlite` (conversation state for CRM commands)

## Data Flow

```
Source adapter (telegram / email / discord)
  → IncomingMessage  [source_adapter field]
  → router (bot.py)
      ├── CRM command (/lead /people /company /deal /enrich)
      │     → crm/commands.py → conv_state → syncer → Notion CRM DBs
      └── Knowledge message (default)
            → media download + transcription (media/)
            → LLM enrichment (llm/)
            → NotionDatabaseWriter → Notion Knowledge DB
```

## Key Config IDs

| Env var | Purpose |
|---------|---------|
| `NOTION_DATABASE_ID` | Knowledge / inbox DB |
| `NOTION_COMPANIES_DATA_SOURCE_ID` | Companies DB (inline DS API) |
| `NOTION_PEOPLE_DATA_SOURCE_ID` | People DB (central CRM syncer: dedup + upsert) |
| `NOTION_DEALS_DATABASE_ID` | Deals DB |

> Email people capture uses the same CRM syncer path as `/people` commands instead of a separate contacts writer.

## Architectural Notes

- Notion SDK is synchronous — all calls go through `asyncio.to_thread`
- Adapters activate by env var presence: no config file changes to add/remove a source
- `source_adapter` field on `IncomingMessage` drives the Notion `Label` via `from_incoming()`
- Check `animation` before `video` in Telegram handlers — Telegram sets both flags for GIFs
- CRM commands use an LLM extraction step to parse free-form text → structured fields
- Conversation state (SQLite) tracks multi-turn CRM interactions per Telegram chat_id
- Deploy: systemd user service on devbox

## Planned Layers

```
Layer 1 (done):   Multi-source ingestion  → Notion DB row (enriched)
Layer 2 (now):    CRM vertical            → People/Companies/Deals + Telegram commands
Layer 3 (next):   Setup wizard            → virgin Notion bootstrap (CRM + Knowledge)
Layer 4 (later):  Email recap             → "à relire" tagging + Telegram summary
Layer 5 (later):  Website                 → landing + Notion OAuth deploy wizard + chatbot
```

## Telegram message workflow

Entry point: `notion_pilot/shared/adapters/telegram.py` (`TelegramAdapter._handle`).
Long-polling receives text, photo, or voice → mapped to `IncomingMessage` (voice is transcribed first).

### 1. Reception

| Input | Handling |
|-------|----------|
| Text | Used as-is |
| Voice | Downloaded → `faster-whisper` transcription → text |
| Photo | Caption/text → knowledge pipeline if routed there |

Each message is keyed by `chat_id`. Multi-turn state lives in SQLite (`crm/conv_state.py`).

### 2. Routing priority (first match wins)

Orchestrator: `TelegramAdapter._build_app()` → inner async `_handle()` in
`notion_pilot/shared/adapters/telegram.py` (~line 354). Every incoming message
hits `_handle` first; priorities are a **sequential if-chain** — first branch
that matches handles the message and `return`s (no fall-through).

State store: `ConvStateStore` in `notion_pilot/crm/conv_state.py`.
- One row per `chat_id` in SQLite (`data/conv_state.db` by default)
- `ConvState` fields: `command`, `collected` (JSON dict), `pending_field`, `created_at`
- 30 min TTL: stale rows deleted on `get()` and at startup (`TIMEOUT_SECONDS = 1800`)
- Instantiated once per bot process: `state_store = ConvStateStore(settings.conv_state_db)` inside `_build_app`

#### Priority 1 — Active conversation state

```python
# telegram.py::_handle — simplified
state = state_store.get(chat_id)
if state is not None and state.command == "infer_confirm":
    ...  # branch A
    return
if state is not None and state.command == "setup":
    ...  # branch B
    return
if state is not None:
    await _fill_field(msg, state, text)  # branch C
    return
```

| Branch | `state.command` | Set by | Handler | Outcome |
|--------|-----------------|--------|---------|---------|
| A | `infer_confirm` | `infer_and_confirm()` success → `state_store.set()` before confirmation reply | inline in `_handle` + `_resolve_confirmation()` | `yes` → CRM handler; `no` → knowledge on `original_text`; `cancel` → discard |
| B | `setup` | `start_setup()` after `/setup` | `advance_setup()` in `crm/setup_wizard.py` | Multi-step Notion workspace bootstrap; `clear()` when wizard ends |
| C | `people`, `lead`, `company`, … | `_dispatch_crm()` when required fields missing | `_fill_field()` in `telegram.py` | Appends user reply to `state.collected`; calls `get_next_prompt()` from `crm/commands.py` until handler runs |

**Branch A — `infer_confirm`** (`collected` keys):
- `inferred_type`: `people` | `company` | `deal`
- `extracted`: JSON string of parsed/LLM fields
- `original_text`, `original_sent_at`: message before confirmation
- `confirmation`, `retry`: prompt text and retry counter

**Branch C — CRM field collection** flow:
1. User sends `/people Alice` → `_dispatch_crm()` → `extract_fields_from_text()` fills what it can
2. Missing required field → `state_store.set(ConvState(command="people", collected={...}))`
3. Next message (no `/` prefix) → Priority 1 catches `state is not None` → `_fill_field()`
4. `_fill_field` writes reply into first missing `FieldDef.name`, re-prompts or calls `cmd.handler()`

Priority 1 **short-circuits** everything below: a user mid-`/people` wizard cannot trigger inference or knowledge on their field answers.

```
Priority 2 — Explicit /commands
  /recap, /leads, /inbox  → read-only Notion queries (no write)
  /people, /company, /deal, /lead, /enrich, /knowledge  → CRM write flows
  /setup                  → workspace bootstrap wizard

Priority 3 — Plain text / voice (smart routing)
  read intent (recap, leads, inbox)  → query Notion, reply formatted text
  infer_and_confirm()                → classify + optional confirm → CRM DB
  else                               → knowledge pipeline → DomBotTelegram DB
```

### 3. Understanding (plain text, no active state)

**Step A — Read intent** (`_detect_read_intent`): whole-word match on `recap`, `leads`, `inbox|relire`. No LLM.

**Step B — `infer_and_confirm()`** — decides people / company / deal vs knowledge:

1. **LinkedIn-only deterministic bypass** (`parse_linkedin_deterministic` in `crm/contact_parse.py`):
   - Called first inside `infer_and_confirm()` (`telegram.py`)
   - Routes by URL path — no LLM when a LinkedIn URL matches:

   | URL pattern | Type | Parser | Example |
   |-------------|------|--------|---------|
   | `linkedin.com/in/…` + `:` + tail | `people` | `parse_linkedin_person_paste` | `…/in/vberge/ : Jean Dupont, Veolia, CTO` |
   | `linkedin.com/company/…` | `company` | `parse_linkedin_company_paste` | `…/company/altotrain/` or `…/company/altotrain/ : Alto, Rail Transportation` |

   - Company name: from text after `:`, else slug (`altotrain` → `Altotrain`)
   - Comma-only lines (`Name, Position, Company`) **do not** skip LLM in smart routing

   | Parser | Used in `infer_and_confirm` | Used in explicit `/command` |
   |--------|----------------------------|----------------------------|
   | `parse_linkedin_person_paste` | Yes → `people` | `/people` |
   | `parse_linkedin_company_paste` | Yes → `company` | `/company` |
   | `parse_comma_contact` | No | `/people` only |

2. **LLM** (OpenRouter, JSON) — classifies `people | company | deal | knowledge` for all non-LinkedIn plain text:
   - Prompt forbids placeholders (`[PERSON_NAME]`, `<name>`, …)
   - `sanitize_extracted()` drops bad values; LinkedIn parse overrides LLM when URL present in message
   - Returns `None` → falls through to knowledge (no confirmation)

**Step C — Knowledge default** (`inbox/pipeline.py` → `build_knowledge_pipeline`):
- LLM enriches title, tags, summary
- Writes to `NOTION_DATABASE_ID` / DomBotTelegram inbox DB

### 4. Confirmation gate (infer_confirm)

When inference returns `people`, `company`, or `deal`:

```
Bot: "Looks like a person — Olivier Coussau @ Veolia (CTO).
      Save to Persons? Reply yes, /knowledge to file as a note, or cancel to discard."
State: infer_confirm stored in SQLite (extracted JSON + original text)
```

Resolved by `_resolve_confirmation()` in `telegram.py`; handled in `_handle` branch A.

| User reply | `_resolve_confirmation` | Action |
|------------|-------------------------|--------|
| `yes` / `oui` / `y` | `yes` | Run `COMMANDS[inferred_type].handler()` → write CRM DB |
| `no` / `non` / `/knowledge` | `no` | Route **original message** to knowledge pipeline (DomBotTelegram DB) |
| `cancel` / `skip` / `rien` / `/cancel` / … | `cancel` | Clear state, reply *Discarded — nothing saved to Notion.* — **no write** |
| Other (once) | `unknown` | Re-prompt confirmation |
| Other (twice) | `unknown` | Fall back to knowledge pipeline |

### 5. Target Notion databases

DB IDs come from `.env` **or** `web/workspaces/*/cockpit_config.json` via `_enrich_settings_from_cockpit()` (required on devbox when env vars are unset).

| Route | Handler | Notion DB | Env / cockpit key |
|-------|---------|-----------|-------------------|
| Knowledge (default) | `inbox/pipeline` | DomBotTelegram / inbox | `NOTION_DATABASE_ID` |
| People | `NotionPeopleSyncer.upsert` | People | `NOTION_PEOPLE_DATA_SOURCE_ID` |
| Company | `NotionCompanySyncer` | Companies | `NOTION_COMPANIES_DATA_SOURCE_ID` |
| Deal | `NotionDealsSyncer` | Deals | `NOTION_DEALS_DATABASE_ID` |
| `/recap`, `/leads`, `/inbox` | `crm/queries` | read-only across CRM + inbox |

People writes also resolve/create the linked Company relation. Fuzzy dedup (≥85% → skip, ≥75% → review) runs before create.

### 6. Explicit CRM commands (`/people`, `/lead`, …)

1. LLM field extraction (`extract_fields_from_text`) — same parsers as inference, then OpenRouter
2. If required fields missing → multi-turn prompts via `conv_state`
3. Handler writes to the matching CRM DB (with cockpit-enriched settings)

### 7. Rules & pitfalls

- **No confirmation** on knowledge path — message is saved immediately.
- **Wrong DB** usually means `infer_and_confirm` returned `None` (LLM said knowledge, or message didn't match parsers).
- **Placeholder names** (`[PERSON_NAME]`) — rejected by `sanitize_extracted()`; LinkedIn paste parser is the reliable fix, comma parser is not.
- **Comma contacts (plain text)** — routed via LLM, not regex; use `/people` prefix for deterministic comma parsing.
- **LinkedIn paste** — only format that skips LLM in smart routing; confirmation still required.
- **Voice "recap"** — transcribed text checked for read intent before inference.
- **Read vs write** — `recap`/`leads`/`inbox` never create pages; only `/people` + infer_confirm `yes` create People rows.
