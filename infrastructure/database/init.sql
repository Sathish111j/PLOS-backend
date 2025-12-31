-- ============================================================================
-- PLOS (Personal Life Operating System) - PostgreSQL Database Schema
-- Version: 1.0.0
-- Last Updated: 2025-12-31
-- ============================================================================
-- 
-- This script initializes the complete PLOS database schema including:
-- - Extensions (UUID, pgcrypto, pg_trgm for fuzzy matching)
-- - Custom ENUMs for type safety
-- - Core tables (users, journal extractions)
-- - Controlled vocabulary tables (categories, activity_types, food_items, metric_types)
-- - 11 extraction tables for comprehensive life tracking
-- - Views for analytics and reporting
-- - Stored functions for pattern analysis
-- - Proper indexes for performance
--
-- ============================================================================

-- ============================================================================
-- EXTENSIONS
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For fuzzy text matching

-- ============================================================================
-- CUSTOM ENUMS
-- ============================================================================

DO $$ BEGIN
    CREATE TYPE extraction_quality AS ENUM ('high', 'medium', 'low');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE time_of_day AS ENUM ('early_morning', 'morning', 'afternoon', 'evening', 'night', 'late_night');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE data_gap_status AS ENUM ('pending', 'answered', 'skipped', 'expired');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- ============================================================================
-- UTILITY FUNCTIONS
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- USERS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) NOT NULL UNIQUE,
    username VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    timezone VARCHAR(50) DEFAULT 'UTC',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

CREATE TRIGGER update_users_updated_at 
    BEFORE UPDATE ON users 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- CONTROLLED VOCABULARY: CATEGORIES
-- Hierarchical category system for organizing data
-- ============================================================================

CREATE TABLE IF NOT EXISTS categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    display_name VARCHAR(100) NOT NULL,
    parent_id INT REFERENCES categories(id),
    description TEXT,
    icon VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_categories_parent ON categories(parent_id);
CREATE INDEX IF NOT EXISTS idx_categories_name ON categories(name);

-- ============================================================================
-- CONTROLLED VOCABULARY: ACTIVITY TYPES
-- ============================================================================

