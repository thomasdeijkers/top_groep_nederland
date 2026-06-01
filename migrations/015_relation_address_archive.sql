ALTER TABLE relations
    ADD COLUMN IF NOT EXISTS street TEXT,
    ADD COLUMN IF NOT EXISTS house_number TEXT,
    ADD COLUMN IF NOT EXISTS house_number_addition TEXT,
    ADD COLUMN IF NOT EXISTS archived_at TIMESTAMP WITHOUT TIME ZONE;

UPDATE relations
SET street = address
WHERE street IS NULL
  AND COALESCE(address, '') <> '';

CREATE INDEX IF NOT EXISTS idx_relations_archived_at
    ON relations (archived_at);
