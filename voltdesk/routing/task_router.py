"""Measurement-driven model routing from the Phase 4 benchmark."""

from __future__ import annotations

from voltdesk.contracts.common import Provider, TaskType
from voltdesk.contracts.routing import ModelChoice, RoutingDecision, RoutingStrategy
from voltdesk.llm.pricing import get_price
from voltdesk.llm.registry import ProviderRegistry
from voltdesk.routing.router import Router

HAIKU_RUN_ID = "eval-8325bd1c-879b-49a0-a858-b3d405377b8f"
GPT_RUN_ID = "eval-8d41a233-c32d-4318-892d-02c8c6f1ff00"
BENCHMARK_GIT_SHA = "f1f10ad03df810eaa2127167369044b5f943b59b"

TASK_MODELS: dict[TaskType, str] = {
    TaskType.BILL_EXTRACTION: "gpt-4o-mini",
    TaskType.EMAIL_EXTRACTION: "gpt-4o-mini",
    TaskType.KNOWLEDGE_QA: "gpt-4o-mini",
    TaskType.SITE_ASSESSMENT_EXTRACTION: "claude-haiku-4-5",
    TaskType.SCHEMA_REPAIR: "gpt-4o-mini",
}

_RATIONALES: dict[TaskType, str] = {
    TaskType.BILL_EXTRACTION: (
        "Phase 4 runs " + GPT_RUN_ID + " and " + HAIKU_RUN_ID
        + " both scored 1/50 exact; gpt-4o-mini had higher field recall "
        "(0.814 vs 0.785) at lower task cost ($0.106 vs $0.422)."
    ),
    TaskType.EMAIL_EXTRACTION: (
        "Phase 4 runs " + GPT_RUN_ID + " and " + HAIKU_RUN_ID
        + " both scored 0/30 exact; gpt-4o-mini had higher field recall "
        "(0.586 vs 0.334) at lower task cost ($0.036 vs $0.091)."
    ),
    TaskType.KNOWLEDGE_QA: (
        "Phase 4 runs " + GPT_RUN_ID + " and " + HAIKU_RUN_ID
        + " scored 16/40 and 18/40 exact with overlapping 95% intervals; "
        "gpt-4o-mini cost $0.005 vs $0.050 for the task."
    ),
    TaskType.SITE_ASSESSMENT_EXTRACTION: (
        "Phase 4 runs " + HAIKU_RUN_ID + " and " + GPT_RUN_ID
        + " scored 27/30 and 0/30 exact with non-overlapping 95% intervals; "
        "claude-haiku-4-5 is the measured quality choice."
    ),
    TaskType.SCHEMA_REPAIR: (
        "Phase 4 audit rows for " + GPT_RUN_ID + " and " + HAIKU_RUN_ID
        + " show successful single repairs on both providers; gpt-4o-mini is the "
        "lower-cost measured option."
    ),
}


def _choice(model_id: str) -> ModelChoice:
    price = get_price(model_id)
    return ModelChoice(provider=price.provider, model_id=price.model_id)


class TaskRouter(Router):
    """Route each task to the model selected by the two full Phase 4 runs."""

    def __init__(self, registry: ProviderRegistry | None = None) -> None:
        self._registry = registry or ProviderRegistry()

    def route(
        self, task_type: TaskType, *, estimated_input_tokens: int | None = None
    ) -> RoutingDecision:
        chosen = _choice(TASK_MODELS[task_type])
        alternate = _choice(
            "claude-haiku-4-5" if chosen.provider == Provider.OPENAI else "gpt-4o-mini"
        )
        return RoutingDecision(
            task_type=task_type,
            chosen=chosen,
            strategy=RoutingStrategy.TASK_TABLE,
            rationale=_RATIONALES[task_type],
            considered=[alternate],
            estimated_input_tokens=estimated_input_tokens,
        )

    def fallback(self, failed: RoutingDecision) -> RoutingDecision | None:
        candidate = _choice(
            "claude-haiku-4-5"
            if failed.chosen.provider == Provider.OPENAI
            else "gpt-4o-mini"
        )
        if not self._registry.is_usable(candidate.provider):
            return None
        return RoutingDecision(
            task_type=failed.task_type,
            chosen=candidate,
            strategy=RoutingStrategy.FALLBACK_AFTER_ERROR,
            rationale=(
                f"{failed.chosen.model_id} failed or its circuit opened; using "
                f"{candidate.model_id}, the other model measured by {GPT_RUN_ID} and "
                f"{HAIKU_RUN_ID}."
            ),
            considered=[failed.chosen],
            fallback_of=failed.chosen,
        )
