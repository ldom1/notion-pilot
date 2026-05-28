"""Resolve Telegram ``file_id`` to bytes over HTTPS (Bot API file URL)."""

import httpx
from telegram import Bot

from notion_pilot.shared.models import MediaPayload


async def download_telegram_file(
    bot: Bot, file_id: str, filename: str, mime_type: str
) -> MediaPayload:
    """Download a file by ``file_id`` and return a ``MediaPayload`` for Notion upload."""
    tg_file = await bot.get_file(file_id)
    url = tg_file.file_path
    if url is None:
        raise RuntimeError(f"Telegram returned no file_path for file_id={file_id}")
    if not url.startswith("http"):
        url = f"https://api.telegram.org/file/bot{bot.token}/{url}"

    async with httpx.AsyncClient(timeout=60.0) as http:
        resp = await http.get(url)
        resp.raise_for_status()
        content = resp.content

    return MediaPayload(content=content, filename=filename, mime_type=mime_type)
