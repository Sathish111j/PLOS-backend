-- ============================================================================
-- PLOS v2.0 DATABASE SCHEMA
-- Intelligent Journal Processing with Context, Inference & Prediction
-- ============================================================================

-- ============================================================================
-- ENUMS
-- ============================================================================

CREATE TYPE relationship_state AS ENUM (
    'HARMONY',
    'TENSION',
    'CONFLICT',
    'COLD_WAR',
    'RECOVERY',
    'RESOLVED'
);

CREATE TYPE alert_level AS ENUM (
    'INFO',
    'MEDIUM',
    'HIGH',
    'CRITICAL'
);

CREATE TYPE extraction_type AS ENUM (
    'explicit',
    'inferred',
    'estimated',
    'default'
);

CREATE TYPE quality_level AS ENUM (
    'EXCELLENT',
    'VERY_GOOD',
    'GOOD',
    'ACCEPTABLE',
    'POOR',
    'UNRELIABLE'
);

CREATE TYPE trajectory AS ENUM (
    'improving',
    'stable',
    'worsening'
);

-- ============================================================================
-- CORE EXTRACTION TABLE
-- ============================================================================

CREATE TABLE journal_extractions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    entry_date DATE NOT NULL,
    
    -- Raw and processed data
    raw_entry TEXT NOT NULL,
    extracted_data JSONB NOT NULL,
    
    -- Metadata about extraction
    extraction_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    overall_confidence FLOAT CHECK (overall_confidence >= 0 AND overall_confidence <= 1),
    quality_score FLOAT CHECK (quality_score >= 0 AND quality_score <= 1),
    quality_level quality_level,
    
    -- Context at extraction time
    user_baseline JSONB,
    day_of_week_pattern JSONB,
    
    -- State tracking
    relationship_state relationship_state,
    relationship_state_day INT DEFAULT 0,
    sleep_debt_cumulative FLOAT DEFAULT 0,
    fatigue_trajectory trajectory,
    mood_trajectory trajectory,
    
    -- Detected issues
    anomalies_detected TEXT[] DEFAULT ARRAY[]::TEXT[],
    health_alerts TEXT[] DEFAULT ARRAY[]::TEXT[],
    clarification_needed TEXT[] DEFAULT ARRAY[]::TEXT[],
    
    -- Temporal linkage
    previous_entry_id UUID,
    conflict_resolution_status TEXT,
    
    -- Timing
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT fk_previous_entry FOREIGN KEY (previous_entry_id) 
        REFERENCES journal_extractions(id) ON DELETE SET NULL
);

-- Indexes for performance
CREATE INDEX idx_journal_user_date ON journal_extractions(user_id, entry_date DESC);
CREATE INDEX idx_journal_quality ON journal_extractions(user_id, quality_score DESC);
CREATE INDEX idx_journal_state ON journal_extractions(user_id, relationship_state);
CREATE INDEX idx_journal_anomalies ON journal_extractions USING GIN(anomalies_detected);
CREATE INDEX idx_journal_created ON journal_extractions(created_at DESC);

-- ============================================================================
-- USER PATTERNS & BASELINES
-- ============================================================================

CREATE TABLE user_patterns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    
    pattern_type TEXT NOT NULL,
    -- "sleep_baseline", "mood_baseline", "energy_baseline", 
    -- "activity_frequency", "conflict_frequency"
    
    value FLOAT,
    std_dev FLOAT,
    
    -- Optionally specific to day of week
    day_of_week INT, -- 0=Monday, 6=Sunday, NULL=overall
    
    sample_count INT DEFAULT 0,
    last_updated TIMESTAMP DEFAULT NOW(),
    confidence FLOAT CHECK (confidence >= 0 AND confidence <= 1),
    
    -- Additional metadata
    metadata JSONB DEFAULT '{}'::jsonb,
    
    created_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(user_id, pattern_type, day_of_week)
);

CREATE INDEX idx_patterns_user ON user_patterns(user_id, pattern_type);
CREATE INDEX idx_patterns_updated ON user_patterns(last_updated DESC);

-- ============================================================================
-- RELATIONSHIP HISTORY
-- ============================================================================

CREATE TABLE relationship_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    
    event_date DATE NOT NULL,
    state_before relationship_state,
    state_after relationship_state,
    trigger TEXT,
    severity INT CHECK (severity >= 1 AND severity <= 10),
    
    resolution_date DATE,
    resolution_days INT,
    what_worked TEXT,
    
    -- Additional details
    notes TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_relationship_user_date ON relationship_history(user_id, event_date DESC);
