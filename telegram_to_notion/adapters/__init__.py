"""Source and sink adapter protocols."""

from collections.abc import Awaitable, Callable
from typing import Protocol, runtime_checkable

from telegram_to_notion.models import IncomingMessage

MessageHandler = Callable[[IncomingMessage], Awaitable[str | None]]


@runtime_checkable
class SourceAdapter(Protocol):
    """Polls or listens for messages and calls handler for each one."""

    name: str

    async def run(self, handler: MessageHandler) -> None:
        """Start the adapter loop. Runs until cancelled."""


@runtime_checkable
class SinkAdapter(Protocol):
    """Sends outbound notifications."""

    name: str

    async def send(self, text: str) -> None:
        """Post a text message via this sink."""
