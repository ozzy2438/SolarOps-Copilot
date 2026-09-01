"""RQ job boundary. Owned by: Phase 2."""

from __future__ import annotations

import pytest
from helpers_phase2 import DOCUMENT_TEXT

from voltdesk.contracts.common import DocumentType
from voltdesk.jobs import process_document
from voltdesk.storage import get_document, put_document


def test_process_document_does_not_leave_extracting_on_provider_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("voltdesk.review.queue._PROCESS_MEMORY", {})
    record = put_document(
        document_type=DocumentType.ELECTRICITY_BILL,
        filename="bill.txt",
        content=DOCUMENT_TEXT.encode(),
        sha256="b" * 64,
    )

    def _boom(_parsed: object) -> object:
        raise TypeError("Could not resolve authentication method")

    monkeypatch.setattr("voltdesk.jobs.Extractor.extract", lambda self, parsed: _boom(parsed))
    process_document(record.id)
    stored = get_document(record.id)
    assert stored is not None
    assert stored.status == "failed"
    assert stored.error_message
    from voltdesk.review.queue import ReviewQueue

    pending = ReviewQueue().list_pending()
    assert any(item.document_id == record.id and item.blocking for item in pending)
