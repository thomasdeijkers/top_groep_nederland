CREATE TABLE IF NOT EXISTS openai_api_audit_events (
    id SERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    source_id INTEGER,
    model TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    request_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    response_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    status_code INTEGER,
    error TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_openai_api_audit_source
    ON openai_api_audit_events (source, source_id);

CREATE INDEX IF NOT EXISTS idx_openai_api_audit_created_at
    ON openai_api_audit_events (created_at DESC);
