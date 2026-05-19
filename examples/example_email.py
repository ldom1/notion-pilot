"""Example: run the email adapter (IMAP polling → OpenRouter enrichment → Notion page).

Required env vars (.env):
    IMAP_HOST, IMAP_USER, IMAP_PASSWORD
    IMAP_ALLOWED_SENDERS  (comma-separated, e.g. "alice@example.com,@mycompany.com")
    NOTION_TOKEN, NOTION_DATABASE_ID
    OPENROUTER_API_KEY

Run with:
    uv run python examples/example_email.py                              # live
    uv run python examples/example_email.py --dry-run                   # preview INBOX
    uv run python examples/example_email.py --dry-run --folder=Promotions  # preview another folder
"""

import asyncio
import sys

from loguru import logger

from telegram_to_notion.adapters.email import EmailAdapter, _sender_allowed
from telegram_to_notion.config import load_settings
from telegram_to_notion.pipelines import build_knowledge_pipeline, build_people_pipeline


async def dry_run(adapter: EmailAdapter, folder: str | None = None) -> None:
    """Fetch emails and print what would be archived / skipped — no side effects."""
    s = adapter._settings
    logger.info("── Dry-run configuration ───────────────────────────────")
    logger.info("  IMAP host     : {}:{}", s.imap_host, s.imap_port)
    logger.info("  Account       : {}", s.imap_user)
    logger.info("  Polling folder: {}", folder or s.imap_inbox)
    logger.info("  Archive folder: {}", s.imap_archive)
    logger.info("  Content allow : {}", ", ".join(adapter._allowed) or "(none)")
    logger.info("  People allow  : {}", ", ".join(adapter._people) or "(none)")
    logger.info("────────────────────────────────────────────────────────")

    scan_folder = folder or s.imap_inbox
    emails = await asyncio.to_thread(adapter._fetch_unseen, ["ALL"], scan_folder)

    if not emails:
        logger.info("No messages in '{}'", scan_folder)
        return

    to_process = [
        e
        for e in emails
        if _sender_allowed(e.sender, adapter._allowed) or _sender_allowed(e.sender, adapter._people)
    ]
    logger.info(
        "Found {} message(s) in '{}' — {} will be processed, {} skipped",
        len(emails),
        scan_folder,
        len(to_process),
        len(emails) - len(to_process),
    )
    logger.info("────────────────────────────────────────────────────────")

    inbox = scan_folder
    archive = s.imap_archive

    for raw in emails:
        if _sender_allowed(raw.sender, adapter._allowed):
            action = f"{inbox} → Notion (content DB) → {archive}"
            verdict = "✓"
        elif _sender_allowed(raw.sender, adapter._people):
            action = f"{inbox} → Notion (people DB) → {archive}"
            verdict = "✓"
        else:
            action = f"SKIP — stays in {inbox} (not in any allowlist)"
            verdict = "✗"
        logger.info(
            "{} [{}] uid={} | from={} | subject={!r} | sent={}",
            verdict,
            action,
            raw.uid,
            raw.sender,
            raw.subject or "(no subject)",
            raw.sent_at.strftime("%Y-%m-%d %H:%M"),
        )

    logger.info("────────────────────────────────────────────────────────")
    logger.info(
        "Dry-run complete. Run without --dry-run to process and archive {} message(s).",
        len(to_process),
    )


def _arg(prefix: str) -> str | None:
    """Return the value of a --key=value CLI argument, or None."""
    for arg in sys.argv:
        if arg.startswith(f"{prefix}="):
            return arg.split("=", 1)[1]
    return None


async def main(dry: bool = False, folder: str | None = None) -> None:
    settings = load_settings()
    adapter = EmailAdapter(settings)
    if dry:
        await dry_run(adapter, folder=folder)
    else:
        pipeline = build_knowledge_pipeline(settings)
        people_pipeline = build_people_pipeline(settings)
        logger.info("Starting email adapter — polling every {}s", settings.imap_poll_interval)
        await adapter.run(pipeline, people_handler=people_pipeline)


if __name__ == "__main__":
    asyncio.run(main(dry="--dry-run" in sys.argv, folder=_arg("--folder")))
