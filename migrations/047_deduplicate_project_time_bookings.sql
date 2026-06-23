WITH ranked_bookings AS (
    SELECT id,
           ROW_NUMBER() OVER (
               PARTITION BY timesheet_inbox_id
               ORDER BY updated_at DESC NULLS LAST, id DESC
           ) AS row_number
    FROM project_time_bookings
    WHERE timesheet_inbox_id IS NOT NULL
)
DELETE FROM project_time_bookings b
USING ranked_bookings r
WHERE b.id = r.id
  AND r.row_number > 1;

CREATE UNIQUE INDEX IF NOT EXISTS idx_project_time_bookings_unique_timesheet
    ON project_time_bookings (timesheet_inbox_id)
    WHERE timesheet_inbox_id IS NOT NULL;
