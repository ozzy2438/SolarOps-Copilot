"""Model-routing interface and the Phase 1 compatibility constructor.

Phase 4 replaced the static default with :class:`TaskRouter`.  The historical
``StaticRouter()`` import remains as a constructor so Phase 2/3 call sites can adopt
the measured policy without modifying those phase-owned modules.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from voltdesk.contracts.common import TaskType
from voltdesk.contracts.routing import RoutingDecision
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


def StaticRouter(registry: ProviderRegistry | None = None) -> Router:  # noqa: N802
    """Backward-compatible constructor for the measured Phase 4 router."""
    from voltdesk.routing.task_router import TaskRouter

    return TaskRouter(registry)
