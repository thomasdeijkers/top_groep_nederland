CREATE TABLE IF NOT EXISTS candidates (
    id SERIAL PRIMARY KEY,
    external_id TEXT UNIQUE,
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    city TEXT,
    status TEXT,
    source TEXT,
    created_external_at DATE,
    motivation TEXT,
    raw_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    imported_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_candidates_name
    ON candidates (name);

CREATE INDEX IF NOT EXISTS idx_candidates_status
    ON candidates (status);

CREATE TABLE IF NOT EXISTS principals (
    id SERIAL PRIMARY KEY,
    external_id TEXT UNIQUE,
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    website TEXT,
    city TEXT,
    status TEXT,
    source TEXT,
    raw_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    imported_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_principals_name
    ON principals (name);

CREATE INDEX IF NOT EXISTS idx_principals_status
    ON principals (status);

CREATE TABLE IF NOT EXISTS tickets (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    sender_name TEXT,
    sender_email TEXT,
    sender_phone TEXT,
    channel TEXT NOT NULL DEFAULT 'manual',
    status TEXT NOT NULL DEFAULT 'nieuw',
    priority TEXT NOT NULL DEFAULT 'normaal',
    category TEXT,
    body TEXT,
    raw_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tickets_status
    ON tickets (status);

CREATE INDEX IF NOT EXISTS idx_tickets_channel
    ON tickets (channel);
