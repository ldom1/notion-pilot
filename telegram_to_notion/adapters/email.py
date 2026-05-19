"""IMAP email source adapter."""

import asyncio
import email as email_lib
from dataclasses import dataclass
from datetime import datetime, timezone
from email.header import decode_header as _email_decode_header
from email.utils import parseaddr, parsedate_to_datetime

from imapclient import IMAPClient
from imapclient.imapclient import SEEN
from loguru import logger

from telegram_to_notion.adapters import MessageHandler
from telegram_to_notion.config import Settings
from telegram_to_notion.models import IncomingMessage, MediaType


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


def _sender_allowed(from_addr: str, allowed: list[str]) -> bool:
    """Return True if from_addr ends with any entry in allowed (case-insensitive)."""
    addr = from_addr.lower()
    return any(addr.endswith(a.lower()) for a in allowed if a)


def _parse_date(date_str: str | None) -> datetime:
    if not date_str:
        return datetime.now(tz=timezone.utc)
    try:
        return parsedate_to_datetime(date_str)
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
            s.strip() for s in (settings.imap_allowed_senders or "").split(",")
        ]

    def _connect(self) -> IMAPClient:
        assert self._settings.imap_host
        assert self._settings.imap_password
        client = IMAPClient(self._settings.imap_host, port=self._settings.imap_port, ssl=True)
        client.login(
            self._settings.imap_user,
            self._settings.imap_password.get_secret_value(),
        )
        return client

    def _fetch_unseen(self) -> list[_RawEmail]:
        with self._connect() as client:
            client.select_folder(self._settings.imap_inbox)
            uids = client.search(["UNSEEN"])
            if not uids:
                return []
            raw_messages = client.fetch(uids, ["RFC822"])
            result: list[_RawEmail] = []
            for uid, data in raw_messages.items():
                msg = email_lib.message_from_bytes(data[b"RFC822"])
                _, from_addr = parseaddr(msg.get("From", ""))
                result.append(
                    _RawEmail(
                        uid=uid,
                        sender=from_addr,
                        subject=_decode_str(msg.get("Subject") or ""),
                        body=_plain_body(msg),
                        sent_at=_parse_date(msg.get("Date")),
                    )
                )
            return result

    def _finalize(self, to_archive: list[int], to_mark_seen: list[int]) -> None:
        with self._connect() as client:
            client.select_folder(self._settings.imap_inbox)
            if to_mark_seen:
                client.add_flags(to_mark_seen, [SEEN])
            if to_archive:
                client.add_flags(to_archive, [SEEN])
                client.move(to_archive, self._settings.imap_archive)

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

    async def run(self, handler: MessageHandler) -> None:
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
                    if _sender_allowed(raw.sender, self._allowed):
                        await handler(self._to_incoming(raw))
                        to_archive.append(raw.uid)
                        logger.info("email processed and queued for archive: {}", raw.sender)
                    else:
                        to_mark_seen.append(raw.uid)
                        logger.debug("email from {} not in allowlist, skipping", raw.sender)
                if to_archive or to_mark_seen:
                    await asyncio.to_thread(self._finalize, to_archive, to_mark_seen)
            except Exception:  # noqa: BLE001  # pylint: disable=broad-exception-caught
                logger.exception("email adapter poll error")
            await asyncio.sleep(self._settings.imap_poll_interval)
