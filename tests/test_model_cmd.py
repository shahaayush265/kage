"""Tests for model onboarding, dynamic discovery, and CLI commands."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from kage.agent.providers import PROVIDER_PRESETS, ModelProviderService
from kage.cli.main import app
from kage.core.config import ProviderConfig, get_settings

runner = CliRunner()


def test_provider_presets_definitions():
    assert "omniroute" in PROVIDER_PRESETS
    assert "anthropic" in PROVIDER_PRESETS
    assert "openai" in PROVIDER_PRESETS
    assert "ollama" in PROVIDER_PRESETS
    assert "deepseek" in PROVIDER_PRESETS

    omniroute = PROVIDER_PRESETS["omniroute"]
    assert "https://api.omniroute.ai" in omniroute["default_api_base"]
    assert len(omniroute["fallback_models"]) > 0


@pytest.mark.asyncio
async def test_fetch_available_models_mocked():
    mock_resp = {
        "data": [
            {"id": "claude-3-7-sonnet-20250219"},
            {"id": "gpt-4o"},
            {"id": "deepseek-chat"},
        ]
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_resp

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        models = await ModelProviderService.fetch_available_models(
            provider="omniroute",
            api_key="test-key",
            api_base="https://api.omniroute.ai/v1",
        )

        assert len(models) == 3
        assert "omniroute/claude-3-7-sonnet-20250219" in models
        assert "omniroute/gpt-4o" in models


def test_cli_model_onboard(tmp_path, monkeypatch):
    settings = get_settings()
    settings.kage_home = tmp_path / ".kage"
    settings.ensure_directories()
    monkeypatch.setenv("HOME", str(tmp_path))

    result = runner.invoke(
        app,
        [
            "model",
            "onboard",
            "--provider",
            "omniroute",
            "--api-key",
            "sk-test-key",
            "--model",
            "omniroute/claude-3-7-sonnet",
            "--no-test",
        ],
    )

    assert result.exit_code == 0
    assert "Successfully onboarded" in result.output

    loaded = get_settings()
    assert loaded.active_provider == "omniroute"
    assert loaded.default_model == "omniroute/claude-3-7-sonnet"
    prov = loaded.get_provider("omniroute")
    assert prov is not None
    assert prov.api_key == "sk-test-key"


def test_cli_model_list_and_set_default(tmp_path, monkeypatch):
    settings = get_settings()
    settings.kage_home = tmp_path / ".kage"
    settings.ensure_directories()
    monkeypatch.setenv("HOME", str(tmp_path))

    prov = ProviderConfig(
        name="omniroute",
        display_name="OmniRoute",
        api_key="sk-test",
        api_base="https://api.omniroute.ai/v1",
        models=["omniroute/claude-3-7-sonnet", "omniroute/gpt-4o"],
        default_model="omniroute/claude-3-7-sonnet",
    )
    settings.set_provider(prov, set_active=True)

    # List
    res_list = runner.invoke(app, ["model", "list"], env={"COLUMNS": "200"})
    assert res_list.exit_code == 0
    assert "OmniRoute" in res_list.output
    assert "omniroute/claude-3-7-sonnet" in res_list.output

    # Set default
    res_set = runner.invoke(app, ["model", "set-default", "omniroute/gpt-4o"])
    assert res_set.exit_code == 0
    assert "Default model set to: omniroute/gpt-4o" in res_set.output

    updated = get_settings()
    assert updated.default_model == "omniroute/gpt-4o"
