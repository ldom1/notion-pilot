"""Process IMAP mail → Notion knowledge DB + people review CSV.

Usage:
    uv run python scripts/inbox/process_email.py --dry-run
    uv run python scripts/inbox/process_email.py --dry-run --inbox=Promotions,INBOX --limit=20
    uv run python scripts/inbox/process_email.py
    uv run python scripts/inbox/process_email.py --from-csv   # rows marked Treated and archived
    uv run python scripts/inbox/process_email.py --dry-run --since-days=14
    uv run python scripts/inbox/process_email.py --limit=10   # newest 10 only (smoke test)
    uv run python scripts/inbox/process_email.py --add-auto-archive=@domain.com,sender@other.com
    uv run python scripts/inbox/process_email.py --apply-review   # apply CSV decisions → YAML
"""

import asyncio
import re
import sys
from pathlib import Path

from loguru import logger
from notion_client import AsyncClient

from notion_pilot.crm.syncer import NotionPeopleSyncer, PersonRecord
from notion_pilot.inbox import build_knowledge_pipeline
from notion_pilot.shared.adapters.email import EmailAdapter, _sender_allowed
from notion_pilot.shared.config import Settings, load_settings
from notion_pilot.shared.models import _first_url
from notion_pilot.shared.utils.enrichment import enrich_person

_SENDER_CONFIG = Path("config/email-senders.yaml")
_REVIEW_CSV = Path("data/inbox/email-import-review.csv")
_CSV_FIELDS = ["uid", "folder", "sender", "subject", "sent_at", "summary", "decision"]
_DECISION_UNTOUCHED = "Untouched"
_DECISION_TREATED = "Treated and archived"
_DECISION_AUTO_ARCHIVED = "Auto archived"

_PEOPLE_REVIEW_CSV = Path("data/inbox/email-import-people-review.csv")
_PEOPLE_CSV_FIELDS = [
    "email",
    "display_name",
    "domain",
    "folder",
    "people_list",
    "enriched",
    "linkedin",
    "seniority",
    "role_type",
    "dedup_status",
    "dedup_score",
    "matched_name",
    "decision",
]
_DECISION_TO_REVIEW = "To Review"


def _flag(name: str) -> bool:
    return name in sys.argv


def _arg(prefix: str) -> str | None:
    for arg in sys.argv:
        if arg.startswith(f"{prefix}="):
            return arg.split("=", 1)[1]
    return None


_MEDIA_CSS_RE = re.compile(r"@media[^{]*\{[^}]*\}", re.IGNORECASE | re.DOTALL)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_URL_ONLY_RE = re.compile(r"^https?://\S+$", re.IGNORECASE)


def _clean_email_text(text: str) -> str:
    text = _MEDIA_CSS_RE.sub(" ", text)
    text = _HTML_TAG_RE.sub(" ", text)
    text = re.sub(r"\{[^{}]{0,200}\}", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _is_good_sentence(sentence: str) -> bool:
    if len(sentence) < 20:
        return False
    low = sentence.lower().strip()
    if low.startswith("@media") or low.startswith("http"):
        return False
    if _URL_ONLY_RE.match(sentence):
        return False
    if re.fullmatch(r"hi[,!]?", low):
        return False
    letters = sum(c.isalpha() for c in sentence)
    return letters >= 15


def _one_sentence(subject: str, body: str) -> str:
    subject = re.sub(r"\s+", " ", (subject or "").strip())
    clean = _clean_email_text(body or "")
    for candidate in (subject, *_sentences(clean)):
        if _is_good_sentence(candidate):
            return candidate[:220]
    if subject:
        return subject[:220]
    return clean[:220] if clean else "(no content)"


def _sentences(text: str) -> list[str]:
    if not text:
        return []
    chunks = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [c.strip() for c in chunks if c.strip()]


def _parse_inbox_arg(raw: str) -> list[str]:
    """Split comma-separated folder names; strip whitespace; drop empty entries."""
    return [f.strip() for f in raw.split(",") if f.strip()]


def _summary(raw) -> str:
    return _one_sentence(raw.subject, raw.body)


def _write_review_csv(rows: list[dict[str, str]]) -> None:
    import pandas as pd

    _REVIEW_CSV.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=_CSV_FIELDS).to_csv(
        _REVIEW_CSV, sep=";", index=False, encoding="utf-8-sig"
    )


