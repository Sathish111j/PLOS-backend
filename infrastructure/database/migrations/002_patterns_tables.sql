-- ============================================================================
-- PLOS PATTERNS AND TRACKING TABLES
-- Additional tables for user patterns, relationship history, sleep debt, and activity impact
-- ============================================================================

-- ============================================================================
-- USER PATTERNS TABLE
-- Stores cached baselines and day-of-week patterns
-- ============================================================================

CREATE TABLE IF NOT EXISTS user_patterns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    
    -- Pattern identification
    pattern_type VARCHAR(50) NOT NULL,        -- 'baseline_30d', 'mood_baseline', 'sleep_baseline', etc.
    day_of_week INT CHECK (day_of_week >= 0 AND day_of_week <= 6),  -- 0=Monday, 6=Sunday (NULL for overall patterns)
    
    -- Pattern values
    value FLOAT,                              -- Primary value (e.g., average)
    std_dev FLOAT,                            -- Standard deviation
    
    -- Quality metrics
    sample_count INT DEFAULT 0,
    confidence FLOAT DEFAULT 0.5 CHECK (confidence >= 0 AND confidence <= 1),
    
    -- Extended data
    metadata JSONB DEFAULT '{}',              -- Additional pattern-specific data
    
    -- Timestamps
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Constraints
    UNIQUE(user_id, pattern_type, day_of_week)
);

CREATE INDEX IF NOT EXISTS idx_user_patterns_user ON user_patterns(user_id);
CREATE INDEX IF NOT EXISTS idx_user_patterns_type ON user_patterns(pattern_type);
CREATE INDEX IF NOT EXISTS idx_user_patterns_dow ON user_patterns(day_of_week);

COMMENT ON TABLE user_patterns IS 'Cached user patterns and baselines for fast context retrieval. Updated periodically.';

-- ============================================================================
-- RELATIONSHIP HISTORY TABLE
-- Tracks relationship state changes over time
-- ============================================================================

CREATE TABLE IF NOT EXISTS relationship_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    
    -- Event details
    event_date DATE NOT NULL,
    state_before VARCHAR(20),                 -- Previous relationship state
    state_after VARCHAR(20) NOT NULL,         -- New relationship state (HARMONY, TENSION, CONFLICT, etc.)
    
    -- Context
    trigger TEXT,                             -- What caused the state change
    severity INT CHECK (severity >= 1 AND severity <= 10),
    
    -- Resolution tracking
    resolution_date DATE,                     -- When the conflict was resolved
    resolution_days INT,                      -- Days until resolution
    what_worked TEXT,                         -- What helped resolve it
    
    -- Additional info
    notes TEXT,
    metadata JSONB DEFAULT '{}',
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_relationship_user ON relationship_history(user_id);
CREATE INDEX IF NOT EXISTS idx_relationship_date ON relationship_history(event_date);
CREATE INDEX IF NOT EXISTS idx_relationship_state ON relationship_history(state_after);

COMMENT ON TABLE relationship_history IS 'Tracks relationship state transitions for pattern analysis and predictions.';

-- ============================================================================
-- SLEEP DEBT LOG TABLE
-- Tracks daily sleep debt accumulation
-- ============================================================================

CREATE TABLE IF NOT EXISTS sleep_debt_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    
    -- Daily data
    entry_date DATE NOT NULL,
    sleep_hours FLOAT CHECK (sleep_hours >= 0 AND sleep_hours <= 24),
    baseline_hours FLOAT,                     -- User's baseline sleep need
    
    -- Debt calculations
    debt_this_day FLOAT,                      -- Debt for this specific day
    debt_cumulative FLOAT,                    -- Running total (with decay)
    recovery_sleep_needed FLOAT,              -- Hours needed to recover
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Ensure one entry per user per date
    UNIQUE(user_id, entry_date)
);

