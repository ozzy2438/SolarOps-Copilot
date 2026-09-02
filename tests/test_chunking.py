"""Structure-aware corpus chunking. Owned by Phase 3."""

from __future__ import annotations

from voltdesk.contracts.common import DocumentType
from voltdesk.contracts.retrieval import CorpusSource
from voltdesk.ingestion.chunking import chunk_document
from voltdesk.parsers.base import ParsedDocument, ParsedPage


def _document(text: str, *, tables: list[list[list[str]]] | None = None) -> ParsedDocument:
    return ParsedDocument(
        document_id="guideline-1",
        document_type=DocumentType.SITE_ASSESSMENT,
        sha256="a" * 64,
        pages=[ParsedPage(page_number=1, text=text, tables=tables or [])],
    )


def test_numbered_clause_is_never_split_and_section_path_is_populated() -> None:
    clause = (
        "5.3 Export limit\n"
        "The system must not export more than the connection agreement permits. "
        "This sentence remains with the numbered clause even beyond the target."
    )
    chunks = chunk_document(
        _document(f"# Connection guide\n\n{clause}\n\n5.4 Commissioning\nRecord tests."),
        target_tokens=5,
        source=CorpusSource.DNSP_CONNECTION_GUIDELINE,
        document_title="Connection guide",
    )

    containing = [chunk for chunk in chunks if "5.3 Export limit" in chunk.text]
    assert len(containing) == 1
    assert clause in containing[0].text
    assert containing[0].token_count > 5
    assert containing[0].section_path[-1] == "5.3 Export limit"
    assert all(chunk.section_path for chunk in chunks)


def test_markdown_table_stays_intact_even_when_oversized() -> None:
    table = (
        "| Model | Maximum output | Standard |\n"
        "|---|---:|---|\n"
        "| Symo 20.0-3-M | 20 kVA | AS/NZS 4777.2 |\n"
        "| Symo 15.0-3-M | 15 kVA | AS/NZS 4777.2 |"
    )
    chunks = chunk_document(
        _document(f"## 4. Approved inverters\n\n{table}\n\n## 5. Installation\nFollow manual."),
        target_tokens=3,
        source=CorpusSource.MANUFACTURER_DATASHEET,
        document_title="Datasheet",
    )

    table_chunks = [chunk for chunk in chunks if "Symo 20.0-3-M" in chunk.text]
    assert len(table_chunks) == 1
    assert table in table_chunks[0].text
    assert table_chunks[0].section_path == ["4. Approved inverters"]


def test_extracted_pdf_table_is_one_separate_chunk() -> None:
    table = [["Requirement", "Value"], ["Export limit", "5 kW"]]
    chunks = chunk_document(_document("# Guide\n\nGeneral text.", tables=[table]))

    table_chunks = [chunk for chunk in chunks if "Requirement | Value" in chunk.text]
    assert len(table_chunks) == 1
    assert table_chunks[0].text == "Requirement | Value\nExport limit | 5 kW"
