"""Unit tests for models.py — no network, no external dependencies."""

from datetime import datetime, timezone

from notion_pilot.models import (
    IncomingMessage,
    MediaType,
    NotionDatabaseProperties,
)


def _msg(
    text: str | None = None,
    caption: str | None = None,
    media_type: MediaType = MediaType.TEXT,
    source_adapter: str = "telegram",
) -> IncomingMessage:
    return IncomingMessage(
        text=text,
        caption=caption,
        sender="tester",
        sent_at=datetime(2026, 4, 18, 12, 0, tzinfo=timezone.utc),
        media_type=media_type,
        media=None,
        source_adapter=source_adapter,
    )


class TestIncomingMessage:
    def test_name_uses_first_line_of_text(self):
        msg = _msg(text="Line 1\nLine 2")
        assert msg.name == "Line 1"

    def test_name_falls_back_to_caption(self):
        msg = _msg(text=None, caption="Caption here")
        assert msg.name == "Caption here"

    def test_name_falls_back_to_media_type_when_empty(self):
        msg = _msg(text=None, caption=None, media_type=MediaType.VOICE)
        assert msg.name == "[voice]"

    def test_name_is_trimmed_to_200_chars(self):
        msg = _msg(text="x" * 300)
        assert len(msg.name) == 200

    def test_body_returns_text_then_caption_then_empty(self):
        assert _msg(text="hello").body == "hello"
        assert _msg(text=None, caption="cap").body == "cap"
        assert _msg().body == ""

    def test_source_adapter_stored(self):
        assert _msg(source_adapter="email").source_adapter == "email"

    def test_source_adapter_cannot_be_empty(self):
        import pytest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            IncomingMessage(
                text="hi",
                caption=None,
                sender="tester",
                sent_at=datetime(2026, 4, 18, 12, 0, tzinfo=timezone.utc),
                media_type=MediaType.TEXT,
                media=None,
                source_adapter="",
            )


class TestNotionDatabasePropertiesFromIncoming:
    def test_detects_url_in_body(self):
        msg = _msg(text="Check https://github.com/ldom1/telegram-to-notion")
        props = NotionDatabaseProperties.from_incoming(msg)
        assert props.url == "https://github.com/ldom1/telegram-to-notion"
        assert props.source == "GitHub"

    def test_no_url_gives_none(self):
        msg = _msg(text="No link here")
        props = NotionDatabaseProperties.from_incoming(msg)
        assert props.url is None
        assert props.source is None

    def test_label_reflects_source_adapter(self):
        assert NotionDatabaseProperties.from_incoming(_msg(source_adapter="email")).label == [
            "email"
        ]
        assert NotionDatabaseProperties.from_incoming(_msg(source_adapter="telegram")).label == [
            "telegram"
        ]

    def test_entry_type_mirrors_media_type(self):
        props = NotionDatabaseProperties.from_incoming(_msg(media_type=MediaType.PHOTO))
        assert props.entry_type == "photo"


class TestToNotionProperties:
    def test_required_keys_always_present(self):
        props = NotionDatabaseProperties(name="T", description="D", label=["a", "b"])
        payload = props.to_notion_properties()
        assert set(payload) >= {"Name", "Label", "Description"}

    def test_name_is_title_block(self):
        payload = NotionDatabaseProperties(name="Hello").to_notion_properties()
        assert payload["Name"] == {"title": [{"text": {"content": "Hello"}}]}

    def test_label_list_becomes_multi_select(self):
        payload = NotionDatabaseProperties(name="T", label=["a", "b"]).to_notion_properties()
        assert payload["Label"] == {"multi_select": [{"name": "a"}, {"name": "b"}]}

    def test_label_single_string_becomes_single_item_multi_select(self):
        payload = NotionDatabaseProperties(name="T", label="solo").to_notion_properties()
        assert payload["Label"] == {"multi_select": [{"name": "solo"}]}

    def test_empty_optional_fields_are_omitted(self):
        payload = NotionDatabaseProperties(name="T").to_notion_properties()
        for optional_key in ("Type", "Interest", "Link", "Source"):
            assert optional_key not in payload

    def test_populated_optionals_are_included(self):
        payload = NotionDatabaseProperties(
            name="T",
            entry_type="note",
            interest="High",
            url="https://ex.com",
            source="Ex",
        ).to_notion_properties()
        assert payload["Type"] == {"select": {"name": "note"}}
        assert payload["Interest"] == {"select": {"name": "High"}}
        assert payload["Link"] == {"url": "https://ex.com"}
        assert payload["Source"] == {"select": {"name": "Ex"}}

    def test_status_is_status_block(self):
        payload = NotionDatabaseProperties(name="T").to_notion_properties()
        assert payload["Status"] == {"status": {"name": "Not analysed"}}

    def test_description_capped_at_2000_chars(self):
        payload = NotionDatabaseProperties(name="T", description="x" * 5000).to_notion_properties()
        assert len(payload["Description"]["rich_text"][0]["text"]["content"]) == 2000
