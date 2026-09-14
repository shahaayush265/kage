"""LiteLLM completion router and provider adapter."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import litellm

# Disable telemetry/noisy logs
litellm.telemetry = False
litellm.suppress_debug_info = True


def normalize_model_for_litellm(
    model: str,
    api_base: Optional[str] = None,
    provider: Optional[str] = None,
) -> Tuple[str, Optional[str]]:
    """Format model and api_base so LiteLLM correctly routes custom gateways like OmniRoute."""
    target_model = model.strip()
    target_base = api_base

    # 1. OmniRoute routing
    if target_model.startswith("omniroute/"):
        clean_model = target_model[len("omniroute/") :]
        target_model = f"openai/{clean_model}"
        if not target_base:
            target_base = "https://api.omniroute.ai/v1"
    elif provider == "omniroute" or (target_base and "omniroute.ai" in target_base):
        clean_model = target_model.removeprefix("omniroute/").removeprefix("openai/")
        target_model = f"openai/{clean_model}"
        if not target_base:
            target_base = "https://api.omniroute.ai/v1"

    # 2. Custom OpenAI-compatible proxy with api_base
    elif target_base and not target_model.startswith(
        ("openai/", "anthropic/", "ollama/", "openrouter/", "gemini/", "groq/")
    ):
        target_model = f"openai/{target_model}"

    # 3. Anthropic direct (add prefix if missing)
    elif provider == "anthropic" or (
        target_model.startswith("claude-") and not target_model.startswith("anthropic/")
    ):
        target_model = f"anthropic/{target_model}"

    return target_model, target_base


class LLMRouter:
    """Dispatches completion requests to LiteLLM multi-provider backends."""

    def __init__(
        self,
        model: str = "omniroute/claude-3-7-sonnet",
        temperature: float = 0.2,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
    ):
        normalized_model, normalized_base = normalize_model_for_litellm(model, api_base=api_base)
        self.raw_model = model
        self.model = normalized_model
        self.temperature = temperature
        self.api_key = api_key
        self.api_base = normalized_base

    async def complete_async(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Any:
        """Call LiteLLM acompletion with tools."""
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        if self.api_key:
            kwargs["api_key"] = self.api_key

        if self.api_base:
            kwargs["api_base"] = self.api_base

        response = await litellm.acompletion(**kwargs)
        return response
