"""Corpus ingestion. Owned by Phase 3."""

from voltdesk.ingestion.chunking import chunk_document
from voltdesk.ingestion.corpus import ingest_path
from voltdesk.ingestion.embeddings import Embedder, store_chunks

__all__ = ["Embedder", "chunk_document", "ingest_path", "store_chunks"]
