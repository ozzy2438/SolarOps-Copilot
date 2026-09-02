"""The Phase 4 router must cite measurements for every decision."""

from __future__ import annotations

import pytest

from voltdesk.contracts.common import Provider, TaskType
from voltdesk.contracts.routing import RoutingStrategy
from voltdesk.llm.base import LLMProvider
from voltdesk.llm.registry import ProviderRegistry
from voltdesk.routing.task_router import GPT_RUN_ID, HAIKU_RUN_ID, TaskRouter


class _Available(LLMProvider):
    def __init__(self, provider: Provider, available: bool = True) -> None:
        self.provider = provider
        self._available = available

    def is_available(self) -> bool:
        return self._available

    def complete(self, request: object) -> object:  # pragma: no cover - not called
        raise NotImplementedError


@pytest.mark.parametrize(
    ("task_type", "model_id"),
    [
        (TaskType.BILL_EXTRACTION, "gpt-4o-mini"),
        (TaskType.EMAIL_EXTRACTION, "gpt-4o-mini"),
        (TaskType.KNOWLEDGE_QA, "gpt-4o-mini"),
        (TaskType.SITE_ASSESSMENT_EXTRACTION, "claude-haiku-4-5"),
        (TaskType.SCHEMA_REPAIR, "gpt-4o-mini"),
    ],
)
def test_every_task_uses_the_measured_table(task_type: TaskType, model_id: str) -> None:
    decision = TaskRouter().route(task_type, estimated_input_tokens=42)

    assert decision.chosen.model_id == model_id
    assert decision.strategy == RoutingStrategy.TASK_TABLE
    assert decision.estimated_input_tokens == 42
    assert GPT_RUN_ID in decision.rationale
    assert HAIKU_RUN_ID in decision.rationale
    assert "static default" not in decision.rationale.casefold()


def test_fallback_uses_only_the_other_measured_model() -> None:
    registry = ProviderRegistry(
        {
            Provider.ANTHROPIC: _Available(Provider.ANTHROPIC),
            Provider.OPENAI: _Available(Provider.OPENAI),
        }
    )
    router = TaskRouter(registry)
    fallback = router.fallback(router.route(TaskType.BILL_EXTRACTION))

    assert fallback is not None
    assert fallback.chosen.model_id == "claude-haiku-4-5"
    assert fallback.strategy == RoutingStrategy.FALLBACK_AFTER_ERROR


def test_fallback_refuses_an_unusable_measured_provider() -> None:
    registry = ProviderRegistry(
        {
            Provider.ANTHROPIC: _Available(Provider.ANTHROPIC, available=False),
            Provider.OPENAI: _Available(Provider.OPENAI),
        }
    )
    router = TaskRouter(registry)
    assert router.fallback(router.route(TaskType.BILL_EXTRACTION)) is None
