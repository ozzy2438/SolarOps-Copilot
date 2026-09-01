"""Extraction prompt templates.

Owned by: Phase 2. See docs/PHASE_2.md.

Rules Phase 2 must follow, because they are load-bearing elsewhere:

- The system prompt must be *stable* across calls (the JSON Schema and the
  instructions, nothing per-document), so the prompt cache is not defeated. The
  document text goes in the user message.
- The schema handed to the model is the committed export from schemas/, not a
  hand-written copy. Two schemas that drift are a silent extraction bug.
- Every prompt gets a version identifier here; `prompt_version_hash` in
  voltdesk/llm/client.py hashes the template so the audit log can attribute a
  result to a prompt version.
- The prompt must instruct the model to emit `confidence: 0.0` and `value: null`
  for a field the document does not state, and NOT to guess. The review queue's
  behaviour depends on that distinction (voltdesk/contracts/README.md).
"""

from __future__ import annotations

from voltdesk.contracts.common import DocumentType

#: Prompt template identifiers. Bump the suffix when the text changes.
BILL_EXTRACTION_PROMPT_ID = "bill_extraction.v1"
SITE_ASSESSMENT_PROMPT_ID = "site_assessment_extraction.v1"
EMAIL_EXTRACTION_PROMPT_ID = "email_extraction.v1"
SCHEMA_REPAIR_PROMPT_ID = "schema_repair.v1"


def system_prompt_for(document_type: DocumentType) -> str:
    """The cacheable half of the prompt: instructions plus the JSON Schema."""
    raise NotImplementedError(
        "system_prompt_for is implemented in Phase 2 (docs/PHASE_2.md, step 3)"
    )


def user_prompt_for(document_type: DocumentType, document_text: str) -> str:
    """The per-document half. Must contain the document text and nothing stable."""
    raise NotImplementedError(
        "user_prompt_for is implemented in Phase 2 (docs/PHASE_2.md, step 3)"
    )


def repair_prompt(invalid_output: str, validation_error: str, schema: str) -> str:
    """One repair attempt after a ValidationError. See docs/GUARDRAILS.md for the
    retry budget - repair is attempted once, then the document goes to review."""
    raise NotImplementedError(
        "repair_prompt is implemented in Phase 2 (docs/PHASE_2.md, step 5)"
    )
