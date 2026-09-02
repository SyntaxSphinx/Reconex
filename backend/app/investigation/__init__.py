"""AI investigation layer for Reconex Phase 3B.

Investigates deterministic reconciliation exceptions. Never a financial source
of truth, and never reads ground truth data.
"""

from .config import InvestigatorConfig
from .context import (
    ALLOWED_CLASSIFICATIONS,
    ELIGIBLE_STATUSES,
    InvestigationContextBuilder,
    exception_id_for,
    is_eligible,
)
from .investigator import AIInvestigator
from .models import (
    AIInvestigation,
    EvidenceItem,
    EvidenceSource,
    GuardrailViolation,
    InvestigationContext,
    InvestigationOutcome,
    InvestigationRecord,
    InvestigationReport,
)
from .provider import (
    LLMProvider,
    LLMProviderError,
    LLMTimeoutError,
    OpenAICompatibleProvider,
)

__all__ = [
    "AIInvestigation",
    "AIInvestigator",
    "ALLOWED_CLASSIFICATIONS",
    "ELIGIBLE_STATUSES",
    "EvidenceItem",
    "EvidenceSource",
    "GuardrailViolation",
    "InvestigationContext",
    "InvestigationContextBuilder",
    "InvestigationOutcome",
    "InvestigationRecord",
    "InvestigationReport",
    "InvestigatorConfig",
    "LLMProvider",
    "LLMProviderError",
    "LLMTimeoutError",
    "OpenAICompatibleProvider",
    "exception_id_for",
    "is_eligible",
]
