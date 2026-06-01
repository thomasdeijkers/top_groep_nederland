CREATE TABLE IF NOT EXISTS payroll_periods (
    id SERIAL PRIMARY KEY,
    year INTEGER NOT NULL,
    period_number INTEGER NOT NULL,
    name TEXT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status TEXT NOT NULL DEFAULT 'concept',
    notes TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    UNIQUE (year, period_number)
);

CREATE TABLE IF NOT EXISTS payroll_period_weeks (
    id SERIAL PRIMARY KEY,
    payroll_period_id INTEGER NOT NULL REFERENCES payroll_periods(id) ON DELETE CASCADE,
    week_index INTEGER NOT NULL CHECK (week_index BETWEEN 1 AND 4),
    week_number INTEGER,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    UNIQUE (payroll_period_id, week_index)
);

ALTER TABLE project_time_bookings
    ADD COLUMN IF NOT EXISTS payroll_period_id INTEGER REFERENCES payroll_periods(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_payroll_periods_dates
    ON payroll_periods (start_date, end_date);

CREATE INDEX IF NOT EXISTS idx_payroll_periods_status
    ON payroll_periods (status);

CREATE INDEX IF NOT EXISTS idx_project_time_bookings_payroll_period
    ON project_time_bookings (payroll_period_id);
