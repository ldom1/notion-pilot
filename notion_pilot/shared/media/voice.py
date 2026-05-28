"""Download a Telegram voice note (OGG/Opus) for transcription."""

from telegram import Message

from notion_pilot.shared.media.base import download_telegram_file
from notion_pilot.shared.models import MediaPayload


async def extract_voice(message: Message) -> MediaPayload:
    """Download ``message.voice`` as bytes (typically ``audio/ogg``)."""
    voice = message.voice
    if voice is None:
        raise ValueError("message has no voice")
    filename = f"{voice.file_unique_id}.ogg"
    mime = voice.mime_type or "audio/ogg"
    return await download_telegram_file(message.get_bot(), voice.file_id, filename, mime)
