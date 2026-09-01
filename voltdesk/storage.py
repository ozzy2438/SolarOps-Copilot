"""Document and extraction persistence.

Owned by: Phase 2. Falls back to process-local memory when the database URL is
the unresolvable placeholder, so the unit suite stays offline.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text

from voltdesk.config import get_settings
from voltdesk.contracts.common import DocumentType
from voltdesk.contracts.documents import ExtractionResult
from voltdesk.db.session import get_engine

_DOCS: dict[str, DocumentRecord] = {}
_EXTRACT: dict[str, dict[str, Any]] = {}

_INSERT_DOC = text(
    """
    INSERT INTO app.documents (
        id, document_type, filename, sha256, tier, byte_size, status, content
    ) VALUES (
        :id, :document_type, :filename, :sha256, :tier, :byte_size, :status, :content
    )
    ON CONFLICT (sha256) DO NOTHING
    RETURNING id
    """
)
_SELECT_DOC = text("SELECT * FROM app.documents WHERE id = :id")
_SELECT_SHA = text("SELECT * FROM app.documents WHERE sha256 = :sha256")
_UPDATE_STATUS = text(
    """
    UPDATE app.documents
    SET status = :status, parsed_at = :parsed_at, error_message = :error_message
    WHERE id = :id
    """
)
_INSERT_EXT = text(
    """
    INSERT INTO app.extractions (
        id, document_id, document_type, payload, min_confidence, model_id,
        prompt_version_hash, crm_written_at, crm_external_key
    ) VALUES (
        :id, :document_id, :document_type, CAST(:payload AS jsonb), :min_confidence,
        :model_id, :prompt_version_hash, :crm_written_at, :crm_external_key
    )
    """
)
_SELECT_EXT = text(
    """
    SELECT * FROM app.extractions
    WHERE document_id = :document_id
    ORDER BY created_at DESC
    LIMIT 1
    """
)
_UPDATE_CRM = text(
    """
    UPDATE app.extractions
    SET crm_written_at = :crm_written_at, crm_external_key = :crm_external_key
    WHERE document_id = :document_id
    """
)


@dataclass
class DocumentRecord:
    id: str
    document_type: DocumentType
    filename: str
    sha256: str
    tier: str
    byte_size: int
    status: str
    content: bytes
    error_message: str | None = None
    received_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    parsed_at: datetime | None = None


def _use_memory() -> bool:
    return "not-configured" in get_settings().database_url


def put_document(
    *,
    document_type: DocumentType,
    filename: str,
    content: bytes,
    sha256: str,
    tier: str = "B",
) -> DocumentRecord:
    if _use_memory():
        for cached in _DOCS.values():
            if cached.sha256 == sha256:
                return cached
        record = DocumentRecord(
            id=str(uuid.uuid4()),
            document_type=document_type,
            filename=filename,
            sha256=sha256,
            tier=tier,
            byte_size=len(content),
            status="received",
            content=content,
        )
        _DOCS[record.id] = record
        return record
    new_id = str(uuid.uuid4())
    with get_engine().begin() as connection:
        row = connection.execute(
            _INSERT_DOC,
            {
                "id": new_id,
                "document_type": str(document_type),
                "filename": filename,
                "sha256": sha256,
                "tier": tier,
                "byte_size": len(content),
                "status": "received",
                "content": content,
            },
        ).first()
        if row is None:
            found = connection.execute(_SELECT_SHA, {"sha256": sha256}).mappings().one()
            return _doc_from_row(_row_dict(found))
        loaded = connection.execute(_SELECT_DOC, {"id": new_id}).mappings().one()
        return _doc_from_row(_row_dict(loaded))


def get_document(document_id: str) -> DocumentRecord | None:
    if _use_memory():
        return _DOCS.get(document_id)
    with get_engine().connect() as connection:
        row = connection.execute(_SELECT_DOC, {"id": document_id}).mappings().first()
    return _doc_from_row(_row_dict(row)) if row is not None else None


def update_document_status(
    document_id: str, status: str, *, error: str | None = None
) -> None:
    parsed_at = datetime.now(UTC) if status in {"parsed", "extracted", "written"} else None
    if _use_memory():
        record = _DOCS[document_id]
        record.status = status
        record.error_message = error
        if parsed_at is not None:
            record.parsed_at = parsed_at
        return
    with get_engine().begin() as connection:
        connection.execute(
            _UPDATE_STATUS,
            {
                "id": document_id,
                "status": status,
                "parsed_at": parsed_at,
                "error_message": error,
            },
        )


def put_extraction(
    *,
    document_id: str,
    extraction: ExtractionResult,
    min_confidence: float,
    model_id: str,
    prompt_version_hash: str,
    crm_external_key: str | None = None,
) -> str:
    extraction_id = str(uuid.uuid4())
    payload = extraction.model_dump(mode="json")
    if _use_memory():
        _EXTRACT[document_id] = {
            "id": extraction_id,
            "payload": payload,
            "min_confidence": min_confidence,
            "model_id": model_id,
            "prompt_version_hash": prompt_version_hash,
            "crm_external_key": crm_external_key,
        }
        return extraction_id
    with get_engine().begin() as connection:
        connection.execute(
            _INSERT_EXT,
            {
                "id": extraction_id,
                "document_id": document_id,
                "document_type": str(extraction.document_type),
                "payload": json.dumps(payload),
                "min_confidence": min_confidence,
                "model_id": model_id,
                "prompt_version_hash": prompt_version_hash,
                "crm_written_at": datetime.now(UTC) if crm_external_key else None,
                "crm_external_key": crm_external_key,
            },
        )
    return extraction_id


def get_extraction(document_id: str) -> dict[str, Any] | None:
    if _use_memory():
        return _EXTRACT.get(document_id)
    with get_engine().connect() as connection:
        row = connection.execute(_SELECT_EXT, {"document_id": document_id}).mappings().first()
    return _row_dict(row) if row is not None else None


def mark_crm_written(document_id: str, external_key: str) -> None:
    if _use_memory():
        row = _EXTRACT.get(document_id)
        if row is not None:
            row["crm_external_key"] = external_key
        return
    with get_engine().begin() as connection:
        connection.execute(
            _UPDATE_CRM,
            {
                "document_id": document_id,
                "crm_written_at": datetime.now(UTC),
                "crm_external_key": external_key,
            },
        )


def _row_dict(row: Any) -> dict[str, Any]:
    return {str(key): row[key] for key in row.keys()}


def _doc_from_row(row: dict[str, Any]) -> DocumentRecord:
    content = row.get("content") or b""
    if isinstance(content, memoryview):
        content = content.tobytes()
    return DocumentRecord(
        id=row["id"],
        document_type=DocumentType(row["document_type"]),
        filename=row["filename"],
        sha256=row["sha256"],
        tier=row["tier"],
        byte_size=int(row["byte_size"]),
        status=row["status"],
        content=bytes(content),
        error_message=row.get("error_message"),
        received_at=row.get("received_at") or datetime.now(UTC),
        parsed_at=row.get("parsed_at"),
    )