def _read_review_csv() -> list[dict[str, str]]:
    import pandas as pd

    return (
        pd.read_csv(_REVIEW_CSV, sep=None, engine="python", encoding="utf-8-sig", dtype=str)
        .fillna("")
        .to_dict("records")
    )


def _write_people_csv(rows: list[dict[str, str]]) -> None:
    import pandas as pd

    _PEOPLE_REVIEW_CSV.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows, columns=_PEOPLE_CSV_FIELDS).drop_duplicates(
        subset=["email"], keep="first"
    )
    df.to_csv(_PEOPLE_REVIEW_CSV, sep=";", index=False, encoding="utf-8-sig")


def _load_sender_config(settings: Settings) -> tuple[list[str], list[str], list[str]]:
    """Return (allowed, auto_archive, people) from YAML if present, else from settings."""
    if _SENDER_CONFIG.exists():
        import yaml  # pyyaml — loaded lazily so unit tests don't require it

        data = yaml.safe_load(_SENDER_CONFIG.read_text(encoding="utf-8")) or {}
        return (
            [str(s) for s in (data.get("allowed") or [])],
            [str(s) for s in (data.get("auto_archive") or [])],
            [str(s) for s in (data.get("people") or [])],
        )

    def _split(val: str) -> list[str]:
        return [s.strip() for s in (val or "").split(",") if s.strip()]

    return (
        _split(settings.imap_allowed_senders),
        _split(settings.imap_auto_archive_senders),
        _split(settings.imap_people_senders),
    )


def _yaml_append_to_section(section: str, patterns: list[str]) -> None:
    """Append quoted patterns to a named section in email-senders.yaml, preserving comments."""
    lines = _SENDER_CONFIG.read_text(encoding="utf-8").splitlines()
    insert_at = len(lines)
    in_block = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(f"{section}:"):
            in_block = True
            continue
        if in_block:
            if stripped.startswith("- ") or stripped.startswith("#") or not stripped:
                insert_at = i + 1
            elif stripped and not line.startswith(" "):
                break
    new_lines = [f'  - "{p}"' for p in patterns]
    result = lines[:insert_at] + new_lines + lines[insert_at:]
    _SENDER_CONFIG.write_text("\n".join(result) + "\n", encoding="utf-8")


def _add_auto_archive(patterns: list[str]) -> None:
    """Append patterns to the auto_archive list in config/email-senders.yaml."""
    if not _SENDER_CONFIG.exists():
        logger.error("{} not found — create it first", _SENDER_CONFIG)
        return
    import yaml

    existing = set(
        (yaml.safe_load(_SENDER_CONFIG.read_text(encoding="utf-8")) or {}).get("auto_archive") or []
    )
    new_patterns = [p for p in patterns if p not in existing]
    if not new_patterns:
        logger.info("All patterns already present in auto_archive")
        return
    _yaml_append_to_section("auto_archive", new_patterns)
    logger.info("Added {} pattern(s) to auto_archive → {}", len(new_patterns), new_patterns)


