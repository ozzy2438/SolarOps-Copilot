"""Routing. Owned by Phase 1 (static default only)."""

from __future__ import annotations

from voltdesk.contracts.common import Provider, TaskType
from voltdesk.contracts.routing import RoutingStrategy
from voltdesk.llm.base import LLMProvider
from voltdesk.llm.registry import ProviderRegistry
from voltdesk.routing.router import StaticRouter


class _Available(LLMProvider):
    def __init__(self, provider: Provider, available: bool = True) -> None:
        self.provider = provider
        self._available = available

    def is_available(self) -> bool:
        return self._available

    def complete(self, request: object) -> object:  # pragma: no cover - not called
        raise NotImplementedError


def test_static_router_returns_the_default_and_says_it_is_a_default() -> None:
    decision = StaticRouter().route(TaskType.BILL_EXTRACTION)
    assert decision.strategy == RoutingStrategy.STATIC_DEFAULT
    assert decision.chosen.model_id == "claude-opus-5"
    # The rationale must not read like a measured finding.
    assert "not a measured choice" in decision.rationale


def test_fallback_crosses_to_the_other_provider_when_it_is_usable() -> None:
    registry = ProviderRegistry(
        {
            Provider.ANTHROPIC: _Available(Provider.ANTHROPIC),
            Provider.OPENAI: _Available(Provider.OPENAI),
        }
    )
    router = StaticRouter(registry)
    fallback = router.fallback(router.route(TaskType.BILL_EXTRACTION))
    assert fallback is not None
    assert fallback.chosen.provider == Provider.OPENAI
    assert fallback.strategy == RoutingStrategy.FALLBACK_AFTER_ERROR
    assert fallback.fallback_of is not None


def test_fallback_returns_none_rather_than_degrading_to_nothing() -> None:
    registry = ProviderRegistry(
        {
            Provider.ANTHROPIC: _Available(Provider.ANTHROPIC),
            Provider.OPENAI: _Available(Provider.OPENAI, available=False),
        }
    )
    router = StaticRouter(registry)
    assert router.fallback(router.route(TaskType.BILL_EXTRACTION)) is None


def test_circuit_breaker_opens_after_repeated_failures() -> None:
    registry = ProviderRegistry(
        {
            Provider.ANTHROPIC: _Available(Provider.ANTHROPIC),
            Provider.OPENAI: _Available(Provider.OPENAI),
        }
    )
    assert registry.is_usable(Provider.ANTHROPIC)
    for _ in range(10):
        registry.record_failure(Provider.ANTHROPIC)
    assert registry.is_open(Provider.ANTHROPIC)
    assert not registry.is_usable(Provider.ANTHROPIC)

    registry.record_success(Provider.ANTHROPIC)
    assert registry.is_usable(Provider.ANTHROPIC)
