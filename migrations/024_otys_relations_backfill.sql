INSERT INTO relations (
    relation_type, external_id, name, first_name, last_name, email, phone,
    address, street, postal_code, city, country, status, source, raw_data,
    imported_at, created_at, updated_at
)
SELECT
    'candidate',
    otys_id,
    name,
    first_name,
    last_name,
    email,
    COALESCE(NULLIF(mobile_phone, ''), phone, ''),
    address,
    address,
    postal_code,
    city,
    country,
    COALESCE(NULLIF(status, ''), 'OTYS'),
    'otys',
    raw_data,
    synced_at,
    COALESCE(created_at, NOW()),
    COALESCE(updated_at, NOW())
FROM otys_candidates
WHERE COALESCE(otys_id, '') <> ''
  AND COALESCE(name, '') <> ''
ON CONFLICT (relation_type, external_id)
WHERE external_id IS NOT NULL
DO UPDATE SET
    name = EXCLUDED.name,
    first_name = EXCLUDED.first_name,
    last_name = EXCLUDED.last_name,
    email = EXCLUDED.email,
    phone = EXCLUDED.phone,
    address = EXCLUDED.address,
    street = EXCLUDED.street,
    postal_code = EXCLUDED.postal_code,
    city = EXCLUDED.city,
    country = EXCLUDED.country,
    status = EXCLUDED.status,
    source = EXCLUDED.source,
    raw_data = EXCLUDED.raw_data,
    imported_at = EXCLUDED.imported_at,
    updated_at = EXCLUDED.updated_at;

INSERT INTO relations (
    relation_type, external_id, name, email, phone, website, city,
    status, source, raw_data, imported_at, created_at, updated_at
)
SELECT
    'principal',
    otys_id,
    name,
    email,
    phone,
    website,
    city,
    'OTYS',
    'otys',
    raw_data,
    synced_at,
    COALESCE(created_at, NOW()),
    COALESCE(updated_at, NOW())
FROM otys_organizations
WHERE COALESCE(otys_id, '') <> ''
  AND COALESCE(name, '') <> ''
ON CONFLICT (relation_type, external_id)
WHERE external_id IS NOT NULL
DO UPDATE SET
    name = EXCLUDED.name,
    email = EXCLUDED.email,
    phone = EXCLUDED.phone,
    website = EXCLUDED.website,
    city = EXCLUDED.city,
    status = EXCLUDED.status,
    source = EXCLUDED.source,
    raw_data = EXCLUDED.raw_data,
    imported_at = EXCLUDED.imported_at,
    updated_at = EXCLUDED.updated_at;
