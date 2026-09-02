"""Synthesis tests exercise the model seam without a provider call."""

from __future__ import annotations

import json

from voltdesk.contracts.audit import TokenUsage
from voltdesk.contracts.common import CallOutcome, Provider
from voltdesk.contracts.retrieval import (
    Chunk,
    Citation,
    CorpusSource,
    RetrievalAnswer,
    RetrievalQuery,
    RetrievedChunk,
)
from voltdesk.llm.base import CompletionRequest, CompletionResponse
from voltdesk.redaction.base import RedactionResult
from voltdesk.retrieval.synthesis import synthesise, verify_citations
from voltdesk.routing.router import StaticRouter


def _retrieved() -> list[RetrievedChunk]:
    chunk = Chunk(
        chunk_id="chunk-1",
        document_id="doc-1",
        source=CorpusSource.REBATE_PROGRAM_DOC,
        document_title="Battery program eligibility",
        text="Eligible battery systems must have a usable capacity of at least 5 kWh.",
        page=2,
        section_path=["Eligibility"],
        token_count=12,
    )
    return [RetrievedChunk(chunk=chunk, score=0.9, rank=1)]


def _citation(quote: str) -> Citation:
    return Citation(
        chunk_id="chunk-1",
        document_title="Battery program eligibility",
        source=CorpusSource.REBATE_PROGRAM_DOC,
        page=2,
        quote=quote,
        supports_claim="An eligible battery must have at least 5 kWh usable capacity.",
    )


class _LLM:
    def __init__(self, quote: str) -> None:
        self.quote = quote
        self.calls: list[CompletionRequest] = []
        self.redact: bool | None = None

    def complete(
        self, request: CompletionRequest, **kwargs: object
    ) -> tuple[CompletionResponse, RedactionResult]:
        self.calls.append(request)
        self.redact = bool(kwargs["redact"])
        payload = {
            "answer_text": "An eligible battery must have at least 5 kWh usable capacity.",
            "citations": [_citation(self.quote).model_dump(mode="json")],
        }
        response = CompletionResponse(
            provider=Provider.ANTHROPIC,
            model_id=request.model_id,
            text=json.dumps(payload),
            usage=TokenUsage(input_tokens=10, output_tokens=10),
            latency_ms=1,
            outcome=CallOutcome.SUCCESS,
        )
        return response, RedactionResult(
            text=request.user_content, entity_counts={}, reversal_map={}
        )


def test_verbatim_citation_is_accepted_after_model_synthesis() -> None:
    llm = _LLM("usable capacity of at least 5 kWh")
    answer = synthesise(
        RetrievalQuery(query_id="q1", question="What is the minimum capacity?"),
        _retrieved(),
        llm=llm,  # type: ignore[arg-type]
        router=StaticRouter(),
    )

    assert answer.abstained is False
    assert answer.citations[0].quote == "usable capacity of at least 5 kWh"
    assert llm.redact is False


def test_non_verbatim_paraphrased_citation_is_rejected() -> None:
    llm = _LLM("minimum usable capacity is five kilowatt-hours")
    answer = synthesise(
        RetrievalQuery(query_id="q1", question="What is the minimum capacity?"),
        _retrieved(),
        llm=llm,  # type: ignore[arg-type]
        router=StaticRouter(),
    )

    assert answer.abstained is True
    assert answer.citations == []


def test_verbatim_quote_must_name_the_chunk_it_came_from() -> None:
    citation = _citation("usable capacity of at least 5 kWh").model_copy(
        update={"chunk_id": "invented-chunk"}
    )
    answer = RetrievalAnswer(
        query_id="q1",
        abstained=False,
        answer_text="An eligible battery must have at least 5 kWh usable capacity.",
        citations=[citation],
        support_score=0.9,
        retrieved=_retrieved(),
    )

    assert verify_citations(answer, _retrieved()) is False
