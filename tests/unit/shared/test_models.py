"""Unit tests for shared/models.py URL extraction."""

from notion_pilot.shared.models import _first_url, all_urls


def test_all_urls_returns_every_match():
    text = (
        "Check https://github.com/example-org/repo-a and also "
        "https://github.com/example-org/repo-b for reference."
    )
    urls = all_urls(text)
    assert urls == [
        "https://github.com/example-org/repo-a",
        "https://github.com/example-org/repo-b",
    ]


def test_all_urls_empty_when_no_url():
    assert all_urls("no links here") == []


def test_first_url_still_returns_only_the_first():
    text = "https://a.example.com/one https://b.example.com/two"
    assert _first_url(text) == "https://a.example.com/one"


def test_all_urls_dedupes_exact_duplicates():
    # Regression guard: a link repeated to confirm it (the same style the /people
    # markdown-link paste format uses) must count once, not as two distinct links.
    text = (
        "[Jordan Belrose](https://www.linkedin.com/in/jordan-belrose-12345678/), "
        "Nordvale Energy :\nhttps://www.linkedin.com/in/jordan-belrose-12345678/"
    )
    assert all_urls(text) == ["https://www.linkedin.com/in/jordan-belrose-12345678/"]


def test_all_urls_preserves_first_seen_order_with_duplicates():
    text = (
        "https://a.example.com/one https://b.example.com/two "
        "https://a.example.com/one https://c.example.com/three"
    )
    assert all_urls(text) == [
        "https://a.example.com/one",
        "https://b.example.com/two",
        "https://c.example.com/three",
    ]
