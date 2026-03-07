-- Migration 009: Add unique constraint for journal_extractions upsert
-- The ON CONFLICT (user_id, entry_date) clause in the journal-parser
-- requires a UNIQUE constraint or index on these columns.

CREATE UNIQUE INDEX IF NOT EXISTS idx_journal_extractions_user_date_unique
    ON journal_extractions (user_id, entry_date);
