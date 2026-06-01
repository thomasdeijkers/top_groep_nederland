CREATE TABLE IF NOT EXISTS relations (
    id SERIAL PRIMARY KEY,
    relation_type TEXT NOT NULL CHECK (relation_type IN ('candidate', 'principal')),
    legacy_table TEXT,
    legacy_id INTEGER,
    external_id TEXT,
    name TEXT NOT NULL,
    first_name TEXT,
    last_name TEXT,
    contact_name TEXT,
    email TEXT,
    phone TEXT,
    website TEXT,
    address TEXT,
    postal_code TEXT,
    city TEXT,
    country TEXT,
    status TEXT,
    source TEXT,
    owner TEXT,
    availability TEXT,
    hourly_rate TEXT,
    kvk_number TEXT,
    vat_number TEXT,
    birth_date DATE,
    motivation TEXT,
    notes TEXT,
    raw_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    imported_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_relations_legacy
    ON relations (legacy_table, legacy_id)
    WHERE legacy_table IS NOT NULL AND legacy_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_relations_external
    ON relations (relation_type, external_id)
    WHERE external_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_relations_type
    ON relations (relation_type);

CREATE INDEX IF NOT EXISTS idx_relations_name
    ON relations (name);

CREATE INDEX IF NOT EXISTS idx_relations_status
    ON relations (status);

INSERT INTO relations (
    relation_type, legacy_table, legacy_id, external_id, name, first_name,
    last_name, email, phone, address, postal_code, city, country, status,
    source, owner, availability, hourly_rate, birth_date, motivation, notes,
    raw_data, imported_at, created_at, updated_at
)
SELECT
    'candidate', 'candidates', id, external_id, name, first_name,
    last_name, email, phone, address, postal_code, city, country, status,
    source, owner, availability, hourly_rate, birth_date, motivation, notes,
    raw_data, imported_at, created_at, updated_at
FROM candidates
ON CONFLICT (legacy_table, legacy_id)
WHERE legacy_table IS NOT NULL AND legacy_id IS NOT NULL
DO UPDATE SET
    external_id = EXCLUDED.external_id,
    name = EXCLUDED.name,
    first_name = EXCLUDED.first_name,
    last_name = EXCLUDED.last_name,
    email = EXCLUDED.email,
    phone = EXCLUDED.phone,
    address = EXCLUDED.address,
    postal_code = EXCLUDED.postal_code,
    city = EXCLUDED.city,
    country = EXCLUDED.country,
    status = EXCLUDED.status,
    source = EXCLUDED.source,
    owner = EXCLUDED.owner,
    availability = EXCLUDED.availability,
    hourly_rate = EXCLUDED.hourly_rate,
    birth_date = EXCLUDED.birth_date,
    motivation = EXCLUDED.motivation,
    notes = EXCLUDED.notes,
    raw_data = EXCLUDED.raw_data,
    imported_at = EXCLUDED.imported_at,
    updated_at = EXCLUDED.updated_at;

INSERT INTO relations (
    relation_type, legacy_table, legacy_id, external_id, name, contact_name,
    email, phone, website, address, postal_code, city, country, status,
    source, kvk_number, vat_number, notes, raw_data, imported_at, created_at,
    updated_at
)
SELECT
    'principal', 'principals', id, external_id, name, contact_name,
    email, phone, website, address, postal_code, city, country, status,
    source, kvk_number, vat_number, notes, raw_data, imported_at, created_at,
    updated_at
FROM principals
ON CONFLICT (legacy_table, legacy_id)
WHERE legacy_table IS NOT NULL AND legacy_id IS NOT NULL
DO UPDATE SET
    external_id = EXCLUDED.external_id,
    name = EXCLUDED.name,
    contact_name = EXCLUDED.contact_name,
    email = EXCLUDED.email,
    phone = EXCLUDED.phone,
    website = EXCLUDED.website,
    address = EXCLUDED.address,
    postal_code = EXCLUDED.postal_code,
    city = EXCLUDED.city,
    country = EXCLUDED.country,
    status = EXCLUDED.status,
    source = EXCLUDED.source,
    kvk_number = EXCLUDED.kvk_number,
    vat_number = EXCLUDED.vat_number,
    notes = EXCLUDED.notes,
    raw_data = EXCLUDED.raw_data,
    imported_at = EXCLUDED.imported_at,
    updated_at = EXCLUDED.updated_at;

ALTER TABLE whatsapp_timesheet_inbox
    ADD COLUMN IF NOT EXISTS matched_relation_id INTEGER REFERENCES relations(id) ON DELETE SET NULL;

UPDATE whatsapp_timesheet_inbox w
SET matched_relation_id = r.id
FROM relations r
WHERE w.matched_relation_id IS NULL
  AND w.matched_candidate_id = r.legacy_id
  AND r.legacy_table = 'candidates'
  AND r.relation_type = 'candidate';