CREATE INDEX idx_relationship_unresolved ON relationship_history(user_id, resolution_date) 
    WHERE resolution_date IS NULL;
CREATE INDEX idx_relationship_severity ON relationship_history(user_id, severity DESC);

-- ============================================================================
-- ACTIVITY IMPACT TRACKING
-- ============================================================================

CREATE TABLE activity_impact (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    
    activity_type TEXT NOT NULL,
    -- "badminton", "programming", "work", "instagram", "conflict", etc
    
    occurrence_count INT DEFAULT 0,
    
    -- Average impacts
    avg_mood_impact FLOAT,
    avg_energy_impact FLOAT,
    avg_sleep_impact FLOAT,
    avg_focus_impact FLOAT,
    
    avg_duration_minutes FLOAT,
    avg_satisfaction FLOAT CHECK (avg_satisfaction >= 0 AND avg_satisfaction <= 10),
    
    confidence FLOAT CHECK (confidence >= 0 AND confidence <= 1),
    last_occurred DATE,
    
    -- Additional metadata
    metadata JSONB DEFAULT '{}'::jsonb,
    
    last_updated TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(user_id, activity_type)
);

CREATE INDEX idx_activity_user ON activity_impact(user_id, activity_type);
CREATE INDEX idx_activity_impact ON activity_impact(user_id, avg_mood_impact DESC);
CREATE INDEX idx_activity_satisfaction ON activity_impact(user_id, avg_satisfaction DESC);

-- ============================================================================
-- SLEEP DEBT TRACKING
-- ============================================================================

CREATE TABLE sleep_debt_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    
    entry_date DATE NOT NULL,
    sleep_hours FLOAT CHECK (sleep_hours >= 0 AND sleep_hours <= 24),
    baseline_hours FLOAT,
    
    debt_this_day FLOAT,  -- baseline - actual
    debt_cumulative FLOAT,  -- running total
    
    recovery_sleep_needed FLOAT,  -- to get back to zero debt
    
    -- Metadata
    metadata JSONB DEFAULT '{}'::jsonb,
    
    created_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(user_id, entry_date)
);

CREATE INDEX idx_sleep_debt_user_date ON sleep_debt_log(user_id, entry_date DESC);
CREATE INDEX idx_sleep_debt_cumulative ON sleep_debt_log(user_id, debt_cumulative DESC);

-- ============================================================================
-- HEALTH ALERTS
-- ============================================================================

CREATE TABLE health_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    
    alert_date DATE NOT NULL,
    alert_level alert_level NOT NULL,
    alert_type TEXT NOT NULL,
    -- "sleep_debt", "mood_crash", "conflict_prolonged", "insomnia_pattern", etc
    alert_text TEXT NOT NULL,
    
    recommendations TEXT[] DEFAULT ARRAY[]::TEXT[],
    severity_score FLOAT CHECK (severity_score >= 0 AND severity_score <= 10),
    requires_immediate_action BOOLEAN DEFAULT FALSE,
    
    user_acknowledged BOOLEAN DEFAULT FALSE,
    user_response TEXT,
    acknowledged_at TIMESTAMP,
    
    resolved BOOLEAN DEFAULT FALSE,
    resolved_date DATE,
    resolution_notes TEXT,
    
    -- Metadata
    metadata JSONB DEFAULT '{}'::jsonb,
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_alerts_user_date ON health_alerts(user_id, alert_date DESC);
CREATE INDEX idx_alerts_unresolved ON health_alerts(user_id, resolved) 
    WHERE resolved = FALSE;
CREATE INDEX idx_alerts_level ON health_alerts(user_id, alert_level);
CREATE INDEX idx_alerts_type ON health_alerts(user_id, alert_type);

-- ============================================================================
-- PREDICTIONS CACHE
-- ============================================================================

CREATE TABLE predictions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    prediction_date DATE NOT NULL,
    
    -- Next day predictions
    predicted_sleep FLOAT,
    predicted_sleep_confidence FLOAT,
    predicted_mood FLOAT,
    predicted_mood_confidence FLOAT,
    predicted_energy FLOAT,
    predicted_energy_confidence FLOAT,
    
    -- Week forecast
    week_forecast JSONB,
    
    -- Activity recommendations
    activity_recommendations JSONB,
    
    -- Metadata
    factors JSONB, -- What influenced the prediction
    model_version TEXT,
    
    created_at TIMESTAMP DEFAULT NOW(),
    valid_until TIMESTAMP,
    
    UNIQUE(user_id, prediction_date)
);

