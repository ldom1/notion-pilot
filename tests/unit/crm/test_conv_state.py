"""Unit tests for crm/conv_state.py — uses in-memory SQLite."""
import time

import pytest

from telegram_to_notion.crm.conv_state import ConvState, ConvStateStore


@pytest.fixture
def store(tmp_path):
    return ConvStateStore(str(tmp_path / "test.db"))


def test_get_returns_none_when_empty(store):
    assert store.get(42) is None


def test_set_and_get_roundtrip(store):
    state = ConvState(chat_id=1, command="lead", collected={"name": "Alice"}, pending_field="company")
    store.set(state)
    result = store.get(1)
    assert result is not None
    assert result.command == "lead"
    assert result.collected == {"name": "Alice"}
    assert result.pending_field == "company"


def test_clear_removes_entry(store):
    store.set(ConvState(chat_id=2, command="people", collected={}))
    store.clear(2)
    assert store.get(2) is None


def test_set_overwrites_existing(store):
    store.set(ConvState(chat_id=3, command="lead", collected={}))
    store.set(ConvState(chat_id=3, command="deal", collected={"title": "X"}))
    result = store.get(3)
    assert result is not None
    assert result.command == "deal"
    assert result.collected == {"title": "X"}


def test_get_returns_none_after_timeout(store):
    old_time = time.time() - ConvStateStore.TIMEOUT_SECONDS - 1
    state = ConvState(chat_id=5, command="lead", collected={}, created_at=old_time)
    store.set(state)
    assert store.get(5) is None


def test_clear_stale_removes_expired(store):
    old_time = time.time() - ConvStateStore.TIMEOUT_SECONDS - 1
    store.set(ConvState(chat_id=6, command="lead", collected={}, created_at=old_time))
    store.set(ConvState(chat_id=7, command="deal", collected={}))
    store.clear_stale()
    assert store.get(6) is None
    assert store.get(7) is not None
