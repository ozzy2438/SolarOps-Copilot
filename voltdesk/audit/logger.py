"""The audit log writer.

Owned by: Phase 1. Fully implemented.

Two sinks, both always written:
  - PostgreSQL (app.model_calls), the queryable record the metrics endpoint reads;
  - a structured log line, which survives a database outage.

A failure to write the audit row must never fail the call that produced it - losing
an audit row is bad, failing a customer's document because the audit table is
unreachable is worse. The write failure is itself logged at error level so it is
visible rather than silent.
"""

from __future__ import annotations

import json

from sqlalchemy import Engine, text

from voltdesk.contracts.audit import AuditRecord
from voltdesk.db.session import get_engine
from voltdesk.logging_setup import get_logger

logger = get_logger(__name__)

_INSERT = text(
    """
    INSERT INTO app.model_calls (
        call_id, occurred_at, task_type, provider, model_id, routing_strategy,
        routing_rationale, prompt_version_hash, input_tokens, output_tokens,
        cache_read_input_tokens, cache_creation_input_tokens, cost_usd, latency_ms,
        outcome, error_message, retry_count, redaction_applied, redacted_entity_counts,
        document_id, query_id
    ) VALUES (
        :call_id, :occurred_at, :task_type, :provider, :model_id, :routing_strategy,
        :routing_rationale, :prompt_version_hash, :input_tokens, :output_tokens,
        :cache_read_input_tokens, :cache_creation_input_tokens, :cost_usd, :latency_ms,
        :outcome, :error_message, :retry_count, :redaction_applied,
        CAST(:redacted_entity_counts AS jsonb), :document_id, :query_id
    )
    ON CONFLICT (call_id) DO NOTHING
    """
)


class AuditLogger:
    """Writes one row per model call. Never raises."""

    def __init__(self, engine: Engine | None = None) -> None:
        self._engine = engine

    def write(self, record: AuditRecord) -> None:
        self._log(record)
        try:
            self._persist(record)
        except Exception as exc:  # noqa: BLE001 - see module docstring
            logger.error(
                "audit_write_failed",
                call_id=record.call_id,
                error=str(exc),
                hint="the structured log line above is the surviving record of this call",
            )

    def _log(self, record: AuditRecord) -> None:
        logger.info(
            "audit_record",
            call_id=record.call_id,
            occurred_at=record.occurred_at.isoformat(),
            task_type=str(record.task_type),
            provider=str(record.routing.chosen.provider),
            model_id=record.routing.chosen.model_id,
            routing_strategy=str(record.routing.strategy),
            routing_rationale=record.routing.rationale,
            prompt_version_hash=record.prompt_version_hash,
            input_tokens=record.usage.input_tokens,
            output_tokens=record.usage.output_tokens,
            cost_usd=record.cost_usd,
            latency_ms=record.latency_ms,
            outcome=str(record.outcome),
            retry_count=record.retry_count,
            redaction_applied=record.redaction_applied,
            document_id=record.document_id,
            query_id=record.query_id,
        )

    def _persist(self, record: AuditRecord) -> None:
        engine = self._engine or get_engine()
        with engine.begin() as connection:
            connection.execute(
                _INSERT,
                {
                    "call_id": record.call_id,
                    "occurred_at": record.occurred_at,
                    "task_type": str(record.task_type),
                    "provider": str(record.routing.chosen.provider),
                    "model_id": record.routing.chosen.model_id,
                    "routing_strategy": str(record.routing.strategy),
                    "routing_rationale": record.routing.rationale,
                    "prompt_version_hash": record.prompt_version_hash,
                    "input_tokens": record.usage.input_tokens,
                    "output_tokens": record.usage.output_tokens,
                    "cache_read_input_tokens": record.usage.cache_read_input_tokens,
                    "cache_creation_input_tokens": record.usage.cache_creation_input_tokens,
                    "cost_usd": record.cost_usd,
                    "latency_ms": record.latency_ms,
                    "outcome": str(record.outcome),
                    "error_message": record.error_message,
                    "retry_count": record.retry_count,
                    "redaction_applied": record.redaction_applied,
                    "redacted_entity_counts": json.dumps(record.redacted_entity_counts),
                    "document_id": record.document_id,
                    "query_id": record.query_id,
                },
            )
