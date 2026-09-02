"""Corpus ingestion pipeline.

Owned by: Phase 3. See docs/PHASE_3.md.

Tier A only. Every corpus document must have a licence recorded in
docs/DATA_SOURCES.md before it is ingested; a document with an unverified source is
not ingested and its TODO stays open. Ingesting a document VoltDesk has no right to
redistribute is the one failure here that cannot be fixed by a later phase.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from voltdesk.contracts.common import DocumentType
from voltdesk.contracts.retrieval import Chunk, CorpusSource
from voltdesk.ingestion.chunking import chunk_document
from voltdesk.ingestion.embeddings import Embedder, store_chunks
from voltdesk.parsers.base import ParsedDocument, ParsedPage
from voltdesk.parsers.site_notes_parser import SiteNotesParser


@dataclass(frozen=True)
class CorpusManifestEntry:
    """One licence-reviewed file declared by a corpus manifest."""

    path: Path
    document_id: str
    title: str
    source: CorpusSource
    source_url: str
    licence: str | None
    retrieved_at: datetime


@dataclass(frozen=True)
class CorpusDocumentRecord:
    """Provenance written atomically with a document's chunks and embeddings."""

    document_id: str
    title: str
    source: CorpusSource
    source_url: str
    licence: str
    retrieved_at: datetime
    sha256: str


class CorpusStore(Protocol):
    """Persistence seam shared by the offline suite and PostgreSQL."""

    def contains_sha256(self, sha256: str) -> bool: ...

    def write(
        self,
        document: CorpusDocumentRecord,
        chunks: list[Chunk],
        vectors: list[list[float]],
        *,
        embedding_model_id: str,
        dimension: int,
    ) -> int: ...


class InMemoryCorpusStore:
    """Process-local corpus used only when VoltDesk has no configured database."""

    def __init__(self) -> None:
        self.documents: dict[str, CorpusDocumentRecord] = {}
        self.document_ids_by_sha256: dict[str, str] = {}
        self.chunks: dict[str, Chunk] = {}
        self.vectors: dict[str, list[float]] = {}
        self.embedding_model_id: str | None = None
        self.dimension: int | None = None

    def contains_sha256(self, sha256: str) -> bool:
        return sha256 in self.document_ids_by_sha256

    def write(
        self,
        document: CorpusDocumentRecord,
        chunks: list[Chunk],
        vectors: list[list[float]],
        *,
        embedding_model_id: str,
        dimension: int,
    ) -> int:
        if self.contains_sha256(document.sha256):
            return 0
        if len(chunks) != len(vectors):
            raise ValueError("one embedding is required for every chunk")
        if self.embedding_model_id not in {None, embedding_model_id}:
            raise ValueError("refusing to mix embedding models in one corpus")
        if self.dimension not in {None, dimension}:
            raise ValueError("refusing to mix embedding dimensions in one corpus")
        for vector in vectors:
            if len(vector) != dimension:
                raise ValueError(f"embedding dimension must be {dimension}")
        self.documents[document.document_id] = document
        self.document_ids_by_sha256[document.sha256] = document.document_id
        self.embedding_model_id = embedding_model_id
        self.dimension = dimension
        for chunk, vector in zip(chunks, vectors, strict=True):
            self.chunks[chunk.chunk_id] = chunk
            self.vectors[chunk.chunk_id] = vector
        return len(chunks)


_PROCESS_STORE = InMemoryCorpusStore()


def _default_store() -> CorpusStore:
    from voltdesk.config import get_settings

    if "not-configured" in get_settings().database_url:
        return _PROCESS_STORE
    from voltdesk.ingestion.embeddings import PostgresCorpusStore

    return PostgresCorpusStore()


def licence_is_verified(licence: str | None) -> bool:
    """A missing or explicitly unresolved licence can never pass the ingest gate."""
    if licence is None or not licence.strip():
        return False
    lowered = licence.casefold()
    return "todo(verify)" not in lowered and "unverified" not in lowered


def load_manifest(path: str | Path) -> list[CorpusManifestEntry]:
    """Load a manifest without hiding missing licences from the dry-run report."""
    requested = Path(path).resolve()
    manifest_path = requested / "manifest.json" if requested.is_dir() else requested
    root = manifest_path.parent.resolve()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    documents = payload.get("documents")
    if not isinstance(documents, list):
        raise ValueError("corpus manifest must contain a documents list")
    entries: list[CorpusManifestEntry] = []
    for raw in documents:
        if not isinstance(raw, dict):
            raise ValueError("each corpus manifest entry must be an object")
        document_path = (root / str(raw["path"])).resolve()
        if root not in document_path.parents:
            raise ValueError("corpus manifest paths must remain inside the manifest directory")
        entries.append(
            CorpusManifestEntry(
                path=document_path,
                document_id=str(raw["document_id"]),
                title=str(raw["title"]),
                source=CorpusSource(str(raw["source"])),
                source_url=str(raw["source_url"]),
                licence=str(raw["licence"]) if raw.get("licence") is not None else None,
                retrieved_at=datetime.fromisoformat(str(raw["retrieved_at"])),
            )
        )
    return entries


def _parse_tier_a(path: Path, document_id: str, sha256: str) -> ParsedDocument:
    content = path.read_bytes()
    if path.suffix.casefold() == ".pdf":
        return SiteNotesParser().parse(document_id, content, path.name)
    if path.suffix.casefold() not in {".md", ".txt"}:
        raise ValueError(f"unsupported Tier A corpus format: {path.suffix}")
    return ParsedDocument(
        document_id=document_id,
        document_type=DocumentType.SITE_ASSESSMENT,
        sha256=sha256,
        pages=[ParsedPage(page_number=1, text=content.decode("utf-8"))],
    )


def ingest_path(
    path: str,
    source: CorpusSource,
    document_title: str,
    *,
    source_url: str | None = None,
    licence: str | None = None,
    retrieved_at: datetime | None = None,
    document_id: str | None = None,
    embedder: Embedder | None = None,
    store: CorpusStore | None = None,
) -> int:
    """Parse, chunk, embed and store one corpus document. Returns chunks written."""
    if not licence_is_verified(licence):
        raise ValueError("a verified licence is required before corpus ingestion")
    assert licence is not None  # narrowed after the explicit licence gate above
    if not source_url:
        raise ValueError("source_url is required before corpus ingestion")
    if retrieved_at is None or retrieved_at.tzinfo is None:
        raise ValueError("a timezone-aware retrieved_at is required before corpus ingestion")
    corpus_path = Path(path).resolve()
    content = corpus_path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    selected_store = store or _default_store()
    if selected_store.contains_sha256(digest):
        return 0
    selected_id = document_id or f"corpus-{digest[:20]}"
    parsed = _parse_tier_a(corpus_path, selected_id, digest)
    chunks = chunk_document(parsed, source=source, document_title=document_title)
    if embedder is None:
        from voltdesk.ingestion.embeddings import default_embedder

        embedder = default_embedder()
    record = CorpusDocumentRecord(
        document_id=selected_id,
        title=document_title,
        source=source,
        source_url=source_url,
        licence=licence,
        retrieved_at=retrieved_at,
        sha256=digest,
    )
    return store_chunks(chunks, embedder, document=record, store=selected_store)
