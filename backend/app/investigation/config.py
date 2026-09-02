"""Minimum LLM provider configuration for the AI investigation layer.

Secrets are never stored on the config object; only the name of the environment
variable holding the key is configured, and the value is read on demand.
"""

import os
from typing import Mapping, Optional

from pydantic import BaseModel, Field


class InvestigatorConfig(BaseModel):
    """Configuration for the AI investigator and its LLM provider."""

    model: str = "gpt-4o-mini"
    base_url: str = "https://api.openai.com/v1"
    api_key_env: str = "RECONEX_LLM_API_KEY"
    timeout_seconds: float = Field(default=30.0, gt=0)

    # Investigations at or below this confidence are escalated to human review.
    confidence_threshold: float = Field(default=0.75, ge=0.0, le=1.0)

    # Hard upper bound on the evidence handed to the AI, keeping context bounded.
    max_evidence_items: int = Field(default=40, gt=0)

    @classmethod
    def from_env(cls, env: Optional[Mapping[str, str]] = None) -> "InvestigatorConfig":
        """Build config from environment variables, falling back to defaults."""
        source = os.environ if env is None else env
        values: dict[str, object] = {}

        if source.get("RECONEX_LLM_MODEL"):
            values["model"] = source["RECONEX_LLM_MODEL"]
        if source.get("RECONEX_LLM_BASE_URL"):
            values["base_url"] = source["RECONEX_LLM_BASE_URL"]
        if source.get("RECONEX_LLM_API_KEY_ENV"):
            values["api_key_env"] = source["RECONEX_LLM_API_KEY_ENV"]
        if source.get("RECONEX_LLM_TIMEOUT_SECONDS"):
            values["timeout_seconds"] = float(source["RECONEX_LLM_TIMEOUT_SECONDS"])
        if source.get("RECONEX_AI_CONFIDENCE_THRESHOLD"):
            values["confidence_threshold"] = float(source["RECONEX_AI_CONFIDENCE_THRESHOLD"])

        return cls(**values)

    def api_key(self, env: Optional[Mapping[str, str]] = None) -> Optional[str]:
        """Read the API key from the environment. Never cached, never logged."""
        source = os.environ if env is None else env
        return source.get(self.api_key_env)