CREATE INDEX idx_predictions_user_date ON predictions(user_id, prediction_date DESC);
CREATE INDEX idx_predictions_valid ON predictions(user_id, valid_until) 
    WHERE valid_until > NOW();

-- ============================================================================
-- MATERIALIZED VIEWS FOR PERFORMANCE
-- ============================================================================

-- 7-day context view (refreshed every hour)
CREATE MATERIALIZED VIEW mv_user_7day_context AS
SELECT 
    user_id,
    AVG(CAST(extracted_data->>'mood_score' AS FLOAT)) as avg_mood_7d,
    AVG(CAST(extracted_data->>'energy_level' AS FLOAT)) as avg_energy_7d,
    AVG(CAST(extracted_data->>'stress_level' AS FLOAT)) as avg_stress_7d,
    AVG(CAST(extracted_data->'health'->>'sleep_hours' AS FLOAT)) as avg_sleep_7d,
    AVG(CAST(extracted_data->'health'->>'sleep_quality' AS FLOAT)) as avg_sleep_quality_7d,
    COUNT(*) as entry_count_7d,
    MAX(entry_date) as last_entry_date
FROM journal_extractions
WHERE entry_date >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY user_id;

CREATE UNIQUE INDEX idx_mv_7day_user ON mv_user_7day_context(user_id);

-- 30-day baseline view (refreshed daily)
CREATE MATERIALIZED VIEW mv_user_30day_baseline AS
SELECT 
    user_id,
    AVG(CAST(extracted_data->>'mood_score' AS FLOAT)) as baseline_mood,
    STDDEV(CAST(extracted_data->>'mood_score' AS FLOAT)) as stddev_mood,
    AVG(CAST(extracted_data->>'energy_level' AS FLOAT)) as baseline_energy,
    STDDEV(CAST(extracted_data->>'energy_level' AS FLOAT)) as stddev_energy,
    AVG(CAST(extracted_data->'health'->>'sleep_hours' AS FLOAT)) as baseline_sleep,
    STDDEV(CAST(extracted_data->'health'->>'sleep_hours' AS FLOAT)) as stddev_sleep,
    COUNT(*) as sample_count
FROM journal_extractions
WHERE entry_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY user_id;

CREATE UNIQUE INDEX idx_mv_30day_user ON mv_user_30day_baseline(user_id);

-- ============================================================================
-- TRIGGERS
-- ============================================================================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_journal_extractions_updated_at
    BEFORE UPDATE ON journal_extractions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- FUNCTIONS
-- ============================================================================

-- Function to refresh materialized views
CREATE OR REPLACE FUNCTION refresh_context_views()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_user_7day_context;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_user_30day_baseline;
END;
$$ LANGUAGE plpgsql;

-- Schedule refresh (requires pg_cron extension)
-- SELECT cron.schedule('refresh-7day-context', '0 * * * *', 'SELECT refresh_context_views()');

-- ============================================================================
-- GRANTS (adjust as needed)
-- ============================================================================

-- Grant access to application user (replace 'plos_app' with actual user)
-- GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO plos_app;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO plos_app;

-- ============================================================================
-- COMMENTS FOR DOCUMENTATION
-- ============================================================================

COMMENT ON TABLE journal_extractions IS 'Core extraction table with full context and intelligence';
COMMENT ON TABLE user_patterns IS 'User baselines and patterns (30-day rolling, day-of-week)';
COMMENT ON TABLE relationship_history IS 'Relationship state machine history and transitions';
COMMENT ON TABLE activity_impact IS 'Correlation matrix of activities to mood/energy/sleep';
COMMENT ON TABLE sleep_debt_log IS 'Sleep debt accumulation tracking';
COMMENT ON TABLE health_alerts IS 'Health monitoring alerts and user responses';
COMMENT ON TABLE predictions IS 'Cached predictions for next day and week forecast';

COMMENT ON COLUMN journal_extractions.extracted_data IS 'JSONB with all extracted fields + confidence scores';
COMMENT ON COLUMN journal_extractions.extraction_metadata IS 'Quality scores, sources, inference details';
COMMENT ON COLUMN journal_extractions.user_baseline IS 'Baseline metrics at time of extraction';
COMMENT ON COLUMN journal_extractions.relationship_state IS 'Current relationship state at time of entry';
COMMENT ON COLUMN journal_extractions.sleep_debt_cumulative IS 'Accumulated sleep debt in hours';
COMMENT ON COLUMN journal_extractions.anomalies_detected IS 'List of detected anomalies';

-- ============================================================================
-- END OF SCHEMA
-- ============================================================================
