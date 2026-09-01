"""Cheap abstention tests, including proof that no model audit row is created."""

from __future__ import annotations

from voltdesk.contracts.retrieval import (
    AbstentionReason,
    Chunk,
    CorpusSource,
    RetrievalQuery,
    RetrievedChunk,
)
from voltdesk.retrieval.abstention import (
    abstention_reason,
    answer_with_evidence,
    support_score,
)


def _retrieved(text: str, score: float = 0.9, chunk_id: str = "chunk-1") -> RetrievedChunk:
    return RetrievedChunk(
        chunk=Chunk(
            chunk_id=chunk_id,
            document_id=f"doc-{chunk_id}",
            source=CorpusSource.REBATE_PROGRAM_DOC,
            document_title="Authoritative program guidance",
            text=text,
            page=1,
            section_path=["Eligibility"],
            token_count=len(text.split()),
        ),
        score=score,
        rank=1,
    )


class _NeverCalledLLM:
    def __init__(self) -> None:
        self.calls = 0
        self.audit_records: list[object] = []

    def complete(self, *args: object, **kwargs: object) -> object:
        self.calls += 1
        self.audit_records.append({"unexpected": True})
        raise AssertionError("the model must not be called for a cheap abstention")


def test_out_of_corpus_question_abstains_without_model_call_or_audit_record() -> None:
    llm = _NeverCalledLLM()
    query = RetrievalQuery(query_id="q-out", question="Who won the football final?")

    answer = answer_with_evidence(query, [], threshold=0.55, llm=llm)

    assert answer.abstained is True
    assert answer.abstention_reason == AbstentionReason.OUT_OF_SCOPE
    assert llm.calls == 0
    assert llm.audit_records == []


def test_support_score_rewards_matching_hybrid_evidence_and_stays_bounded() -> None:
    query = RetrievalQuery(query_id="q1", question="What solar battery capacity is eligible?")
    relevant = [_retrieved("An eligible solar battery must have at least 5 kWh capacity.")]
    unrelated = [_retrieved("The document describes an inverter warranty.", score=0.5)]

    assert 0.55 < support_score(query, relevant) <= 1.0
    assert 0.0 <= support_score(query, unrelated) < 0.55


def test_empty_domain_query_has_no_relevant_evidence() -> None:
    query = RetrievalQuery(query_id="q1", question="What solar rebate applies?")

    assert support_score(query, []) == 0.0
    assert (
        abstention_reason(query, [], 0.0) == AbstentionReason.NO_RELEVANT_EVIDENCE
    )


def test_conflicting_quantities_are_named_honestly() -> None:
    query = RetrievalQuery(query_id="q1", question="What battery capacity is required?")
    chunks = [
        _retrieved("The required battery capacity is 5 kWh.", chunk_id="one"),
        _retrieved("The required battery capacity is 10 kWh.", chunk_id="two"),
    ]

    assert (
        abstention_reason(query, chunks, support_score(query, chunks))
        == AbstentionReason.CONFLICTING_EVIDENCE
    )


def test_unknown_explicit_identifier_stays_below_threshold() -> None:
    query = RetrievalQuery(query_id="q1", question="Which DNSP applies to postcode 3000?")
    chunks = [_retrieved("Installations must comply with the applicable DNSP agreement.")]

    assert support_score(query, chunks) < 0.55
