"""Runtime configuration loaded from environment variables."""

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):  # pylint: disable=too-many-instance-attributes
    """Application secrets and ids from the environment (and optional ``.env`` file)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    # ── Notion (optional when using OAuth) ──────────────────────────────────
    notion_token: SecretStr | None = Field(
        default=None,
        description="Notion integration token. Not required when using the OAuth deploy wizard.",
    )
    notion_telegram_msg_database_id: str = Field(
        validation_alias=AliasChoices(
            "notion_telegram_msg_database_id",
            "NOTION_TELEGRAM_MSG_DATABASE_ID",
            "NOTION_DATABASE_ID",
        ),
    )
    notion_telegram_msg_database_title_property: str = Field(
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
        default="notion-pilot",
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
    imap_promotions_folder: str = Field(
        default="Promotions",
        description="IMAP folder for newsletter promotions (e.g. Medium, TLDR).",
    )
    imap_since_days: int = Field(
        default=7,
        description="Only process mail newer than this many days (0 = no limit).",
    )
    imap_archive: str = Field(default="Archive", description="Folder to move processed mail into")
    imap_poll_interval: int = Field(default=60, description="Seconds between IMAP poll cycles")
    imap_allowed_senders: str = Field(
        default="",
        description=(
            "Comma-separated sender suffixes to accept (e.g. @tldr.tech,@medium.com). "
            "Emails from other senders are marked seen but not archived or forwarded."
        ),
    )
    imap_auto_archive_senders: str = Field(
        default="members@medium.com,partnerprogram@medium.com",
        description=(
            "Comma-separated sender suffixes to archive without Notion "
            "(e.g. @e.vivinomail.com, members@medium.com). Checked before allowlist."
        ),
    )
    imap_people_senders: str = Field(
        default="",
        description=(
            "Comma-separated sender suffixes for personal contacts "
            "(e.g. @gmail.com,@icloud.com). Routed through the CRM People syncer."
        ),
    )

    # ── CRM / People import (optional) ──────────────────────────────────────
    notion_people_data_source_id: str | None = Field(
        default=None,
        description="Notion data source ID for the People database (inline DS API).",
    )
    notion_companies_data_source_id: str | None = Field(
        default=None,
        description="Notion data source ID for the Companies & departments database.",
    )
    brave_api_key: SecretStr | None = Field(
        default=None,
        description="Brave Search API key for email enrichment during people import.",
    )

    # ── CRM Enrichment (optional) ────────────────────────────────────────────
    apollo_api_key: SecretStr | None = Field(
        default=None,
        description="Apollo.io API key for person/company enrichment (Tier 1).",
    )

    # ── Deals DB (optional) ──────────────────────────────────────────────────
    notion_deals_database_id: str | None = Field(
        default=None,
        description="Notion database ID for the Deals database (standard databases API, not data_sources).",
    )

    # ── Knowledge Inbox DBs (optional) ──────────────────────────────────────
    notion_notions_database_id: str | None = Field(
        default=None,
        description="Notion database ID for the Notions database (personal reflections, methodologies).",
    )
    notion_ideas_database_id: str | None = Field(
        default=None,
        description="Notion database ID for the Ideas database.",
    )
    notion_tools_database_id: str | None = Field(
        default=None,
        description="Notion database ID for the Tools database.",
    )
    notion_data_tech_database_id: str | None = Field(
        default=None,
        description="Notion database ID for the Data & Technology database.",
    )

    # ── Web server (optional) ────────────────────────────────────────────────
    web_admin_username: str = Field(default="admin", description="Web UI admin username.")
    web_admin_password: SecretStr | None = Field(
        default=None,
        description="Web UI admin password. Required to start the web server.",
    )
    web_secret_key: SecretStr | None = Field(
        default=None,
        description="JWT signing secret for the web server.",
    )
    web_token_expire_minutes: int = Field(default=60, description="JWT token TTL in minutes.")

    # ── Notion OAuth (for deploy wizard) ────────────────────────────────────
    notion_oauth_client_id: str | None = Field(
        default=None,
        description="Notion public integration client_id for the deploy wizard OAuth flow.",
    )
    notion_oauth_client_secret: SecretStr | None = Field(
        default=None,
        description="Notion public integration client_secret for the deploy wizard OAuth flow.",
    )
    notion_oauth_redirect_uri: str = Field(
        default="http://localhost:8080/auth/notion/callback",
        description="OAuth redirect URI. Must match what is registered in the Notion integration.",
    )
    web_session_secret: SecretStr | None = Field(
        default=None,
        description="Secret key for signing session cookies (deploy wizard). Required when NOTION_OAUTH_CLIENT_ID is set.",
    )

    # ── CRM conversation state ───────────────────────────────────────────────
    conv_state_db: str = Field(
        default="data/conv_state.db",
        description="Path to SQLite file for Telegram CRM command conversation state.",
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
