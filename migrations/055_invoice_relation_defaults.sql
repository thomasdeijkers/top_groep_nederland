ALTER TABLE relations ADD COLUMN IF NOT EXISTS invoice_obs_number TEXT;
ALTER TABLE relations ADD COLUMN IF NOT EXISTS invoice_payment_method TEXT;
ALTER TABLE relations ADD COLUMN IF NOT EXISTS invoice_customer_number TEXT;

WITH source(name, hourly_rate, obs_number, payment_method, note) AS (
    VALUES
        ('Matko Medic', '56.50', '19008', 'incasso', ''),
        ('Marco Sloos', '57.50', '84001', 'incasso', 'mail'),
        ('Aad Bouter', '54.50', '25046', 'incasso', ''),
        ('Glen Belle', '56.50', '31016', 'incasso', ''),
        ('Eric de Jong', '67.50', '32007', 'incasso', ''),
        ('Mike Lagerwaard', '54.50', '30066', 'incasso', ''),
        ('Rene de Gelder', '54.50', '25030', 'geen_incasso', 'Let op: EUR 8,50 doorbelasten in plaats van incasso'),
        ('Sam Pietersz', '54.50', '30025', 'incasso', ''),
        ('Cor Loubout', '59.95', '25026', 'incasso', ''),
        ('Michael ten Velden', '56.50', '20002', 'incasso', ''),
        ('Stefan Groenewegen', '58.50', '27111', 'incasso', ''),
        ('Bart ter Haar', '58.50', '31015', 'incasso', ''),
        ('Ygor Mathilda', '58.50', '11003', 'incasso', ''),
        ('Swensley Millac', '58.50', '25036', 'incasso', 'mail'),
        ('Ruwan Pannebakker', '56.50', '23002', 'incasso', ''),
        ('Marcin Milewski', '55.50', '31011', 'incasso', ''),
        ('Leroy van Wijngaarden', '54.50', '31012', 'geen_incasso', 'Let op: EUR 8,50 doorbelasten in plaats van incasso'),
        ('Xavier Frauenfelder', '56.50', '25035', 'incasso', ''),
        ('Jon Tucker', '56.50', '24012', 'incasso', ''),
        ('Wim van den Berg', '57.50', '25044', 'incasso', ''),
        ('Patrick Flips', '56.50', '33025', 'incasso', ''),
        ('Marshall Luciano', '53.95', '32029', 'incasso', ''),
        ('Tom Radecke', '54.50', '43004', 'factoring', 'Pronkert Factoring'),
        ('Marten Beswerda', '54.50', '26007', 'factoring', 'Pronkert Factoring'),
        ('Ramazan Canbolat', '55.50', '13002', 'factoring', 'Pronkert Factoring'),
        ('Zeki Uygun', '55.50', '15005', 'factoring', 'Pronkert Factoring'),
        ('Przem Penck', '56.50', '11010', 'factoring', 'Pronkert Factoring')
), updated AS (
    UPDATE relations r
    SET hourly_rate = s.hourly_rate,
        invoice_obs_number = s.obs_number,
        invoice_payment_method = s.payment_method,
        notes = CASE WHEN s.note <> '' THEN s.note ELSE COALESCE(r.notes, '') END,
        updated_at = NOW()
    FROM source s
    WHERE r.relation_type = 'candidate' AND LOWER(r.name) = LOWER(s.name)
    RETURNING r.id
)
INSERT INTO relations (relation_type, name, hourly_rate, invoice_obs_number, invoice_payment_method, notes, status, source)
SELECT 'candidate', s.name, s.hourly_rate, s.obs_number, s.payment_method, s.note, 'Actief', 'facturatie-overzicht'
FROM source s
WHERE NOT EXISTS (
    SELECT 1 FROM relations r WHERE r.relation_type = 'candidate' AND LOWER(r.name) = LOWER(s.name)
);

WITH source(name, customer_number) AS (
    VALUES
        ('Akerbouw B.V.', '1012'),
        ('B2 Restauratie B.V.', '2106'),
        ('Bouwbureau Bakels en Ouwerkerk B.V.', '2032'),
        ('Aannemingsbedrijf Holleman en Zonen Santpoort B.V.', '8048'),
        ('Jurriens West B.V.', '10016'),
        ('Koesr Projecten B.V.', '1010'),
        ('Koninklijke Woudenberg Ameide B.V.', '231001'),
        ('Nico de Bont', '14005'),
        ('Bouwonderneming Stout B.V.', '19013'),
        ('Van Wijk Vastgoedonderhoud B.V.', '23002')
), updated AS (
    UPDATE relations r
    SET invoice_customer_number = s.customer_number, updated_at = NOW()
    FROM source s
    WHERE r.relation_type = 'principal' AND LOWER(r.name) = LOWER(s.name)
    RETURNING r.id
)
INSERT INTO relations (relation_type, name, invoice_customer_number, status, source)
SELECT 'principal', s.name, s.customer_number, 'Actief', 'facturatie-overzicht'
FROM source s
WHERE NOT EXISTS (
    SELECT 1 FROM relations r WHERE r.relation_type = 'principal' AND LOWER(r.name) = LOWER(s.name)
);
