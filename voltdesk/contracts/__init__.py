"""Every object that crosses a VoltDesk boundary.

Owned by: Phase 1. Read voltdesk/contracts/README.md before changing anything here.
"""

from voltdesk.contracts.audit import AuditRecord, TokenUsage
from voltdesk.contracts.common import (
    CallOutcome,
    Confidence,
    DateRange,
    DocumentType,
    ExtractedField,
    MoneyAUD,
    Provenance,
    Provider,
    ReviewStatus,
    StrictModel,
    TaskType,
)
from voltdesk.contracts.crm import (
    CrmEntity,
    CrmPayload,
    EnergyProfilePayload,
    GridConnectionPayload,
    ProposalPayload,
    SiteAssessmentPayload,
)
from voltdesk.contracts.documents import (
    EmailIntent,
    ExtractedBill,
    ExtractedEmailThread,
    ExtractedSiteAssessment,
    ExtractionResult,
    PhaseConfiguration,
    RoofOrientation,
    RoofPlane,
    TariffComponent,
    TariffType,
)
from voltdesk.contracts.evaluation import (
    EvaluationResult,
    FieldScore,
    GoldenRecord,
    RecordResult,
)
from voltdesk.contracts.retrieval import (
    AbstentionReason,
    Chunk,
    Citation,
    CorpusSource,
    RetrievalAnswer,
    RetrievalQuery,
    RetrievedChunk,
)
from voltdesk.contracts.review import FieldForReview, ReviewItem
from voltdesk.contracts.routing import ModelChoice, RoutingDecision, RoutingStrategy

#: Contracts exported to schemas/ by scripts/export_schemas.py. Adding a contract
#: without adding it here means it ships without a JSON Schema; the export script's
#: --check mode fails the build when the two drift apart.
EXPORTED_CONTRACTS = [
    ExtractedBill,
    ExtractedSiteAssessment,
    ExtractedEmailThread,
    SiteAssessmentPayload,
    EnergyProfilePayload,
    GridConnectionPayload,
    ProposalPayload,
    RetrievalQuery,
    RetrievalAnswer,
    Chunk,
    RoutingDecision,
    AuditRecord,
    ReviewItem,
    GoldenRecord,
    EvaluationResult,
]

__all__ = [
    "AbstentionReason",
    "AuditRecord",
    "CallOutcome",
    "Chunk",
    "Citation",
    "Confidence",
    "CorpusSource",
    "CrmEntity",
    "CrmPayload",
    "DateRange",
    "DocumentType",
    "EXPORTED_CONTRACTS",
    "EmailIntent",
    "EnergyProfilePayload",
    "EvaluationResult",
    "ExtractedBill",
    "ExtractedEmailThread",
    "ExtractedField",
    "ExtractedSiteAssessment",
    "ExtractionResult",
    "FieldForReview",
    "FieldScore",
    "GoldenRecord",
    "GridConnectionPayload",
    "ModelChoice",
    "MoneyAUD",
    "PhaseConfiguration",
    "Provenance",
    "ProposalPayload",
    "Provider",
    "RecordResult",
    "RetrievalAnswer",
    "RetrievalQuery",
    "RetrievedChunk",
    "ReviewItem",
    "ReviewStatus",
    "RoofOrientation",
    "RoofPlane",
    "RoutingDecision",
    "RoutingStrategy",
    "SiteAssessmentPayload",
    "StrictModel",
    "TariffComponent",
    "TariffType",
    "TaskType",
    "TokenUsage",
]
