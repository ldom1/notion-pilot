"""Telegram source adapter — long-polling via python-telegram-bot async API."""

import asyncio
import datetime as _dt
import json
import re as _re
import tempfile
from datetime import timezone
from pathlib import Path
from typing import Any

import httpx
from loguru import logger
from telegram import Message, Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from notion_pilot.crm.commands import COMMANDS, extract_fields_from_text, get_next_prompt
from notion_pilot.crm.contact_parse import parse_linkedin_deterministic, sanitize_extracted
from notion_pilot.crm.conv_state import ConvState, ConvStateStore
from notion_pilot.crm.queries import get_inbox_items, get_open_leads, get_recent_people
from notion_pilot.crm.recap import format_inbox, format_leads, format_recap
from notion_pilot.crm.setup_wizard import advance_setup, start_setup
from notion_pilot.shared.adapters import MessageHandler as PipelineHandler
from notion_pilot.shared.config import Settings
from notion_pilot.shared.media import extract_photo, extract_voice
from notion_pilot.shared.media.transcribe_voice import transcribe_file
from notion_pilot.shared.models import IncomingMessage, MediaType

_last_seen: _dt.datetime | None = None


def get_last_seen() -> _dt.datetime | None:
    """Return the timestamp of the last successfully handled Telegram message."""
    return _last_seen


READ_COMMANDS: frozenset[str] = frozenset({"recap", "leads", "inbox"})

_READ_INTENT_PATTERNS: list[tuple[str, str]] = [
    (r"\brecap\b", "recap"),
    (r"\bleads\b", "leads"),
    (r"inbox|relire", "inbox"),
]


def _detect_read_intent(text: str) -> str | None:
    """Return a READ_COMMANDS name if text is a query intent, else None.

    Matches whole-word keywords only to avoid false positives on data entries
    like "j'ai un lead intéressant" (no trailing 's').
    """
    lowered = text.lower()
    for pattern, cmd in _READ_INTENT_PATTERNS:
        if _re.search(pattern, lowered):
            return cmd
    return None


def _enrich_settings_from_cockpit(settings: Settings) -> Settings:
    """Return settings patched with DB IDs from the first available cockpit_config.json."""
    workspaces_dir = Path(__file__).parent.parent.parent.parent / "web" / "workspaces"
    if not workspaces_dir.exists():
        return settings
    overrides: dict[str, str] = {}
    for ws_dir in sorted(workspaces_dir.iterdir()):
        cfg_path = ws_dir / "cockpit_config.json"
        if not cfg_path.exists():
            continue
        try:
            cfg = json.loads(cfg_path.read_text())
            overrides = cfg.get("databases", {})
            break
        except Exception:
            continue
    if not overrides:
        return settings
    # Build a new settings instance with cockpit values filling in missing env values
    data = settings.model_dump()
    for field, env_key in (
        ("notion_deals_database_id", "notion_deals_database_id"),
        ("notion_people_data_source_id", "notion_people_data_source_id"),
        ("notion_companies_data_source_id", "notion_companies_data_source_id"),
        ("notion_telegram_msg_database_id", "notion_telegram_msg_database_id"),
        ("notion_notions_database_id", "notion_notions_database_id"),
        ("notion_ideas_database_id", "notion_ideas_database_id"),
        ("notion_tools_database_id", "notion_tools_database_id"),
        ("notion_data_tech_database_id", "notion_data_tech_database_id"),
    ):
        if not data.get(field) and overrides.get(env_key):
            data[field] = overrides[env_key]
    return Settings.model_validate(data)


async def dispatch_read(cmd_name: str, settings: Settings) -> str:
    """Query Notion and return a formatted string for a read command."""
    settings = _enrich_settings_from_cockpit(settings)
    try:
        if cmd_name == "leads":
            leads = await get_open_leads(settings)
            return format_leads(leads)
        if cmd_name == "inbox":
            items = await get_inbox_items(settings)
            return format_inbox(items)
        if cmd_name == "recap":
            leads, items, people = await asyncio.gather(
                get_open_leads(settings),
                get_inbox_items(settings),
                get_recent_people(settings),
            )
            return format_recap(leads=leads, people=people, inbox=items)
    except Exception:  # noqa: BLE001
        logger.exception("telegram: read command /{} failed", cmd_name)
        return f"Could not fetch data for /{cmd_name}. Check server logs."
    return "Unknown read command."