CREATE INDEX IF NOT EXISTS idx_sleep_debt_user ON sleep_debt_log(user_id);
CREATE INDEX IF NOT EXISTS idx_sleep_debt_date ON sleep_debt_log(entry_date);

COMMENT ON TABLE sleep_debt_log IS 'Daily sleep debt tracking with cumulative calculations.';

-- ============================================================================
-- ACTIVITY IMPACT TABLE
-- Stores learned correlations between activities and metrics
-- ============================================================================

CREATE TABLE IF NOT EXISTS activity_impact (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    
    -- Activity identification
    activity_type VARCHAR(100) NOT NULL,      -- Canonical activity name
    occurrence_count INT DEFAULT 0,           -- How many times tracked
    
    -- Impact correlations (next-day effects)
    avg_mood_impact FLOAT,                    -- Average change in mood
    avg_energy_impact FLOAT,                  -- Average change in energy
    avg_sleep_impact FLOAT,                   -- Average change in sleep quality
    avg_focus_impact FLOAT,                   -- Average change in focus
    
    -- Activity stats
    avg_duration_minutes FLOAT,
    avg_satisfaction FLOAT CHECK (avg_satisfaction >= 0 AND avg_satisfaction <= 10),
    
    -- Quality metrics
    confidence FLOAT DEFAULT 0.5 CHECK (confidence >= 0 AND confidence <= 1),
    last_occurred DATE,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Ensure one record per user per activity
    UNIQUE(user_id, activity_type)
);

CREATE INDEX IF NOT EXISTS idx_activity_impact_user ON activity_impact(user_id);
CREATE INDEX IF NOT EXISTS idx_activity_impact_type ON activity_impact(activity_type);
CREATE INDEX IF NOT EXISTS idx_activity_impact_mood ON activity_impact(avg_mood_impact DESC);

COMMENT ON TABLE activity_impact IS 'Learned correlations between activities and wellness metrics.';

-- ============================================================================
-- HEALTH ALERTS TABLE
-- Stores health alerts generated from pattern analysis
-- ============================================================================

CREATE TABLE IF NOT EXISTS health_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    
    -- Alert details
    alert_date DATE NOT NULL,
    alert_level VARCHAR(20) NOT NULL,         -- INFO, MEDIUM, HIGH, CRITICAL
    alert_type VARCHAR(50) NOT NULL,          -- 'sleep_debt', 'mood_decline', 'energy_low', etc.
    alert_text TEXT NOT NULL,
    
    -- Severity and action
    severity_score FLOAT CHECK (severity_score >= 0 AND severity_score <= 10),
    requires_immediate_action BOOLEAN DEFAULT FALSE,
    recommendations JSONB DEFAULT '[]',
    
    -- User response
    user_acknowledged BOOLEAN DEFAULT FALSE,
    user_response TEXT,
    acknowledged_at TIMESTAMPTZ,
    
    -- Resolution
    resolved BOOLEAN DEFAULT FALSE,
    resolved_date DATE,
    resolution_notes TEXT,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_health_alerts_user ON health_alerts(user_id);
CREATE INDEX IF NOT EXISTS idx_health_alerts_date ON health_alerts(alert_date);
CREATE INDEX IF NOT EXISTS idx_health_alerts_level ON health_alerts(alert_level);
CREATE INDEX IF NOT EXISTS idx_health_alerts_resolved ON health_alerts(resolved);

COMMENT ON TABLE health_alerts IS 'Health alerts generated from pattern analysis.';

-- ============================================================================
-- PREDICTIONS TABLE
-- Stores AI-generated predictions
-- ============================================================================

