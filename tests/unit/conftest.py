"""Unit test configuration — isolates tests from .env file."""

import pytest
from pydantic_settings import SettingsConfigDict

# Keys that must NOT bleed from the developer's .env into unit tests that
# construct Settings with no explicit values for these fields.
_ENV_KEYS_TO_CLEAR = [
    "INFISICAL_CLIENT_ID",
    "INFISICAL_CLIENT_SECRET",
    "OPENROUTER_API_KEY",
    "BRAVE_API_KEY",
    "APOLLO_API_KEY",
    "TELEGRAM_BOT_TOKEN",
    "DISCORD_BOT_TOKEN",
    "IMAP_HOST",
    "IMAP_USER",
    "IMAP_PASSWORD",
]


@pytest.fixture(autouse=True)
def _clear_optional_env(monkeypatch):
    """Remove optional secrets from env and disable .env file loading for unit tests."""
    import notion_pilot.shared.config as cfg_module

    # Prevent pydantic-settings from reading the .env file during unit tests.
    monkeypatch.setattr(
        cfg_module.Settings,
        "model_config",
        SettingsConfigDict(
            env_file=None,
            env_file_encoding="utf-8",
            case_sensitive=False,
            extra="ignore",
        ),
    )
    for key in _ENV_KEYS_TO_CLEAR:
        monkeypatch.delenv(key, raising=False)
