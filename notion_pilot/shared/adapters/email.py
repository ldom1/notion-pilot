"""IMAP email source adapter."""

import asyncio
import email as email_lib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from email.header import decode_header as _email_decode_header
from email.utils import parseaddr, parsedate_to_datetime

from imapclient import IMAPClient
from imapclient.imapclient import SEEN
from loguru import logger

from notion_pilot.shared.adapters import MessageHandler  # noqa: TCH001
from notion_pilot.shared.config import Settings
from notion_pilot.shared.models import IncomingMessage, MediaType


def _decode_str(value: str) -> str:
    """Decode an RFC 2047-encoded header value to a plain string."""
    parts = _email_decode_header(value)
    result = []
    for raw, enc in parts:
        if isinstance(raw, bytes):
            result.append(raw.decode(enc or "utf-8", errors="replace"))
        else:
            result.append(raw)
    return "".join(result)


class _HTMLText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def text(self) -> str:
        return " ".join(self._parts)


def _html_body(msg: email_lib.message.Message) -> str:
    """Extract text from the first text/html part."""
    parts: list[email_lib.message.Message] = [msg] if not msg.is_multipart() else list(msg.walk())
    for part in parts:
        if part.get_content_type() != "text/html":
            continue
        payload = part.get_payload(decode=True)
        if not isinstance(payload, bytes):
            continue
        charset = part.get_content_charset() or "utf-8"
        html = payload.decode(charset, errors="replace")
        parser = _HTMLText()
        parser.feed(html)
        return parser.text()
    return ""


def _message_body(msg: email_lib.message.Message) -> str:
    """Prefer text/plain; fall back to stripped text/html."""
    body = _plain_body(msg)
    return body if body.strip() else _html_body(msg)