async def _to_incoming(settings: Settings, msg: Message) -> IncomingMessage:
    """Map a Telegram Message to IncomingMessage."""
    user = msg.from_user
    sender = (user.username or user.full_name or "unknown") if user else "unknown"
    sent_at = msg.date
    if sent_at.tzinfo is None:
        sent_at = sent_at.replace(tzinfo=timezone.utc)

    if msg.voice is not None:
        payload = await extract_voice(msg)
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp.write(payload.content)
            path = tmp.name
        try:
            transcript = await asyncio.to_thread(
                transcribe_file, path, settings.whisper_language, settings.whisper_model_size
            )
        finally:
            Path(path).unlink(missing_ok=True)
        return IncomingMessage(
            text=transcript or "[voice] Transcription unavailable.",
            caption=msg.caption,
            sender=sender,
            sent_at=sent_at,
            media_type=MediaType.VOICE,
            media=None,
            source_adapter="telegram",
        )

    if msg.photo:
        return IncomingMessage(
            text=msg.text,
            caption=msg.caption,
            sender=sender,
            sent_at=sent_at,
            media_type=MediaType.PHOTO,
            media=await extract_photo(msg),
            source_adapter="telegram",
        )

    return IncomingMessage(
        text=msg.text,
        caption=msg.caption,
        sender=sender,
        sent_at=sent_at,
        media_type=MediaType.TEXT,
        media=None,
        source_adapter="telegram",
    )


_INFER_PROMPT = (
    "Classify the following message into exactly one category: people, company, deal, knowledge.\n"
    "- people: mentions a specific person (name + context)\n"
    "- company: mentions a company without a specific contact\n"
    "- deal: mentions a sales opportunity, project, or client deal\n"
    "- knowledge: everything else (notes, articles, ideas, reflections)\n\n"
    "Return JSON with keys: type (one of the 4 categories), "
    "name, company, position, email, linkedin_url, title, stage, notes. "
    "Use empty string for fields that don't apply.\n"
    "NEVER use placeholder text like [PERSON_NAME], [COMPANY], <name>, etc. "
    "Always use literal values from the message.\n"
    "For 'URL : Name, Company, Position' format: company is the second comma-separated "
    "value; everything after the second comma is the position.\n"
    "Set linkedin_url from any linkedin.com/in/ URL in the message.\n\n"
    "Message: "
)

_TYPE_LABEL: dict[str, str] = {
    "people": "person",
    "company": "company",
    "deal": "deal",
}


def _build_infer_confirmation(inferred_type: str, extracted: dict[str, str]) -> str:
    label = _TYPE_LABEL[inferred_type]
    name = extracted.get("name") or extracted.get("title") or "this entry"
    company = extracted.get("company", "")
    position = extracted.get("position", "")
    details = name
    if company:
        details += f" @ {company}"
    if position:
        details += f" ({position})"
    return (
        f"Looks like a {label} — {details}.\n"
        f"Save to {label.capitalize()}s? Reply yes, /knowledge to file as a note, or cancel to discard."
    )


async def infer_and_confirm(
    text: str, settings: Settings
) -> tuple[str, str, dict[str, str]] | None:
    """Classify text via LLM. Returns (inferred_type, confirmation_text, extracted) or None for knowledge."""
    linkedin = parse_linkedin_deterministic(text)
    if linkedin:
        inferred_type, parsed = linkedin
        return inferred_type, _build_infer_confirmation(inferred_type, parsed), parsed

    if not settings.openrouter_api_key:
        return None
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
            resp = await client.post(
                f"{settings.openrouter_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openrouter_api_key.get_secret_value()}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.openrouter_model,
                    "messages": [{"role": "user", "content": _INFER_PROMPT + text}],
                    "response_format": {"type": "json_object"},
                },
            )
        resp.raise_for_status()
        data = json.loads(resp.json()["choices"][0]["message"]["content"])
        inferred_type = str(data.get("type", "knowledge")).lower()
        if inferred_type not in ("people", "company", "deal"):
            return None
        llm_fields = {k: str(v) for k, v in data.items() if v and k != "type"}
        fallback = None
        linkedin_fb = parse_linkedin_deterministic(text)
        if linkedin_fb and linkedin_fb[0] == inferred_type:
            fallback = linkedin_fb[1]
        extracted = sanitize_extracted(llm_fields, fallback=fallback)
        if inferred_type in ("people", "company") and not extracted.get("name"):
            return None
        confirmation = _build_infer_confirmation(inferred_type, extracted)
        return inferred_type, confirmation, extracted
    except Exception:  # noqa: BLE001
        logger.warning("telegram: LLM inference failed, falling back to knowledge pipeline")
        return None


