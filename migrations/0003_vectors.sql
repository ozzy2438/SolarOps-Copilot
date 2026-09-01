-- 0003_vectors.sql — corpus chunks and their embeddings.
-- Owned by Phase 1 (shape); Phase 3 chooses the embedding model and must set the
-- vector dimension below to match it.

CREATE TABLE IF NOT EXISTS vec.corpus_documents (
    id             TEXT PRIMARY KEY,
    title          TEXT NOT NULL,
    source         TEXT NOT NULL CHECK (source IN (
                       'cec_approved_list', 'manufacturer_datasheet',
                       'dnsp_connection_guideline', 'regulator_methodology',
                       'rebate_program_doc', 'internal_standard')),
    source_url     TEXT,
    -- Licence must be recorded before ingestion. A NULL here means the document had
    -- no verified licence and should not have been ingested; see docs/DATA_SOURCES.md.
    licence        TEXT,
    retrieved_at   TIMESTAMPTZ,
    sha256         CHAR(64) NOT NULL,
    ingested_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS vec.chunks (
    chunk_id      TEXT PRIMARY KEY,
    document_id   TEXT NOT NULL REFERENCES vec.corpus_documents (id) ON DELETE CASCADE,
    text          TEXT NOT NULL,
    page          INTEGER CHECK (page IS NULL OR page >= 1),
    section_path  TEXT[] NOT NULL DEFAULT '{}',
    token_count   INTEGER NOT NULL CHECK (token_count > 0)
);

CREATE INDEX IF NOT EXISTS chunks_document_idx ON vec.chunks (document_id);
-- Lexical search alongside vector search: staff ask about clause numbers and model
-- numbers, which embeddings blur. See voltdesk/retrieval/search.py.
CREATE INDEX IF NOT EXISTS chunks_text_fts_idx
    ON vec.chunks USING GIN (to_tsvector('english', text));

-- TODO(verify): 1536 is a placeholder dimension. Phase 3 sets this to the chosen
-- embedding model's dimension and records the choice as an ADR. A mismatch here
-- fails loudly on insert, which is the intended behaviour.
CREATE TABLE IF NOT EXISTS vec.embeddings (
    chunk_id            TEXT PRIMARY KEY REFERENCES vec.chunks (chunk_id) ON DELETE CASCADE,
    -- Which model produced this vector. A corpus embedded with two models is
    -- silently unusable; recording the model is the only defence.
    embedding_model_id  TEXT NOT NULL,
    dimension           INTEGER NOT NULL,
    embedding           vector(1536) NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS embeddings_model_idx ON vec.embeddings (embedding_model_id);
