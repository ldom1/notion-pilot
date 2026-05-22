"""Unit tests for crm/dedup.py — no network, no Notion."""
import pytest
from telegram_to_notion.crm.dedup import DedupStatus, MatchResult, find_match, normalize


def test_normalize_lowercases_and_strips():
    assert normalize("  Héllo  ") == "hello"


def test_normalize_unicode_nfkd():
    assert normalize("Élodie") == "elodie"


def test_find_match_exact_duplicate():
    candidates = [{"name": "Jean Dupont", "company": "EDF", "page_id": "abc"}]
    result = find_match("Jean Dupont", "EDF", candidates)
    assert result.status == DedupStatus.SKIP
    assert result.score >= 85
    assert result.matched_name == "Jean Dupont"


def test_find_match_name_reorder():
    candidates = [{"name": "Dupont Jean", "company": "EDF", "page_id": "abc"}]
    result = find_match("Jean Dupont", "EDF", candidates)
    assert result.status == DedupStatus.SKIP


def test_find_match_review_range():
    # same name, different company → score ~81 (review range)
    candidates = [{"name": "Jean Dupont", "company": "Engie", "page_id": "abc"}]
    result = find_match("Jean Dupont", "EDF", candidates)
    assert result.status == DedupStatus.REVIEW
    assert 75 <= result.score < 85


def test_find_match_new_person():
    candidates = [{"name": "Alice Martin", "company": "Engie", "page_id": "xyz"}]
    result = find_match("Bob Bernard", "OVHcloud", candidates)
    assert result.status == DedupStatus.NEW
    assert result.score < 75


def test_find_match_empty_candidates():
    result = find_match("Jean Dupont", "EDF", [])
    assert result.status == DedupStatus.NEW
    assert result.score == 0.0
