"""Unit tests for the OpenRouter system prompt."""

from datetime import datetime, timezone

from notion_pilot.shared.llm.prompt import build_openrouter_system_prompt
from notion_pilot.shared.models import IncomingMessage, MediaType


def _msg(text: str = "Hi", media_type: MediaType = MediaType.TEXT) -> IncomingMessage:
    return IncomingMessage(
        text=text,
        caption=None,
        sender="alice",
        sent_at=datetime(2026, 4, 18, 12, 0, tzinfo=timezone.utc),
        media_type=media_type,
        media=None,
        source_adapter="telegram",
    )


class TestPrompt:
    def test_uses_aliased_keys_not_python_field_names(self):
        prompt = build_openrouter_system_prompt(_msg())
        # JSON keys must match Notion column names (aliases), not Python identifiers.
        for alias in ("Name", "Label", "Type", "Link", "Source", "Description", "Interest"):
            assert f'"{alias}"' in prompt
        # Python-style field name with no alias must not leak into the spec.
        assert '"entry_type"' not in prompt

    def test_excludes_status_field(self):
        prompt = build_openrouter_system_prompt(_msg())
        assert '"Status"' not in prompt

    def test_label_must_be_array(self):
        prompt = build_openrouter_system_prompt(_msg())
        assert "Label" in prompt and "array" in prompt.lower()

    def test_source_hint_added_when_known_domain(self):
        prompt = build_openrouter_system_prompt(_msg(text="check https://github.com/foo/bar"))
        assert "GitHub" in prompt

    def test_no_source_hint_for_unknown_domain(self):
        prompt = build_openrouter_system_prompt(_msg(text="no url here"))
        assert "SOURCE HINT" not in prompt

    def test_includes_sender_and_media_type(self):
        prompt = build_openrouter_system_prompt(_msg(media_type=MediaType.VOICE))
        assert "alice" in prompt
        assert "voice" in prompt

    def test_body_is_truncated_to_12000(self):
        huge = "x" * 20000
        prompt = build_openrouter_system_prompt(_msg(text=huge))
        body = prompt.split("<message>")[1].split("</message>")[0].strip()
        assert len(body) == 12000
