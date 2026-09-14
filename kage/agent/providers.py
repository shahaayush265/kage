"""Model provider discovery, API onboarding, and dynamic /models introspection."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

import httpx

PROVIDER_PRESETS: Dict[str, Dict[str, Any]] = {
    "omniroute": {
        "display_name": "OmniRoute (Universal Gateway)",
        "default_api_base": "https://api.omniroute.ai/v1",
        "env_key": "OMNIROUTE_API_KEY",
        "description": "Connect to all frontier models (Claude 3.7, GPT-4o, DeepSeek, Gemini) through a single endpoint.",
        "default_model": "omniroute/claude-3-7-sonnet",
        "fallback_models": [
            "omniroute/claude-3-7-sonnet-20250219",
            "omniroute/claude-3-5-sonnet-20241022",
            "omniroute/gpt-4o",
            "omniroute/gpt-4o-mini",
            "omniroute/deepseek-chat",
            "omniroute/deepseek-reasoner",
            "omniroute/gemini-2.0-flash",
        ],
    },
    "anthropic": {
        "display_name": "Anthropic",
        "default_api_base": "https://api.anthropic.com/v1",
        "env_key": "ANTHROPIC_API_KEY",
        "description": "Direct Anthropic API for Claude 3.7 Sonnet, Claude 3.5 Sonnet, and Claude 3.5 Haiku.",
        "default_model": "claude-3-7-sonnet-20250219",
        "fallback_models": [
            "claude-3-7-sonnet-20250219",
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
        ],
    },
    "openai": {
        "display_name": "OpenAI",
        "default_api_base": "https://api.openai.com/v1",
        "env_key": "OPENAI_API_KEY",
        "description": "Direct OpenAI API for GPT-4o, GPT-4o-mini, and o3-mini.",
        "default_model": "gpt-4o",
        "fallback_models": [
            "gpt-4o",
            "gpt-4o-mini",
            "o1",
            "o3-mini",
            "gpt-4-turbo",
        ],
    },
    "deepseek": {
        "display_name": "DeepSeek",
        "default_api_base": "https://api.deepseek.com/v1",
        "env_key": "DEEPSEEK_API_KEY",
        "description": "Direct DeepSeek API for DeepSeek-V3 and DeepSeek-R1.",
        "default_model": "deepseek/deepseek-chat",
        "fallback_models": [
            "deepseek/deepseek-chat",
            "deepseek/deepseek-reasoner",
        ],
    },
    "ollama": {
        "display_name": "Ollama (Local Models)",
        "default_api_base": "http://localhost:11434",
        "env_key": "",
        "description": "Local, private model inference running directly on host GPU/CPU.",
        "default_model": "ollama/qwen2.5-coder:latest",
        "fallback_models": [
            "ollama/qwen2.5-coder:latest",
            "ollama/llama3.2:latest",
            "ollama/llama3.2-vision:latest",
            "ollama/deepseek-r1:latest",
            "ollama/mistral:latest",
        ],
    },
    "openrouter": {
        "display_name": "OpenRouter",
        "default_api_base": "https://openrouter.ai/api/v1",
        "env_key": "OPENROUTER_API_KEY",
        "description": "OpenRouter unified model endpoint.",
        "default_model": "openrouter/anthropic/claude-3.7-sonnet",
        "fallback_models": [
            "openrouter/anthropic/claude-3.7-sonnet",
            "openrouter/openai/gpt-4o",
            "openrouter/deepseek/deepseek-chat",
            "openrouter/google/gemini-2.0-flash-001",
        ],
    },
    "custom": {
        "display_name": "Custom OpenAI-Compatible (vLLM / LocalAI / LiteLLM proxy)",
        "default_api_base": "http://localhost:8000/v1",
        "env_key": "CUSTOM_API_KEY",
        "description": "Any self-hosted or proxy OpenAI-compatible API endpoint.",
        "default_model": "custom-model",
        "fallback_models": [],
    },
}


class ModelProviderService:
    """Handles fetching available models and testing provider connections."""

    @classmethod
    async def fetch_available_models(
        cls,
        provider: str,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        timeout: float = 12.0,
    ) -> List[str]:
        """Query the provider's /models or /tags endpoint to discover active models."""
        preset = PROVIDER_PRESETS.get(provider.lower(), {})
        base_url = (api_base or preset.get("default_api_base", "")).rstrip("/")
        key = api_key or (os.getenv(preset.get("env_key", "")) if preset.get("env_key") else None)

        models: List[str] = []

        # 1. Ollama Native Endpoint
        if provider.lower() == "ollama":
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    # Try /api/tags
                    resp = await client.get(f"{base_url}/api/tags")
                    if resp.status_code == 200:
                        data = resp.json()
                        for m in data.get("models", []):
                            m_name = m.get("name", "")
                            if m_name:
                                models.append(f"ollama/{m_name}")
                        if models:
                            return sorted(models)
            except Exception:
                pass

        # 2. Anthropic Models Endpoint
        if provider.lower() == "anthropic" and key:
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    resp = await client.get(
                        "https://api.anthropic.com/v1/models",
                        headers={
                            "x-api-key": key,
                            "anthropic-version": "2023-06-01",
                        },
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        for m in data.get("data", []):
                            m_id = m.get("id", "")
                            if m_id:
                                models.append(m_id)
                        if models:
                            return sorted(models)
            except Exception:
                pass

        # 3. Standard OpenAI-Compatible /v1/models (OmniRoute, OpenAI, DeepSeek, OpenRouter, Custom)
        if base_url:
            headers = {}
            if key:
                headers["Authorization"] = f"Bearer {key}"

            models_url = f"{base_url}/models" if not base_url.endswith("/models") else base_url

            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    resp = await client.get(models_url, headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        items = data.get("data") or data.get("models") or []
                        prefix = f"{provider}/" if provider in ("omniroute", "deepseek") else ""

                        for item in items:
                            if isinstance(item, dict):
                                m_id = item.get("id") or item.get("name")
                            else:
                                m_id = str(item)
                            if m_id:
                                # Avoid duplicating prefix
                                if prefix and not m_id.startswith(prefix):
                                    models.append(f"{prefix}{m_id}")
                                else:
                                    models.append(m_id)

                        if models:
                            return sorted(list(set(models)))
            except Exception:
                pass

        # 4. Fallback to curated preset list if dynamic discovery is unavailable
        fallback = preset.get("fallback_models", [])
        return fallback

    @classmethod
    async def test_connection(
        cls,
        provider: str,
        model: str,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Test API connectivity by sending a lightweight completion request."""
        preset = PROVIDER_PRESETS.get(provider.lower(), {})
        base_url = api_base or preset.get("default_api_base")
        key = api_key or (os.getenv(preset.get("env_key", "")) if preset.get("env_key") else None)

        import litellm

        litellm.telemetry = False
        litellm.suppress_debug_info = True

        try:
            kwargs: Dict[str, Any] = {
                "model": model,
                "messages": [{"role": "user", "content": "Respond with 'ok'."}],
                "max_tokens": 10,
            }
            if key:
                kwargs["api_key"] = key
            if base_url:
                kwargs["api_base"] = base_url

            resp = await litellm.acompletion(**kwargs)
            choice = resp.choices[0]
            content = choice.message.content or "Connected"
            return True, f"Success: {content.strip()}"
        except Exception as e:
            return False, f"Connection failed: {e}"
