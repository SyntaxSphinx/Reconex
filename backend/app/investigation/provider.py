"""LLM provider abstraction for the AI investigation layer.

The investigator depends only on the `LLMProvider` protocol, so tests supply a
mock and no test requires a real LLM or network access.
"""

import json
import urllib.error
import urllib.request
from typing import Protocol, runtime_checkable
from urllib.parse import urlparse

from .config import InvestigatorConfig
from .models import AIInvestigation


class LLMProviderError(Exception):
    """Any provider-side failure. Always handled as a safe fallback."""


class LLMTimeoutError(LLMProviderError):
    """The provider did not respond within the configured timeout."""


@runtime_checkable
class LLMProvider(Protocol):
    """Minimal provider interface: prompts in, raw text out."""

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Return the raw model response text, or raise `LLMProviderError`."""
        ...


def _openai_compatible_schema() -> dict:
    """JSON Schema for structured output. Pydantic remains the authority later."""
    schema = AIInvestigation.model_json_schema()
    properties = schema.get("properties") or {}
    schema["required"] = list(properties)
    schema["additionalProperties"] = False
    schema.pop("title", None)
    schema.pop("description", None)
    return schema


class OpenAICompatibleProvider:
    """Adapter for any OpenAI-compatible /chat/completions endpoint.

    Uses only the standard library so no dependency is added. The API key is
    read from the environment at call time and is never stored or logged.

    Official OpenAI endpoints receive the investigation JSON Schema. Other
    OpenAI-compatible hosts keep `json_object`, because structured-output
    support is not guaranteed there. Pydantic validation still runs either way.
    """

    def __init__(self, config: InvestigatorConfig):
        self.config = config

    def supports_json_schema(self) -> bool:
        host = (urlparse(self.config.base_url).hostname or "").lower()
        return host == "api.openai.com" or host.endswith(".openai.com")

    def response_format(self) -> dict:
        if self.supports_json_schema():
            return {
                "type": "json_schema",
                "json_schema": {
                    "name": "ai_investigation",
                    "strict": True,
                    "schema": _openai_compatible_schema(),
                },
            }
        return {"type": "json_object"}

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        api_key = self.config.api_key()
        if not api_key:
            raise LLMProviderError(
                f"No API key found in environment variable {self.config.api_key_env}"
            )

        payload = json.dumps(
            {
                "model": self.config.model,
                "temperature": 0,
                "response_format": self.response_format(),
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            }
        ).encode("utf-8")

        request = urllib.request.Request(
            url=f"{self.config.base_url.rstrip('/')}/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except TimeoutError as exc:
            raise LLMTimeoutError("LLM request timed out") from exc
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", exc)
            if isinstance(reason, TimeoutError):
                raise LLMTimeoutError("LLM request timed out") from exc
            raise LLMProviderError(f"LLM request failed: {reason}") from exc
        except (json.JSONDecodeError, OSError) as exc:
            raise LLMProviderError(f"LLM response could not be read: {exc}") from exc

        try:
            return body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError("LLM response had an unexpected shape") from exc
