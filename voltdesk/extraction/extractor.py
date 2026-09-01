"""Parsed document -> validated extraction contract.

Owned by: Phase 2. See docs/PHASE_2.md.

The extractor calls the model through voltdesk.llm.LLMClient and never through a
provider adapter directly - redaction and the audit record are not optional.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from voltdesk.contracts.common import DocumentType, Provenance, TaskType
from voltdesk.contracts.documents import (
    ExtractedBill,
    ExtractedEmailThread,
    ExtractedSiteAssessment,
    ExtractionResult,
)
from voltdesk.extraction.prompts import (
    SCHEMA_REPAIR_PROMPT_ID,
    prompt_id_for,
    repair_prompt,
    schema_dict_for,
    system_prompt_for,
    user_prompt_for,
)
from voltdesk.llm.base import CompletionRequest
from voltdesk.llm.client import LLMClient
from voltdesk.parsers.base import ParsedDocument
from voltdesk.routing.router import Router, StaticRouter

_TASK = {
    DocumentType.ELECTRICITY_BILL: TaskType.BILL_EXTRACTION,
    DocumentType.SITE_ASSESSMENT: TaskType.SITE_ASSESSMENT_EXTRACTION,
    DocumentType.EMAIL_THREAD: TaskType.EMAIL_EXTRACTION,
}


class ExtractionFailed(ValueError):
    """Schema-invalid after the single repair attempt. The job queues review."""

    def __init__(self, message: str, *, raw_text: str, error: str) -> None:
        super().__init__(message)
        self.raw_text = raw_text
        self.error = error


class Extractor:
    """Runs one extraction, validates it, and repairs it once if it fails validation."""

    def __init__(
        self,
        llm: LLMClient | None = None,
        router: Router | None = None,
    ) -> None:
        self._llm = llm or LLMClient()
        self._router = router or StaticRouter()

    def extract(self, document: ParsedDocument) -> ExtractionResult:
        system = system_prompt_for(document.document_type)
        schema = schema_dict_for(document.document_type)
        user = user_prompt_for(document.document_type, _document_payload(document))
        task = _TASK[document.document_type]
        routing = self._router.route(task)
        request = CompletionRequest(
            model_id=routing.chosen.model_id,
            system=system,
            user_content=user,
            json_schema=schema if isinstance(schema, dict) else None,
        )
        response, redaction = self._llm.complete(
            request,
            task_type=task,
            routing=routing,
            prompt_template=prompt_id_for(document.document_type),
            document_id=document.document_id,
        )
        text = redaction.rehydrate(response.text)
        try:
            return self._validate(document, text)
        except (ValidationError, json.JSONDecodeError, KeyError, ValueError) as exc:
            repaired_user = repair_prompt(text, str(exc), json.dumps(schema))
            repair_routing = self._router.route(TaskType.SCHEMA_REPAIR)
            repair_request = CompletionRequest(
                model_id=repair_routing.chosen.model_id,
                system=system,
                user_content=repaired_user,
                json_schema=schema if isinstance(schema, dict) else None,
            )
            repair_response, repair_redaction = self._llm.complete(
                repair_request,
                task_type=TaskType.SCHEMA_REPAIR,
                routing=repair_routing,
                prompt_template=SCHEMA_REPAIR_PROMPT_ID,
                document_id=document.document_id,
            )
            repaired = repair_redaction.rehydrate(repair_response.text)
            try:
                return self._validate(document, repaired)
            except (ValidationError, json.JSONDecodeError, KeyError, ValueError) as again:
                raise ExtractionFailed(
                    "extraction invalid after one repair attempt",
                    raw_text=repaired,
                    error=str(again),
                ) from again

    def _validate(self, document: ParsedDocument, raw: str) -> ExtractionResult:
        payload = _parse_json(raw)
        provenance = Provenance(
            document_id=document.document_id,
            sha256=document.sha256,
            ingested_at=datetime.now(UTC),
            tier="B",
        )
        payload["provenance"] = provenance.model_dump(mode="json")
        payload["document_type"] = str(document.document_type)
        payload.setdefault("parser_warnings", document.warnings)
        if document.document_type == DocumentType.ELECTRICITY_BILL:
            payload["page_count"] = len(document.pages)
        if document.document_type == DocumentType.ELECTRICITY_BILL:
            return ExtractedBill.model_validate(payload)
        if document.document_type == DocumentType.SITE_ASSESSMENT:
            return ExtractedSiteAssessment.model_validate(payload)
        return ExtractedEmailThread.model_validate(payload)


def _document_payload(document: ParsedDocument) -> str:
    chunks = [document.full_text()]
    for page in document.pages:
        for table in page.tables:
            rendered = "\n".join(" | ".join(row) for row in table)
            chunks.append(f"[table page {page.page_number}]\n{rendered}")
    return "\n\n".join(chunks)


def _parse_json(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        inner = [line for line in lines if not line.startswith("```")]
        text = "\n".join(inner).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("model output was not JSON")
    payload = json.loads(text[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("model JSON was not an object")
    return payload
