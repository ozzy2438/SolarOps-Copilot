"""Build VoltDesk's deterministic Phase 4 golden set.

The extraction records come from generator seed 7. The QA labels are human-authored
against the 12 committed, licence-verified Phase 3 chunks. This script deliberately
does not call a model or promote synthetic documents as human-labelled evidence.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from voltdesk.contracts.common import DocumentType, TaskType
from voltdesk.contracts.evaluation import GoldenRecord
from voltdesk.ingestion.chunking import chunk_document
from voltdesk.ingestion.corpus import load_manifest
from voltdesk.parsers.base import ParsedDocument, ParsedPage
from voltdesk.synthetic import GeneratorConfig, SyntheticGenerator

REPO_ROOT = Path(__file__).resolve().parents[1]
RECORDS_DIR = REPO_ROOT / "data/golden/records"
QUESTIONS_DIR = REPO_ROOT / "data/golden/questions"
CORPUS_DIR = REPO_ROOT / "tests/fixtures/corpus"
GENERATOR_SEED = 7


QA_ANSWERABLE: list[tuple[str, str, list[str]]] = [
    ("How long after installation may STCs be created?", "stc_before", ["12 months"]),
    ("Which registry is used to create STCs?", "stc_before", ["REC Registry"]),
    ("What eligibility check is required before creating STCs?", "stc_before", ["eligible"]),
    ("What right must be confirmed before creating STCs?", "stc_before", ["right to create"]),
    (
        "What kind of registry account must be used?",
        "stc_before",
        ["correct REC Registry account type"],
    ),
    (
        "What state must the required evidence be in before creating STCs?",
        "stc_before",
        ["complete", "signed"],
    ),
    (
        "Can a system owner statutory declaration be required for an STC claim?",
        "stc_docs",
        ["system owner statutory declaration"],
    ),
    (
        "Can a system size statutory declaration be required for an STC claim?",
        "stc_docs",
        ["system size statutory declaration"],
    ),
    (
        "Name two commercial records that may support an STC claim.",
        "stc_docs",
        ["invoices", "contract information"],
    ),
    (
        "How accurate must claim documents be before an STC claim is created?",
        "stc_docs",
        ["complete and accurate"],
    ),
    (
        "Which three approved product lists are used for small generation unit claims?",
        "stc_lists",
        ["PV module", "inverter", "solar battery"],
    ),
    (
        "When should product-list eligibility be checked for an STC claim?",
        "stc_lists",
        ["current list", "claim is prepared"],
    ),
    ("When did the Cheaper Home Batteries Program begin?", "battery_program", ["1 July 2025"]),
    (
        "What approximate discount does the Cheaper Home Batteries Program fund?",
        "battery_program",
        ["around 30%"],
    ),
    (
        "Must an eligible battery connect only to new rooftop solar?",
        "battery_program",
        ["new or existing rooftop solar"],
    ),
    (
        "Through which scheme is the Cheaper Home Batteries Program delivered?",
        "battery_program",
        ["Small-scale Renewable Energy Scheme"],
    ),
    (
        "Who generally provides the federal home-battery discount?",
        "battery_program",
        ["retailers and installers"],
    ),
    (
        "Which customer groups does the Cheaper Home Batteries Program support?",
        "battery_support",
        ["households", "small businesses"],
    ),
    (
        "Should applicants rely on an old summary or current battery-program guidance?",
        "battery_support",
        ["current program guidance"],
    ),
    (
        "In which Australian jurisdictions is the home-battery program available?",
        "battery_availability",
        ["every state and territory"],
    ),
    (
        "What inverter region setting does Solar Victoria recommend by default?",
        "vic_inverter",
        ["Australia A"],
    ),
    (
        "Which standard is named for inverter power-quality response settings?",
        "vic_inverter",
        ["AS/NZS 4777.2"],
    ),
    (
        "What network agreement must a Victorian solar installation comply with?",
        "vic_inverter",
        ["DNSP connection agreement"],
    ),
    (
        "Which two product lists must eligible Victorian solar modules appear on?",
        "vic_modules",
        ["Solar Victoria product list", "Clean Energy Council approved modules list"],
    ),
    (
        "What minimum product warranty is listed for eligible solar modules?",
        "vic_modules",
        ["at least five years"],
    ),
]

QA_UNANSWERABLE = [
    "What export limit applies to a commercial solar system in Cairns?",
    "What is the maximum eligible battery capacity under the federal program?",
    "Which exact Fronius inverter models are currently CEC-approved?",
    "How many years of warranty does Fronius provide for the Symo Advanced?",
    "What dollar rebate does New South Wales pay for a household battery?",
    "Which DNSP serves postcode 3000?",
    "What is the 2026 Victorian Default Offer peak tariff in cents per kWh?",
    "What is today's market value of one STC?",
    "What installer accreditation number is required on an STC claim?",
    "What fire setback distance applies to a battery installed beside a window?",
    "Which battery chemistry is eligible for the federal discount?",
    "How many business days does a DNSP connection approval take?",
    "For how many years must an installer retain STC evidence?",
    "What is the maximum PV system capacity eligible for a Solar Victoria rebate?",
    "What checksum algorithm validates an Australian NMI?",
]


def _chunk_ids() -> dict[str, str]:
    chunks_by_section: dict[str, str] = {}
    for entry in load_manifest(CORPUS_DIR):
        content = entry.path.read_bytes()
        parsed = ParsedDocument(
            document_id=entry.document_id,
            document_type=DocumentType.SITE_ASSESSMENT,
            sha256=hashlib.sha256(content).hexdigest(),
            pages=[ParsedPage(page_number=1, text=content.decode("utf-8"))],
        )
        for chunk in chunk_document(parsed, source=entry.source, document_title=entry.title):
            section = chunk.section_path[-1]
            if section == "1. Before creating STCs":
                chunks_by_section["stc_before"] = chunk.chunk_id
            elif section == "2. Required documents":
                chunks_by_section["stc_docs"] = chunk.chunk_id
            elif section == "3. Approved product lists":
                chunks_by_section["stc_lists"] = chunk.chunk_id
            elif section == "1. Program":
                chunks_by_section["battery_program"] = chunk.chunk_id
            elif section == "2. Who the program supports":
                chunks_by_section["battery_support"] = chunk.chunk_id
            elif section == "3. Availability":
                chunks_by_section["battery_availability"] = chunk.chunk_id
            elif section == "3.2.2 Solar PV inverter recommendations":
                chunks_by_section["vic_inverter"] = chunk.chunk_id
            elif section == "3.2.3 Solar PV module mandatory requirements":
                chunks_by_section["vic_modules"] = chunk.chunk_id
    expected = {section for _, section, _ in QA_ANSWERABLE}
    if missing := expected - chunks_by_section.keys():
        raise RuntimeError(f"QA labels refer to missing corpus sections: {sorted(missing)}")
    return chunks_by_section


def _write_record(payload: dict[str, Any]) -> Path:
    record = GoldenRecord.model_validate(payload)
    path = RECORDS_DIR / f"{record.record_id}.json"
    path.write_text(json.dumps(record.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8")
    return path


def _extraction_records() -> list[Path]:
    generated = SyntheticGenerator(
        GeneratorConfig(
            seed=GENERATOR_SEED,
            bill_count=50,
            site_assessment_count=30,
            email_thread_count=30,
        )
    ).generate()
    counters = {"electricity_bill": 0, "site_assessment": 0, "email_thread": 0}
    task_types = {
        "electricity_bill": TaskType.BILL_EXTRACTION,
        "site_assessment": TaskType.SITE_ASSESSMENT_EXTRACTION,
        "email_thread": TaskType.EMAIL_EXTRACTION,
    }
    prefixes = {"electricity_bill": "bill", "site_assessment": "site", "email_thread": "email"}
    paths: list[Path] = []
    for document in generated:
        counters[document.document_type] += 1
        index = counters[document.document_type]
        record_id = f"{prefixes[document.document_type]}-{index:04d}"
        input_path = Path(document.path).resolve().relative_to(REPO_ROOT).as_posix()
        defect_names = [defect.value for defect in document.defects]
        paths.append(
            _write_record(
                {
                    "record_id": record_id,
                    "task_type": task_types[document.document_type],
                    "input_path": input_path,
                    "expected": document.ground_truth,
                    "ground_truth_source": "generator_seed",
                    "notes": (
                        f"Synthetic generator seed {GENERATOR_SEED}; defects: {defect_names}"
                    ),
                }
            )
        )
    return paths


def _qa_records() -> list[Path]:
    chunk_ids = _chunk_ids()
    paths: list[Path] = []
    cases = [
        (question, False, answers, [chunk_ids[section]])
        for question, section, answers in QA_ANSWERABLE
    ]
    cases.extend((question, True, [], []) for question in QA_UNANSWERABLE)
    for index, (question, should_abstain, answers, citations) in enumerate(cases, start=1):
        record_id = f"qa-{index:04d}"
        question_path = QUESTIONS_DIR / f"{record_id}.txt"
        question_path.write_text(question + "\n", encoding="utf-8")
        paths.append(
            _write_record(
                {
                    "record_id": record_id,
                    "task_type": TaskType.KNOWLEDGE_QA,
                    "input_path": question_path.relative_to(REPO_ROOT).as_posix(),
                    "expected": {
                        "should_abstain": should_abstain,
                        "answer_contains": answers,
                        "required_citation_chunk_ids": citations,
                    },
                    "ground_truth_source": "human_labelled",
                    "notes": "Labelled against the 12-chunk licensed Phase 3 corpus.",
                }
            )
        )
    return paths


def main() -> None:
    RECORDS_DIR.mkdir(parents=True, exist_ok=True)
    QUESTIONS_DIR.mkdir(parents=True, exist_ok=True)
    written = [*_extraction_records(), *_qa_records()]
    expected_paths = set(written)
    unexpected = set(RECORDS_DIR.glob("*.json")) - expected_paths
    if unexpected:
        raise RuntimeError(
            f"unexpected golden records remain: {sorted(str(p) for p in unexpected)}"
        )
    print(f"golden records: {len(written)}")
    print("split: 50 bills, 30 site assessments, 30 emails, 25 answerable QA, 15 unanswerable QA")


if __name__ == "__main__":
    main()
