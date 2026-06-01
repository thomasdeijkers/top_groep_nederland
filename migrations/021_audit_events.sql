CREATE TABLE IF NOT EXISTS audit_events (
    id SERIAL PRIMARY KEY,
    actor_name TEXT NOT NULL DEFAULT 'Admin',
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id INTEGER,
    entity_label TEXT,
    description TEXT,
    status TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_events_created_at
    ON audit_events (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_audit_events_entity
    ON audit_events (entity_type, entity_id);

INSERT INTO audit_events (
    actor_name,
    action,
    entity_type,
    entity_label,
    description,
    status,
    created_at
)
SELECT
    'Admin',
    'Auditspoor geactiveerd',
    'dashboard',
    'Auditspoor',
    'Vanaf dit moment worden dashboardacties als auditregels opgeslagen.',
    'Systeem',
    NOW()
WHERE NOT EXISTS (
    SELECT 1
    FROM audit_events
    WHERE action = 'Auditspoor geactiveerd'
      AND entity_type = 'dashboard'
);
