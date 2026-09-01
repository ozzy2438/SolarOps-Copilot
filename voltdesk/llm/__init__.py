"""LLM provider abstraction. Owned by Phase 1.

Call models through `LLMClient`. Adapters are not part of the public surface -
importing one directly bypasses redaction and the audit log.
"""

from voltdesk.llm.base import (
    CompletionRequest,
    CompletionResponse,
    LLMProvider,
    ProviderError,
)
from voltdesk.llm.client import LLMClient, prompt_version_hash
from voltdesk.llm.pricing import DEFAULT_MODEL_ID, ModelPrice, compute_cost_usd, get_price
from voltdesk.llm.registry import ProviderRegistry

__all__ = [
    "DEFAULT_MODEL_ID",
    "CompletionRequest",
    "CompletionResponse",
    "LLMClient",
    "LLMProvider",
    "ModelPrice",
    "ProviderError",
    "ProviderRegistry",
    "compute_cost_usd",
    "get_price",
    "prompt_version_hash",
]
