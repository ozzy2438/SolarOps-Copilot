"""The provider abstraction: one `complete()` interface, two implementations.

Owned by: Phase 1. Fully implemented.

Everything above this layer is provider-agnostic. Everything below it is not. The
seam is deliberately narrow - one method, two dataclasses - because the routing and
evaluation phases depend on Anthropic and OpenAI calls being measurable in the same
units. Anything a provider offers that cannot be expressed here does not get used.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import Field

from voltdesk.contracts.audit import TokenUsage
from voltdesk.contracts.common import CallOutcome, Provider, StrictModel


class CompletionRequest(StrictModel):
    """A single, non-streaming completion request.

    Streaming is permanently out of scope (docs/SCOPE.md), so this interface has no
    streaming variant by design.
    """

    model_id: str
    system: str | None = Field(
        default=None, description="System prompt. Stable across calls so it stays cacheable."
    )
    user_content: str = Field(min_length=1, description="Already redacted by the caller.")
    max_tokens: int = Field(default=16000, ge=1)
    json_schema: dict[str, object] | None = Field(
        default=None,
        description=(
            "When set, the provider is asked to constrain its output to this schema. "
            "Adapters translate it into the provider's own structured-output mechanism."
        ),
    )
    stop_sequences: list[str] = Field(default_factory=list)


class CompletionResponse(StrictModel):
    """A completion, normalised across providers."""

    provider: Provider
    model_id: str
    text: str = Field(description="Concatenated text output. Empty on a refusal.")
    usage: TokenUsage
    latency_ms: int = Field(ge=0)
    outcome: CallOutcome
    stop_reason: str | None = None
    refusal_category: str | None = Field(
        default=None,
        description="Set when outcome is REFUSAL and the provider names a category.",
    )
    raw_response_id: str | None = Field(
        default=None, description="Provider-side id, for correlating with their logs."
    )


class ProviderError(RuntimeError):
    """A provider call failed in a way the caller may retry or route around."""

    def __init__(self, message: str, *, retryable: bool, outcome: CallOutcome) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.outcome = outcome


class LLMProvider(ABC):
    """One method. Implementations do not log, do not retry across providers, and do
    not decide policy - the caller (voltdesk.llm.client) owns all three."""

    provider: Provider

    @abstractmethod
    def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Make one call. Raise ProviderError on failure; never return a partial result."""
        raise NotImplementedError

    @abstractmethod
    def is_available(self) -> bool:
        """False when the provider has no credentials configured. Not a health check -
        this must not make a network call."""
        raise NotImplementedError
