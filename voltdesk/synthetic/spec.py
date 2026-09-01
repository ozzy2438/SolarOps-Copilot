"""Synthetic data generator specification.

Owned by: Phase 1 (this specification). Phase 2 implements the generator.

Tier B only: synthetic documents exist so that no real personal information is ever
committed to this repository. The rule from docs/DATA_SOURCES.md is absolute - names,
addresses, account numbers and contacts are fabricated; tariff structures and interval
data are real. A synthetic bill whose prices are invented teaches the parser nothing.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from voltdesk.contracts.common import StrictModel


class Defect(StrEnum):
    """Deliberate realistic defects. The generator injects these on purpose; a corpus
    of clean documents produces a parser that fails on the first real one."""

    SKEWED_SCAN = "skewed_scan"
    NO_TEXT_LAYER = "no_text_layer"
    MULTI_PAGE_TABLE_SPLIT = "multi_page_table_split"
    INCONSISTENT_DATE_FORMAT = "inconsistent_date_format"
    MISSING_FIELD = "missing_field"
    HANDWRITTEN_NOTES = "handwritten_notes"
    QUOTED_EMAIL_HISTORY = "quoted_email_history"
    LOW_CONTRAST_PHOTOCOPY = "low_contrast_photocopy"


class RetailerLayout(StrEnum):
    """Two distinct bill layouts, so extraction cannot overfit to one template."""

    RETAILER_A = "retailer_a"
    RETAILER_B = "retailer_b"


class GeneratorConfig(StrictModel):
    """Everything the generator needs. Fully determined by `seed` plus these values,
    so a golden set is reproducible: same config, same documents, byte for byte."""

    seed: int = Field(description="Any change to this changes every generated document.")
    bill_count: int = Field(default=60, ge=0)
    site_assessment_count: int = Field(default=45, ge=0)
    email_thread_count: int = Field(default=45, ge=0)

    defect_rate: float = Field(
        default=0.35,
        ge=0.0,
        le=1.0,
        description="Fraction of documents carrying at least one defect.",
    )
    enabled_defects: list[Defect] = Field(default_factory=lambda: list(Defect))
    layouts: list[RetailerLayout] = Field(default_factory=lambda: list(RetailerLayout))

    tariff_source_path: str = Field(
        default="data/corpus/tariffs.json",
        description=(
            "Real tariff structures. TODO(verify): source and licence must be recorded "
            "in docs/DATA_SOURCES.md before this file is committed."
        ),
    )
    interval_data_path: str = Field(
        default="data/corpus/interval_data.csv",
        description="Real half-hourly consumption/generation data. Same licence rule.",
    )

    output_dir: str = Field(default="data/generated")


class GeneratedDocument(StrictModel):
    """What the generator emits alongside each file: the answers it already knows.

    This is why synthetic data is worth generating rather than collecting - ground
    truth comes free, with `ground_truth_source='generator_seed'`.
    """

    path: str
    document_type: str
    defects: list[Defect] = Field(default_factory=list)
    ground_truth: dict[str, object] = Field(
        description="field_path -> true value, as the generator constructed it."
    )
