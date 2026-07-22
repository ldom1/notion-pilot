"""Unit tests for InfisicalSettingsSource."""

from unittest.mock import MagicMock, patch

import pytest

from notion_pilot.shared.config import InfisicalSettingsSource, Settings


def _make_secret(key: str, value: str) -> MagicMock:
    s = MagicMock()
    s.secretKey = key
    s.secretValue = value
    return s


def _make_list_response(secrets: list[MagicMock]) -> MagicMock:
    resp = MagicMock()
    resp.secrets = secrets
    return resp


class TestInfisicalSettingsSourceNoOp:
    def test_returns_empty_dict_when_client_id_absent(self, monkeypatch):
        monkeypatch.delenv("INFISICAL_CLIENT_ID", raising=False)
        source = InfisicalSettingsSource(Settings)
        assert source() == {}

    def test_does_not_instantiate_sdk_when_client_id_absent(self, monkeypatch):
        monkeypatch.delenv("INFISICAL_CLIENT_ID", raising=False)
        with patch("notion_pilot.shared.config.InfisicalSDKClient") as mock_cls:
            source = InfisicalSettingsSource(Settings)
            result = source()
        mock_cls.assert_not_called()
        assert result == {}


class TestInfisicalSettingsSourceFetch:
    @pytest.fixture()
    def mock_client(self):
        return MagicMock()

    @pytest.fixture(autouse=True)
    def _set_env(self, monkeypatch):
        monkeypatch.setenv("INFISICAL_CLIENT_ID", "test-client-id")
        monkeypatch.setenv("INFISICAL_CLIENT_SECRET", "test-secret")
        monkeypatch.setenv("INFISICAL_PROJECT_ID", "test-project-id")

    def test_authenticates_with_universal_auth(self, mock_client):
        mock_client.secrets.list_secrets.return_value = []
        with patch("notion_pilot.shared.config.InfisicalSDKClient", return_value=mock_client):
            InfisicalSettingsSource(Settings)()
        mock_client.auth.universal_auth.login.assert_called_once_with(
            client_id="test-client-id",
            client_secret="test-secret",
        )

    def test_fetches_from_global_and_app_paths(self, mock_client):
        mock_client.secrets.list_secrets.return_value = []
        with patch("notion_pilot.shared.config.InfisicalSDKClient", return_value=mock_client):
            InfisicalSettingsSource(Settings)()
        assert mock_client.secrets.list_secrets.call_count == 2
        calls = mock_client.secrets.list_secrets.call_args_list
        paths = [c.kwargs["secret_path"] for c in calls]
        assert "/global" in paths
        assert "/" in paths

    def test_uses_prod_env_by_default(self, mock_client):
        mock_client.secrets.list_secrets.return_value = []
        with patch("notion_pilot.shared.config.InfisicalSDKClient", return_value=mock_client):
            InfisicalSettingsSource(Settings)()
        for c in mock_client.secrets.list_secrets.call_args_list:
            assert c.kwargs["environment_slug"] == "prod"

    def test_returns_secrets_as_lowercase_dict(self, mock_client):
        mock_client.secrets.list_secrets.side_effect = [
            _make_list_response([_make_secret("OPENROUTER_API_KEY", "or-key")]),
            _make_list_response([_make_secret("TELEGRAM_BOT_TOKEN", "bot-tok")]),
        ]
        with patch("notion_pilot.shared.config.InfisicalSDKClient", return_value=mock_client):
            result = InfisicalSettingsSource(Settings)()
        assert result["openrouter_api_key"] == "or-key"
        assert result["telegram_bot_token"] == "bot-tok"

    def test_app_path_overrides_global_on_key_conflict(self, mock_client):
        mock_client.secrets.list_secrets.side_effect = [
            _make_list_response([_make_secret("SHARED_KEY", "from-global")]),
            _make_list_response([_make_secret("SHARED_KEY", "from-app")]),
        ]
        with patch("notion_pilot.shared.config.InfisicalSDKClient", return_value=mock_client):
            result = InfisicalSettingsSource(Settings)()
        assert result["shared_key"] == "from-app"

    def test_raises_on_partial_credentials(self, monkeypatch):
        monkeypatch.delenv("INFISICAL_CLIENT_SECRET", raising=False)
        with pytest.raises(ValueError, match="INFISICAL_CLIENT_SECRET"):
            InfisicalSettingsSource(Settings)()

    def test_custom_env_slug_from_env_var(self, mock_client, monkeypatch):
        monkeypatch.setenv("INFISICAL_ENV", "dev")
        mock_client.secrets.list_secrets.return_value = []
        with patch("notion_pilot.shared.config.InfisicalSDKClient", return_value=mock_client):
            InfisicalSettingsSource(Settings)()
        for c in mock_client.secrets.list_secrets.call_args_list:
            assert c.kwargs["environment_slug"] == "dev"
