"""Retrieval and answer-synthesis contracts.

Owned by: Phase 1 (definition). Phase 3 implements against these.
The abstention flag is not decoration: an answer VoltDesk is not entitled to give
must be representable, and the evaluator scores abstention precision and recall
from these fields.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from voltdesk.contracts.common import StrictModel


class CorpusSource(StrEnum):
    """Provenance class of a corpus document. Tier A only - the corpus is never synthetic."""

    CEC_APPROVED_LIST = "cec_approved_list"
    MANUFACTURER_DATASHEET = "manufacturer_datasheet"
    DNSP_CONNECTION_GUIDELINE = "dnsp_connection_guideline"
    REGULATOR_METHODOLOGY = "regulator_methodology"
    REBATE_PROGRAM_DOC = "rebate_program_doc"
    INTERNAL_STANDARD = "internal_standard"


class Chunk(StrictModel):
    """A retrievable unit of the corpus."""

    chunk_id: str
    document_id: str
    source: CorpusSource
    document_title: str
    text: str = Field(min_length=1)
    page: int | None = Field(default=None, ge=1)
    section_path: list[str] = Field(
        default_factory=list,
        description="Heading breadcrumb, e.g. ['5. Inverters', '5.2 Anti-islanding'].",
    )
    token_count: int = Field(ge=1)


class RetrievalQuery(StrictModel):
    """A question put to the knowledge capability."""

    query_id: str
    question: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=8, ge=1, le=50)
    source_filter: list[CorpusSource] = Field(
        default_factory=list, description="Empty means no filter."
    )
    asked_by: str | None = Field(
        default=None, description="Staff identifier for the audit log. Never sent to a provider."
    )


class RetrievedChunk(StrictModel):
    """A chunk plus why it was retrieved."""

    chunk: Chunk
    score: float = Field(description="Similarity score as returned by the retriever.")
    rank: int = Field(ge=1)


class Citation(StrictModel):
    """A specific claim in an answer tied to a specific piece of evidence.

    `quote` must appear verbatim in the cited chunk. Phase 3 verifies this before
    returning the answer; a citation that fails verification invalidates the answer
    rather than being silently dropped.
    """

    chunk_id: str
    document_title: str
    source: CorpusSource
    page: int | None = Field(default=None, ge=1)
    quote: str = Field(min_length=1, max_length=1000)
    supports_claim: str = Field(
        min_length=1, description="The sentence in the answer this citation backs."
    )


class AbstentionReason(StrEnum):
    NO_RELEVANT_EVIDENCE = "no_relevant_evidence"
    CONFLICTING_EVIDENCE = "conflicting_evidence"
    INSUFFICIENT_SPECIFICITY = "insufficient_specificity"
    OUT_OF_SCOPE = "out_of_scope"


class RetrievalAnswer(StrictModel):
    """The answer, or an explicit refusal to answer.

    Invariant enforced below: an abstained answer carries a reason and no
    answer text; an answered query carries at least one citation.
    """

    query_id: str
    abstained: bool
    answer_text: str | None = Field(
        default=None, description="None when abstained is True."
    )
    abstention_reason: AbstentionReason | None = None
    abstention_message: str | None = Field(
        default=None, description="What the user is told, and what would be needed instead."
    )
    citations: list[Citation] = Field(default_factory=list)
    support_score: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "How well the retrieved evidence supports the answer. Compared against "
            "VOLTDESK_ABSTENTION_THRESHOLD by Phase 3's scorer."
        ),
    )
    retrieved: list[RetrievedChunk] = Field(
        default_factory=list, description="Everything retrieved, including chunks not cited."
    )

    @model_validator(mode="after")
    def _enforce_abstention_invariant(self) -> RetrievalAnswer:
        if self.abstained:
            if self.answer_text is not None:
                raise ValueError("an abstained answer must not carry answer_text")
            if self.abstention_reason is None:
                raise ValueError("an abstained answer must carry an abstention_reason")
        else:
            if not self.answer_text:
                raise ValueError("a non-abstained answer must carry answer_text")
            if not self.citations:
                raise ValueError(
                    "a non-abstained answer must carry at least one citation; "
                    "an uncitable answer is an abstention"
                )
        return self