def _resolve_confirmation(text: str) -> str:
    """Return 'yes', 'no', 'cancel', or 'unknown' based on user reply."""
    t = text.strip().lower()
    if t in ("yes", "oui", "y", "o"):
        return "yes"
    if t in ("no", "non", "n") or t.startswith("/knowledge"):
        return "no"
    if t in ("cancel", "skip", "abort", "rien", "nothing", "discard") or t.startswith(
        ("/cancel", "/skip")
    ):
        return "cancel"
    return "unknown"


_ERROR_MESSAGE_CAP = 120


def _format_handler_error(exc: Exception) -> str:
    """Sanitized, user-facing error text: always show the exception class name;
    never surface a raw notion_client SDK message (may contain page/database IDs
    or schema internals); cap any other exception's message length.

    Checked against NotionClientErrorBase — the true root of every notion_client
    exception (verified: RequestTimeoutError, InvalidPathParameterError,
    HTTPResponseError, UnknownHTTPResponseError, and APIResponseError all inherit
    from it) — not just APIResponseError, so a timeout or an internal-path error
    from the SDK gets the same generic treatment instead of leaking its message."""
    from notion_client.errors import NotionClientErrorBase

    cls_name = type(exc).__name__
    if isinstance(exc, NotionClientErrorBase):
        return f"⚠ Failed to save to Notion: {cls_name} — Notion API error, see server logs."
    detail = str(exc)
    if len(detail) > _ERROR_MESSAGE_CAP:
        detail = detail[:_ERROR_MESSAGE_CAP] + "..."
    return f"⚠ Failed to save to Notion: {cls_name} — {detail}"


