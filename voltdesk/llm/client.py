"""The only supported way to call a model.

Owned by: Phase 1. Fully implemented.

Nothing in phases 2-4 may call a provider adapter directly. This class is where the
three non-negotiable things happen, in this order:

  1. redaction, before the payload leaves the process;
  2. the call, with retry and the circuit breaker;
  3. the audit record, written whether the call succeeded or failed.

An unaudited model call is a defect, not a shortcut. That is why the audit write is
in a `finally` and not on the happy path.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from datetime import UTC, datetime

from voltdesk.audit.logger import AuditLogger
from voltdesk.config import get_settings
from voltdesk.contracts.audit import AuditRecord, TokenUsage
from voltdesk.contracts.common import CallOutcome, TaskType
from voltdesk.contracts.routing import RoutingDecision
from voltdesk.llm.base import CompletionRequest, CompletionResponse, ProviderError
from voltdesk.llm.pricing import compute_cost_usd
from voltdesk.llm.registry import ProviderRegistry
from voltdesk.logging_setup import get_logger
from voltdesk.redaction import Redactor, default_redactor
from voltdesk.redaction.base import RedactionResult

logger = get_logger(__name__)


def prompt_version_hash(system: str | None, template: str) -> str:
    """SHA-256 of the prompt *template*, not the filled-in prompt.

    Hashing the filled prompt would give every call a unique hash and answer no
    question. Hashing the template answers "which prompt version produced this row",
    which is the question asked after a prompt edit changes the numbers.
    """
    payload = f"{system or ''}\x00{template}".encode()
    return hashlib.sha256(payload).hexdigest()


class LLMClient:
    """Redaction, retry, breaker and audit around one provider call."""

    def __init__(
        self,
        registry: ProviderRegistry | None = None,
        audit: AuditLogger | None = None,
        redactor: Redactor | None = None,
    ) -> None:
        self._registry = registry or ProviderRegistry()
        self._audit = audit or AuditLogger()
        self._redactor = redactor or default_redactor()
        self._settings = get_settings()

    def complete(
        self,
        request: CompletionRequest,
        *,
        task_type: TaskType,
        routing: RoutingDecision,
        prompt_template: str,
        document_id: str | None = None,
        query_id: str | None = None,
        redact: bool = True,
    ) -> tuple[CompletionResponse, RedactionResult]:
        """Make one audited call.

        Returns the response together with the RedactionResult, because the caller
        needs the reversal map to rehydrate placeholders before writing to the CRM.

        `redact=False` is only legitimate for Tier A corpus text, which contains no
        PII by construction. Passing it for a customer document is an incident.
        """
        call_id = str(uuid.uuid4())
        started_at = datetime.now(UTC)
        started = time.perf_counter()

        if redact:
            redaction = self._redactor.redact(request.user_content)
        else:
            redaction = RedactionResult(
                text=request.user_content, entity_counts={}, reversal_map={}
            )
        outbound = request.model_copy(update={"user_content": redaction.text})

        provider_adapter = self._registry.for_model(request.model_id)
        provider = provider_adapter.provider

        response: CompletionResponse | None = None
        outcome = CallOutcome.PROVIDER_ERROR
        error_message: str | None = None
        retry_count = 0
        usage = TokenUsage(input_tokens=0, output_tokens=0)

        try:
            if self._registry.is_open(provider):
                outcome = CallOutcome.CIRCUIT_OPEN
                raise ProviderError(
                    f"circuit breaker open for {provider}",
                    retryable=False,
                    outcome=CallOutcome.CIRCUIT_OPEN,
                )

            last_error: ProviderError | None = None
            for attempt in range(self._settings.llm_max_retries + 1):
                retry_count = attempt
                try:
                    response = provider_adapter.complete(outbound)
                    break
                except ProviderError as exc:
                    last_error = exc
                    self._registry.record_failure(provider)
                    if not exc.retryable or attempt == self._settings.llm_max_retries:
                        raise
                    # Exponential backoff. Bounded by llm_max_retries, so this cannot
                    # become an unbounded stall inside a request handler.
                    time.sleep(2**attempt)
            if response is None:  # pragma: no cover - defensive
                raise last_error or ProviderError(
                    "no response and no error", retryable=False, outcome=CallOutcome.PROVIDER_ERROR
                )

            usage = response.usage
            outcome = response.outcome
            if outcome == CallOutcome.SUCCESS:
                self._registry.record_success(provider)
            return response, redaction

        except ProviderError as exc:
            outcome = exc.outcome
            error_message = str(exc)
            raise
        finally:
            latency_ms = int((time.perf_counter() - started) * 1000)
            record = AuditRecord(
                call_id=call_id,
                occurred_at=started_at,
                task_type=task_type,
                routing=routing,
                prompt_version_hash=prompt_version_hash(request.system, prompt_template),
                usage=usage,
                cost_usd=compute_cost_usd(
                    request.model_id,
                    usage.input_tokens,
                    usage.output_tokens,
                    cache_read_input_tokens=usage.cache_read_input_tokens,
                    cache_creation_input_tokens=usage.cache_creation_input_tokens,
                ),
                latency_ms=latency_ms,
                outcome=outcome,
                error_message=error_message,
                retry_count=retry_count,
                redaction_applied=redaction.applied,
                redacted_entity_counts=redaction.entity_counts,
                document_id=document_id,
                query_id=query_id,
            )
            self._audit.write(record)
            logger.info(
                "llm_call",
                call_id=call_id,
                model=request.model_id,
                task_type=str(task_type),
                outcome=str(outcome),
                latency_ms=latency_ms,
                cost_usd=record.cost_usd,
            )
