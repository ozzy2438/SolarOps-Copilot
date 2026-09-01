"""Knowledge Q&A routes backed only by the licensed Tier A corpus."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from voltdesk.contracts.retrieval import RetrievalAnswer, RetrievalQuery
from voltdesk.db.session import get_engine
from voltdesk.retrieval.abstention import answer_with_evidence
from voltdesk.retrieval.search import retrieve

router = APIRouter(prefix="/qa", tags=["qa"])

@router.post("/ask", response_model=RetrievalAnswer)
def ask(query: RetrievalQuery) -> RetrievalAnswer:
    """Answer a staff question with citations, or abstain explicitly.

    An abstention is a 200, not an error: the system did its job.
    """
    return answer_with_evidence(query, retrieve(query))


def _read_corpus_stats() -> dict[str, object]:
    statement = text(
        "SELECT d.source, COUNT(DISTINCT d.id) AS documents, "
        "COUNT(c.chunk_id) AS chunks "
        "FROM vec.corpus_documents AS d "
        "LEFT JOIN vec.chunks AS c ON c.document_id = d.id "
        "GROUP BY d.source ORDER BY d.source"
    )
    with get_engine().connect() as connection:
        rows = connection.execute(statement).mappings().all()
    by_source = [
        {
            "source": row["source"],
            "documents": int(row["documents"]),
            "chunks": int(row["chunks"]),
        }
        for row in rows
    ]
    return {
        "documents": sum(item["documents"] for item in by_source),
        "chunks": sum(item["chunks"] for item in by_source),
        "by_source": by_source,
    }


@router.get("/corpus/stats")
def corpus_stats() -> dict[str, object]:
    """Chunk and document counts per corpus source."""
    return _read_corpus_stats()
