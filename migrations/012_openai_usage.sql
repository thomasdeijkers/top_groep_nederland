CREATE TABLE IF NOT EXISTS openai_usage_events (
    id SERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    source_id INTEGER,
    model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    cached_input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    estimated_cost_usd NUMERIC(12, 6) NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_openai_usage_source
    ON openai_usage_events (source, source_id);

CREATE INDEX IF NOT EXISTS idx_openai_usage_created_at
    ON openai_usage_events (created_at);
