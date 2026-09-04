UPDATE invoice_inputs
SET fee_percent = 13.50,
    updated_at = NOW()
WHERE status = 'concept'
  AND fee_percent <> 13.50;
