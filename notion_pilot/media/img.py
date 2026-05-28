"""Extract the largest ``PhotoSize`` from a Telegram message and download it."""

from telegram import Message

from notion_pilot.media.base import download_telegram_file
from notion_pilot.models import MediaPayload


async def extract_photo(message: Message) -> MediaPayload:
    """Use the last (largest) photo entry, JPEG filename, ``image/jpeg`` MIME."""
    if not message.photo:
        raise ValueError("message has no photo")
    largest = message.photo[-1]
    filename = f"{largest.file_unique_id}.jpg"
    return await download_telegram_file(message.get_bot(), largest.file_id, filename, "image/jpeg")
