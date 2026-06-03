"""Contact pipeline → Notion people database."""

from loguru import logger
from notion_client import APIResponseError
from notion_client import AsyncClient as NotionClient

from notion_pilot.crm.syncer import NotionCompanySyncer, NotionPeopleSyncer, PersonRecord
from notion_pilot.shared.adapters import MessageHandler
from notion_pilot.shared.config import Settings
from notion_pilot.shared.models import IncomingMessage


def _person_from_incoming(incoming: IncomingMessage) -> PersonRecord:
    name = incoming.sender.split("@")[0].replace(".", " ").replace("_", " ").title()
    return PersonRecord(name=name or incoming.sender, company="", email=incoming.sender)


def build_people_pipeline(settings: Settings) -> MessageHandler | None:
    """Return a handler that upserts email senders through the central People syncer."""
    if not settings.notion_people_data_source_id or not settings.notion_companies_data_source_id:
        return None
    if settings.notion_token is None:
        raise ValueError("NOTION_TOKEN is required for People sync")

    client = NotionClient(auth=settings.notion_token.get_secret_value())
    company_syncer = NotionCompanySyncer(client, settings.notion_companies_data_source_id)
    people_syncer = NotionPeopleSyncer(
        client, settings.notion_people_data_source_id, company_syncer
    )
    snapshots_loaded = False

    async def _handler(incoming: IncomingMessage) -> str | None:
        nonlocal snapshots_loaded
        try:
            if not snapshots_loaded:
                await company_syncer.load_snapshot()
                await people_syncer.load_snapshot()
                snapshots_loaded = True
            result = await people_syncer.upsert(_person_from_incoming(incoming))
            logger.info("People sync result for {}: {}", incoming.sender, result.status)
            return result.page_id or None
        except APIResponseError as exc:
            logger.error("notion API error (people): {}", exc)
            return None
        except Exception:  # pylint: disable=broad-exception-caught  # noqa: BLE001
            logger.exception("failed to sync person to notion")
            return None

    return _handler
