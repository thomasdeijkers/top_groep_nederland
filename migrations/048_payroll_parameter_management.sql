WITH parameter_seed(parameter_key, name, category, unit, value_type, applies_to, source_reference, description) AS (
    VALUES
        ('vacation_days_18_plus', 'Vakantiedagen 18+', 'reservering', 'dagen', 'decimal', 'both', 'Cao 3.1 / Leeswijzer tabel Grondslag', 'Wettelijke vakantiedagen; naar rato bij deeltijd of deeljaar.'),
        ('rv_days_build', 'Roostervrij bouwplaats', 'reservering', 'dagen', 'decimal', 'build', 'Cao 3.2 / Leeswijzer tabel Grondslag', 'ADV/RV dagen voor bouwplaats.'),
        ('rv_days_uta', 'Roostervrij UTA', 'reservering', 'dagen', 'decimal', 'uta', 'Cao 3.2 / Leeswijzer tabel Grondslag', 'ADV/RV dagen voor UTA.'),
        ('training_reservation_days', 'Reservering scholing', 'reservering', 'dagen', 'decimal', 'both', 'Cao 4.14 / Leeswijzer tabel Grondslag', 'Apart gereserveerde scholingsdagen.'),
        ('training_reservation_percent', 'Reservering scholing percentage', 'reservering', 'percentage', 'decimal', 'both', 'Cao 4.14 / Leeswijzer tabel Grondslag', 'Scholingspercentage dat los van DI wordt gereserveerd.'),
        ('travel_hour_rate_build_low', 'Reisuur bouwplaats laag', 'reiskosten', 'euro_per_uur', 'money', 'build', 'Cao 5.10 / Leeswijzer tabel Grondslag', 'Bruto reisuurvergoeding laagste functiegroep.'),
        ('travel_hour_rate_build_high', 'Reisuur bouwplaats hoog', 'reiskosten', 'euro_per_uur', 'money', 'build', 'Cao 5.10 / Leeswijzer tabel Grondslag', 'Bruto reisuurvergoeding hoogste genoemde bandbreedte.'),
        ('s3_shoes_annual', 'S3-schoenen declarabel', 'vergoeding', 'euro_per_jaar', 'money', 'both', 'Leeswijzer tabel Grondslag', 'Jaarlijks declarabel bedrag voor S3-schoenen.'),
        ('individual_budget_percent', 'Individueel budget', 'compensatie', 'percentage', 'decimal', 'both', 'Cao 4.14 / bijlage 4.2', 'IB-percentage inclusief DI en scholing waar van toepassing.'),
        ('public_holidays_per_year', 'Feestdagen per jaar', 'grondslag', 'dagen', 'integer', 'both', 'Leeswijzer tabel Grondslag', 'Aantal erkende feestdagen voor netto werkbare dagen.'),
        ('net_workable_days_per_year', 'Netto werkbare dagen per jaar', 'grondslag', 'dagen', 'integer', 'both', 'Leeswijzer tabel Grondslag', 'Werkdagen minus feestdagen.')
)
INSERT INTO payroll_parameters (
    parameter_key, name, category, unit, value_type, applies_to, source_reference, description
)
SELECT parameter_key, name, category, unit, value_type, applies_to, source_reference, description
FROM parameter_seed
ON CONFLICT (parameter_key)
DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    unit = EXCLUDED.unit,
    value_type = EXCLUDED.value_type,
    applies_to = EXCLUDED.applies_to,
    source_reference = EXCLUDED.source_reference,
    description = EXCLUDED.description,
    updated_at = NOW();

WITH version_seed(parameter_key, year, period_number, build_value, uta_value, source_reference, notes) AS (
    VALUES
        ('vacation_days_18_plus', 2026, 1, 20, 20, 'Cao 3.1', 'Standaardwaarde uit blauwdruk.'),
        ('rv_days_build', 2026, 1, 20, NULL, 'Cao 3.2', 'Bouwplaats RV/ADV-dagen.'),
        ('rv_days_uta', 2026, 1, NULL, 15, 'Cao 3.2', 'UTA RV/ADV-dagen.'),
        ('training_reservation_days', 2026, 1, 2, 2, 'Cao 4.14', 'Scholing apart gereserveerd.'),
        ('training_reservation_percent', 2026, 1, 0.0077, 0.0077, 'Cao 4.14', '2 dagen / 261 werkdagen.'),
        ('travel_hour_rate_build_low', 2026, 1, 18.95, NULL, 'Cao 5.10', 'Functiegroep A.'),
        ('travel_hour_rate_build_high', 2026, 1, 20.02, NULL, 'Cao 5.10', 'Bandbreedte uit blauwdruk.'),
        ('s3_shoes_annual', 2026, 1, 125, 125, 'Leeswijzer tabel Grondslag', 'Eenmalig per jaar declarabel.'),
        ('individual_budget_percent', 2026, 1, 0.0451, 0.0230, 'Cao 4.14 / bijlage 4.2', 'Bouwplaats 4,51%; UTA 2,3%.'),
        ('public_holidays_per_year', 2026, 1, 6, 6, 'Leeswijzer tabel Grondslag', 'Erkende feestdagen.'),
        ('net_workable_days_per_year', 2026, 1, 255, 255, 'Leeswijzer tabel Grondslag', '261 werkdagen - 6 feestdagen.')
)
INSERT INTO payroll_parameter_versions (
    parameter_id, year, period_number, build_value, uta_value, source_reference, notes
)
SELECT p.id, v.year, v.period_number, v.build_value, v.uta_value, v.source_reference, v.notes
FROM version_seed v
JOIN payroll_parameters p ON p.parameter_key = v.parameter_key
ON CONFLICT (parameter_id, year, period_number)
DO UPDATE SET
    build_value = EXCLUDED.build_value,
    uta_value = EXCLUDED.uta_value,
    source_reference = EXCLUDED.source_reference,
    notes = EXCLUDED.notes,
    updated_at = NOW();