def _plain_body(msg: email_lib.message.Message) -> str:
    """Extract the first text/plain part; return empty string if none."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if isinstance(payload, bytes):
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
        return ""
    if msg.get_content_type() != "text/plain":
        return ""
    payload = msg.get_payload(decode=True)
    if not isinstance(payload, bytes):
        return ""
    charset = msg.get_content_charset() or "utf-8"
    return payload.decode(charset, errors="replace")


def _sender_patterns(*fields: str | None) -> list[str]:
    out: list[str] = []
    for field in fields:
        out.extend(s.strip() for s in (field or "").split(",") if s.strip())
    return out


def _sender_allowed(from_addr: str, allowed: list[str]) -> bool:
    """Return True if from_addr ends with any entry in allowed (case-insensitive)."""
    addr = from_addr.lower()
    return any(addr.endswith(a.lower()) for a in allowed if a)


def _parse_date(date_str: str | None) -> datetime:
    """Parse an RFC 2822 date string; fall back to now(UTC) if missing or malformed."""
    if not date_str:
        return datetime.now(tz=timezone.utc)
    try:
        dt = parsedate_to_datetime(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:  # noqa: BLE001
        return datetime.now(tz=timezone.utc)


@dataclass
class _RawEmail:
    uid: int
    sender: str
    subject: str
    body: str
    sent_at: datetime


class EmailAdapter:
    """IMAP polling source adapter with sender allowlist and archive-on-process."""

    name = "email"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._allowed: list[str] = [
            s.strip() for s in (settings.imap_allowed_senders or "").split(",") if s.strip()
        ]
        self._people: list[str] = [
            s.strip() for s in (settings.imap_people_senders or "").split(",") if s.strip()
        ]
        self._auto_archive = _sender_patterns(settings.imap_auto_archive_senders)
        if not self._allowed and not self._people:
            logger.warning(
                "email adapter: IMAP_ALLOWED_SENDERS and IMAP_PEOPLE_SENDERS are both empty — "
                "all incoming emails will be skipped"
            )
        if not settings.imap_host:
            raise ValueError("imap_host is required for the email adapter")
        if not settings.imap_user:
            raise ValueError("imap_user is required for the email adapter")
        if not settings.imap_password:
            raise ValueError("imap_password is required for the email adapter")

    def _connect(self) -> IMAPClient:
        port = self._settings.imap_port
        # Port 993 → direct TLS; anything else (e.g. 587, 143) → STARTTLS
        use_ssl = port == 993
        client = IMAPClient(self._settings.imap_host, port=port, ssl=use_ssl)
        if not use_ssl:
            client.starttls()
        assert self._settings.imap_password is not None
        client.login(
            self._settings.imap_user,
            self._settings.imap_password.get_secret_value(),
        )
        return client

    def _fetch(
        self,
        folder: str,
        search: list[str] | None = None,
        *,
        uids: list[int] | None = None,
        since_days: int = 0,
    ) -> list[_RawEmail]:
        with self._connect() as client:
            client.select_folder(folder)
            if uids is not None:
                target_uids = uids
            else:
                target_uids = client.search(search or ["UNSEEN"])
            if not target_uids:
                return []
            # BODY.PEEK[] fetches the full message without setting the \Seen flag,
            # unlike RFC822 which silently marks messages as read on the server.
            raw_messages = client.fetch(target_uids, ["BODY.PEEK[]"])
            result: list[_RawEmail] = []
            for uid, data in raw_messages.items():
                msg = email_lib.message_from_bytes(data[b"BODY[]"])
                _, from_addr = parseaddr(msg.get("From", ""))
                result.append(
                    _RawEmail(
                        uid=uid,
                        sender=from_addr,
                        subject=_decode_str(msg.get("Subject") or ""),
                        body=_message_body(msg),
                        sent_at=_parse_date(msg.get("Date")),
                    )
                )
            if since_days > 0:
                cutoff = datetime.now(tz=timezone.utc) - timedelta(days=since_days)
                result = [e for e in result if e.sent_at >= cutoff]
            return result

    def fetch_messages(
        self,
        folder: str,
        *,
        all_messages: bool = False,
        since_days: int = 0,
        uids: list[int] | None = None,
    ) -> list[_RawEmail]:
        """Fetch messages from ``folder`` (ALL or UNSEEN), optionally filtered by age."""
        search = None if uids is not None else (["ALL"] if all_messages else ["UNSEEN"])
        return self._fetch(folder, search, uids=uids, since_days=since_days)

    def _fetch_unseen(
        self, search: list[str] | None = None, folder: str | None = None
    ) -> list[_RawEmail]:
        return self._fetch(folder or self._settings.imap_inbox, search)

    def _resolve_folder(self, client: IMAPClient, wanted: str) -> str:
        """Match ``wanted`` to an existing IMAP folder (case-insensitive, suffix match)."""
        wanted_l = wanted.lower()
        names = [name for _flags, _delimiter, name in client.list_folders()]
        for name in names:
            low = name.lower()
            if low == wanted_l or low.endswith(f"/{wanted_l}") or low.endswith(f".{wanted_l}"):
                return name
        similar = [n for n in names if "archiv" in n.lower()]
        hint = similar[0] if len(similar) == 1 else similar
        raise ValueError(
            f"IMAP_ARCHIVE folder {wanted!r} does not exist on the server. "
            f"Set IMAP_ARCHIVE in .env to an exact folder name, e.g. {hint!r}. "
            f"Archive-like folders found: {similar or 'none'}."
        )

    def finalize_folder(
        self, folder: str, to_archive: list[int], to_mark_seen: list[int]
    ) -> str:
        """Mark seen and move messages to the archive folder. Returns destination folder."""
        return self._finalize(to_archive, to_mark_seen, folder)

    def _finalize(
        self, to_archive: list[int], to_mark_seen: list[int], folder: str | None = None
    ) -> str:
        with self._connect() as client:
            src = folder or self._settings.imap_inbox
            client.select_folder(src)
            dest = self._resolve_folder(client, self._settings.imap_archive)
            if to_mark_seen:
                client.add_flags(to_mark_seen, [SEEN])
            if to_archive:
                client.add_flags(to_archive, [SEEN])
                logger.info(
                    "IMAP: moving {} message(s) {} → {}", len(to_archive), src, dest
                )
                client.move(to_archive, dest)
            return dest

    def _to_incoming(self, raw: _RawEmail) -> IncomingMessage:
        text = f"{raw.subject}\n\n{raw.body}".strip() if raw.body else raw.subject
        return IncomingMessage(
            text=text or None,
            caption=None,
            sender=raw.sender,
            sent_at=raw.sent_at,
            media_type=MediaType.TEXT,
            media=None,
            source_adapter="email",
        )

    async def run(
        self,
        handler: MessageHandler,
        people_handler: MessageHandler | None = None,
    ) -> None:
        logger.info(
            "email adapter: polling {} every {}s",
            self._settings.imap_host,
            self._settings.imap_poll_interval,
        )
        while True:
            try:
                emails = await asyncio.to_thread(self._fetch_unseen)
                to_archive: list[int] = []
                to_mark_seen: list[int] = []
                for raw in emails:
                    if _sender_allowed(raw.sender, self._auto_archive):
                        to_archive.append(raw.uid)
                        logger.info("email auto-archived (no Notion): {}", raw.sender)
                    elif _sender_allowed(raw.sender, self._allowed):
                        await handler(self._to_incoming(raw))
                        to_archive.append(raw.uid)
                        logger.info("email processed → content DB: {}", raw.sender)
                    elif people_handler and _sender_allowed(raw.sender, self._people):
                        await people_handler(self._to_incoming(raw))
                        to_archive.append(raw.uid)
                        logger.info("email processed → people DB: {}", raw.sender)
                    else:
                        to_mark_seen.append(raw.uid)
                        logger.debug("email from {} not in any allowlist, skipping", raw.sender)
                # At-least-once delivery: if _finalize raises after handler already wrote to Notion,
                # the UID remains UNSEEN and will be reprocessed on the next poll.
                if to_archive or to_mark_seen:
                    await asyncio.to_thread(
                        self._finalize, to_archive, to_mark_seen, self._settings.imap_inbox
                    )
            except Exception:  # noqa: BLE001  # pylint: disable=broad-exception-caught
                logger.exception("email adapter poll error")
            await asyncio.sleep(self._settings.imap_poll_interval)
