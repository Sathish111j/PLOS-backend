-- PLOS TimescaleDB Extension Setup
-- Optimized for time-series data (health metrics, mood tracking, etc.)

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- ============================================================================
-- Convert tables to hypertables (optimized for time-series queries)
-- ============================================================================

-- Mood entries - high-frequency time-series data
SELECT create_hypertable('mood_entries', 'timestamp', 
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists => TRUE
);

-- Health metrics - daily/multiple readings per day
SELECT create_hypertable('health_metrics', 'timestamp',
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists => TRUE
);

-- Nutrition entries - 3-5 times per day
SELECT create_hypertable('nutrition_entries', 'timestamp',
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists => TRUE
);

-- Exercise entries - variable frequency
SELECT create_hypertable('exercise_entries', 'timestamp',
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists => TRUE
);

-- Work entries - daily tracking
SELECT create_hypertable('work_entries', 'timestamp',
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists => TRUE
);

-- Habit entries - daily tracking
SELECT create_hypertable('habit_entries', 'timestamp',
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists => TRUE
);

-- ============================================================================
-- Create continuous aggregates (materialized views for fast queries)
-- ============================================================================

-- Daily mood averages
CREATE MATERIALIZED VIEW IF NOT EXISTS mood_daily_avg
WITH (timescaledb.continuous) AS
SELECT
    user_id,
    time_bucket('1 day', timestamp) AS day,
    AVG(mood_score) AS avg_mood,
    COUNT(*) AS entry_count
FROM mood_entries
GROUP BY user_id, day
WITH NO DATA;

-- Refresh policy: update every 1 hour, retain data for 30 days
SELECT add_continuous_aggregate_policy('mood_daily_avg',
    start_offset => INTERVAL '30 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);

-- Weekly health summary
CREATE MATERIALIZED VIEW IF NOT EXISTS health_weekly_avg
WITH (timescaledb.continuous) AS
SELECT
    user_id,
    time_bucket('7 days', timestamp) AS week,
    AVG(sleep_hours) AS avg_sleep_hours,
    AVG(sleep_quality) AS avg_sleep_quality,
    AVG(energy_level) AS avg_energy_level,
    AVG(stress_level) AS avg_stress_level,
    AVG(weight_kg) AS avg_weight_kg,
    COUNT(*) AS entry_count
FROM health_metrics
GROUP BY user_id, week
WITH NO DATA;

SELECT add_continuous_aggregate_policy('health_weekly_avg',
    start_offset => INTERVAL '60 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);

-- Daily nutrition totals
CREATE MATERIALIZED VIEW IF NOT EXISTS nutrition_daily_totals
WITH (timescaledb.continuous) AS
SELECT
    user_id,
    time_bucket('1 day', timestamp) AS day,
    SUM(calories) AS total_calories,
    SUM(protein_g) AS total_protein,
    SUM(carbs_g) AS total_carbs,
    SUM(fat_g) AS total_fat,
    SUM(water_ml) AS total_water,
    COUNT(*) AS meal_count
FROM nutrition_entries
GROUP BY user_id, day
WITH NO DATA;

SELECT add_continuous_aggregate_policy('nutrition_daily_totals',
    start_offset => INTERVAL '30 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);

-- Weekly exercise summary
CREATE MATERIALIZED VIEW IF NOT EXISTS exercise_weekly_summary
WITH (timescaledb.continuous) AS
SELECT
    user_id,
    time_bucket('7 days', timestamp) AS week,
    SUM(duration_minutes) AS total_duration,
    SUM(calories_burned) AS total_calories_burned,
    SUM(distance_km) AS total_distance,
    COUNT(*) AS workout_count
FROM exercise_entries
GROUP BY user_id, week
WITH NO DATA;

SELECT add_continuous_aggregate_policy('exercise_weekly_summary',
    start_offset => INTERVAL '60 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);

-- Daily productivity metrics
CREATE MATERIALIZED VIEW IF NOT EXISTS work_daily_summary
WITH (timescaledb.continuous) AS
SELECT
    user_id,
    time_bucket('1 day', timestamp) AS day,
    SUM(hours_worked) AS total_hours,
    AVG(productivity_score) AS avg_productivity,
    AVG(focus_level) AS avg_focus,
    COUNT(*) AS entry_count
FROM work_entries
GROUP BY user_id, day
WITH NO DATA;

SELECT add_continuous_aggregate_policy('work_daily_summary',
    start_offset => INTERVAL '30 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);

-- ============================================================================
-- Data retention policies (auto-cleanup old data)
-- ============================================================================

-- Keep raw mood entries for 1 year
SELECT add_retention_policy('mood_entries', INTERVAL '365 days', if_not_exists => TRUE);

-- Keep raw health metrics for 1 year
SELECT add_retention_policy('health_metrics', INTERVAL '365 days', if_not_exists => TRUE);

-- Keep raw nutrition entries for 6 months
SELECT add_retention_policy('nutrition_entries', INTERVAL '180 days', if_not_exists => TRUE);

-- Keep raw exercise entries for 1 year
SELECT add_retention_policy('exercise_entries', INTERVAL '365 days', if_not_exists => TRUE);

-- Keep raw work entries for 1 year
SELECT add_retention_policy('work_entries', INTERVAL '365 days', if_not_exists => TRUE);

-- Keep raw habit entries for 1 year
SELECT add_retention_policy('habit_entries', INTERVAL '365 days', if_not_exists => TRUE);

-- ============================================================================
-- Compression policies (reduce storage for old data)
-- ============================================================================

-- Compress mood data older than 7 days
SELECT add_compression_policy('mood_entries', INTERVAL '7 days', if_not_exists => TRUE);

-- Compress health data older than 7 days
SELECT add_compression_policy('health_metrics', INTERVAL '7 days', if_not_exists => TRUE);

-- Compress nutrition data older than 7 days
SELECT add_compression_policy('nutrition_entries', INTERVAL '7 days', if_not_exists => TRUE);

-- Compress exercise data older than 7 days
SELECT add_compression_policy('exercise_entries', INTERVAL '7 days', if_not_exists => TRUE);

-- Compress work data older than 7 days
SELECT add_compression_policy('work_entries', INTERVAL '7 days', if_not_exists => TRUE);

-- Compress habit data older than 7 days
SELECT add_compression_policy('habit_entries', INTERVAL '7 days', if_not_exists => TRUE);

COMMIT;
