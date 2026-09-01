"""Document intake routes.

Owned by: Phase 1 (route signatures, registered and reachable). Phase 2 implements
the bodies.

POST /documents returns 202 immediately and enqueues; it must not wait for a model.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from voltdesk.contracts.common import DocumentType
from voltdesk.contracts.documents import (
    ExtractedBill,
    ExtractedEmailThread,
    ExtractedSiteAssessment,
)
from voltdesk.crm.writer import CrmWriter
from voltdesk.extraction.confidence import calibrate
from voltdesk.jobs import enqueue_process_document
from voltdesk.parsers import parser_for
from voltdesk.parsers.pdf_io import sha256_hex
from voltdesk.storage import (
    get_document,
    get_extraction,
    mark_crm_written,
    put_document,
    update_document_status,
)

router = APIRouter(prefix="/documents", tags=["documents"])

DocumentTypeForm = Annotated[DocumentType, Form()]
UploadFileForm = Annotated[UploadFile, File()]


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def submit_document(
    document_type: DocumentTypeForm,
    file: UploadFileForm,
) -> dict[str, Any]:
    """Accept a document, queue it for extraction, return a document id."""
    content = await file.read()
    if not content:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "empty file")
    record = put_document(
        document_type=document_type,
        filename=file.filename or "document",
        content=content,
        sha256=sha256_hex(content),
    )
    enqueue_process_document(record.id)
    return {"document_id": record.id, "status": record.status}


@router.get("/{document_id}")
async def get_document_route(document_id: str) -> dict[str, Any]:
    """Document status and, once extracted, its extraction."""
    record = get_document(document_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document not found")
    body: dict[str, Any] = {
        "document_id": record.id,
        "document_type": str(record.document_type),
        "filename": record.filename,
        "sha256": record.sha256,
        "status": record.status,
        "error_message": record.error_message,
    }
    extraction = get_extraction(document_id)
    if extraction is not None:
        body["extraction"] = extraction.get("payload")
    return body


@router.get("/{document_id}/extraction")
async def get_extraction_route(document_id: str) -> dict[str, Any]:
    """The validated extraction contract for a document."""
    extraction = get_extraction(document_id)
    if extraction is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "extraction not found")
    return extraction["payload"] if "payload" in extraction else extraction


@router.post("/{document_id}/write-to-crm")
async def write_to_crm(document_id: str) -> dict[str, Any]:
    """Idempotent CRM write of a document's extraction.

    Fields below the auto-write confidence threshold are held back and queued for
    review instead - see docs/GUARDRAILS.md.
    """
    record = get_document(document_id)
    stored = get_extraction(document_id)
    if record is None or stored is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "extraction not found")
    payload = stored["payload"] if "payload" in stored else stored
    if not isinstance(payload, dict):
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "stored payload is not an object"
        )
    if record.document_type == DocumentType.ELECTRICITY_BILL:
        extraction: ExtractedBill | ExtractedSiteAssessment | ExtractedEmailThread = (
            ExtractedBill.model_validate(payload)
        )
    elif record.document_type == DocumentType.SITE_ASSESSMENT:
        extraction = ExtractedSiteAssessment.model_validate(payload)
    else:
        extraction = ExtractedEmailThread.model_validate(payload)
    parsed = parser_for(record.document_type).parse(
        document_id, record.content, record.filename
    )
    outcome = CrmWriter().write(calibrate(extraction, parsed), parsed)
    if outcome.written and outcome.external_key:
        mark_crm_written(document_id, outcome.external_key)
        update_document_status(document_id, "written")
    return {
        "written": outcome.written,
        "blocking": outcome.blocking,
        "external_key": outcome.external_key,
        "created": outcome.created,
    }
