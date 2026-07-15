"""Unit tests for utils/dedup.py — no network, no Notion."""

from notion_pilot.shared.utils.dedup import (
    DedupStatus,
    find_company_duplicates,
    find_match,
    find_people_duplicates,
    normalize,
    notion_page_url,
)


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


def test_candidate_record_accepts_optional_fields():
    # CandidateRecord TypedDict allows optional prospection fields
    c = {"name": "A", "company": "B", "page_id": "p", "seniority": "vp", "role_type": ["sales"]}
    result = find_match("A", "B", [c])
    assert result.status == DedupStatus.SKIP


def test_notion_page_url_strips_dashes():
    assert notion_page_url("abcd-1234-efgh") == "https://www.notion.so/abcd1234efgh"


def test_find_company_duplicates_above_threshold():
    # "EDF" vs "RTE" score far below threshold under plain token_sort_ratio;
    # "Acme Corp" vs "Acme Corp." (trailing period only) reliably scores >=85.
    id_to_name = {"id-a": "Acme Corp", "id-a2": "Acme Corp.", "id-rte": "RTE"}
    pairs = find_company_duplicates(id_to_name, threshold=85)
    assert len(pairs) == 1
    assert {pairs[0].name_a, pairs[0].name_b} == {"Acme Corp", "Acme Corp."}
    assert pairs[0].score >= 85


def test_find_company_duplicates_sorted_by_score_desc():
    id_to_name = {"a": "Acme Corp", "b": "Acme Corp.", "c": "Acme Corporation"}
    pairs = find_company_duplicates(id_to_name, threshold=50)
    scores = [p.score for p in pairs]
    assert scores == sorted(scores, reverse=True)


def test_find_people_duplicates_matches_on_name_and_company():
    existing = [
        {"page_id": "p1", "name": "Jean Dupont", "company": "EDF"},
        {"page_id": "p2", "name": "Jean Dupont", "company": "EDF"},
        {"page_id": "p3", "name": "Alice Martin", "company": "Engie"},
    ]
    pairs = find_people_duplicates(existing, threshold=85)
    assert len(pairs) == 1
    assert {pairs[0].id_a, pairs[0].id_b} == {"p1", "p2"}
    assert pairs[0].context_a == "EDF"


def test_find_match_exact_email_skips_even_with_different_name():
    candidates = [
        {"name": "A. Martin", "company": "RTE", "page_id": "p1", "email": "alice.martin@rte-france.com"}
    ]
    result = find_match(
        "MARTIN Alice", "Rte France", candidates, email="alice.martin@rte-france.com"
    )
    assert result.status == DedupStatus.SKIP
    assert result.matched_name == "A. Martin"


def test_find_match_exact_linkedin_skips_even_with_different_name():
    candidates = [
        {
            "name": "A. Martin",
            "company": "RTE",
            "page_id": "p1",
            "linkedin_url": "https://linkedin.com/in/amartin",
        }
    ]
    result = find_match(
        "MARTIN Alice",
        "Rte France",
        candidates,
        linkedin_url="https://linkedin.com/in/amartin",
    )
    assert result.status == DedupStatus.SKIP


def test_find_match_email_signal_ignored_when_no_candidate_has_it():
    candidates = [{"name": "Alice Martin", "company": "Engie", "page_id": "xyz"}]
    result = find_match("Bob Bernard", "OVHcloud", candidates, email="bob@ovhcloud.com")
    assert result.status == DedupStatus.NEW
