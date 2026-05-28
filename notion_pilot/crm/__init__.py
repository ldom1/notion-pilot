"""CRM utilities — people/company syncing, dedup, enrichment."""

from notion_pilot.shared.utils.dedup import CandidateRecord, DedupStatus, MatchResult, find_match
from notion_pilot.crm.syncer import (
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
