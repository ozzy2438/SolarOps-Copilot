"""Provider lookup and circuit breaking.

Owned by: Phase 1. Fully implemented.

The circuit breaker lives here rather than in each adapter so that both providers
are cut out by the same rule and the router can ask one question - "is this provider
usable right now?" - without knowing how either one fails.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

from voltdesk.config import get_settings
from voltdesk.contracts.common import Provider
from voltdesk.llm.anthropic_provider import AnthropicProvider
from voltdesk.llm.base import LLMProvider
from voltdesk.llm.openai_provider import OpenAIProvider
from voltdesk.llm.pricing import get_price


@dataclass
class _BreakerState:
    consecutive_failures: int = 0
    opened_at: float | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)


class ProviderRegistry:
    """Holds one adapter per provider plus that provider's breaker state.

    Deliberately process-local. A shared breaker across API and worker processes would
    need Redis; that is more coupling than the failure mode justifies, and the
    consequence - each process discovers an outage independently - is acceptable.
    Recorded as ADR-0011.
    """

    def __init__(self, providers: dict[Provider, LLMProvider] | None = None) -> None:
        self._providers: dict[Provider, LLMProvider] = providers or {
            Provider.ANTHROPIC: AnthropicProvider(),
            Provider.OPENAI: OpenAIProvider(),
        }
        self._breakers: dict[Provider, _BreakerState] = {
            provider: _BreakerState() for provider in self._providers
        }
        self._settings = get_settings()

    def get(self, provider: Provider) -> LLMProvider:
        return self._providers[provider]

    def for_model(self, model_id: str) -> LLMProvider:
        """Resolve a model id to its provider adapter, refusing unknown ids."""
        return self._providers[get_price(model_id).provider]

    def is_usable(self, provider: Provider) -> bool:
        """Configured, and not currently cut out by the breaker."""
        return self._providers[provider].is_available() and not self.is_open(provider)

    def is_open(self, provider: Provider) -> bool:
        """True while the breaker is holding this provider out of service."""
        state = self._breakers[provider]
        with state.lock:
            if state.opened_at is None:
                return False
            if time.monotonic() - state.opened_at >= self._settings.circuit_breaker_reset_seconds:
                # Half-open: let the next call through and judge by its outcome.
                state.opened_at = None
                state.consecutive_failures = 0
                return False
            return True

    def record_success(self, provider: Provider) -> None:
        state = self._breakers[provider]
        with state.lock:
            state.consecutive_failures = 0
            state.opened_at = None

    def record_failure(self, provider: Provider) -> None:
        state = self._breakers[provider]
        with state.lock:
            state.consecutive_failures += 1
            if state.consecutive_failures >= self._settings.circuit_breaker_failure_threshold:
                state.opened_at = time.monotonic()

    def usable_providers(self) -> list[Provider]:
        return [p for p in self._providers if self.is_usable(p)]
