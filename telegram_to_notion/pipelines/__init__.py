"""Pipeline builders: one per destination schema."""

from telegram_to_notion.pipelines.knowledge import build_knowledge_pipeline, process_message
from telegram_to_notion.pipelines.people import build_people_pipeline

__all__ = ["build_knowledge_pipeline", "build_people_pipeline", "process_message"]
