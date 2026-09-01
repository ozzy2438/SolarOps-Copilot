"""RQ job functions.

Owned by: Phase 2. POST /documents enqueues `process_document` and returns 202;
the HTTP request must not wait for a model.
"""

from __future__ import annotations

from voltdesk.contracts.common import DocumentType
from voltdesk.contracts.review import FieldForReview
from voltdesk.crm.writer import CrmWriter
from voltdesk.extraction.confidence import calibrate, min_confidence
from voltdesk.extraction.extractor import ExtractionFailed, Extractor
from voltdesk.logging_setup import get_logger
from voltdesk.parsers import parser_for
from voltdesk.review.queue import ReviewQueue, new_review_item
from voltdesk.storage import (
    get_document,
    mark_crm_written,
    put_extraction,
    update_document_status,
)

logger = get_logger(__name__)


def process_document(document_id: str) -> None:
    """Parse, extract, calibrate, write or queue. Failures are stored, not raised
    out of the worker unless the document row itself is missing.
    """
    record = get_document(document_id)
    if record is None:
        raise KeyError(document_id)
    update_document_status(document_id, "parsing")
    parsed = parser_for(record.document_type).parse(
        document_id, record.content, record.filename
    )
    update_document_status(document_id, "parsed")
    update_document_status(document_id, "extracting")
    try:
        extraction = Extractor().extract(parsed)
    except ExtractionFailed as exc:
        _fail_for_review(
            document_id,
            record.document_type,
            error=str(exc),
            reason="Schema validation failed after one repair attempt.",
        )
        return
    except Exception as exc:  # noqa: BLE001 - job boundary: never leave status=extracting
        logger.exception("extraction_failed", document_id=document_id)
        _fail_for_review(
            document_id,
            record.document_type,
            error=str(exc),
            reason="Extraction raised before a validated record existed.",
        )
        return

    calibrated = calibrate(extraction, parsed)
    put_extraction(
        document_id=document_id,
        extraction=calibrated,
        min_confidence=min_confidence(calibrated),
        model_id="unknown",
        prompt_version_hash="0" * 64,
    )
    update_document_status(document_id, "extracted")
    try:
        outcome = CrmWriter().write(calibrated, parsed)
    except Exception as exc:  # noqa: BLE001 - job boundary
        logger.exception("crm_write_failed", document_id=document_id)
        _fail_for_review(
            document_id,
            record.document_type,
            error=str(exc),
            reason="CRM write failed after a validated extraction.",
        )
        return
    if outcome.review_fields:
        ReviewQueue().enqueue(
            new_review_item(
                document_id=document_id,
                document_type=record.document_type,
                fields=outcome.review_fields,
                blocking=outcome.blocking,
            )
        )
    if outcome.written and outcome.external_key:
        mark_crm_written(document_id, outcome.external_key)
        update_document_status(document_id, "written")
    elif outcome.blocking:
        update_document_status(document_id, "failed", error="blocking_nmi")
    logger.info(
        "document_processed",
        document_id=document_id,
        written=outcome.written,
        blocking=outcome.blocking,
    )


def _fail_for_review(
    document_id: str,
    document_type: DocumentType,
    *,
    error: str,
    reason: str,
) -> None:
    update_document_status(document_id, "failed", error=error)
    ReviewQueue().enqueue(
        new_review_item(
            document_id=document_id,
            document_type=document_type,
            fields=[
                FieldForReview(
                    field_path="_document",
                    proposed_value=None,
                    confidence=0.0,
                    reason=reason,
                )
            ],
            blocking=True,
        )
    )


def enqueue_process_document(document_id: str) -> None:
    """Enqueue on the `voltdesk` RQ queue. Tests monkeypatch this."""
    from redis import Redis
    from rq import Queue

    from voltdesk.config import get_settings

    queue = Queue("voltdesk", connection=Redis.from_url(get_settings().redis_url))
    queue.enqueue(process_document, document_id)
