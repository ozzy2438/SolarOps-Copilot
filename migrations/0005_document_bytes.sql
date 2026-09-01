-- 0005_document_bytes.sql — store inbound file bytes next to the document row.
-- Owned by Phase 2. app.documents in 0001 has sha256 and byte_size but no payload;
-- api and worker share Postgres, so the bytes live here rather than on a host volume.
-- Phase 3 must number vector-dimension changes 0006 or later.

ALTER TABLE app.documents
    ADD COLUMN IF NOT EXISTS content BYTEA;