async def _apply_review() -> None:
    """Read email-import-people-review.csv, update email-senders.yaml, and upsert people to Notion.

    Edit the 'decision' column in the CSV before running this command:
      allowed      → add to allowed (knowledge DB)
      auto_archive → add to auto_archive (silent archive)
      people       → add to people YAML section + immediately enrich & upsert to Notion People DB
      ignore       → skip permanently (no YAML entry, no Notion write)
      To Review    → skip for now (process later)

    Edit the 'email' column to '@domain.com' to add a domain-level rule
    instead of matching only that exact address (domain rules are never upserted as individuals).
    """
    if not _PEOPLE_REVIEW_CSV.exists():
        logger.error("{} not found — run --dry-run first", _PEOPLE_REVIEW_CSV)
        return
    if not _SENDER_CONFIG.exists():
        logger.error("{} not found", _SENDER_CONFIG)
        return

    import yaml

    data = yaml.safe_load(_SENDER_CONFIG.read_text(encoding="utf-8")) or {}
    existing: dict[str, set[str]] = {
        "allowed": set(data.get("allowed") or []),
        "auto_archive": set(data.get("auto_archive") or []),
        "people": set(data.get("people") or []),
    }
    _DECISION_MAP = {
        "allowed": "allowed",
        "auto_archive": "auto_archive",
        "archive": "auto_archive",
        "people": "people",
    }
    to_add: dict[str, list[str]] = {"allowed": [], "auto_archive": [], "people": []}
    people_to_upsert: list[dict[str, str]] = []
    skipped = 0

    import pandas as pd

    df = pd.read_csv(
        _PEOPLE_REVIEW_CSV, sep=None, engine="python", encoding="utf-8-sig", dtype=str
    ).fillna("")
    for row in df.to_dict("records"):
        decision = (row.get("decision") or "").strip().lower()
        pattern = (row.get("email") or "").strip()
        if not pattern or decision in ("to review", "", "ignore"):
            skipped += 1
            continue
        dest = _DECISION_MAP.get(decision)
        if dest and pattern not in existing[dest]:
            to_add[dest].append(pattern)
            existing[dest].add(pattern)
        # Collect individual addresses tagged people (domain rules @… have no person to upsert)
        if decision == "people" and pattern and not pattern.startswith("@"):
            people_to_upsert.append(row)

    for section, patterns in to_add.items():
        if patterns:
            _yaml_append_to_section(section, patterns)
            logger.info("  {} ← {}", section, patterns)

    total = sum(len(v) for v in to_add.values())
    if total:
        logger.info("Applied {} routing decision(s) to {}", total, _SENDER_CONFIG)
    else:
        logger.info(
            "Nothing to apply — set decision column to allowed/auto_archive/people in {}",
            _PEOPLE_REVIEW_CSV,
        )
    logger.info("Skipped {} rows (To Review / ignore / no pattern)", skipped)

    # ── Notion upsert for people rows ────────────────────────────────────────
    if not people_to_upsert:
        return
    settings = load_settings()
    token = settings.notion_token.get_secret_value()
    people_syncer = await _build_people_syncer(settings, token)
    if people_syncer is None:
        logger.warning("NOTION_PEOPLE_DATA_SOURCE_ID not set — skipping Notion upsert")
        return
    logger.info("Upserting {} person(s) to Notion People DB...", len(people_to_upsert))
    for row in people_to_upsert:
        email = row.get("email", "").strip()
        display = row.get("display_name", "").strip() or email
        domain = row.get("domain", "").strip()
        enrichment = await enrich_person(display, domain, settings)
        person = PersonRecord(
            name=display,
            email=email,
            company=domain,
            linkedin_url=enrichment.linkedin_url or "",
            position=",".join(enrichment.role_type) if enrichment.role_type else "",
        )
        result = await people_syncer.upsert(person)
        logger.info(
            "  {} | {} | dedup={} score={:.0f}",
            email,
            display,
            result.status,
            result.score,
        )


def _can_archive(folder: str, imap_inbox: str) -> bool:
    """Return False for the main INBOX — those emails must never be archived."""
    return folder.lower() != imap_inbox.lower()


async def _build_people_syncer(settings: Settings, token: str) -> NotionPeopleSyncer | None:
    """Return a ready NotionPeopleSyncer or None if not configured."""
    ds_id = settings.notion_people_data_source_id
    if not ds_id:
        return None
    client = AsyncClient(auth=token)
    syncer = NotionPeopleSyncer(client, ds_id, company_syncer=None)
    await syncer.load_snapshot()
    return syncer


async def _archive_uids(adapter: EmailAdapter, folder: str, uids: list[int], *, label: str) -> bool:
    if not uids:
        return True
    try:
        dest = await asyncio.to_thread(adapter.finalize_folder, folder, uids, [])
        logger.info("Archived {} uid(s) ({}) → {}", len(uids), label, dest)
        return True
    except Exception:  # noqa: BLE001
        logger.exception("IMAP archive failed for {} uid(s) ({})", len(uids), label)
        return False


def _csv_requests_process(decision: str) -> bool:
    """True when the CSV row asks to process (manual override or planned action)."""
    d = (decision or "").strip().lower()
    return d == _DECISION_TREATED.lower() or d == "process"


async def _data_source_id(client: AsyncClient, database_id: str) -> str:
    db = await client.databases.retrieve(database_id)
    sources = db.get("data_sources") or []
    if not sources:
        raise RuntimeError(f"No data source on database {database_id}")
    return str(sources[0]["id"])


