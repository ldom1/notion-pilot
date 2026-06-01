"""Integration tests — hits the real Notion API. Requires a working repo-root .env.

Run with:
    uv run pytest tests/integration -v
"""

from datetime import datetime, timezone
from pathlib import Path

import pytest
from notion_client import AsyncClient

from notion_pilot.shared.config import load_settings
from notion_pilot.shared.llm.openrouter import interpret_message
from notion_pilot.shared.media.transcribe_voice import transcribe_file
from notion_pilot.shared.models import IncomingMessage, MediaType, NotionDatabaseProperties
from notion_pilot.shared.notion import NotionDatabaseWriter

pytestmark = pytest.mark.integration

AUDIO_FIXTURE = Path(__file__).parent.parent / "data" / "audio_example.ogg"
TRANSCRIPT_FIXTURE = Path(__file__).parent.parent / "data" / "audio_example_transcript.txt"


@pytest.fixture
def settings():
    return load_settings()


@pytest.fixture
async def writer(settings):
    client = AsyncClient(auth=settings.notion_token.get_secret_value())
    yield NotionDatabaseWriter(
        client=client, database_id=settings.notion_telegram_msg_database_id
    )
    await client.aclose()


def _incoming(text: str, media_type: MediaType = MediaType.TEXT) -> IncomingMessage:
    return IncomingMessage(
        text=text,
        caption=None,
        sender="pytest",
        sent_at=datetime.now(timezone.utc),
        media_type=media_type,
        media=None,
    )


@pytest.mark.asyncio
async def test_create_and_delete_text_page(writer, settings):
    """Text message → enriched properties → Notion page → archived in teardown."""
    incoming = _incoming("Integration test text: https://github.com/ldom1/telegram-to-notion")
    properties = await interpret_message(settings, incoming)
    page_id = await writer.create_page(properties)
    try:
        assert page_id
        assert len(page_id) >= 32  # UUID-ish
    finally:
        await writer.delete_page(page_id)


@pytest.mark.asyncio
async def test_create_and_delete_voice_page(writer, settings):
    """Transcribe the audio fixture, enrich, write to Notion, archive in teardown."""
    assert AUDIO_FIXTURE.is_file(), f"missing fixture: {AUDIO_FIXTURE}"
    transcript = transcribe_file(
        AUDIO_FIXTURE, settings.whisper_language, settings.whisper_model_size
    )
    assert transcript, "transcription produced no text"

    incoming = _incoming(transcript, media_type=MediaType.VOICE)
    properties = await interpret_message(settings, incoming)
    page_id = await writer.create_page(properties)
    try:
        assert page_id
    finally:
        await writer.delete_page(page_id)


@pytest.mark.asyncio
async def test_delete_page_archives_it(writer):
    """Direct create→delete path, bypassing the LLM."""
    props = NotionDatabaseProperties(
        name="pytest-delete-check",
        description="Created then archived by integration test.",
        label=["pytest"],
        entry_type="note",
    )
    page_id = await writer.create_page(props)
    await writer.delete_page(page_id)
    # Verify it really is archived from Notion's point of view.
    fetched = await writer.client.pages.retrieve(page_id)
    assert fetched["archived"] is True


@pytest.mark.asyncio
async def test_end_to_end_like_example(settings):
    """Mirror examples/example.py exactly: build, interpret, write, delete.

    Validates that the README's 3-step promise actually works end-to-end.
    """
    client = AsyncClient(auth=settings.notion_token.get_secret_value())
    writer = NotionDatabaseWriter(
        client=client, database_id=settings.notion_telegram_msg_database_id
    )
    try:
        # Step 1 — same message as examples/example.py
        incoming = IncomingMessage(
            text="J'ai trouvé un nouvel outil hyper intéressant: https://github.com/ldom1/telegram-to-notion",
            caption=None,
            sender="example.py",
            sent_at=datetime.now(timezone.utc),
            media_type=MediaType.TEXT,
            media=None,
        )
        # Step 2 — enrich
        properties = await interpret_message(settings, incoming)
        assert properties.url == "https://github.com/ldom1/telegram-to-notion"
        assert properties.source == "GitHub"
        # Step 3 — write then clean up
        page_id = await writer.create_page(properties)
        try:
            assert page_id
        finally:
            await writer.delete_page(page_id)
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_audio_fixture_from_data(writer, settings):
    """End-to-end: transcribe the audio fixture, persist transcript, enrich, upload, archive."""
    assert AUDIO_FIXTURE.is_file(), f"missing fixture: {AUDIO_FIXTURE}"
    assert AUDIO_FIXTURE.stat().st_size > 0, "audio fixture is empty"

    # 1. Transcribe the audio (local Whisper — no network).
    transcript = transcribe_file(
        AUDIO_FIXTURE, settings.whisper_language, settings.whisper_model_size
    )
    assert transcript and len(transcript.strip()) >= 3, "transcript too short"

    # 2. Persist the transcript next to the audio so the artifact is inspectable.
    TRANSCRIPT_FIXTURE.write_text(transcript, encoding="utf-8")
    assert TRANSCRIPT_FIXTURE.read_text(encoding="utf-8").strip() == transcript.strip()

    # 3. Enrich via OpenRouter (or heuristics if no key).
    incoming = _incoming(transcript, media_type=MediaType.VOICE)
    properties = await interpret_message(settings, incoming)
    assert properties.name, "name should be populated"
    assert properties.description, "description should be populated"
    assert properties.entry_type, "entry_type should be populated"

    # 4. Write to Notion and confirm; archive in teardown.
    page_id = await writer.create_page(properties)
    try:
        fetched = await writer.client.pages.retrieve(page_id)
        assert fetched["archived"] is False
        assert fetched["parent"]["database_id"].replace(
            "-", ""
        ) == settings.notion_telegram_msg_database_id.replace("-", "")
    finally:
        await writer.delete_page(page_id)
        archived = await writer.client.pages.retrieve(page_id)
        assert archived["archived"] is True
