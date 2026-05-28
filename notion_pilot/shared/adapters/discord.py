"""Discord source adapter (inbound messages) + sink adapter (outbound notifications)."""

from datetime import timezone

import discord
from loguru import logger

from notion_pilot.shared.adapters import MessageHandler
from notion_pilot.shared.config import Settings
from notion_pilot.shared.models import IncomingMessage, MediaType


class DiscordAdapter:
    """Reads messages from a Discord channel and can send notifications back."""

    name = "discord"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        if not settings.discord_bot_token:
            raise ValueError("discord_bot_token is required for the Discord adapter")
        if not settings.discord_channel_id:
            raise ValueError("discord_channel_id is required for the Discord adapter")
        intents = discord.Intents.default()
        intents.message_content = True
        self._client: discord.Client = discord.Client(intents=intents)

    async def run(self, handler: MessageHandler) -> None:
        @self._client.event  # type: ignore[untyped-decorator]
        async def on_ready() -> None:
            logger.info("discord adapter: connected as {}", self._client.user)

        @self._client.event  # type: ignore[untyped-decorator]
        async def on_message(discord_msg: discord.Message) -> None:
            if discord_msg.author == self._client.user:
                return
            if str(discord_msg.channel.id) != self._settings.discord_channel_id:
                return
            sent_at = discord_msg.created_at
            if sent_at.tzinfo is None:
                sent_at = sent_at.replace(tzinfo=timezone.utc)
            incoming = IncomingMessage(
                text=discord_msg.content or None,
                caption=None,
                sender=str(discord_msg.author),
                sent_at=sent_at,
                media_type=MediaType.TEXT,
                media=None,
                source_adapter="discord",
            )
            await handler(incoming)

        assert self._settings.discord_bot_token is not None
        await self._client.start(self._settings.discord_bot_token.get_secret_value())

    # Sink is scaffolded — not yet wired into the pipeline. Will be connected
    # when notification support is added (post-v1.1 roadmap item).
    async def send(self, text: str) -> None:
        """Post a notification message to the configured Discord channel."""
        channel = self._client.get_channel(int(self._settings.discord_channel_id))  # type: ignore[arg-type]
        if isinstance(channel, discord.TextChannel):
            await channel.send(text)
        else:
            logger.warning(
                "discord sink: channel {} not found or not a text channel",
                self._settings.discord_channel_id,
            )
