"""Document intake routes.

Owned by: Phase 1 (route signatures, registered and reachable). Phase 2 implements
the bodies.

Every route here returns 501 with a message naming the phase, rather than 404. A
404 is indistinguishable from a typo in the path; a 501 that names Phase 2 tells the
next model exactly what is missing.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from voltdesk.contracts.common import DocumentType

router = APIRouter(prefix="/documents", tags=["documents"])

_PHASE_2 = "implemented in Phase 2 - see docs/PHASE_2.md"


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def submit_document(
    document_type: DocumentType,
    file: UploadFile = File(...),  # noqa: B008 - FastAPI's documented signature
) -> dict[str, Any]:
    """Accept a document, queue it for extraction, return a document id."""
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, f"submit_document is {_PHASE_2}")


@router.get("/{document_id}")
async def get_document(document_id: str) -> dict[str, Any]:
    """Document status and, once extracted, its extraction."""
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, f"get_document is {_PHASE_2}")


@router.get("/{document_id}/extraction")
async def get_extraction(document_id: str) -> dict[str, Any]:
    """The validated extraction contract for a document."""
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, f"get_extraction is {_PHASE_2}")


@router.post("/{document_id}/write-to-crm")
async def write_to_crm(document_id: str) -> dict[str, Any]:
    """Idempotent CRM write of a document's extraction.

    Fields below the auto-write confidence threshold are held back and queued for
    review instead - see docs/GUARDRAILS.md.
    """
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, f"write_to_crm is {_PHASE_2}")
