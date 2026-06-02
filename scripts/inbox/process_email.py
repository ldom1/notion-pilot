"""Process Infomaniak Promotions mail → DomTelegramBot (NOTION_TELEGRAM_MSG_DATABASE_ID).

Usage:
    uv sync --extra email
    uv run python scripts/inbox/process_email.py --dry-run
    uv run python scripts/inbox/process_email.py
    uv run python scripts/inbox/process_email.py --from-csv   # rows marked Treated and archived
    uv run python scripts/inbox/process_email.py --dry-run --since-days=14
    uv run python scripts/inbox/process_email.py --limit=10   # newest 10 only (smoke test)
"""

import asyncio
import csv
import re
import sys
from pathlib import Path

from loguru import logger
from notion_client import AsyncClient

from notion_pilot.inbox import build_knowledge_pipeline
from notion_pilot.shared.adapters.email import EmailAdapter, _sender_allowed
from notion_pilot.shared.config import load_settings
from notion_pilot.shared.models import _first_url

_REVIEW_CSV = Path("data/email-import-review.csv")
_CSV_FIELDS = ["uid", "folder", "sender", "subject", "sent_at", "summary", "decision"]
_DECISION_UNTOUCHED = "Untouched"
_DECISION_TREATED = "Treated and archived"
_DECISION_AUTO_ARCHIVED = "Auto archived"

_PEOPLE_REVIEW_CSV = Path("data/email-import-people-review.csv")
_PEOPLE_CSV_FIELDS = [
    "email", "display_name", "domain", "folder",
    "people_list", "enriched", "linkedin", "seniority", "role_type",
    "dedup_status", "dedup_score", "matched_name", "decision",
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


_AUTOMATED_PATTERNS = frozenset({
    "noreply", "no-reply", "donotreply", "do-not-reply",
    "support", "info", "postmaster", "bounce", "mailer-daemon",
    "notifications", "newsletter",
})


def _is_automated(sender: str) -> bool:
    """Return True if the sender looks like an automated/noreply address."""
    local = sender.lower().split("@")[0]
    return any(p in local for p in _AUTOMATED_PATTERNS)


def _parse_inbox_arg(raw: str) -> list[str]:
    """Split comma-separated folder names; strip whitespace; drop empty entries."""
    return [f.strip() for f in raw.split(",") if f.strip()]


def _summary(raw) -> str:
    return _one_sentence(raw.subject, raw.body)


def _write_review_csv(rows: list[dict[str, str]]) -> None:
    _REVIEW_CSV.parent.mkdir(parents=True, exist_ok=True)
    with _REVIEW_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _read_review_csv() -> list[dict[str, str]]:
    with _REVIEW_CSV.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_people_csv(rows: list[dict[str, str]]) -> None:
    _PEOPLE_REVIEW_CSV.parent.mkdir(parents=True, exist_ok=True)
    with _PEOPLE_REVIEW_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_PEOPLE_CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


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
    allowed = adapter._allowed
    auto_archive = adapter._auto_archive
    if not allowed:
        logger.error("IMAP_ALLOWED_SENDERS is empty — set e.g. @tldr.tech,@medium.com")
        sys.exit(1)

    if since_days is None:
        since_days = 0 if dry_run else settings.imap_since_days

    token = settings.notion_token.get_secret_value()
    db_id = settings.notion_telegram_msg_database_id
    titles, urls = await _load_notion_keys(db_id, token)
    logger.info("Notion index: {} titles, {} links", len(titles), len(urls))

    pipeline = build_knowledge_pipeline(settings)

    csv_rows: list[dict[str, str]] = []
    pending_archive: list[tuple[int, str]] = []
    counts = {"process": 0, "skip": 0, "review": 0, "dedup": 0, "auto_archive": 0, "archive_fail": 0}
    people_candidates: list[tuple] = []  # (_RawEmail, folder: str, in_people_list: bool)

    for folder in folders:
        if from_csv:
            rows = _read_review_csv()
            to_process = [
                r for r in rows
                if _csv_requests_process(r.get("decision", ""))
                and r.get("folder", folder) == folder
            ]
            if limit > 0:
                to_process = to_process[:limit]
            if not to_process:
                logger.info("No rows for folder '{}' with decision='{}' in {}", folder, _DECISION_TREATED, _REVIEW_CSV)
                continue
            uids = [int(r["uid"]) for r in to_process]
            emails = await asyncio.to_thread(
                adapter.fetch_messages, folder, uids=uids, since_days=0
            )
            logger.info("--from-csv: {} message(s) to process from {}", len(emails), folder)
        else:
            emails = await asyncio.to_thread(
                adapter.fetch_messages,
                folder,
                all_messages=dry_run,
                since_days=since_days,
            )
            if limit > 0:
                emails = sorted(emails, key=lambda e: e.sent_at, reverse=True)[:limit]

        logger.info("── Email run ─────────────────────────────────────────────")
        logger.info("  Mode          : {}", "DRY RUN" if dry_run else "LIVE")
        logger.info("  Folder        : {}", folder)
        logger.info("  Since days    : {} ({})", since_days, "all" if since_days == 0 else "filtered")
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
                if not dry_run:
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
                if in_people_list or not _is_automated(raw.sender):
                    people_candidates.append((raw, folder, in_people_list))
                logger.info(
                    "REVIEW uid={} | people={} | from={} | subject={!r}",
                    raw.uid,
                    "yes" if in_people_list else ("candidate" if not _is_automated(raw.sender) else "automated"),
                    raw.sender,
                    raw.subject or "(no subject)",
                )
                continue

            if _is_duplicate(raw, titles, urls):
                counts["dedup"] += 1
                row["decision"] = _DECISION_TREATED
                if not dry_run and _sender_allowed(raw.sender, allowed):
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
                archived = await _archive_uids(adapter, folder, [raw.uid], label="notion")
                if not archived:
                    counts["archive_fail"] += 1
                    pending_archive.append((raw.uid, folder))
                logger.info(
                    "OK    uid={} | {} | notion page {} | imap={}",
                    raw.uid,
                    _DECISION_TREATED,
                    page_id,
                    "archived" if archived else "ARCHIVE FAILED",
                )
            else:
                counts["skip"] += 1
                logger.warning("FAIL  uid={} | {} | Notion write failed", raw.uid, _DECISION_UNTOUCHED)

    # ── People CSV (no Notion upsert here — see Task 6 for enrichment) ─────
    people_rows: list[dict[str, str]] = []
    for raw, folder, in_people_list in people_candidates:
        domain = raw.sender.split("@")[-1] if "@" in raw.sender else ""
        display = raw.sender.split("@")[0].replace(".", " ").replace("_", " ").title()
        people_rows.append({
            "email": raw.sender,
            "display_name": display,
            "domain": domain,
            "folder": folder,
            "people_list": "yes" if in_people_list else "no",
            "enriched": "",
            "linkedin": "",
            "seniority": "",
            "role_type": "",
            "dedup_status": "",
            "dedup_score": "",
            "matched_name": "",
            "decision": _DECISION_UNTOUCHED if in_people_list else _DECISION_TO_REVIEW,
        })

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
