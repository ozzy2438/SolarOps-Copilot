"""Contracts import, validate, and export. Owned by Phase 1.

These tests exist to make the "later phases may add fields, never rename or remove
them" rule enforceable rather than aspirational.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from voltdesk.contracts import EXPORTED_CONTRACTS
from voltdesk.contracts.common import DateRange, ExtractedField, Provenance
from voltdesk.contracts.documents import ExtractedBill, TariffType
from voltdesk.contracts.retrieval import (
    AbstentionReason,
    Citation,
    CorpusSource,
    RetrievalAnswer,
)

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"


def test_every_exported_contract_produces_a_schema() -> None:
    for model in EXPORTED_CONTRACTS:
        schema = model.model_json_schema()
        assert schema["type"] == "object"
        assert "properties" in schema


def test_committed_schemas_match_the_models() -> None:
    """The committed exports are what Phase 2 hands to the model. Drift is a bug."""
    for model in EXPORTED_CONTRACTS:
        name = model.__name__
        snake = "".join(f"_{c.lower()}" if c.isupper() and i else c.lower()
                        for i, c in enumerate(name))
        path = SCHEMA_DIR / f"{snake}.json"
        assert path.exists(), f"{name} has no committed schema; run `make schemas`"
        committed = json.loads(path.read_text())
        assert committed == model.model_json_schema(), (
            f"{name}'s committed schema has drifted; run `make schemas`"
        )


def test_extra_fields_are_rejected(provenance: Provenance) -> None:
    """A hallucinated field must raise, not be silently dropped."""
    with pytest.raises(ValidationError):
        ExtractedBill(
            provenance=provenance,
            retailer_name=ExtractedField[str](value="X", confidence=0.9),
            account_number=ExtractedField[str](value="1", confidence=0.9),
            nmi=ExtractedField[str](value="6123456789", confidence=0.9),
            site_address=ExtractedField[str](value="a", confidence=0.9),
            billing_period=ExtractedField[DateRange](
                value=DateRange(start=date(2026, 1, 1), end=date(2026, 3, 31)),
                confidence=0.9,
            ),
            total_amount=ExtractedField(value=None, confidence=0.0),
            total_consumption_kwh=ExtractedField[float](value=1.0, confidence=0.9),
            tariff_type=ExtractedField[TariffType](value=TariffType.FLAT, confidence=0.9),
            page_count=1,
            hallucinated_field="oops",
        )


def test_confidence_is_bounded() -> None:
    with pytest.raises(ValidationError):
        ExtractedField[str](value="x", confidence=1.5)
    with pytest.raises(ValidationError):
        ExtractedField[str](value="x", confidence=-0.1)


def test_date_range_counts_days_inclusively() -> None:
    assert DateRange(start=date(2026, 1, 1), end=date(2026, 1, 31)).days() == 31


def test_abstained_answer_may_not_carry_answer_text() -> None:
    with pytest.raises(ValidationError):
        RetrievalAnswer(
            query_id="q1",
            abstained=True,
            answer_text="but here is an answer anyway",
            abstention_reason=AbstentionReason.NO_RELEVANT_EVIDENCE,
            support_score=0.1,
        )


def test_abstained_answer_needs_a_reason() -> None:
    with pytest.raises(ValidationError):
        RetrievalAnswer(query_id="q1", abstained=True, support_score=0.1)


def test_answered_query_needs_a_citation() -> None:
    """An uncitable answer is an abstention. This is the system's core promise."""
    with pytest.raises(ValidationError):
        RetrievalAnswer(
            query_id="q1", abstained=False, answer_text="Yes.", support_score=0.9
        )


def test_valid_answer_round_trips() -> None:
    answer = RetrievalAnswer(
        query_id="q1",
        abstained=False,
        answer_text="The export limit is 5 kW.",
        support_score=0.91,
        citations=[
            Citation(
                chunk_id="c1",
                document_title="Connection Guideline",
                source=CorpusSource.DNSP_CONNECTION_GUIDELINE,
                page=12,
                quote="the export limit is 5 kW",
                supports_claim="The export limit is 5 kW.",
            )
        ],
    )
    assert RetrievalAnswer.model_validate_json(answer.model_dump_json()) == answer
