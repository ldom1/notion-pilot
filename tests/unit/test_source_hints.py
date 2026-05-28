"""Unit tests for URL → platform label heuristics."""

import pytest

from notion_pilot.llm.source_hints import (
    format_source_hint_for_prompt,
    infer_source_label,
)


@pytest.mark.parametrize(
    "body, expected",
    [
        ("look at https://github.com/foo/bar", "GitHub"),
        ("https://youtu.be/dQw4w9WgXcQ", "YouTube"),
        ("via https://arxiv.org/abs/2401.00000", "arXiv"),
        ("no link here", None),
        ("", None),
    ],
)
def test_infer_source_label(body, expected):
    assert infer_source_label(body) == expected


def test_format_source_hint_includes_label_when_known():
    hint = format_source_hint_for_prompt("see https://github.com/x/y")
    assert "GitHub" in hint


def test_format_source_hint_empty_when_unknown():
    assert format_source_hint_for_prompt("no url") == ""
