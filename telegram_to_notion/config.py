"""Runtime configuration loaded from environment variables."""

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):  # pylint: disable=too-many-instance-attributes
    """Application secrets and ids from the environment (and optional ``.env`` file)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Notion (required) ────────────────────────────────────────────────────
    notion_token: SecretStr
    notion_database_id: str
    notion_title_property: str = Field(
        default="Name",
        description="Notion title column name (use Name if your DB uses the default title)",
    )

    # ── Telegram (optional) ──────────────────────────────────────────────────
    telegram_bot_token: SecretStr | None = Field(
        default=None,
        description="Telegram bot token from @BotFather; enables the Telegram adapter",
    )

    # ── OpenRouter (optional) ────────────────────────────────────────────────
    openrouter_api_key: SecretStr | None = Field(
        default=None,
        description="OpenRouter API key; when set, rows are enriched via chat completions",
    )
    openrouter_model: str = Field(
        default="google/gemini-2.5-flash-lite",
        description="OpenRouter model id",
    )
    openrouter_url: str = Field(
        default="https://openrouter.ai/api/v1",
        description="OpenRouter API URL",
    )
    openrouter_http_referer: str = Field(
        default="",
        description="HTTP-Referer header sent to OpenRouter for cost attribution",
    )
    openrouter_app_title: str = Field(
        default="telegram-to-notion",
        description="X-Title header sent to OpenRouter for dashboard display",
    )

    # ── Whisper (optional) ───────────────────────────────────────────────────
    whisper_language: str = Field(default="fr", description="faster-whisper language code")
    whisper_model_size: str = Field(default="base", description="faster-whisper model size")

    # ── IMAP / Email (optional) ──────────────────────────────────────────────
    imap_host: str | None = Field(default=None, description="IMAP server hostname")
    imap_port: int = Field(default=993, description="IMAP server port (SSL)")
    imap_user: str | None = Field(default=None, description="IMAP login username")
    imap_password: SecretStr | None = Field(default=None, description="IMAP login password")
    imap_inbox: str = Field(default="INBOX", description="Folder to poll for new mail")
    imap_archive: str = Field(default="Archive", description="Folder to move processed mail into")
    imap_poll_interval: int = Field(default=60, description="Seconds between IMAP poll cycles")
    imap_allowed_senders: str = Field(
        default="",
        description=(
            "Comma-separated sender suffixes to accept (e.g. @tldr.tech,@medium.com). "
            "Emails from other senders are marked seen but not archived or forwarded."
        ),
    )

    # ── Discord (optional) ───────────────────────────────────────────────────
    discord_bot_token: SecretStr | None = Field(
        default=None, description="Discord bot token; enables the Discord adapter"
    )
    discord_channel_id: str | None = Field(
        default=None, description="Discord channel ID to read from and write to"
    )


def load_settings() -> Settings:
    """Load settings, failing fast with a clear error on missing vars."""
    return Settings()
