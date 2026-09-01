-- 0001_init.sql — schemas, extensions, and the document/extraction tables.
-- Owned by Phase 1. Plain SQL, applied in filename order (see migrations/README.md).

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- One database, two schemas. `app` is application data; `vec` is vector storage.
-- The split exists so that a corpus re-embed can truncate `vec` without touching
-- anything operational.
CREATE SCHEMA IF NOT EXISTS app;
CREATE SCHEMA IF NOT EXISTS vec;

CREATE TABLE IF NOT EXISTS app.documents (
    id              TEXT PRIMARY KEY,
    document_type   TEXT NOT NULL
        CHECK (document_type IN ('electricity_bill', 'site_assessment', 'email_thread')),
    filename        TEXT NOT NULL,
    sha256          CHAR(64) NOT NULL,
    -- 'A' = real and publicly sourced, 'B' = synthetic. See docs/DATA_SOURCES.md.
    -- A synthetic document must never be reportable as real, so the tier is a column,
    -- not a naming convention.
    tier            CHAR(1) NOT NULL CHECK (tier IN ('A', 'B')),
    byte_size       INTEGER NOT NULL CHECK (byte_size > 0),
    received_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    parsed_at       TIMESTAMPTZ,
    status          TEXT NOT NULL DEFAULT 'received'
        CHECK (status IN ('received', 'parsing', 'parsed', 'extracting', 'extracted',
                          'written', 'failed')),
    error_message   TEXT
);

-- Re-submitting the same bytes must not create a second document.
CREATE UNIQUE INDEX IF NOT EXISTS documents_sha256_key ON app.documents (sha256);
CREATE INDEX IF NOT EXISTS documents_status_idx ON app.documents (status, received_at DESC);

CREATE TABLE IF NOT EXISTS app.extractions (
    id                  TEXT PRIMARY KEY,
    document_id         TEXT NOT NULL REFERENCES app.documents (id) ON DELETE CASCADE,
    document_type       TEXT NOT NULL,
    -- The validated contract instance, as produced by Phase 2.
    payload             JSONB NOT NULL,
    -- Lowest per-field confidence in the payload. Denormalised because the review
    -- and metrics queries filter on it constantly.
    min_confidence      REAL NOT NULL CHECK (min_confidence >= 0 AND min_confidence <= 1),
    model_id            TEXT NOT NULL,
    prompt_version_hash CHAR(64) NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Set once the extraction has been written to the CRM.
    crm_written_at      TIMESTAMPTZ,
    crm_external_key    TEXT
);

CREATE INDEX IF NOT EXISTS extractions_document_idx ON app.extractions (document_id);
CREATE INDEX IF NOT EXISTS extractions_confidence_idx ON app.extractions (min_confidence);