CREATE TABLE IF NOT EXISTS predictions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    prediction_date DATE NOT NULL,
    
    -- Next-day predictions
    predicted_sleep FLOAT,
    predicted_sleep_confidence FLOAT CHECK (predicted_sleep_confidence >= 0 AND predicted_sleep_confidence <= 1),
    predicted_mood FLOAT,
    predicted_mood_confidence FLOAT CHECK (predicted_mood_confidence >= 0 AND predicted_mood_confidence <= 1),
    predicted_energy FLOAT,
    predicted_energy_confidence FLOAT CHECK (predicted_energy_confidence >= 0 AND predicted_energy_confidence <= 1),
    
    -- Extended forecasts
    week_forecast JSONB,
    activity_recommendations JSONB,
    factors JSONB,                            -- Factors influencing predictions
    
    -- Metadata
    model_version VARCHAR(20) DEFAULT 'v2.0',
    valid_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_predictions_user ON predictions(user_id);
CREATE INDEX IF NOT EXISTS idx_predictions_date ON predictions(prediction_date);

COMMENT ON TABLE predictions IS 'AI-generated predictions for next-day and weekly forecasts.';

-- ============================================================================
-- USER CONTEXT STATE TABLE
-- Real-time user context for fast retrieval
-- ============================================================================

CREATE TABLE IF NOT EXISTS user_context_state (
    user_id UUID PRIMARY KEY,
    
    -- Current metrics
    current_mood_score FLOAT,
    current_energy_level INT,
    current_stress_level INT,
    
    -- Averages
    sleep_quality_avg_7d FLOAT,
    productivity_score_avg_7d FLOAT,
    
    -- Task tracking
    active_goals_count INT DEFAULT 0,
    pending_tasks_count INT DEFAULT 0,
    completed_tasks_today INT DEFAULT 0,
    
    -- Extended context
    context_data JSONB DEFAULT '{}',
    
    -- Timestamp
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE user_context_state IS 'Real-time user context for fast API responses.';

-- ============================================================================
-- VIEWS FOR PATTERN ANALYSIS
-- ============================================================================

-- Day-of-week average mood
CREATE OR REPLACE VIEW v_dow_mood_patterns AS
SELECT 
    je.user_id,
    EXTRACT(DOW FROM je.entry_date) as day_of_week,
    AVG((em.value)::float) as avg_mood,
    STDDEV((em.value)::float) as stddev_mood,
    COUNT(*) as sample_count
FROM journal_extractions je
JOIN extraction_metrics em ON je.id = em.extraction_id
JOIN metric_types mt ON em.metric_type_id = mt.id
WHERE mt.name = 'mood_score'
GROUP BY je.user_id, EXTRACT(DOW FROM je.entry_date);

-- 7-day rolling averages
CREATE OR REPLACE VIEW v_rolling_averages AS
SELECT 
    je.user_id,
    je.entry_date,
    AVG((em.value)::float) FILTER (WHERE mt.name = 'mood_score') 
        OVER (PARTITION BY je.user_id ORDER BY je.entry_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) as avg_mood_7d,
    AVG((em.value)::float) FILTER (WHERE mt.name = 'energy_level') 
        OVER (PARTITION BY je.user_id ORDER BY je.entry_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) as avg_energy_7d,
    AVG((em.value)::float) FILTER (WHERE mt.name = 'sleep_duration') 
        OVER (PARTITION BY je.user_id ORDER BY je.entry_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) as avg_sleep_7d,
    AVG((em.value)::float) FILTER (WHERE mt.name = 'stress_level') 
        OVER (PARTITION BY je.user_id ORDER BY je.entry_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) as avg_stress_7d
FROM journal_extractions je
JOIN extraction_metrics em ON je.id = em.extraction_id
JOIN metric_types mt ON em.metric_type_id = mt.id;

-- ============================================================================
-- FUNCTIONS FOR PATTERN CALCULATION
-- ============================================================================

-- Calculate user baseline from recent entries
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
        LEAST(p_sample_count::FLOAT / 30.0, 1.0),  -- Confidence based on samples
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

COMMENT ON FUNCTION calculate_user_baseline IS 'Calculates user baseline metrics from journal extractions.';
COMMENT ON FUNCTION update_user_pattern_cache IS 'Upserts a user pattern into the cache.';
