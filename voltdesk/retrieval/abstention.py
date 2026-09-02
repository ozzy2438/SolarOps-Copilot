"""Cheap evidence scoring and honest abstention before model synthesis."""

from __future__ import annotations

import re
from typing import Any

from voltdesk.config import get_settings
from voltdesk.contracts.retrieval import (
    AbstentionReason,
    RetrievalAnswer,
    RetrievalQuery,
    RetrievedChunk,
)
from voltdesk.routing.router import Router

_WORD = re.compile(r"[a-z0-9]+(?:[./-][a-z0-9]+)*", re.IGNORECASE)
_IDENTIFIER = re.compile(r"\b(?:[A-Za-z0-9]+[-/.])+[A-Za-z0-9]+\b|\b\d{4,}\b")
_QUANTITY = re.compile(r"\b(\d+(?:\.\d+)?)\s*(kwh|kw|w|a|v|%|days?)\b", re.IGNORECASE)
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "can",
    "does",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "the",
    "to",
    "what",
    "when",
    "which",
    "with",
}
_DOMAIN_TERMS = {
    "battery",
    "capacity",
    "cec",
    "certificate",
    "connection",
    "dnsp",
    "electricity",
    "energy",
    "export",
    "grid",
    "installation",
    "inverter",
    "kw",
    "kwh",
    "meter",
    "nmi",
    "panel",
    "photovoltaic",
    "pv",
    "rebate",
    "solar",
    "stc",
}


def _terms(text: str) -> set[str]:
    return {token.casefold() for token in _WORD.findall(text)} - _STOPWORDS


def _has_conflicting_quantities(chunks: list[RetrievedChunk]) -> bool:
    by_unit: dict[str, set[str]] = {}
    for item in chunks[:5]:
        for value, unit in _QUANTITY.findall(item.chunk.text):
            by_unit.setdefault(unit.casefold(), set()).add(value)
    return any(len(values) > 1 for values in by_unit.values())


def support_score(query: RetrievalQuery, chunks: list[RetrievedChunk]) -> float:
    """Combine actual hybrid rank with question-term coverage, bounded to [0, 1]."""
    if not chunks:
        return 0.0
    question_terms = _terms(query.question)
    evidence_terms = set().union(*(_terms(item.chunk.text) for item in chunks[:5]))
    coverage = (
        len(question_terms & evidence_terms) / len(question_terms) if question_terms else 0.0
    )
    top_hybrid_score = min(1.0, max(0.0, chunks[0].score))
    score = 0.65 * top_hybrid_score + 0.35 * coverage

    identifiers = _IDENTIFIER.findall(query.question)
    evidence_text = "\n".join(item.chunk.text for item in chunks[:5]).casefold()
    if identifiers:
        if all(identifier.casefold() in evidence_text for identifier in identifiers):
            score += 0.05
        else:
            score *= 0.5
    return min(1.0, max(0.0, score))


def abstention_reason(
    query: RetrievalQuery, chunks: list[RetrievedChunk], score: float
) -> AbstentionReason:
    """Classify why the evidence cannot safely support an answer."""
    if not (_terms(query.question) & _DOMAIN_TERMS):
        return AbstentionReason.OUT_OF_SCOPE
    if not chunks:
        return AbstentionReason.NO_RELEVANT_EVIDENCE
    if _has_conflicting_quantities(chunks):
        return AbstentionReason.CONFLICTING_EVIDENCE
    return AbstentionReason.INSUFFICIENT_SPECIFICITY


def _message(reason: AbstentionReason) -> str:
    return {
        AbstentionReason.NO_RELEVANT_EVIDENCE: (
            "No relevant authoritative evidence was found in the licensed corpus."
        ),
        AbstentionReason.CONFLICTING_EVIDENCE: (
            "The retrieved authoritative sources contain conflicting quantities; "
            "a human must resolve which revision applies."
        ),
        AbstentionReason.INSUFFICIENT_SPECIFICITY: (
            "The available evidence is not specific enough to answer safely. "
            "Please add a model, clause, program or jurisdiction."
        ),
        AbstentionReason.OUT_OF_SCOPE: (
            "This question is outside VoltDesk's solar, battery and energy corpus."
        ),
    }[reason]


def answer_with_evidence(
    query: RetrievalQuery,
    chunks: list[RetrievedChunk],
    *,
    threshold: float | None = None,
    llm: Any | None = None,
    router: Router | None = None,
) -> RetrievalAnswer:
    """Abstain below threshold without constructing or calling an LLM client."""
    score = support_score(query, chunks)
    selected_threshold = (
        get_settings().abstention_threshold if threshold is None else threshold
    )
    if not 0.0 <= selected_threshold <= 1.0:
        raise ValueError("abstention threshold must be between 0 and 1")
    if score < selected_threshold:
        reason = abstention_reason(query, chunks, score)
        return RetrievalAnswer(
            query_id=query.query_id,
            abstained=True,
            abstention_reason=reason,
            abstention_message=_message(reason),
            support_score=score,
            retrieved=chunks,
        )

    from voltdesk.retrieval.synthesis import synthesise

    return synthesise(
        query,
        chunks,
        llm=llm,
        router=router,
        support_score_value=score,
    )
