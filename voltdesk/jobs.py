"""RQ job functions.

Owned by: Phase 2. POST /documents enqueues `process_document` and returns 202;
the HTTP request must not wait for a model.
"""

from __future__ import annotations

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
        update_document_status(document_id, "failed", error=str(exc))
        ReviewQueue().enqueue(
            new_review_item(
                document_id=document_id,
                document_type=record.document_type,
                fields=[
                    FieldForReview(
                        field_path="_document",
                        proposed_value=None,
                        confidence=0.0,
                        reason="Schema validation failed after one repair attempt.",
                    )
                ],
                blocking=True,
            )
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
    outcome = CrmWriter().write(calibrated, parsed)
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


def enqueue_process_document(document_id: str) -> None:
    """Enqueue on the `voltdesk` RQ queue. Tests monkeypatch this."""
    from redis import Redis
    from rq import Queue

    from voltdesk.config import get_settings

    queue = Queue("voltdesk", connection=Redis.from_url(get_settings().redis_url))
    queue.enqueue(process_document, document_id)
