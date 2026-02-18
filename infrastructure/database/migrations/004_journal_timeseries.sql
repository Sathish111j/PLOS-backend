-- ============================================================================
-- PLOS Journal Time-Series Migration
-- Adds Timescale hypertable for analytics-friendly journal metrics.
-- ============================================================================

SET search_path TO public;

CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS journal_timeseries (
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ts TIMESTAMPTZ NOT NULL,
    extraction_id UUID NOT NULL REFERENCES journal_extractions(id) ON DELETE CASCADE,
    entry_date DATE NOT NULL,
    calories_in DOUBLE PRECISION,
    sleep_hours DOUBLE PRECISION,
    sleep_quality DOUBLE PRECISION,
    mood_score DOUBLE PRECISION,
    water_ml DOUBLE PRECISION,
    steps INTEGER,
    activity_minutes INTEGER,
    activity_calories INTEGER,
    protein_g DOUBLE PRECISION,
    carbs_g DOUBLE PRECISION,
    fat_g DOUBLE PRECISION,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, ts, extraction_id)
);

SELECT create_hypertable(
    'journal_timeseries',
    'ts',
    if_not_exists => TRUE,
    migrate_data => TRUE,
    chunk_time_interval => INTERVAL '30 days'
);

CREATE INDEX IF NOT EXISTS idx_journal_timeseries_user_ts
    ON journal_timeseries (user_id, ts DESC);

CREATE INDEX IF NOT EXISTS idx_journal_timeseries_entry_date
    ON journal_timeseries (entry_date DESC);

CREATE INDEX IF NOT EXISTS idx_journal_timeseries_extraction
    ON journal_timeseries (extraction_id);

DO $$
BEGIN
    RAISE NOTICE 'Journal timeseries migration completed successfully!';
END $$;
