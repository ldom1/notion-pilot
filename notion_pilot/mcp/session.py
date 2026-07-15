"""Session-scoped cache of the Notion CRM snapshot for the MCP server."""

import asyncio

from loguru import logger
from notion_client import AsyncClient

from notion_pilot.crm.syncer import NotionCompanySyncer, NotionPeopleSyncer
from notion_pilot.shared.config import Settings


class SyncerSession:
    """Loads the Notion People/Companies snapshot once and caches it for the
    life of the process.

    Call `start_prewarm()` at server startup (non-blocking) so the snapshot is
    likely already warm by the time the first real tool call arrives; call
    `await ensure_loaded()` at the top of any tool that needs the cache (it
    starts the load if `start_prewarm()` was never called, and is a no-op if
    already loaded)."""

    def __init__(self, settings: Settings) -> None:
        if not settings.notion_token:
            raise ValueError("NOTION_TOKEN is required for the MCP server")
        self._settings = settings
        client = AsyncClient(auth=settings.notion_token.get_secret_value())
        self.company_syncer = NotionCompanySyncer(
            client, settings.notion_companies_data_source_id or ""
        )
        self.people_syncer = NotionPeopleSyncer(
            client, settings.notion_people_data_source_id or "", self.company_syncer
        )
        self._load_task: asyncio.Task[None] | None = None

    def start_prewarm(self) -> None:
        """Kick off snapshot loading in the background. Non-blocking; safe to
        call more than once (subsequent calls are no-ops while a load is
        in-flight or already complete)."""
        if self._load_task is None:
            self._load_task = asyncio.create_task(self._load())
            self._load_task.add_done_callback(self._log_prewarm_failure)

    @staticmethod
    def _log_prewarm_failure(task: "asyncio.Task[None]") -> None:
        # A background pre-warm failure (e.g. bad credentials) must not crash
        # the server nor surface as an "exception was never retrieved"
        # warning when nothing else awaits this task. Foreground callers
        # (ensure_loaded/refresh) still see the exception via their own await.
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.warning("Background Notion snapshot pre-warm failed: {}", exc)

    async def _load(self) -> None:
        await self.company_syncer.load_snapshot()
        await self.people_syncer.load_snapshot()

    async def ensure_loaded(self) -> None:
        """Await the in-flight/prior load, starting one first if necessary."""
        self.start_prewarm()
        assert self._load_task is not None
        await self._load_task

    async def refresh(self) -> tuple[int, int]:
        """Force a fresh reload, discarding the cached snapshot. Returns
        (people_count, companies_count) after the reload completes."""
        self._load_task = asyncio.create_task(self._load())
        await self._load_task
        return len(self.people_syncer._existing), len(self.company_syncer._id_to_name)
