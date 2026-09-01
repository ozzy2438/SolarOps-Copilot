-- 0004_audit.sql — the audit log and evaluation/incident tables.
-- Owned by Phase 1. This table's columns are the AuditRecord contract
-- (voltdesk/contracts/audit.py). Changing one without the other loses data silently.

CREATE TABLE IF NOT EXISTS app.model_calls (
    call_id                     TEXT PRIMARY KEY,
    occurred_at                 TIMESTAMPTZ NOT NULL,
    task_type                   TEXT NOT NULL,
    provider                    TEXT NOT NULL CHECK (provider IN ('anthropic', 'openai')),
    model_id                    TEXT NOT NULL,
    routing_strategy            TEXT NOT NULL,
    routing_rationale           TEXT NOT NULL,
    prompt_version_hash         CHAR(64) NOT NULL,
    input_tokens                INTEGER NOT NULL CHECK (input_tokens >= 0),
    output_tokens               INTEGER NOT NULL CHECK (output_tokens >= 0),
    cache_read_input_tokens     INTEGER NOT NULL DEFAULT 0,
    cache_creation_input_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd                    NUMERIC(12, 6) NOT NULL CHECK (cost_usd >= 0),
    latency_ms                  INTEGER NOT NULL CHECK (latency_ms >= 0),
    outcome                     TEXT NOT NULL CHECK (outcome IN (
                                    'success', 'schema_invalid', 'provider_error',
                                    'timeout', 'refusal', 'circuit_open')),
    error_message               TEXT,
    retry_count                 INTEGER NOT NULL DEFAULT 0,
    -- False here on a call that carried customer data is an incident, not a metric.
    redaction_applied           BOOLEAN NOT NULL,
    redacted_entity_counts      JSONB NOT NULL DEFAULT '{}'::jsonb,
    document_id                 TEXT,
    query_id                    TEXT
);

CREATE INDEX IF NOT EXISTS model_calls_time_idx ON app.model_calls (occurred_at DESC);
CREATE INDEX IF NOT EXISTS model_calls_task_model_idx
    ON app.model_calls (task_type, model_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS model_calls_document_idx ON app.model_calls (document_id)
    WHERE document_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS app.evaluation_runs (
    run_id                TEXT PRIMARY KEY,
    started_at            TIMESTAMPTZ NOT NULL,
    finished_at           TIMESTAMPTZ,
    provider              TEXT NOT NULL,
    model_id              TEXT NOT NULL,
    git_sha               TEXT NOT NULL,
    record_count          INTEGER NOT NULL CHECK (record_count >= 0),
    exact_match_rate      REAL,
    field_precision       REAL,
    field_recall          REAL,
    citation_correctness  REAL,
    abstention_precision  REAL,
    abstention_recall     REAL,
    p50_latency_ms        INTEGER,
    p95_latency_ms        INTEGER,
    total_cost_usd        NUMERIC(12, 6),
    results               JSONB NOT NULL DEFAULT '[]'::jsonb
);

CREATE INDEX IF NOT EXISTS evaluation_runs_model_idx
    ON app.evaluation_runs (model_id, started_at DESC);

-- The written incident log. A portfolio claim of production operation is only
-- credible with one, so it is a table from Phase 1 rather than a Phase 4 afterthought.
CREATE TABLE IF NOT EXISTS app.incidents (
    id            TEXT PRIMARY KEY,
    opened_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at   TIMESTAMPTZ,
    severity      TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high')),
    title         TEXT NOT NULL,
    summary       TEXT NOT NULL,
    -- What actually went wrong, not what was reported.
    root_cause    TEXT,
    remediation   TEXT,
    related_call_ids TEXT[] NOT NULL DEFAULT '{}'
);
