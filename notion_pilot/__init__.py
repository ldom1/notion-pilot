"""Telegram → Notion bridge: long-poll bot, forward messages to a Notion database."""

import sys
from importlib.metadata import version

from loguru import logger

__version__ = version("telegram-to-notion")


logger.remove()
logger.add(
    sys.stderr,
    level="INFO",
    format=f"{{time:YYYY-MM-DD HH:mm:ss}} | v{__version__} | {{level:<8}} | {{name}}:{{function}} - {{message}}",
)