CREATE TABLE IF NOT EXISTS activity_types (
    id SERIAL PRIMARY KEY,
    canonical_name VARCHAR(100) NOT NULL UNIQUE,
    display_name VARCHAR(100) NOT NULL,
    category_id INT NOT NULL REFERENCES categories(id),
    is_physical BOOLEAN DEFAULT FALSE,
    is_screen_time BOOLEAN DEFAULT FALSE,
    avg_calories_per_hour INT,
    typical_duration_minutes INT,
    search_vector TSVECTOR,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE activity_types IS 'Controlled vocabulary for activities. New activities are added here with canonical names.';

CREATE INDEX IF NOT EXISTS idx_activity_types_category ON activity_types(category_id);
CREATE INDEX IF NOT EXISTS idx_activity_types_search ON activity_types USING GIN(search_vector);

-- Activity aliases for fuzzy matching
CREATE TABLE IF NOT EXISTS activity_aliases (
    id SERIAL PRIMARY KEY,
    alias VARCHAR(100) NOT NULL UNIQUE,
    activity_type_id INT NOT NULL REFERENCES activity_types(id),
    confidence FLOAT DEFAULT 1.0,
    source VARCHAR(50) DEFAULT 'manual',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE activity_aliases IS 'Maps user variations to canonical activity names. Grows over time as we learn new terms.';

CREATE INDEX IF NOT EXISTS idx_aliases_alias ON activity_aliases(alias);
CREATE INDEX IF NOT EXISTS idx_aliases_trgm ON activity_aliases USING GIN(alias gin_trgm_ops);

-- ============================================================================
-- CONTROLLED VOCABULARY: FOOD ITEMS
-- ============================================================================

CREATE TABLE IF NOT EXISTS food_items (
    id SERIAL PRIMARY KEY,
    canonical_name VARCHAR(100) NOT NULL UNIQUE,
    display_name VARCHAR(100) NOT NULL,
    category VARCHAR(50),
    serving_size_g INT DEFAULT 100,
    calories_per_serving INT,
    protein_g FLOAT,
    carbs_g FLOAT,
    fat_g FLOAT,
    fiber_g FLOAT,
    is_healthy BOOLEAN,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_food_items_category ON food_items(category);

-- Food aliases for fuzzy matching
CREATE TABLE IF NOT EXISTS food_aliases (
    id SERIAL PRIMARY KEY,
    alias VARCHAR(100) NOT NULL UNIQUE,
    food_item_id INT NOT NULL REFERENCES food_items(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- CONTROLLED VOCABULARY: METRIC TYPES
-- ============================================================================

CREATE TABLE IF NOT EXISTS metric_types (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    display_name VARCHAR(100) NOT NULL,
    category_id INT REFERENCES categories(id),
    unit VARCHAR(20),
    min_value FLOAT,
    max_value FLOAT,
    description TEXT
);

-- ============================================================================
-- JOURNAL EXTRACTIONS (Main Entry Table)
-- ============================================================================

CREATE TABLE IF NOT EXISTS journal_extractions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    entry_date DATE NOT NULL,
    raw_entry TEXT NOT NULL,
    preprocessed_entry TEXT,
    overall_quality extraction_quality,
    extraction_time_ms INT,
    gemini_model VARCHAR(50),
    has_gaps BOOLEAN DEFAULT FALSE,
    gaps_resolved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, entry_date)
);

CREATE INDEX IF NOT EXISTS idx_extractions_user_date ON journal_extractions(user_id, entry_date);
CREATE INDEX IF NOT EXISTS idx_journal_entry_date ON journal_extractions(entry_date);
CREATE INDEX IF NOT EXISTS idx_journal_user_date ON journal_extractions(user_id, entry_date);
CREATE INDEX IF NOT EXISTS idx_journal_user_entry ON journal_extractions(user_id, entry_date);

-- ============================================================================
-- EXTRACTION TABLE: ACTIVITIES
-- ============================================================================

CREATE TABLE IF NOT EXISTS extraction_activities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    extraction_id UUID NOT NULL REFERENCES journal_extractions(id) ON DELETE CASCADE,
    activity_type_id INT REFERENCES activity_types(id),
    activity_raw VARCHAR(100),
    activity_category VARCHAR(50),
    start_time TIME,
    end_time TIME,
    duration_minutes INT,
    time_of_day time_of_day,
    intensity VARCHAR(10) CHECK (intensity IN ('low', 'medium', 'high')),
    satisfaction INT CHECK (satisfaction >= 1 AND satisfaction <= 10),
    calories_burned INT,
    is_outdoor BOOLEAN,
    with_others BOOLEAN,
    location VARCHAR(100),
    mood_before INT CHECK (mood_before >= 1 AND mood_before <= 10),
    mood_after INT CHECK (mood_after >= 1 AND mood_after <= 10),
    confidence FLOAT DEFAULT 0.5,
    raw_mention TEXT,
    needs_clarification BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_activities_extraction ON extraction_activities(extraction_id);
CREATE INDEX IF NOT EXISTS idx_activities_type ON extraction_activities(activity_type_id);
CREATE INDEX IF NOT EXISTS idx_activities_category ON extraction_activities(activity_category);
CREATE INDEX IF NOT EXISTS idx_activities_time ON extraction_activities(time_of_day);
CREATE INDEX IF NOT EXISTS idx_activities_raw ON extraction_activities(activity_raw);
CREATE INDEX IF NOT EXISTS idx_activities_date_cat ON extraction_activities(extraction_id, activity_category);

-- ============================================================================
-- EXTRACTION TABLE: CONSUMPTIONS (Food, Drinks, Medications)
-- ============================================================================

CREATE TABLE IF NOT EXISTS extraction_consumptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    extraction_id UUID NOT NULL REFERENCES journal_extractions(id) ON DELETE CASCADE,
    food_item_id INT REFERENCES food_items(id),
    item_raw VARCHAR(200),
    food_category VARCHAR(50),
    consumption_type VARCHAR(20) NOT NULL CHECK (consumption_type IN ('meal', 'snack', 'drink', 'medication', 'supplement')),
    meal_type VARCHAR(20) CHECK (meal_type IN ('breakfast', 'lunch', 'dinner', 'snack')),
    consumption_time TIME,
    time_of_day time_of_day,
    quantity FLOAT DEFAULT 1,
    unit VARCHAR(20) DEFAULT 'serving',
    calories INT,
    protein_g FLOAT,
    carbs_g FLOAT,
    fat_g FLOAT,
    fiber_g FLOAT,
    sugar_g FLOAT,
    sodium_mg FLOAT,
    caffeine_mg FLOAT,
    alcohol_units FLOAT,
    water_ml INT,
    is_processed BOOLEAN,
    is_healthy BOOLEAN,
    is_home_cooked BOOLEAN,
    confidence FLOAT DEFAULT 0.5,
    raw_mention TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_consumptions_extraction ON extraction_consumptions(extraction_id);
CREATE INDEX IF NOT EXISTS idx_consumptions_type ON extraction_consumptions(consumption_type);
CREATE INDEX IF NOT EXISTS idx_consumptions_meal_type ON extraction_consumptions(meal_type);
CREATE INDEX IF NOT EXISTS idx_consumptions_category ON extraction_consumptions(food_category);
CREATE INDEX IF NOT EXISTS idx_consumptions_time ON extraction_consumptions(time_of_day);
CREATE INDEX IF NOT EXISTS idx_consumptions_raw ON extraction_consumptions(item_raw);
CREATE INDEX IF NOT EXISTS idx_consumptions_date_type ON extraction_consumptions(extraction_id, food_category);

-- ============================================================================
-- EXTRACTION TABLE: SLEEP
-- ============================================================================

CREATE TABLE IF NOT EXISTS extraction_sleep (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    extraction_id UUID NOT NULL UNIQUE REFERENCES journal_extractions(id) ON DELETE CASCADE,
    duration_hours FLOAT,
    quality INT CHECK (quality >= 1 AND quality <= 10),
    bedtime TIME,
    waketime TIME,
    disruptions INT DEFAULT 0,
    trouble_falling_asleep BOOLEAN,
    woke_up_tired BOOLEAN,
    nap_duration_minutes INT DEFAULT 0,
    sleep_environment VARCHAR(100),
    pre_sleep_activity VARCHAR(100),
    dreams_noted TEXT,
    confidence FLOAT DEFAULT 0.5,
    raw_mention TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- EXTRACTION TABLE: SOCIAL INTERACTIONS
-- ============================================================================

CREATE TABLE IF NOT EXISTS extraction_social (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    extraction_id UUID NOT NULL REFERENCES journal_extractions(id) ON DELETE CASCADE,
    person_name VARCHAR(100),
    relationship VARCHAR(50),
    relationship_category VARCHAR(50),
    interaction_type VARCHAR(50),
    duration_minutes INT,
    time_of_day time_of_day,
    sentiment VARCHAR(20) CHECK (sentiment IN ('positive', 'negative', 'neutral', 'conflict')),
    quality_score INT CHECK (quality_score >= 1 AND quality_score <= 10),
    conflict_level INT CHECK (conflict_level >= 0 AND conflict_level <= 10),
    mood_before INT CHECK (mood_before >= 1 AND mood_before <= 10),
    mood_after INT CHECK (mood_after >= 1 AND mood_after <= 10),
    emotional_impact VARCHAR(50),
    interaction_outcome VARCHAR(50),
    initiated_by VARCHAR(20),
    is_virtual BOOLEAN,
    location VARCHAR(100),
    topic VARCHAR(200),
    confidence FLOAT DEFAULT 0.5,
    raw_mention TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON COLUMN extraction_social.relationship IS 'Specific: mom, dad, girlfriend, boyfriend, boss, colleague, classmate, teacher, student, neighbor, etc.';
COMMENT ON COLUMN extraction_social.relationship_category IS 'family|romantic|professional|friend|acquaintance|other';
COMMENT ON COLUMN extraction_social.mood_before IS 'Mood 1-10 before interaction';
COMMENT ON COLUMN extraction_social.mood_after IS 'Mood 1-10 after interaction';
COMMENT ON COLUMN extraction_social.conflict_level IS '0=no conflict, 10=major fight';
COMMENT ON COLUMN extraction_social.emotional_impact IS 'energized|drained|supported|stressed|happy|sad|frustrated|calm|anxious';
COMMENT ON COLUMN extraction_social.initiated_by IS 'user|other|mutual';
COMMENT ON COLUMN extraction_social.interaction_outcome IS 'resolved|ongoing|escalated|positive|negative|neutral';

CREATE INDEX IF NOT EXISTS idx_social_extraction ON extraction_social(extraction_id);
CREATE INDEX IF NOT EXISTS idx_social_person ON extraction_social(person_name);
CREATE INDEX IF NOT EXISTS idx_social_relationship ON extraction_social(relationship);
CREATE INDEX IF NOT EXISTS idx_social_relationship_category ON extraction_social(relationship_category);
CREATE INDEX IF NOT EXISTS idx_social_sentiment ON extraction_social(sentiment);
CREATE INDEX IF NOT EXISTS idx_social_conflict ON extraction_social(conflict_level);
CREATE INDEX IF NOT EXISTS idx_social_emotional_impact ON extraction_social(emotional_impact);

-- ============================================================================
-- EXTRACTION TABLE: METRICS (Numeric Scores)
-- ============================================================================

CREATE TABLE IF NOT EXISTS extraction_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    extraction_id UUID NOT NULL REFERENCES journal_extractions(id) ON DELETE CASCADE,
    metric_type_id INT NOT NULL REFERENCES metric_types(id),
    value FLOAT NOT NULL,
    time_of_day time_of_day,
    confidence FLOAT DEFAULT 0.5,
    raw_mention TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(extraction_id, metric_type_id, time_of_day)
);

CREATE INDEX IF NOT EXISTS idx_metrics_extraction ON extraction_metrics(extraction_id);
CREATE INDEX IF NOT EXISTS idx_metrics_type ON extraction_metrics(metric_type_id);

-- ============================================================================
-- EXTRACTION TABLE: WORK / PRODUCTIVITY
-- ============================================================================

CREATE TABLE IF NOT EXISTS extraction_work (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    extraction_id UUID NOT NULL REFERENCES journal_extractions(id) ON DELETE CASCADE,
    work_type VARCHAR(50),
    project_name VARCHAR(200),
    duration_minutes INT,
    time_of_day time_of_day,
    productivity_score INT CHECK (productivity_score >= 1 AND productivity_score <= 10),
    focus_quality VARCHAR(20),
    interruptions INT DEFAULT 0,
    accomplishments TEXT,
    blockers TEXT,
    raw_mention TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_work_extraction ON extraction_work(extraction_id);
CREATE INDEX IF NOT EXISTS idx_work_type ON extraction_work(work_type);

-- ============================================================================
-- EXTRACTION TABLE: HEALTH SYMPTOMS
-- ============================================================================

CREATE TABLE IF NOT EXISTS extraction_health (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    extraction_id UUID NOT NULL REFERENCES journal_extractions(id) ON DELETE CASCADE,
    symptom_type VARCHAR(100) NOT NULL,
    body_part VARCHAR(50),
    severity INT CHECK (severity >= 1 AND severity <= 10),
    duration_minutes INT,
    time_of_day VARCHAR(20),
    possible_cause TEXT,
    medication_taken TEXT,
    is_resolved BOOLEAN,
    impact_score INT CHECK (impact_score >= 1 AND impact_score <= 10),
    triggers TEXT,
    raw_mention TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_health_extraction ON extraction_health(extraction_id);
CREATE INDEX IF NOT EXISTS idx_health_symptom ON extraction_health(symptom_type);

-- ============================================================================
-- EXTRACTION TABLE: WEATHER CONTEXT
-- ============================================================================

CREATE TABLE IF NOT EXISTS extraction_weather (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    extraction_id UUID NOT NULL REFERENCES journal_extractions(id) ON DELETE CASCADE,
    weather_condition VARCHAR(50),
    temperature_feel VARCHAR(20),
    mentioned_impact TEXT,
    raw_mention TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_weather_extraction ON extraction_weather(extraction_id);
CREATE INDEX IF NOT EXISTS idx_weather_condition ON extraction_weather(weather_condition);

-- ============================================================================
-- EXTRACTION TABLE: LOCATIONS
-- ============================================================================

CREATE TABLE IF NOT EXISTS extraction_locations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    extraction_id UUID NOT NULL REFERENCES journal_extractions(id) ON DELETE CASCADE,
    location_name VARCHAR(255) NOT NULL,
    location_type VARCHAR(50),
    time_of_day VARCHAR(20),
    duration_minutes INT,
    activity_context TEXT,
    raw_mention TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_locations_extraction ON extraction_locations(extraction_id);
CREATE INDEX IF NOT EXISTS idx_locations_type ON extraction_locations(location_type);

-- ============================================================================
-- EXTRACTION TABLE: NOTES (Goals, Gratitude, Thoughts)
-- ============================================================================

CREATE TABLE IF NOT EXISTS extraction_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    extraction_id UUID NOT NULL REFERENCES journal_extractions(id) ON DELETE CASCADE,
    note_type VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    sentiment VARCHAR(20),
    confidence FLOAT DEFAULT 0.5,
    raw_mention TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notes_extraction ON extraction_notes(extraction_id);
CREATE INDEX IF NOT EXISTS idx_notes_type ON extraction_notes(note_type);

-- ============================================================================
-- EXTRACTION TABLE: GAPS (Clarification Questions)
-- ============================================================================

CREATE TABLE IF NOT EXISTS extraction_gaps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    extraction_id UUID NOT NULL REFERENCES journal_extractions(id) ON DELETE CASCADE,
    field_category VARCHAR(50) NOT NULL,
    question TEXT NOT NULL,
    context TEXT,
    original_mention TEXT,
    priority INT DEFAULT 1,
    status data_gap_status DEFAULT 'pending',
    user_response TEXT,
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE extraction_gaps IS 'Questions that need user clarification. LLM generates these when data is ambiguous.';

CREATE INDEX IF NOT EXISTS idx_gaps_extraction ON extraction_gaps(extraction_id);
CREATE INDEX IF NOT EXISTS idx_gaps_status ON extraction_gaps(status);

-- ============================================================================
-- USER PATTERNS TABLE (Cached Baselines)
-- ============================================================================

CREATE TABLE IF NOT EXISTS user_patterns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    pattern_type VARCHAR(50) NOT NULL,
    day_of_week INT CHECK (day_of_week >= 0 AND day_of_week <= 6),
    value FLOAT,
    std_dev FLOAT,
    sample_count INT DEFAULT 0,
    confidence FLOAT DEFAULT 0.5 CHECK (confidence >= 0 AND confidence <= 1),
    metadata JSONB DEFAULT '{}',
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, pattern_type, day_of_week)
);

COMMENT ON TABLE user_patterns IS 'Cached user patterns and baselines for fast context retrieval. Updated periodically.';

CREATE INDEX IF NOT EXISTS idx_user_patterns_user ON user_patterns(user_id);
CREATE INDEX IF NOT EXISTS idx_user_patterns_type ON user_patterns(pattern_type);
CREATE INDEX IF NOT EXISTS idx_user_patterns_dow ON user_patterns(day_of_week);

-- ============================================================================
-- USER CONTEXT STATE (Real-time State)
-- ============================================================================

CREATE TABLE IF NOT EXISTS user_context_state (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    current_mood_score INT,
    current_energy_level INT,
    current_stress_level INT,
    sleep_quality_avg_7d NUMERIC(4,2),
    productivity_score_avg_7d NUMERIC(4,2),
    active_goals_count INT DEFAULT 0,
    pending_tasks_count INT DEFAULT 0,
    completed_tasks_today INT DEFAULT 0,
    context_data JSONB,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE user_context_state IS 'Real-time user context for fast API responses.';

-- ============================================================================
-- VIEWS FOR ANALYTICS
-- ============================================================================

-- Activity summary view
CREATE OR REPLACE VIEW v_activity_summary AS
SELECT 
    je.user_id,
    je.entry_date,
    COALESCE(at.canonical_name, ea.activity_raw) as activity,
    COALESCE(at.display_name, ea.activity_raw) as activity_display,
    c.name as category,
    ea.duration_minutes,
    ea.time_of_day,
    ea.intensity,
    ea.satisfaction,
    ea.calories_burned,
    at.is_physical,
    at.is_screen_time
FROM extraction_activities ea
JOIN journal_extractions je ON ea.extraction_id = je.id
LEFT JOIN activity_types at ON ea.activity_type_id = at.id
LEFT JOIN categories c ON at.category_id = c.id;

-- Daily nutrition view
CREATE OR REPLACE VIEW v_daily_nutrition AS
SELECT 
    je.user_id,
    je.entry_date,
    COUNT(*) FILTER (WHERE ec.consumption_type = 'meal') as meals_count,
    SUM(ec.calories) as total_calories,
    SUM(ec.protein_g) as total_protein,
    SUM(ec.carbs_g) as total_carbs,
    SUM(ec.fat_g) as total_fat,
    COUNT(*) FILTER (WHERE ec.is_healthy = TRUE) as healthy_items,
    COUNT(*) FILTER (WHERE ec.is_home_cooked = TRUE) as home_cooked
FROM extraction_consumptions ec
JOIN journal_extractions je ON ec.extraction_id = je.id
GROUP BY je.user_id, je.entry_date;

-- Pending gaps view
CREATE OR REPLACE VIEW v_pending_gaps AS
SELECT 
    je.user_id,
    eg.id as gap_id,
    je.entry_date,
    eg.field_category,
    eg.question,
    eg.context,
    eg.priority,
    eg.created_at
FROM extraction_gaps eg
JOIN journal_extractions je ON eg.extraction_id = je.id
WHERE eg.status = 'pending'
ORDER BY eg.priority, eg.created_at;

-- Rolling averages view
CREATE OR REPLACE VIEW v_rolling_averages AS
SELECT 
    je.user_id,
    je.entry_date,
    AVG(em.value) FILTER (WHERE mt.name = 'mood_score') 
        OVER (PARTITION BY je.user_id ORDER BY je.entry_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) as avg_mood_7d,
    AVG(em.value) FILTER (WHERE mt.name = 'energy_level') 
        OVER (PARTITION BY je.user_id ORDER BY je.entry_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) as avg_energy_7d,
    AVG(em.value) FILTER (WHERE mt.name = 'sleep_duration') 
        OVER (PARTITION BY je.user_id ORDER BY je.entry_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) as avg_sleep_7d,
    AVG(em.value) FILTER (WHERE mt.name = 'stress_level') 
        OVER (PARTITION BY je.user_id ORDER BY je.entry_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) as avg_stress_7d
FROM journal_extractions je
JOIN extraction_metrics em ON je.id = em.extraction_id
JOIN metric_types mt ON em.metric_type_id = mt.id;

-- Day of week mood patterns
CREATE OR REPLACE VIEW v_dow_mood_patterns AS
SELECT 
    je.user_id,
    EXTRACT(DOW FROM je.entry_date) as day_of_week,
    AVG(em.value) as avg_mood,
    STDDEV(em.value) as stddev_mood,
    COUNT(*) as sample_count
FROM journal_extractions je
JOIN extraction_metrics em ON je.id = em.extraction_id
JOIN metric_types mt ON em.metric_type_id = mt.id
WHERE mt.name = 'mood_score'
GROUP BY je.user_id, EXTRACT(DOW FROM je.entry_date);

-- ============================================================================
-- STORED FUNCTIONS
-- ============================================================================

-- Calculate user baseline metrics
CREATE OR REPLACE FUNCTION calculate_user_baseline(
    p_user_id UUID, 
    p_entry_date DATE, 
    p_days INT DEFAULT 30
)
RETURNS TABLE (
    avg_sleep FLOAT,
    stddev_sleep FLOAT,
    avg_mood FLOAT,
    stddev_mood FLOAT,
    avg_energy FLOAT,
    stddev_energy FLOAT,
    avg_stress FLOAT,
    stddev_stress FLOAT,
    sample_count BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        AVG(CASE WHEN mt.name = 'sleep_duration' THEN em.value END)::FLOAT as avg_sleep,
        STDDEV(CASE WHEN mt.name = 'sleep_duration' THEN em.value END)::FLOAT as stddev_sleep,
        AVG(CASE WHEN mt.name = 'mood_score' THEN em.value END)::FLOAT as avg_mood,
        STDDEV(CASE WHEN mt.name = 'mood_score' THEN em.value END)::FLOAT as stddev_mood,
        AVG(CASE WHEN mt.name = 'energy_level' THEN em.value END)::FLOAT as avg_energy,
        STDDEV(CASE WHEN mt.name = 'energy_level' THEN em.value END)::FLOAT as stddev_energy,
        AVG(CASE WHEN mt.name = 'stress_level' THEN em.value END)::FLOAT as avg_stress,
        STDDEV(CASE WHEN mt.name = 'stress_level' THEN em.value END)::FLOAT as stddev_stress,
        COUNT(DISTINCT je.id)::BIGINT as sample_count
    FROM journal_extractions je
    JOIN extraction_metrics em ON je.id = em.extraction_id
    JOIN metric_types mt ON em.metric_type_id = mt.id
    WHERE je.user_id = p_user_id
      AND je.entry_date >= (p_entry_date - p_days)
      AND je.entry_date < p_entry_date;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION calculate_user_baseline IS 'Calculates user baseline metrics from journal extractions.';

-- Resolve activity name to ID
CREATE OR REPLACE FUNCTION resolve_activity_name(p_name VARCHAR)
RETURNS INT AS $$
DECLARE
    v_type_id INT;
BEGIN
    -- Try exact match first
    SELECT id INTO v_type_id FROM activity_types 
    WHERE canonical_name = LOWER(p_name) OR display_name ILIKE p_name;
    
    IF v_type_id IS NOT NULL THEN
        RETURN v_type_id;
    END IF;
    
    -- Try alias
    SELECT activity_type_id INTO v_type_id FROM activity_aliases
    WHERE alias ILIKE p_name OR alias ILIKE '%' || p_name || '%';
    
    IF v_type_id IS NOT NULL THEN
        RETURN v_type_id;
    END IF;
    
    -- Try fuzzy match
    SELECT at.id INTO v_type_id FROM activity_types at
    WHERE at.canonical_name % LOWER(p_name)
    ORDER BY similarity(at.canonical_name, LOWER(p_name)) DESC
    LIMIT 1;
    
    RETURN v_type_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION resolve_activity_name IS 'Resolves user activity text to canonical activity_type_id using exact match, alias, then fuzzy match.';

-- Get activity totals for date range
CREATE OR REPLACE FUNCTION get_activity_totals(
    p_user_id UUID,
    p_start_date DATE,
    p_end_date DATE,
    p_category VARCHAR DEFAULT NULL
)
RETURNS TABLE (
    activity VARCHAR,
    category VARCHAR,
    total_minutes BIGINT,
    total_hours FLOAT,
    occurrences BIGINT,
    avg_satisfaction FLOAT,
    total_calories BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        v.activity::VARCHAR,
        v.category::VARCHAR,
        SUM(v.duration_minutes)::BIGINT,
        SUM(v.duration_minutes)::FLOAT / 60,
        COUNT(*)::BIGINT,
        AVG(v.satisfaction)::FLOAT,
        SUM(v.calories_burned)::BIGINT
    FROM v_activity_summary v
    WHERE v.user_id = p_user_id
      AND v.entry_date BETWEEN p_start_date AND p_end_date
      AND (p_category IS NULL OR v.category = p_category)
    GROUP BY v.activity, v.category
    ORDER BY SUM(v.duration_minutes) DESC NULLS LAST;
END;
$$ LANGUAGE plpgsql;

-- Update user pattern cache
CREATE OR REPLACE FUNCTION update_user_pattern_cache(
    p_user_id UUID,
    p_pattern_type VARCHAR,
    p_value FLOAT,
    p_std_dev FLOAT,
    p_sample_count INT,
    p_day_of_week INT DEFAULT NULL,
    p_metadata JSONB DEFAULT '{}'
)
RETURNS UUID AS $$
DECLARE
    v_pattern_id UUID;
BEGIN
    INSERT INTO user_patterns (
        user_id, pattern_type, day_of_week, value, std_dev, 
        sample_count, confidence, metadata, last_updated
    ) VALUES (
        p_user_id, p_pattern_type, p_day_of_week, p_value, p_std_dev,
        p_sample_count, 
        LEAST(p_sample_count::FLOAT / 30.0, 1.0),
        p_metadata,
        NOW()
    )
    ON CONFLICT (user_id, pattern_type, day_of_week) 
    DO UPDATE SET
        value = EXCLUDED.value,
        std_dev = EXCLUDED.std_dev,
        sample_count = EXCLUDED.sample_count,
        confidence = LEAST(EXCLUDED.sample_count::FLOAT / 30.0, 1.0),
        metadata = EXCLUDED.metadata,
        last_updated = NOW()
    RETURNING id INTO v_pattern_id;
    
    RETURN v_pattern_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION update_user_pattern_cache IS 'Upserts a user pattern into the cache.';

-- ============================================================================
-- END OF SCHEMA
-- ============================================================================
