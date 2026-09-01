"""Extraction tests. Owned by: Phase 2. Recorded fixtures, no network."""

from __future__ import annotations

from pathlib import Path

import pytest
from helpers_phase2 import DOCUMENT_TEXT, parsed_bill

from voltdesk.contracts.audit import TokenUsage
from voltdesk.contracts.common import CallOutcome, DocumentType, Provider
from voltdesk.contracts.routing import RoutingDecision
from voltdesk.extraction.extractor import ExtractionFailed, Extractor
from voltdesk.extraction.prompts import system_prompt_for
from voltdesk.llm.base import CompletionRequest, CompletionResponse, LLMProvider
from voltdesk.llm.client import LLMClient
from voltdesk.llm.registry import ProviderRegistry

_FIXTURES = Path(__file__).resolve().parent / "fixtures"


class RecordingAudit:
    def write(self, record: object) -> None:
        return None


class ScriptedProvider(LLMProvider):
    provider = Provider.ANTHROPIC

    def __init__(self, texts: list[str]) -> None:
        self.texts = texts
        self.calls = 0

    def is_available(self) -> bool:
        return True

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        text = self.texts[min(self.calls, len(self.texts) - 1)]
        self.calls += 1
        return CompletionResponse(
            provider=self.provider,
            model_id=request.model_id,
            text=text,
            usage=TokenUsage(input_tokens=10, output_tokens=10),
            latency_ms=1,
            outcome=CallOutcome.SUCCESS,
        )


def _extractor(texts: list[str]) -> tuple[Extractor, ScriptedProvider]:
    provider = ScriptedProvider(texts)
    registry = ProviderRegistry({Provider.ANTHROPIC: provider, Provider.OPENAI: provider})
    llm = LLMClient(registry=registry, audit=RecordingAudit())  # type: ignore[arg-type]
    return Extractor(llm=llm), provider


def _fixture(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


def test_system_prompt_is_stable_across_calls() -> None:
    first = system_prompt_for(DocumentType.ELECTRICITY_BILL)
    second = system_prompt_for(DocumentType.ELECTRICITY_BILL)
    assert first == second
    assert "value: null" in first
    assert "JSON Schema" in first


def test_extracts_a_recorded_valid_bill(routing_decision: RoutingDecision) -> None:
    _ = routing_decision
    extractor, provider = _extractor([_fixture("bill_valid.json")])
    result = extractor.extract(parsed_bill(DOCUMENT_TEXT))
    assert result.nmi.value == "6305888444"
    assert provider.calls == 1


def test_malformed_response_triggers_exactly_one_repair(
    routing_decision: RoutingDecision,
) -> None:
    _ = routing_decision
    extractor, provider = _extractor(
        [_fixture("bill_invalid_extra_field.json"), _fixture("bill_valid.json")]
    )
    result = extractor.extract(parsed_bill(DOCUMENT_TEXT))
    assert result.nmi.value == "6305888444"
    assert provider.calls == 2


def test_repair_still_invalid_raises(routing_decision: RoutingDecision) -> None:
    _ = routing_decision
    invalid = _fixture("bill_invalid_extra_field.json")
    extractor, provider = _extractor([invalid, invalid])
    with pytest.raises(ExtractionFailed):
        extractor.extract(parsed_bill(DOCUMENT_TEXT))
    assert provider.calls == 2
