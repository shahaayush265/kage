"""LiteLLM completion router and provider adapter."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import litellm

# Disable telemetry/noisy logs
litellm.telemetry = False
litellm.suppress_debug_info = True


class LLMRouter:
    """Dispatches completion requests to LiteLLM multi-provider backends."""

    def __init__(
        self,
        model: str = "anthropic/claude-3-7-sonnet-20250219",
        temperature: float = 0.2,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
    ):
        self.model = model
        self.temperature = temperature
        self.api_key = api_key
        self.api_base = api_base

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
