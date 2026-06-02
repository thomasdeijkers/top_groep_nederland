CREATE TABLE IF NOT EXISTS otys_api_usage_events (
    id SERIAL PRIMARY KEY,
    service TEXT,
    method TEXT NOT NULL,
    request_id INTEGER,
    status_code INTEGER,
    duration_ms INTEGER,
    rate_limit_blocked TEXT,
    rate_limit_remaining_timeframe INTEGER,
    rate_limit_requests_remaining INTEGER,
    error TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_otys_api_usage_created_at
    ON otys_api_usage_events (created_at);

CREATE INDEX IF NOT EXISTS idx_otys_api_usage_service
    ON otys_api_usage_events (service, method);
