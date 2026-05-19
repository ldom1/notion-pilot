"""Entry point runner: loads active adapters and starts the pipeline."""

import asyncio

from loguru import logger

from telegram_to_notion.adapters import SourceAdapter
from telegram_to_notion.config import Settings, load_settings
from telegram_to_notion.pipelines import build_people_pipeline, build_pipeline


def _build_adapters(settings: Settings) -> list[SourceAdapter]:
    adapters: list[SourceAdapter] = []

    if settings.telegram_bot_token:
        from telegram_to_notion.adapters.telegram import TelegramAdapter

        adapters.append(TelegramAdapter(settings))

    if settings.imap_host and settings.imap_user and settings.imap_password:
        from telegram_to_notion.adapters.email import EmailAdapter

        adapters.append(EmailAdapter(settings))

    if settings.discord_bot_token and settings.discord_channel_id:
        from telegram_to_notion.adapters.discord import DiscordAdapter

        adapters.append(DiscordAdapter(settings))

    return adapters


async def _main(settings: Settings) -> None:
    from telegram_to_notion.adapters.email import EmailAdapter

    adapters = _build_adapters(settings)
    if not adapters:
        raise RuntimeError(
            "No adapters configured. Set at least one of: "
            "TELEGRAM_BOT_TOKEN, IMAP_HOST+IMAP_USER+IMAP_PASSWORD, DISCORD_BOT_TOKEN."
        )
    names = [a.name for a in adapters]
    logger.info("starting with adapters: {}", names)
    pipeline = build_pipeline(settings)
    people_pipeline = build_people_pipeline(settings)

    async def _run(adapter: SourceAdapter) -> None:
        if isinstance(adapter, EmailAdapter) and people_pipeline:
            await adapter.run(pipeline, people_handler=people_pipeline)
        else:
            await adapter.run(pipeline)

    await asyncio.gather(*[_run(a) for a in adapters])


def run() -> None:
    """Load settings and start all configured adapters."""
    settings = load_settings()
    asyncio.run(_main(settings))
