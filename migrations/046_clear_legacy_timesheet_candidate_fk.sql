DO $$
DECLARE
    legacy_constraint RECORD;
BEGIN
    IF to_regclass('public.whatsapp_timesheet_inbox') IS NULL THEN
        RETURN;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'whatsapp_timesheet_inbox'
          AND column_name = 'matched_candidate_id'
    ) THEN
        UPDATE whatsapp_timesheet_inbox
        SET matched_candidate_id = NULL
        WHERE matched_candidate_id IS NOT NULL;

        FOR legacy_constraint IN
            SELECT con.conname
            FROM pg_constraint con
            JOIN pg_class rel
              ON rel.oid = con.conrelid
            JOIN pg_namespace nsp
              ON nsp.oid = rel.relnamespace
            JOIN pg_attribute att
              ON att.attrelid = rel.oid
             AND att.attnum = ANY(con.conkey)
            WHERE nsp.nspname = 'public'
              AND rel.relname = 'whatsapp_timesheet_inbox'
              AND con.contype = 'f'
              AND att.attname = 'matched_candidate_id'
        LOOP
            EXECUTE format(
                'ALTER TABLE public.whatsapp_timesheet_inbox DROP CONSTRAINT IF EXISTS %I',
                legacy_constraint.conname
            );
        END LOOP;
    END IF;
END $$;
