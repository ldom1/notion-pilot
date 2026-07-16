"""Notion API wrapper for database page creation and file uploads."""

from typing import Any, Protocol, runtime_checkable

from loguru import logger
from notion_client import AsyncClient
from notion_client.errors import APIResponseError


@runtime_checkable
class _HasNotionProperties(Protocol):
    @property
    def name(self) -> str: ...

    def to_notion_properties(self) -> dict[str, Any]: ...


class NotionDatabaseWriter:
    """Thin async wrapper around notion-client for create/update/archive page ops."""

    def __init__(self, client: AsyncClient, database_id: str):
        self.client = client
        self.database_id = database_id

    async def create_page(
        self, properties: _HasNotionProperties, children: list[dict[str, Any]] | None = None
    ) -> str:
        """Create a new page in the database with the given properties, and
        optionally an initial set of body blocks (``children``)."""
        logger.info(f"Creating page in database {self.database_id} for {properties.name}...")
        kwargs: dict[str, Any] = {
            "parent": {"type": "database_id", "database_id": self.database_id},
            "properties": properties.to_notion_properties(),
        }
        if children:
            kwargs["children"] = children
        try:
            page = await self.client.pages.create(**kwargs)
            return str(page["id"])
        except APIResponseError as e:
            logger.error(
                f"Failed to create page in database {self.database_id} for {properties.name}: {e}"
            )
            raise e

    async def update_page(self, page_id: str, properties: _HasNotionProperties) -> None:
        """Update an existing page in the database with the given content following the notion database structure."""
        logger.info(
            f"Updating page {page_id} in database {self.database_id} for {properties.name}..."
        )
        try:
            await self.client.pages.update(page_id, properties=properties.to_notion_properties())
        except APIResponseError as e:
            logger.error(
                f"Failed to update page {page_id} in database {self.database_id} for {properties.name}: {e}"
            )
            raise e

    async def delete_page(self, page_id: str) -> None:
        """Archive (soft-delete) a page; Notion has no hard delete via the API."""
        logger.info(f"Archiving page {page_id} in database {self.database_id}...")
        try:
            await self.client.pages.update(page_id, archived=True)
        except APIResponseError as e:
            logger.error(f"Failed to archive page {page_id}: {e}")
            raise e
