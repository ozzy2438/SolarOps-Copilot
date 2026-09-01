"""Model routing.

Owned by: Phase 1 (interface plus a static default). Phase 4 implements the
measurement-driven policy.

Phase 1 deliberately ships the dumbest possible router. Choosing a cheaper model for
a task before measuring that task is a guess, and a guess recorded in the audit log
looks exactly like a measurement six months later. `StaticRouter` says, in its
rationale field, that it is a default and not a finding.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from voltdesk.contracts.common import Provider, TaskType
from voltdesk.contracts.routing import ModelChoice, RoutingDecision, RoutingStrategy
from voltdesk.llm.pricing import DEFAULT_MODEL_ID, get_price
from voltdesk.llm.registry import ProviderRegistry


class Router(ABC):
    """Chooses which model runs a task, and records why."""

    @abstractmethod
    def route(
        self, task_type: TaskType, *, estimated_input_tokens: int | None = None
    ) -> RoutingDecision:
        raise NotImplementedError

    @abstractmethod
    def fallback(self, failed: RoutingDecision) -> RoutingDecision | None:
        """A replacement decision after a failure, or None when there is nowhere to go.

        Returning None is a real answer: degrading to a provider we have not measured
        is worse than failing the request and saying so."""
        raise NotImplementedError


class StaticRouter(Router):
    """Always the default model, with a documented fallback to the other provider."""

    def __init__(self, registry: ProviderRegistry | None = None) -> None:
        self._registry = registry or ProviderRegistry()

    def route(
        self, task_type: TaskType, *, estimated_input_tokens: int | None = None
    ) -> RoutingDecision:
        price = get_price(DEFAULT_MODEL_ID)
        return RoutingDecision(
            task_type=task_type,
            chosen=ModelChoice(provider=price.provider, model_id=price.model_id),
            strategy=RoutingStrategy.STATIC_DEFAULT,
            rationale=(
                "Phase 1 static default. No benchmark has been run for this task type yet; "
                "this is not a measured choice. Phase 4 replaces it with a task table."
            ),
            estimated_input_tokens=estimated_input_tokens,
        )

    def fallback(self, failed: RoutingDecision) -> RoutingDecision | None:
        other = (
            Provider.OPENAI
            if failed.chosen.provider == Provider.ANTHROPIC
            else Provider.ANTHROPIC
        )
        if not self._registry.is_usable(other):
            return None

        candidate_id = _first_model_for(other)
        if candidate_id is None:
            return None

        return RoutingDecision(
            task_type=failed.task_type,
            chosen=ModelChoice(provider=other, model_id=candidate_id),
            strategy=RoutingStrategy.FALLBACK_AFTER_ERROR,
            rationale=(
                f"{failed.chosen.model_id} failed or its provider's circuit is open; "
                f"degrading to {candidate_id}. Quality on this task type is unmeasured."
            ),
            considered=[failed.chosen],
            fallback_of=failed.chosen,
        )


def _first_model_for(provider: Provider) -> str | None:
    from voltdesk.llm.pricing import ALL_MODELS

    for model_id, price in ALL_MODELS.items():
        if price.provider == provider:
            return model_id
    return None
