# Email Processing — Tutorial

This guide covers the full workflow for processing emails from IMAP into Notion using `scripts/inbox/process_email.py`.

---

## Overview

The script reads emails from one or more IMAP folders, classifies each sender, and routes them:

| Route | Destination | Archived? |
|-------|-------------|-----------|
| **allowed** | Notion knowledge DB (enriched by LLM) | Yes (Promotions only) |
| **auto_archive** | Silently archived, no Notion entry | Yes (Promotions only) |
| **people** | Notion People DB (with enrichment) | No |
| **unknown** | Review CSV only — nothing written | No |

> **INBOX emails are never archived** — only Promotions-style folders are.

Sender routing rules live in **`config/email-senders.yaml`** (version-controlled, not sensitive).

---

## Quickstart

```bash
# 1. Dry-run: preview decisions, generate review CSVs
uv run python scripts/inbox/process_email.py --dry-run --inbox=Promotions,INBOX --limit=20

# 2. Review the CSVs (see section below)

# 3. Apply your routing decisions to the YAML
uv run python scripts/inbox/process_email.py --apply-review

# 4. Re-run dry-run to verify the new routing
uv run python scripts/inbox/process_email.py --dry-run --inbox=Promotions --limit=20

# 5. Run live (processes and archives)
uv run python scripts/inbox/process_email.py --inbox=Promotions --limit=10
```

---

## Step 1 — Dry Run

```bash
uv run python scripts/inbox/process_email.py --dry-run --inbox=Promotions,INBOX --limit=20
```

**Flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `--dry-run` | — | Preview only — no Notion writes, no archiving |
| `--inbox=F1,F2` | `Promotions` | Comma-separated IMAP folders to process |
| `--limit=N` | 0 (all) | Limit to N newest emails per folder |
| `--since-days=N` | 7 (live) / 0 (dry) | Only fetch emails newer than N days |

This generates two CSV files in `data/`:

- **`email-import-review.csv`** — all content emails (allowed + auto_archive + dedup)
- **`email-import-people-review.csv`** — all unrecognised senders for routing decisions

---

## Step 2 — Review the People CSV

Open `data/email-import-people-review.csv`. It looks like this:

```
email,display_name,domain,folder,people_list,decision,...
annonce@amazon.fr,Annonce,amazon.fr,Promotions,no,To Review,...
Alexandra.Atangana@paris.fr,Alexandra Atangana,paris.fr,INBOX,no,To Review,...
```

**Edit the `decision` column** for each row:

| Value | Effect |
|-------|--------|
| `allowed` | Add to knowledge DB routing (newsletters, useful content) |
| `auto_archive` | Silently archive — no Notion entry (marketing, transactional) |
| `people` | Add to People DB with contact enrichment |
| `ignore` | Skip permanently (don't add to any list) |
| `To Review` | Leave for next time (no change) |

**Edit the `email` column** to use a domain pattern instead of an exact address:

```
# Before (exact match only):
annonce@amazon.fr → allowed

# After (matches all @amazon.fr senders):
@amazon.fr → auto_archive
```

**Examples from a typical review:**

```
email,decision
@amazon.fr,auto_archive          ← all Amazon marketing
@tripadvisor.com,auto_archive    ← all TripAdvisor emails
@glassdoor.com,auto_archive
@mail.notion.so,auto_archive     ← Notion transactional (you're already a user)
Alexandra.Atangana@paris.fr,people   ← real person, add to People DB
pierre-louis.jeauffroy@edhec.com,people
marion@lebigdata.fr,allowed      ← newsletter you want in Notion
```

---

## Step 3 — Apply Review Decisions

```bash
uv run python scripts/inbox/process_email.py --apply-review
```

This reads `data/email-import-people-review.csv` and appends each decision to the appropriate section in `config/email-senders.yaml`. Comments in the YAML are preserved.

Output:
```
INFO  auto_archive ← ['@amazon.fr', '@tripadvisor.com', '@glassdoor.com']
INFO  people ← ['Alexandra.Atangana@paris.fr', 'pierre-louis.jeauffroy@edhec.com']
INFO  Applied 5 routing decision(s) to config/email-senders.yaml
```

Then commit the updated YAML:
```bash
git add config/email-senders.yaml
git commit -m "chore(email): update sender routing rules"
```

---

## Step 4 — Re-run Dry Run to Verify

```bash
uv run python scripts/inbox/process_email.py --dry-run --inbox=Promotions --limit=20
```

Senders you routed to `auto_archive` now show `WOULD Auto archived` in the logs. Senders in `allowed` show `WOULD Treated and archived`.

---

## Step 5 — Live Run

```bash
# Process Promotions, archive processed emails, write to Notion
uv run python scripts/inbox/process_email.py --inbox=Promotions --limit=50

# Process all INBOX people contacts (no archiving)
uv run python scripts/inbox/process_email.py --inbox=INBOX --limit=20
```

---

## Sender Config — `config/email-senders.yaml`

```yaml
allowed:
  - "louis@giron-dom.eu"       # exact match
  - "@tldrnewsletter.com"      # domain match

auto_archive:
  - "@amazon.fr"
  - "members@medium.com"       # exact: only this address

people:
  - "@gmail.com"
  - "@icloud.com"
```

**Direct edits** are always fine — just edit and commit. The `--apply-review` and `--add-auto-archive` commands are shortcuts that append to the file.

### Quick CLI helpers

```bash
# Add one or more patterns to auto_archive directly (no CSV needed)
uv run python scripts/inbox/process_email.py --add-auto-archive=@domain.com,other@example.com
```

---

## Full Flag Reference

```
--dry-run                  Preview mode — no writes, no archiving
--inbox=F1,F2              IMAP folders to process (default: Promotions)
--limit=N                  Max emails per folder (default: all)
--since-days=N             Only emails newer than N days (default: 7 in live, 0 in dry)
--from-csv                 Re-process rows marked "Treated and archived" in email-import-review.csv
--apply-review             Apply routing decisions from email-import-people-review.csv → YAML
--add-auto-archive=P1,P2   Append patterns directly to auto_archive in YAML
```

---

## Typical Weekly Workflow

```
Mon  uv run python scripts/inbox/process_email.py --dry-run --inbox=Promotions,INBOX --limit=50
     → review data/email-import-people-review.csv in a spreadsheet
     → edit decision column, change @domain.com patterns where useful
     uv run python scripts/inbox/process_email.py --apply-review
     git add config/email-senders.yaml && git commit -m "chore(email): routing update"

Tue+ uv run python scripts/inbox/process_email.py --inbox=Promotions --limit=50
     → emails processed into Notion and archived
```