class TelegramAdapter:
    """Telegram long-polling source adapter."""

    name = "telegram"

    def __init__(self, settings: Settings) -> None:
        if not settings.telegram_bot_token:
            raise ValueError("telegram_bot_token is required for the Telegram adapter")
        self._settings = settings

    def _build_app(self, handler: PipelineHandler) -> Application[Any, Any, Any, Any, Any, Any]:
        settings = self._settings
        state_store = ConvStateStore(settings.conv_state_db)

        async def _send_reply(msg: Any, text: str) -> None:
            await msg.reply_text(text)

        async def _dispatch_crm(msg: Any, cmd_name: str, text: str) -> None:
            """Start a new CRM command conversation."""
            cmd = COMMANDS[cmd_name]
            if not cmd.fields:
                # /knowledge or zero-field commands — run handler immediately
                result = await cmd.handler({}, settings)
                if result != "__KNOWLEDGE__":
                    await _send_reply(msg, result)
                    return
                # Fall through to knowledge pipeline
                incoming = await _to_incoming(settings, msg)
                await handler(incoming)
                await _send_reply(msg, f"Saved to Notion.\nTitle: {incoming.name[:120]}")
                return

            # Try LLM extraction from the command message body
            body = text[len(cmd_name) + 2 :].strip()  # strip "/command " prefix
            collected = await extract_fields_from_text(body, cmd, settings) if body else {}

            state = ConvState(
                chat_id=msg.chat_id,
                command=cmd_name,
                collected=collected,
            )
            prompt = get_next_prompt(cmd, state)
            if prompt is None:
                # All required fields extracted — run handler immediately
                try:
                    result = await cmd.handler(collected, _enrich_settings_from_cockpit(settings))
                    await _send_reply(msg, result)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("telegram: CRM handler failed for /{}", cmd_name)
                    await _send_reply(msg, _format_handler_error(exc))
                return

            state.pending_field = prompt
            state_store.set(state)
            await _send_reply(msg, prompt)

        async def _fill_field(msg: Any, state: ConvState, text: str) -> None:
            """Fill the pending field with the user's reply."""
            cmd = COMMANDS.get(state.command)
            if cmd is None:
                state_store.clear(msg.chat_id)
                return

            # Find which field we're filling (first required field not yet collected)
            pending_field_name = None
            for f in cmd.fields:
                if f.required and not state.collected.get(f.name):
                    pending_field_name = f.name
                    break
            if pending_field_name is None:
                state_store.clear(msg.chat_id)
                return

            state.collected[pending_field_name] = text
            prompt = get_next_prompt(cmd, state)
            if prompt is None:
                # All required fields filled — run handler
                state_store.clear(msg.chat_id)
                try:
                    result = await cmd.handler(
                        state.collected, _enrich_settings_from_cockpit(settings)
                    )
                    await _send_reply(msg, result)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("telegram: CRM handler failed for /{}", state.command)
                    await _send_reply(msg, _format_handler_error(exc))
            else:
                state.pending_field = prompt
                state_store.set(state)
                await _send_reply(msg, prompt)

        async def _handle(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
            msg = update.effective_message
            if msg is None:
                return
            text = (msg.text or "").strip()
            chat_id = msg.chat_id

            try:
                global _last_seen
                _last_seen = _dt.datetime.now(_dt.timezone.utc)
                logger.info(
                    "telegram: incoming chat_id={} from_user={}",
                    chat_id,
                    msg.from_user.id if msg.from_user else None,
                )

                # Priority 1: active conversation state → route by command type
                state = state_store.get(chat_id)
                if state is not None and state.command == "infer_confirm":
                    resolution = _resolve_confirmation(text)
                    if resolution == "yes":
                        state_store.clear(chat_id)
                        inferred_type = state.collected.get("inferred_type", "")
                        extracted = json.loads(state.collected.get("extracted", "{}"))
                        cmd = COMMANDS.get(inferred_type)
                        if cmd:
                            try:
                                result = await cmd.handler(
                                    extracted, _enrich_settings_from_cockpit(settings)
                                )
                                await _send_reply(msg, result)
                            except Exception:  # noqa: BLE001
                                logger.exception("telegram: inferred handler failed")
                                await _send_reply(msg, "Failed to save. See server logs.")
                        else:
                            await _send_reply(msg, "Unknown type — saved nothing.")
                    elif resolution == "cancel":
                        state_store.clear(chat_id)
                        await _send_reply(msg, "Discarded — nothing saved to Notion.")
                    elif resolution == "no":
                        state_store.clear(chat_id)
                        original_text = state.collected.get("original_text", text)
                        current = await _to_incoming(settings, msg)
                        _original_sent_at_str = state.collected.get("original_sent_at")
                        _original_sent_at = (
                            _dt.datetime.fromisoformat(_original_sent_at_str)
                            if _original_sent_at_str
                            else current.sent_at
                        )
                        original_incoming = IncomingMessage(
                            text=original_text,
                            caption=None,
                            sender=current.sender,
                            sent_at=_original_sent_at,
                            media_type=MediaType.TEXT,
                            media=None,
                            source_adapter="telegram",
                        )
                        page_id = await handler(original_incoming)
                        reply = f"Saved to Notion.\nTitle: {original_incoming.name[:120]}"
                        if page_id:
                            reply += f"\nPage id: {page_id}"
                        await _send_reply(msg, reply)
                    else:
                        # Unknown reply: retry once, then fall back to knowledge
                        retry = int(state.collected.get("retry", "0"))
                        if retry < 1:
                            state.collected["retry"] = str(retry + 1)
                            state_store.set(state)
                            await _send_reply(
                                msg,
                                state.collected.get(
                                    "confirmation", "Reply yes, /knowledge, or cancel."
                                ),
                            )
                        else:
                            state_store.clear(chat_id)
                            original_text = state.collected.get("original_text", text)
                            current = await _to_incoming(settings, msg)
                            _original_sent_at_str = state.collected.get("original_sent_at")
                            _original_sent_at = (
                                _dt.datetime.fromisoformat(_original_sent_at_str)
                                if _original_sent_at_str
                                else current.sent_at
                            )
                            original_incoming = IncomingMessage(
                                text=original_text,
                                caption=None,
                                sender=current.sender,
                                sent_at=_original_sent_at,
                                media_type=MediaType.TEXT,
                                media=None,
                                source_adapter="telegram",
                            )
                            await handler(original_incoming)
                            await _send_reply(
                                msg,
                                f"Saved to Notion as a note.\nTitle: {original_incoming.name[:120]}",
                            )
                    return

                if state is not None and state.command == "setup":
                    new_state, reply = await advance_setup(state, text, settings)
                    if new_state is None:
                        state_store.clear(chat_id)
                    else:
                        state_store.set(new_state)
                    await _send_reply(msg, reply)
                    return

                if state is not None:
                    await _fill_field(msg, state, text)
                    return

                # Priority 2: /command prefix → CRM dispatch
                if text.startswith("/"):
                    parts = text.lstrip("/").split()
                    if parts:
                        cmd_name = parts[0].lower()
                        if cmd_name == "setup":
                            new_state, reply = await start_setup(chat_id, settings)
                            state_store.set(new_state)
                            await _send_reply(msg, reply)
                            return

                        if cmd_name in READ_COMMANDS:
                            reply = await dispatch_read(cmd_name, settings)
                            await _send_reply(msg, reply)
                            return

                        if cmd_name in COMMANDS:
                            await _dispatch_crm(msg, cmd_name, text)
                            return

                # Priority 3: plain text / voice → check for read command intent first
                incoming = await _to_incoming(settings, msg)
                read_cmd = _detect_read_intent(incoming.text or "")
                if read_cmd is not None:
                    reply = await dispatch_read(read_cmd, settings)
                    await _send_reply(msg, reply)
                    return
                from notion_pilot.inbox.knowledge import _MULTI_LINK_THRESHOLD
                from notion_pilot.shared.models import all_urls as _telegram_all_urls

                # incoming.body (text-or-caption), matching what inbox/knowledge.py's
                # process_message actually routes on — using incoming.text alone would
                # miss photo messages, whose content lands in .caption, not .text.
                if len(_telegram_all_urls(incoming.body)) >= _MULTI_LINK_THRESHOLD:
                    await _send_reply(
                        msg, "Processing… (multiple links found, this may take a moment)"
                    )

                infer_result = await infer_and_confirm(incoming.text or "", settings)
                if infer_result is not None:
                    inferred_type, confirmation, extracted = infer_result
                    state_store.set(
                        ConvState(
                            chat_id=chat_id,
                            command="infer_confirm",
                            collected={
                                "inferred_type": inferred_type,
                                "original_text": incoming.text or "",
                                "extracted": json.dumps(extracted),
                                "confirmation": confirmation,
                                "retry": "0",
                                "original_sent_at": incoming.sent_at.isoformat(),
                            },
                        )
                    )
                    await _send_reply(msg, confirmation)
                else:
                    page_id = await handler(incoming)
                    reply = f"Saved to Notion.\nTitle: {incoming.name[:120]}"
                    if page_id:
                        reply += f"\nPage id: {page_id}"
                    await _send_reply(msg, reply)

            except Exception:  # noqa: BLE001
                logger.exception("telegram: failed to forward message")
                await _send_reply(msg, "Could not forward to Notion. See server logs.")

        async def _ping(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
            if update.message is not None:
                await update.message.reply_text("notion-pilot: ok")

        assert self._settings.telegram_bot_token is not None
        app = (
            ApplicationBuilder().token(self._settings.telegram_bot_token.get_secret_value()).build()
        )
        app.add_handler(CommandHandler("ping", _ping))
        app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.VOICE, _handle))
        return app

    async def run(self, handler: PipelineHandler) -> None:
        app = self._build_app(handler)
        async with app:
            await app.start()
            if app.updater is None:
                raise RuntimeError("Telegram Application updater is None — cannot start polling")
            await app.updater.start_polling(
                allowed_updates=Update.ALL_TYPES, drop_pending_updates=True
            )
            logger.info("telegram adapter: polling started")
            await asyncio.Event().wait()  # block until cancelled
            await app.updater.stop()
            await app.stop()
