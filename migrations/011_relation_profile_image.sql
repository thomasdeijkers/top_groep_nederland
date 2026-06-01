ALTER TABLE relations
    ADD COLUMN IF NOT EXISTS photo_filename TEXT,
    ADD COLUMN IF NOT EXISTS photo_path TEXT;
