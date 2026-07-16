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
