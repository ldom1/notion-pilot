"""Pipeline builders: one per destination schema."""

from notion_pilot.inbox.knowledge import build_knowledge_pipeline, process_message
from notion_pilot.inbox.people import build_people_pipeline

__all__ = ["build_knowledge_pipeline", "build_people_pipeline", "process_message"]
