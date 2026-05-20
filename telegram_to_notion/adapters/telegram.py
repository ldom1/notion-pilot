"""Telegram source adapter — long-polling via python-telegram-bot async API."""

import asyncio
import tempfile
from datetime import timezone
from pathlib import Path
from typing import Any

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

from telegram_to_notion.adapters import MessageHandler as PipelineHandler
from telegram_to_notion.config import Settings
from telegram_to_notion.media import extract_photo, extract_voice
from telegram_to_notion.media.transcribe_voice import transcribe_file
from telegram_to_notion.models import IncomingMessage, MediaType


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


class TelegramAdapter:
    """Telegram long-polling source adapter."""

    name = "telegram"

    def __init__(self, settings: Settings) -> None:
        if not settings.telegram_bot_token:
            raise ValueError("telegram_bot_token is required for the Telegram adapter")
        self._settings = settings

    def _build_app(self, handler: PipelineHandler) -> Application[Any, Any, Any, Any, Any, Any]:
        settings = self._settings

        async def _handle(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
            msg = update.effective_message
            if msg is None:
                return
            try:
                logger.info(
                    "telegram: incoming chat_id={} from_user={}",
                    msg.chat_id,
                    msg.from_user.id if msg.from_user else None,
                )
                incoming = await _to_incoming(settings, msg)
                page_id = await handler(incoming)
                reply = f"Saved to Notion.\nTitle: {incoming.name[:120]}"
                if page_id:
                    reply += f"\nPage id: {page_id}"
                await msg.reply_text(reply)
            except Exception:  # noqa: BLE001  # pylint: disable=broad-exception-caught
                logger.exception("telegram: failed to forward message")
                await msg.reply_text("Could not forward to Notion. See server logs.")

        async def _ping(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
            if update.message is not None:
                await update.message.reply_text("telegram-to-notion: ok")

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
            await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
            logger.info("telegram adapter: polling started")
            await asyncio.Event().wait()  # block until cancelled
            await app.updater.stop()
            await app.stop()
