"""Live record execution for the Phase 4 evaluation runner."""

from __future__ import annotations

import re
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from voltdesk.audit.logger import AuditLogger
from voltdesk.contracts.audit import AuditRecord
from voltdesk.contracts.common import DocumentType, ExtractedField, TaskType
from voltdesk.contracts.evaluation import FieldScore, GoldenRecord, RecordResult
from voltdesk.contracts.retrieval import RetrievalQuery
from voltdesk.contracts.routing import ModelChoice, RoutingDecision, RoutingStrategy
from voltdesk.extraction.extractor import Extractor
from voltdesk.llm.client import LLMClient
from voltdesk.parsers import parser_for
from voltdesk.retrieval.abstention import answer_with_evidence
from voltdesk.retrieval.search import retrieve
from voltdesk.routing.router import Router

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PUNCTUATION = re.compile(r"[^\w\s]", re.UNICODE)


class _PinnedRouter(Router):
    def __init__(self, model: ModelChoice) -> None:
        self.model = model

    def route(
        self, task_type: TaskType, *, estimated_input_tokens: int | None = None
    ) -> RoutingDecision:
        return RoutingDecision(
            task_type=task_type,
            chosen=self.model,
            strategy=RoutingStrategy.FORCED_BY_CALLER,
            rationale=f"Phase 4 benchmark forced {self.model.model_id} for comparison.",
            estimated_input_tokens=estimated_input_tokens,
        )

    def fallback(self, failed: RoutingDecision) -> None:
        return None


class _CollectingAudit(AuditLogger):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[AuditRecord] = []

    def write(self, record: AuditRecord) -> None:
        self.records.append(record)
        super().write(record)


class LiveRecordExecutor:
    """Call the unchanged Phase 2/3 capabilities and score their outputs."""

    def __init__(self) -> None:
        self.audit = _CollectingAudit()

    def __call__(self, record: GoldenRecord, model: ModelChoice) -> RecordResult:
        started_calls = len(self.audit.records)
        router = _PinnedRouter(model)
        llm = LLMClient(audit=self.audit)
        try:
            if record.task_type == TaskType.KNOWLEDGE_QA:
                result = self._qa(record, model, llm, router)
            else:
                result = self._extraction(record, model, llm, router)
        except Exception as exc:  # noqa: BLE001 - one failed record must be resumable
            result = RecordResult(
                record_id=record.record_id,
                task_type=record.task_type,
                model=model,
                exact_match=False,
                latency_ms=0,
                cost_usd=0.0,
                error=f"{type(exc).__name__}: {exc}",
            )
        calls = self.audit.records[started_calls:]
        return result.model_copy(
            update={
                "latency_ms": sum(call.latency_ms for call in calls),
                "cost_usd": sum(call.cost_usd for call in calls),
            }
        )

    @staticmethod
    def _extraction(
        record: GoldenRecord,
        model: ModelChoice,
        llm: LLMClient,
        router: Router,
    ) -> RecordResult:
        document_type = {
            TaskType.BILL_EXTRACTION: DocumentType.ELECTRICITY_BILL,
            TaskType.SITE_ASSESSMENT_EXTRACTION: DocumentType.SITE_ASSESSMENT,
            TaskType.EMAIL_EXTRACTION: DocumentType.EMAIL_THREAD,
        }[record.task_type]
        path = _REPO_ROOT / record.input_path
        parsed = parser_for(document_type).parse(record.record_id, path.read_bytes(), path.name)
        actual = Extractor(llm=llm, router=router).extract(parsed)
        scores = [
            _field_score(actual, field_path, expected)
            for field_path, expected in record.expected.items()
        ]
        return RecordResult(
            record_id=record.record_id,
            task_type=record.task_type,
            model=model,
            exact_match=all(score.correct for score in scores),
            field_scores=scores,
            latency_ms=0,
            cost_usd=0.0,
        )

    @staticmethod
    def _qa(
        record: GoldenRecord,
        model: ModelChoice,
        llm: LLMClient,
        router: Router,
    ) -> RecordResult:
        question = (_REPO_ROOT / record.input_path).read_text(encoding="utf-8").strip()
        query = RetrievalQuery(query_id=record.record_id, question=question)
        answer = answer_with_evidence(query, retrieve(query), llm=llm, router=router)
        required = set(record.expected["required_citation_chunk_ids"])
        retrieved = {item.chunk.chunk_id: item.chunk.text for item in answer.retrieved}
        citations_correct = None
        if not answer.abstained:
            citations_correct = bool(answer.citations) and all(
                citation.chunk_id in required
                and citation.quote in retrieved.get(citation.chunk_id, "")
                for citation in answer.citations
            )
        contains = all(
            expected.casefold() in (answer.answer_text or "").casefold()
            for expected in record.expected["answer_contains"]
        )
        expected_abstention = bool(record.expected["should_abstain"])
        exact = answer.abstained == expected_abstention and (
            answer.abstained or (contains and citations_correct is True)
        )
        return RecordResult(
            record_id=record.record_id,
            task_type=record.task_type,
            model=model,
            exact_match=exact,
            abstained=answer.abstained,
            citations_correct=citations_correct,
            latency_ms=0,
            cost_usd=0.0,
        )


def _field_score(actual: Any, field_path: str, expected: Any) -> FieldScore:
    value, confidence = _resolve(actual, field_path.split("."))
    return FieldScore(
        field_path=field_path,
        expected=expected,
        actual=_json_value(value),
        correct=_values_match(field_path, value, expected),
        predicted_present=value is not None,
        expected_present=expected is not None,
        confidence=confidence,
    )


def _resolve(value: Any, parts: list[str]) -> tuple[Any, float | None]:
    confidence: float | None = None
    current = value
    for part in parts:
        if isinstance(current, ExtractedField):
            confidence = current.confidence
            current = current.value
        if current is None:
            return None, confidence
        current = current[int(part)] if part.isdigit() else getattr(current, part, None)
    if isinstance(current, ExtractedField):
        confidence = current.confidence
        current = current.value
    return current, confidence


def _json_value(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    return value


def _values_match(field_path: str, actual: Any, expected: Any) -> bool:
    actual = _json_value(actual)
    if actual is None or expected is None:
        return actual is expected
    if isinstance(actual, bool) or isinstance(expected, bool):
        return actual is expected
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        digits = 2 if "amount" in field_path else 0 if "kwh" in field_path else 6
        return round(float(actual), digits) == round(float(expected), digits)
    if isinstance(actual, str) and isinstance(expected, str):
        actual_normalised = " ".join(_PUNCTUATION.sub(" ", actual.casefold()).split())
        expected_normalised = " ".join(_PUNCTUATION.sub(" ", expected.casefold()).split())
        return actual_normalised == expected_normalised
    return bool(actual == expected)
