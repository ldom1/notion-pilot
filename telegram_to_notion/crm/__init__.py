"""CRM utilities — people/company syncing, dedup, enrichment."""

from telegram_to_notion.utils.dedup import CandidateRecord, DedupStatus, MatchResult, find_match
from telegram_to_notion.crm.syncer import (
    NotionCompanySyncer,
    NotionPeopleSyncer,
    PersonRecord,
    UpsertResult,
)

__all__ = [
    "CandidateRecord",
    "DedupStatus",
    "MatchResult",
    "find_match",
    "NotionCompanySyncer",
    "NotionPeopleSyncer",
    "PersonRecord",
    "UpsertResult",
]
