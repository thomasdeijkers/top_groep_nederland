CREATE TABLE IF NOT EXISTS vacancies (
    id SERIAL PRIMARY KEY,
    external_id TEXT UNIQUE,
    title TEXT NOT NULL,
    reference_number TEXT,
    status TEXT,
    owner TEXT,
    relation_name TEXT,
    location TEXT,
    publication_status TEXT NOT NULL DEFAULT 'concept',
    website_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    indeed_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    applicant_count INTEGER NOT NULL DEFAULT 0,
    raw_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    imported_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vacancies_title
    ON vacancies (title);

CREATE INDEX IF NOT EXISTS idx_vacancies_status
    ON vacancies (status);

CREATE INDEX IF NOT EXISTS idx_vacancies_publication_status
    ON vacancies (publication_status);
