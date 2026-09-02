"""The audited call path. Owned by Phase 1.

The invariant under test: no model call escapes without an audit record, and nothing
leaves the process un-redacted.
"""

from __future__ import annotations

import pytest

from voltdesk.contracts.audit import AuditRecord, TokenUsage
from voltdesk.contracts.common import CallOutcome, Provider, TaskType
from voltdesk.contracts.routing import RoutingDecision
from voltdesk.llm.base import (
    CompletionRequest,
    CompletionResponse,
    LLMProvider,
    ProviderError,
)
from voltdesk.llm.client import LLMClient, prompt_version_hash
from voltdesk.llm.pricing import compute_cost_usd
from voltdesk.llm.registry import ProviderRegistry


class RecordingAudit:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    def write(self, record: AuditRecord) -> None:
        self.records.append(record)


class FakeProvider(LLMProvider):
    provider = Provider.ANTHROPIC

    def __init__(self, error: ProviderError | None = None) -> None:
        self.error = error
        self.seen: list[CompletionRequest] = []

    def is_available(self) -> bool:
        return True

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        self.seen.append(request)
        if self.error is not None:
            raise self.error
        return CompletionResponse(
            provider=self.provider,
            model_id=request.model_id,
            text="ok",
            usage=TokenUsage(
                input_tokens=100,
                output_tokens=50,
                cache_read_input_tokens=20,
                cache_creation_input_tokens=10,
            ),
            latency_ms=5,
            outcome=CallOutcome.SUCCESS,
        )


def _client(provider: FakeProvider, audit: RecordingAudit) -> LLMClient:
    registry = ProviderRegistry({Provider.ANTHROPIC: provider, Provider.OPENAI: provider})
    return LLMClient(registry=registry, audit=audit)  # type: ignore[arg-type]


def _request() -> CompletionRequest:
    return CompletionRequest(
        model_id="claude-opus-5",
        system="You extract bills.",
        user_content="Account 4029183746 for jane@example.com",
    )


def test_payload_is_redacted_before_it_reaches_the_provider(
    routing_decision: RoutingDecision,
) -> None:
    provider, audit = FakeProvider(), RecordingAudit()
    _client(provider, audit).complete(
        _request(),
        task_type=TaskType.BILL_EXTRACTION,
        routing=routing_decision,
        prompt_template="t",
    )
    sent = provider.seen[0].user_content
    assert "jane@example.com" not in sent
    assert "4029183746" not in sent


def test_success_writes_exactly_one_audit_record(routing_decision: RoutingDecision) -> None:
    provider, audit = FakeProvider(), RecordingAudit()
    _client(provider, audit).complete(
        _request(),
        task_type=TaskType.BILL_EXTRACTION,
        routing=routing_decision,
        prompt_template="t",
        document_id="doc-1",
    )
    assert len(audit.records) == 1
    record = audit.records[0]
    assert record.outcome == CallOutcome.SUCCESS
    assert record.usage.input_tokens == 100
    assert record.cost_usd == pytest.approx(
        compute_cost_usd(
            "claude-opus-5",
            100,
            50,
            cache_read_input_tokens=20,
            cache_creation_input_tokens=10,
        )
    )
    assert record.redaction_applied is True
    assert record.document_id == "doc-1"


def test_failure_still_writes_an_audit_record(routing_decision: RoutingDecision) -> None:
    """An unaudited failed call is exactly the one you need later."""
    provider = FakeProvider(
        error=ProviderError("boom", retryable=False, outcome=CallOutcome.PROVIDER_ERROR)
    )
    audit = RecordingAudit()
    with pytest.raises(ProviderError):
        _client(provider, audit).complete(
            _request(),
            task_type=TaskType.BILL_EXTRACTION,
            routing=routing_decision,
            prompt_template="t",
        )
    assert len(audit.records) == 1
    assert audit.records[0].outcome == CallOutcome.PROVIDER_ERROR
    assert audit.records[0].error_message is not None


def test_prompt_version_hash_tracks_the_template_not_the_document() -> None:
    a = prompt_version_hash("sys", "template {doc}")
    b = prompt_version_hash("sys", "template {doc}")
    c = prompt_version_hash("sys", "different template")
    assert a == b
    assert a != c
    assert len(a) == 64
