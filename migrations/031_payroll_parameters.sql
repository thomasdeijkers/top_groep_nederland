CREATE TABLE IF NOT EXISTS payroll_parameters (
    id SERIAL PRIMARY KEY,
    parameter_key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    unit TEXT NOT NULL,
    value_type TEXT NOT NULL DEFAULT 'decimal',
    applies_to TEXT NOT NULL DEFAULT 'both',
    source_reference TEXT,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS payroll_parameter_versions (
    id SERIAL PRIMARY KEY,
    parameter_id INTEGER NOT NULL REFERENCES payroll_parameters(id) ON DELETE CASCADE,
    year INTEGER,
    period_number INTEGER CHECK (period_number IS NULL OR period_number BETWEEN 1 AND 13),
    effective_from DATE,
    effective_until DATE,
    build_value NUMERIC(14,4),
    uta_value NUMERIC(14,4),
    text_value TEXT,
    source_reference TEXT,
    notes TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE (parameter_id, year, period_number)
);

CREATE INDEX IF NOT EXISTS idx_payroll_parameter_versions_period
    ON payroll_parameter_versions (year, period_number);

CREATE INDEX IF NOT EXISTS idx_payroll_parameters_category
    ON payroll_parameters (category, status);

WITH parameter_seed(parameter_key, name, category, unit, value_type, applies_to, source_reference, description) AS (
    VALUES
        ('working_days_per_year', 'Werkdagen per jaar', 'grondslag', 'dagen', 'integer', 'both', 'Leeswijzer 3.1 / Grondslag B50', 'Noemer voor reservering- en compensatiepercentages.'),
        ('holiday_allowance_percent', 'Vakantiegeldpercentage', 'grondslag', 'percentage', 'decimal', 'both', 'NBBU art. 36a', 'Periode-gebonden percentage; wijzigt van 8,33% naar 8%.'),
        ('health_insurance_4w', 'Zorgverzekeringsvergoeding per 4 weken', 'vergoeding', 'euro_per_4_weken', 'money', 'both', 'Cao 5.18 / Grondslag C31', 'Alleen toepassen bij kwalificerende polis per werknemer.'),
        ('travel_km_net_build', 'Reiskosten netto bouwplaats', 'reiskosten', 'euro_per_km', 'money', 'build', 'Leeswijzer 5.2 / Bijlage F', 'Netto vlak tarief voor alle kilometers bouwplaats.'),
        ('travel_km_gross_build', 'Reiskosten bruto bouwplaats', 'reiskosten', 'euro_per_km', 'money', 'build', 'Leeswijzer Bijlage F', 'Alleen tonen; Easyflex past bruto toe.'),
        ('travel_km_net_uta', 'Reiskosten netto UTA', 'reiskosten', 'euro_per_km', 'money', 'uta', 'Leeswijzer 5.2 / Bijlage F', 'Netto vlak tarief UTA; wijzigt vanaf periode 6.'),
        ('tool_allowance_carpenter_day', 'Handgereedschap timmerman', 'dagvergoeding', 'euro_per_dag', 'money', 'build', 'Cao 5.5', 'Netto GV per gewerkte dag, alleen voor passende functie.'),
        ('tool_allowance_mason_day', 'Handgereedschap metselaar', 'dagvergoeding', 'euro_per_dag', 'money', 'build', 'Cao 5.5', 'Netto GV per gewerkte dag, alleen voor passende functie.'),
        ('workwear_day', 'Werkkleding', 'dagvergoeding', 'euro_per_dag', 'money', 'both', 'Cao 5.17', 'Netto WKR per gewerkte dag.'),
        ('boots_day', 'Laarzen', 'dagvergoeding', 'euro_per_dag', 'money', 'both', 'Leeswijzer 3.1', 'Netto GV per gewerkte dag.'),
        ('washing_day', 'Wasgeld', 'dagvergoeding', 'euro_per_dag', 'money', 'both', 'Ruling Belastingdienst', 'Netto IK per gewerkte dag.'),
        ('di_percent', 'Duurzame inzetbaarheid', 'compensatie', 'percentage', 'decimal', 'both', 'Cao 4.14 / bijlage 4.2', 'DI-compensatiepercentage per cao-tak.'),
        ('stipp_hour_franchise', 'Stipp uurfranchise', 'pensioen', 'euro_per_uur', 'money', 'both', 'Stipp-grondslag', 'Franchise voor Stipp-pensioencompensatie.'),
        ('stipp_pension_compensation_percent', 'Compensatie pensioen bij Stipp', 'pensioen', 'percentage', 'decimal', 'both', 'Leeswijzer 4.4', 'Premieverschil BPF ten opzichte van Stipp.')
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
        ('working_days_per_year', 2026, 1, 261, 261, 'Leeswijzer 3.1', 'Geldt als noemer voor het loonjaar.'),
        ('holiday_allowance_percent', 2026, 1, 0.0833, 0.0833, 'NBBU art. 36a', 'Geldig t/m 30-06-2026.'),
        ('holiday_allowance_percent', 2026, 7, 0.0800, 0.0800, 'NBBU art. 36a', 'Vanaf 01-07-2026.'),
        ('health_insurance_4w', 2026, 1, 20.67, 20.67, 'Cao 5.18', '22,39 per maand x 12/13.'),
        ('travel_km_net_build', 2026, 1, 0.28, NULL, 'Leeswijzer 5.2', 'Netto tarief bouwplaats.'),
        ('travel_km_gross_build', 2026, 1, 0.32, NULL, 'Bijlage F', 'Bruto tarief alleen tonen.'),
        ('travel_km_net_uta', 2026, 1, NULL, 0.23, 'Leeswijzer 5.2', 'Netto UTA t/m periode 5.'),
        ('travel_km_net_uta', 2026, 6, NULL, 0.25, 'Leeswijzer 5.2', 'Netto UTA vanaf periode 6.'),
        ('tool_allowance_carpenter_day', 2026, 1, 0.96, NULL, 'Cao 5.5', 'Timmerman.'),
        ('tool_allowance_mason_day', 2026, 1, 0.68, NULL, 'Cao 5.5', 'Metselaar.'),
        ('workwear_day', 2026, 1, 1.10, 1.10, 'Cao 5.17', 'WKR per gewerkte dag.'),
        ('boots_day', 2026, 1, 0.68, 0.68, 'Leeswijzer 3.1', 'GV per gewerkte dag.'),
        ('washing_day', 2026, 1, 0.48, 0.48, 'Ruling Belastingdienst', 'IK per gewerkte dag.'),
        ('di_percent', 2026, 1, 0.0365, 0.0230, 'Cao 4.14 / bijlage 4.2', 'Bouwplaats 3,65%; UTA 2,3%.'),
        ('stipp_hour_franchise', 2026, 1, 9.24, 9.24, 'Stipp-grondslag', 'Uurfranchise.'),
        ('stipp_pension_compensation_percent', 2026, 1, 0.027182, 0.014596, 'Leeswijzer 4.4', 'Premieverschil BPF ten opzichte van Stipp.')
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
