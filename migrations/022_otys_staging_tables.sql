CREATE TABLE IF NOT EXISTS otys_candidates (
    id SERIAL PRIMARY KEY,
    otys_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    first_name TEXT,
    last_name TEXT,
    email TEXT,
    phone TEXT,
    mobile_phone TEXT,
    address TEXT,
    postal_code TEXT,
    city TEXT,
    country TEXT,
    status TEXT,
    raw_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    synced_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

ALTER TABLE otys_candidates
    ADD COLUMN IF NOT EXISTS entry_date_time TEXT;

ALTER TABLE otys_candidates
    ADD COLUMN IF NOT EXISTS address TEXT,
    ADD COLUMN IF NOT EXISTS postal_code TEXT,
    ADD COLUMN IF NOT EXISTS country TEXT;

CREATE INDEX IF NOT EXISTS idx_otys_candidates_name
    ON otys_candidates (name);

CREATE INDEX IF NOT EXISTS idx_otys_candidates_status
    ON otys_candidates (status);

ALTER TABLE otys_contacts
    ADD COLUMN IF NOT EXISTS first_name TEXT,
    ADD COLUMN IF NOT EXISTS last_name TEXT,
    ADD COLUMN IF NOT EXISTS mobile_phone TEXT,
    ADD COLUMN IF NOT EXISTS status TEXT,
    ADD COLUMN IF NOT EXISTS relation_name TEXT;

CREATE TABLE IF NOT EXISTS otys_vacancies (
    id SERIAL PRIMARY KEY,
    otys_id TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    reference_number TEXT,
    status TEXT,
    owner TEXT,
    relation_otys_id TEXT,
    relation_name TEXT,
    location TEXT,
    publication_status TEXT,
    applicant_count INTEGER NOT NULL DEFAULT 0,
    raw_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    synced_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

ALTER TABLE otys_vacancies
    ADD COLUMN IF NOT EXISTS entry_date_time TEXT;

CREATE INDEX IF NOT EXISTS idx_otys_vacancies_title
    ON otys_vacancies (title);

CREATE INDEX IF NOT EXISTS idx_otys_vacancies_status
    ON otys_vacancies (status);

CREATE TABLE IF NOT EXISTS otys_raw_records (
    id SERIAL PRIMARY KEY,
    record_type TEXT NOT NULL,
    otys_id TEXT NOT NULL,
    display_name TEXT,
    raw_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    synced_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    UNIQUE (record_type, otys_id)
);

CREATE INDEX IF NOT EXISTS idx_otys_raw_records_type
    ON otys_raw_records (record_type);

CREATE INDEX IF NOT EXISTS idx_otys_raw_records_display_name
    ON otys_raw_records (display_name);
