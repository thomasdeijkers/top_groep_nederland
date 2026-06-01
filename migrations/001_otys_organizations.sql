CREATE TABLE IF NOT EXISTS otys_organizations (
    id SERIAL PRIMARY KEY,
    otys_id TEXT NOT NULL UNIQUE,
    organization_type TEXT NOT NULL,
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    website TEXT,
    city TEXT,
    raw_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    synced_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_otys_organizations_type
    ON otys_organizations (organization_type);

CREATE INDEX IF NOT EXISTS idx_otys_organizations_name
    ON otys_organizations (name);

CREATE TABLE IF NOT EXISTS otys_contacts (
    id SERIAL PRIMARY KEY,
    otys_id TEXT NOT NULL UNIQUE,
    organization_otys_id TEXT,
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    raw_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    synced_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_otys_contacts_organization_otys_id
    ON otys_contacts (organization_otys_id);