async def _load_notion_keys(database_id: str, token: str) -> tuple[set[str], set[str]]:
    titles: set[str] = set()
    urls: set[str] = set()
    client = AsyncClient(auth=token)
    try:
        ds_id = await _data_source_id(client, database_id)
        cursor = None
        while True:
            kwargs: dict = {"page_size": 100}
            if cursor:
                kwargs["start_cursor"] = cursor
            resp = await client.data_sources.query(ds_id, **kwargs)
            for page in resp["results"]:
                props = page.get("properties", {})
                name_prop = props.get("Name") or props.get("Title") or {}
                for block in name_prop.get("title", []):
                    t = block.get("plain_text", "").strip().lower()
                    if t:
                        titles.add(t)
                link_prop = props.get("Link") or {}
                url = (link_prop.get("url") or "").strip()
                if url:
                    urls.add(url)
            if not resp.get("has_more"):
                break
            cursor = resp["next_cursor"]
    finally:
        await client.aclose()
    return titles, urls


def _is_duplicate(raw, titles: set[str], urls: set[str]) -> bool:
    subj = raw.subject.strip().lower()
    if subj and subj in titles:
        return True
    url = _first_url(raw.body or "") or _first_url(raw.subject or "")
    return bool(url and url in urls)


async def run(
    *,
    dry_run: bool,
    from_csv: bool,
    since_days: int | None,
    limit: int = 0,
    inbox: list[str] | None = None,
) -> None:
    settings = load_settings()
    if settings.notion_token is None:
        logger.error("NOTION_TOKEN is required")
        sys.exit(1)

    adapter = EmailAdapter(settings)
    folders = inbox or [settings.imap_promotions_folder]
    allowed, auto_archive, people = _load_sender_config(settings)
    # Override adapter lists so the rest of the script uses YAML values
    adapter._allowed = allowed
    adapter._auto_archive = auto_archive
    adapter._people = people
    if not allowed:
        logger.error(
            "allowed list is empty — add senders to {} or set IMAP_ALLOWED_SENDERS in .env",
            _SENDER_CONFIG,
        )
        sys.exit(1)

    if since_days is None:
        since_days = 0 if dry_run else settings.imap_since_days

    token = settings.notion_token.get_secret_value()
    db_id = settings.notion_telegram_msg_database_id
    titles, urls = await _load_notion_keys(db_id, token)
    logger.info("Notion index: {} titles, {} links", len(titles), len(urls))

    pipeline = build_knowledge_pipeline(settings)

    people_syncer: NotionPeopleSyncer | None = None
    if adapter._people and not dry_run:
        people_syncer = await _build_people_syncer(settings, token)
        if people_syncer is None:
            logger.warning(
                "IMAP_PEOPLE_SENDERS is set but neither NOTION_PEOPLE_DATA_SOURCE_ID nor "
                "NOTION_PEOPLE_DATABASE_ID is configured — explicit people written to CSV only"
            )

    csv_rows: list[dict[str, str]] = []
    pending_archive: list[tuple[int, str]] = []
    counts = {
        "process": 0,
        "skip": 0,
        "review": 0,
        "dedup": 0,
        "auto_archive": 0,
        "archive_fail": 0,
    }
    people_candidates: list[tuple] = []  # (_RawEmail, folder: str, in_people_list: bool)

    for folder in folders:
        if from_csv:
            rows = _read_review_csv()
            to_process = [
                r
                for r in rows
                if _csv_requests_process(r.get("decision", ""))
                and r.get("folder", folder) == folder
            ]
            if limit > 0:
                to_process = to_process[:limit]
            if not to_process:
                logger.info(
                    "No rows for folder '{}' with decision='{}' in {}",
                    folder,
                    _DECISION_TREATED,
                    _REVIEW_CSV,
                )
                continue
            uids = [int(r["uid"]) for r in to_process]
            emails = await asyncio.to_thread(
                adapter.fetch_messages, folder, uids=uids, since_days=0
            )
            logger.info("--from-csv: {} message(s) to process from {}", len(emails), folder)
        else:
            is_inbox = folder.lower() == settings.imap_inbox.lower()
            if is_inbox and not dry_run:
                # Live INBOX: enforce a minimum window to avoid hanging on a large mailbox.
                folder_since = max(since_days or 0, settings.imap_since_days)
            else:
                folder_since = since_days
            emails = await asyncio.to_thread(
                adapter.fetch_messages,
                folder,
                all_messages=(dry_run and not is_inbox),
                since_days=folder_since,
            )
            if limit > 0:
                emails = sorted(emails, key=lambda e: e.sent_at, reverse=True)[:limit]

        logger.info("── Email run ─────────────────────────────────────────────")
        logger.info("  Mode          : {}", "DRY RUN" if dry_run else "LIVE")
        logger.info("  Folder        : {}", folder)
        logger.info(
            "  Since days    : {} ({})", since_days, "all" if since_days == 0 else "filtered"
        )
        if limit > 0:
            logger.info("  Limit         : {} (newest first)", limit)
        logger.info("  Allowlist     : {}", ", ".join(allowed))
        logger.info("  Auto-archive  : {}", ", ".join(auto_archive) or "(none)")
        logger.info("  Messages      : {}", len(emails))
        logger.info("──────────────────────────────────────────────────────────")

        for raw in emails:
            summary = _summary(raw)
            row = {
                "uid": str(raw.uid),
                "folder": folder,
                "sender": raw.sender,
                "subject": raw.subject,
                "sent_at": raw.sent_at.strftime("%Y-%m-%d %H:%M"),
                "summary": summary,
                "decision": _DECISION_UNTOUCHED,
            }
            csv_rows.append(row)

            if not from_csv and auto_archive and _sender_allowed(raw.sender, auto_archive):
                counts["auto_archive"] += 1
                row["decision"] = _DECISION_AUTO_ARCHIVED
                if not dry_run and _can_archive(folder, settings.imap_inbox):
                    ok = await _archive_uids(adapter, folder, [raw.uid], label="auto-archive")
                    if not ok:
                        counts["archive_fail"] += 1
                logger.info(
                    "{} uid={} | {} | from={} | subject={!r}",
                    "WOULD" if dry_run else "OK",
                    raw.uid,
                    _DECISION_AUTO_ARCHIVED,
                    raw.sender,
                    raw.subject or "(no subject)",
                )
                continue

            if not from_csv and not _sender_allowed(raw.sender, allowed):
                counts["review"] += 1
                in_people_list = _sender_allowed(raw.sender, adapter._people)
                people_candidates.append((raw, folder, in_people_list))
                logger.info(
                    "REVIEW uid={} | people={} | from={} | subject={!r}",
                    raw.uid,
                    "yes" if in_people_list else "review",
                    raw.sender,
                    raw.subject or "(no subject)",
                )
                continue

            if _is_duplicate(raw, titles, urls):
                counts["dedup"] += 1
                row["decision"] = _DECISION_TREATED
                if (
                    not dry_run
                    and _sender_allowed(raw.sender, allowed)
                    and _can_archive(folder, settings.imap_inbox)
                ):
                    archived = await _archive_uids(adapter, folder, [raw.uid], label="dedup")
                    if not archived:
                        counts["archive_fail"] += 1
                        pending_archive.append((raw.uid, folder))
                logger.info(
                    "SKIP  uid={} | {} | dedup (already in Notion) | subject={!r}",
                    raw.uid,
                    _DECISION_TREATED if not dry_run else _DECISION_UNTOUCHED,
                    raw.subject or "(no subject)",
                )
                continue

            if dry_run:
                counts["process"] += 1
                row["decision"] = _DECISION_TREATED
                logger.info(
                    "WOULD uid={} | {} | → Notion → {} | subject={!r} | sent={}",
                    raw.uid,
                    _DECISION_TREATED,
                    settings.imap_archive,
                    raw.subject or "(no subject)",
                    raw.sent_at.strftime("%Y-%m-%d"),
                )
                continue

            incoming = adapter._to_incoming(raw)
            page_id = await pipeline(incoming)
            if page_id:
                counts["process"] += 1
                row["decision"] = _DECISION_TREATED
                subj = raw.subject.strip().lower()
                if subj:
                    titles.add(subj)
                url = _first_url(raw.body or "") or _first_url(raw.subject or "")
                if url:
                    urls.add(url)
                if _can_archive(folder, settings.imap_inbox):
                    archived = await _archive_uids(adapter, folder, [raw.uid], label="notion")
                    if not archived:
                        counts["archive_fail"] += 1
                        pending_archive.append((raw.uid, folder))
                else:
                    archived = True
                logger.info(
                    "OK    uid={} | {} | notion page {} | imap={}",
                    raw.uid,
                    _DECISION_TREATED,
                    page_id,
                    "archived" if archived else "ARCHIVE FAILED",
                )
            else:
                counts["skip"] += 1
                logger.warning(
                    "FAIL  uid={} | {} | Notion write failed", raw.uid, _DECISION_UNTOUCHED
                )

    # ── People: enrich explicit list, write both to CSV ────────────────────
    people_rows: list[dict[str, str]] = []
    for raw, folder, in_people_list in people_candidates:
        domain = raw.sender.split("@")[-1] if "@" in raw.sender else ""
        display = raw.sender.split("@")[0].replace(".", " ").replace("_", " ").title()
        enriched_flag = ""
        linkedin = seniority = role_type_str = ""
        dedup_status = dedup_score = matched_name = ""

        if in_people_list and not dry_run and people_syncer:
            enrichment = await enrich_person(display, domain, settings)
            if enrichment.source:
                enriched_flag = enrichment.source
            linkedin = enrichment.linkedin_url
            seniority = enrichment.seniority
            role_type_str = ",".join(enrichment.role_type)
            person = PersonRecord(
                name=display,
                company="",
                email=raw.sender,
                linkedin_url=linkedin,
                seniority=seniority,
                role_type=enrichment.role_type,
            )
            result = await people_syncer.upsert(person)
            dedup_status = result.status
            dedup_score = f"{result.score:.0f}" if result.score else ""
            matched_name = result.matched_name

        if in_people_list and dry_run:
            dedup_status = "dry-run"

        decision = (
            _DECISION_TO_REVIEW if not in_people_list else (dedup_status or _DECISION_UNTOUCHED)
        )

        people_rows.append(
            {
                "email": raw.sender,
                "display_name": display,
                "domain": domain,
                "folder": folder,
                "people_list": "yes" if in_people_list else "no",
                "enriched": enriched_flag,
                "linkedin": linkedin,
                "seniority": seniority,
                "role_type": role_type_str,
                "dedup_status": dedup_status,
                "dedup_score": dedup_score,
                "matched_name": matched_name,
                "decision": decision,
            }
        )
        logger.info(
            "PEOPLE uid={} | list={} | enriched={} | dedup={} | from={}",
            raw.uid,
            "yes" if in_people_list else "no",
            enriched_flag or "—",
            dedup_status or "—",
            raw.sender,
        )

    if people_rows:
        _write_people_csv(people_rows)
        logger.info("Wrote {} people candidates → {}", len(people_rows), _PEOPLE_REVIEW_CSV)

    _write_review_csv(csv_rows)
    logger.info("Wrote {}", _REVIEW_CSV)

    if not dry_run and pending_archive:
        failed = [
            (u, fldr)
            for u, fldr in pending_archive
            if not await _archive_uids(adapter, fldr, [u], label="retry")
        ]
        if failed:
            logger.error(
                "Archive still failed for {} uid(s): {} — check IMAP_ARCHIVE in .env",
                len(failed),
                [u for u, _ in failed][:10],
            )

    logger.info(
        "Done. treated={} auto_archived={} untouched={} dedup={} notion_fail={} archive_fail={}",
        counts["process"],
        counts["auto_archive"],
        counts["review"],
        counts["dedup"],
        counts["skip"],
        counts["archive_fail"],
    )


if __name__ == "__main__":
    _add_archive_raw = _arg("--add-auto-archive")
    if _add_archive_raw is not None:
        _add_auto_archive(_parse_inbox_arg(_add_archive_raw))
        sys.exit(0)

    if _flag("--apply-review"):
        asyncio.run(_apply_review())
        sys.exit(0)

    _since = _arg("--since-days")
    _limit = _arg("--limit")
    _inbox_raw = _arg("--inbox")
    asyncio.run(
        run(
            dry_run=_flag("--dry-run"),
            from_csv=_flag("--from-csv"),
            since_days=int(_since) if _since is not None else None,
            limit=int(_limit) if _limit else 0,
            inbox=_parse_inbox_arg(_inbox_raw) if _inbox_raw else None,
        )
    )
