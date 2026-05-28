"""Notion Pilot: self-hosted Notion automation — CRM and knowledge inbox, piloted by Telegram."""

import sys
from importlib.metadata import version

from loguru import logger

__version__ = version("notion-pilot")


logger.remove()
logger.add(
    sys.stderr,
    level="INFO",
    format=f"{{time:YYYY-MM-DD HH:mm:ss}} | v{__version__} | {{level:<8}} | {{name}}:{{function}} - {{message}}",
)
