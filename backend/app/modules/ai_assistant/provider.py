"""Provider-agnostic AI client supporting OpenAI-compatible endpoints and Groq.

Resolution order:
  1. Tenant override (per-tenant provider/base_url/model/key).
  2. Environment default (AI_PROVIDER, AI_BASE_URL, AI_MODEL, AI_API_KEY).
  3. Legacy Groq env vars (GROQ_API_KEY/GROQ_MODEL) for backward compatibility.

The public surface mirrors GroqClient so existing services need no change:
  is_configured, generate_chat_completion, generate_chat_completion_with_tools.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import Settings, get_settings
from app.modules.ai_assistant.client import GroqClient, get_groq_client
from app.modules.ai_assistant.exceptions import GroqAPIError, GroqNotConfiguredError

logger = logging.getLogger("propflow.ai_assistant.provider")


class OpenAICompatibleClient:
    """Minimal OpenAI-compatible chat-completion client (no vendor lock-in)."""

    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        timeout: float = 20.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.base_url)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _post(self, path: str, payload: dict) -> dict:
        import httpx

        if not self.is_configured:
            raise GroqNotConfiguredError("AI provider is not configured (missing API key).")
        try:
            response = httpx.post(
                f"{self.base_url}{path}",
                headers=self._headers(),
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            logger.warning("OpenAI-compatible provider request failed: %s", exc)
            raise GroqAPIError(str(exc)) from exc

    def generate_chat_completion(
        self,
        *,
        system_prompt: str,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
    ) -> str:
        data = self._post(
            "/chat/completions",
            {
                "model": self.model,
                "messages": [{"role": "system", "content": system_prompt}] + messages,
                "temperature": temperature,
            },
        )
        choices = data.get("choices") or []
        if not choices:
            raise GroqAPIError("No completion choices returned by provider.")
        content = (choices[0].get("message") or {}).get("content", "")
        if not content:
            raise GroqAPIError("Empty completion content returned by provider.")
        return content.strip()

    def generate_chat_completion_with_tools(
        self,
        *,
        system_prompt: str,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
        tool_choice: str | dict[str, Any] = "auto",
        temperature: float = 0.2,
    ) -> Any:
        # Return a lightweight object shaped like the Groq SDK response so the
        # existing tool-call loop (choices[0].message.tool_calls) works unchanged.
        from types import SimpleNamespace

        data = self._post(
            "/chat/completions",
            {
                "model": self.model,
                "messages": [{"role": "system", "content": system_prompt}] + messages,
                "temperature": temperature,
                "tools": tools,
                "tool_choice": tool_choice,
            },
        )
        choices = data.get("choices") or []
        if not choices:
            raise GroqAPIError("No completion choices returned by provider.")
        message = choices[0].get("message", {}) or {}
        raw_tool_calls = message.get("tool_calls") or []
        # Normalise each tool call to objects (id/type/function.name/arguments)
        # so the existing Groq-shaped tool loop can consume them unchanged.
        tool_calls = [
            SimpleNamespace(
                id=call.get("id"),
                type=call.get("type", "function"),
                function=SimpleNamespace(
                    name=(call.get("function") or {}).get("name"),
                    arguments=(call.get("function") or {}).get("arguments", "{}"),
                ),
            )
            for call in raw_tool_calls
        ]
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=message.get("content"),
                        tool_calls=tool_calls,
                    )
                )
            ]
        )


def resolve_ai_client(settings: Settings | None = None, *, tenant_config: dict | None = None):
    """Return the configured AI client: tenant override > generic env > Groq env.

    ``tenant_config`` is the decrypted per-tenant dict returned by
    ``tenant_ai.service.resolve_provider_config`` (provider/base_url/api_key/
    model). When present it takes precedence over all central settings; when
    ``None`` the existing environment-based behaviour is preserved unchanged.
    """

    config = settings or get_settings()

    if tenant_config is not None:
        provider = (tenant_config.get("provider") or "").strip().lower()
        api_key = tenant_config.get("api_key")
        model = tenant_config.get("model") or config.ai_model
        if provider == "groq":
            return GroqClient(
                api_key=api_key,
                model=model,
                timeout=config.groq_timeout_seconds,
                max_retries=config.groq_max_retries,
            )
        return OpenAICompatibleClient(
            api_key=api_key,
            base_url=tenant_config.get("base_url") or "https://api.openai.com/v1",
            model=model,
            timeout=config.groq_timeout_seconds,
        )

    # No tenant override: honour the generic env provider when configured.
    provider = (config.ai_provider or "").strip().lower()
    if provider and provider != "groq":
        return OpenAICompatibleClient(
            api_key=config.ai_api_key.get_secret_value() if config.ai_api_key else None,
            base_url=config.ai_base_url,
            model=config.ai_model,
            timeout=config.groq_timeout_seconds,
        )

    # Generic OpenAI-compatible endpoint takes precedence when AI_BASE_URL is set.
    if config.ai_base_url and config.ai_api_key:
        return OpenAICompatibleClient(
            api_key=config.ai_api_key.get_secret_value(),
            base_url=config.ai_base_url,
            model=config.ai_model,
            timeout=config.groq_timeout_seconds,
        )

    # Default: existing Groq integration.
    return get_groq_client()
