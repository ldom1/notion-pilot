"""Telegram bot: long-polling listener that forwards messages to Notion."""

import asyncio
import tempfile
from datetime import timezone
from pathlib import Path
from typing import Any

from loguru import logger
from notion_client import APIResponseError, AsyncClient as NotionClient
from telegram import Message, Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from telegram_to_notion.config import Settings, load_settings
from telegram_to_notion.llm.openrouter import interpret_message
from telegram_to_notion.media import extract_photo, extract_voice
from telegram_to_notion.media.transcribe_voice import transcribe_file
from telegram_to_notion.models import IncomingMessage, MediaType
from telegram_to_notion.notion import NotionDatabaseWriter


async def handle_telegram_message(settings: Settings, msg: Message) -> IncomingMessage:
    """Map a Telegram Message to our internal IncomingMessage."""
    user = msg.from_user
    sender = (user.username or user.full_name or "unknown") if user else "unknown"
    sent_at = msg.date
    if sent_at.tzinfo is None:
        sent_at = sent_at.replace(tzinfo=timezone.utc)

    # Handle voice message
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


async def health_check(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Lightweight health check via /ping command."""
    if update.message is not None:
        await update.message.reply_text("telegram-to-notion: ok")


def build_application(settings: Settings) -> Application[Any, Any, Any, Any, Any, Any]:
    """Wire Telegram Application with Notion-backed message handlers."""
    notion_client = NotionClient(auth=settings.notion_token.get_secret_value())
    writer = NotionDatabaseWriter(client=notion_client, database_id=settings.notion_database_id)

    async def handle(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        msg = update.effective_message
        if msg is None:
            return
        try:
            logger.info(
                "incoming message chat_id={} from_user={}",
                msg.chat_id,
                msg.from_user.id if msg.from_user else None,
            )
            incoming = await handle_telegram_message(settings, msg)
            notion_properties = await interpret_message(settings, incoming)
            page_id = await writer.create_page(notion_properties)
            logger.info(f"Wrote notion page {page_id} from {incoming.sender}")
            await msg.reply_text(
                f"Saved to Notion.\nTitle: {incoming.name[:120]}\nPage id: {page_id}"
            )
        except APIResponseError as exc:
            logger.error("notion API error: {}", exc)
            detail = str(exc).replace("\n", " ").strip()[:450]
            await msg.reply_text(f"Notion API error:\n{detail}")
        except Exception:  # noqa: BLE001  # pylint: disable=broad-exception-caught
            logger.exception("failed to forward telegram message to notion")
            await msg.reply_text("Could not forward to Notion. See server logs.")

    app = ApplicationBuilder().token(settings.telegram_bot_token.get_secret_value()).build()
    app.add_handler(CommandHandler("ping", health_check))
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.VOICE, handle))
    return app


def run() -> None:
    """Load settings, configure logging, and start long polling."""
    settings = load_settings()
    app = build_application(settings)
    logger.info("starting telegram-to-notion polling")
    app.run_polling(allowed_updates=Update.ALL_TYPES)
