-- 0002_review.sql — the human review queue.
-- Owned by Phase 1; populated by Phase 2.

CREATE TABLE IF NOT EXISTS app.review_queue (
    review_id     TEXT PRIMARY KEY,
    document_id   TEXT NOT NULL REFERENCES app.documents (id) ON DELETE CASCADE,
    document_type TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'pending_review'
        CHECK (status IN ('auto_applied', 'pending_review', 'approved', 'rejected')),
    -- True when nothing may be written to the CRM until this is resolved.
    blocking      BOOLEAN NOT NULL DEFAULT FALSE,
    fields        JSONB NOT NULL,
    corrections   JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at   TIMESTAMPTZ,
    resolved_by   TEXT,

    -- A resolved item must record who resolved it and when. Enforced here rather
    -- than in application code because the audit story depends on it.
    CONSTRAINT review_resolution_complete CHECK (
        (status IN ('pending_review') AND resolved_at IS NULL AND resolved_by IS NULL)
        OR (status <> 'pending_review')
    )
);

CREATE INDEX IF NOT EXISTS review_pending_idx
    ON app.review_queue (status, created_at)
    WHERE status = 'pending_review';

-- One open review per document. A second one means the extraction ran twice.
CREATE UNIQUE INDEX IF NOT EXISTS review_one_open_per_document
    ON app.review_queue (document_id)
    WHERE status = 'pending_review';
