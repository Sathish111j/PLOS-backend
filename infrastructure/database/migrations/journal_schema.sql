-- ============================================================================
-- PLOS v2.2 GENERALIZED DATABASE SCHEMA
-- Handles infinite variety of user data with controlled vocabulary
-- ============================================================================

-- ============================================================================
-- DESIGN PHILOSOPHY
-- ============================================================================
-- 
-- PROBLEM: Users have infinite variety of hobbies, foods, activities
-- PROBLEM: Gemini might extract "exercise_time" vs "exercise_duration" 
-- PROBLEM: "yoga" could be under "exercise", "sport", or "wellness"
-- PROBLEM: Can't have endless tables for each category
--
-- SOLUTION: 
-- 1. Controlled vocabulary tables (canonical names)
-- 2. Generic extraction tables with foreign keys
-- 3. Category hierarchy for flexible grouping
-- 4. Alias/synonym mapping for normalization
--
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For fuzzy text matching

-- ============================================================================
-- ENUMS
-- ============================================================================

CREATE TYPE extraction_quality AS ENUM ('high', 'medium', 'low');
CREATE TYPE time_of_day AS ENUM ('early_morning', 'morning', 'afternoon', 'evening', 'night', 'late_night');
CREATE TYPE data_gap_status AS ENUM ('pending', 'answered', 'skipped', 'expired');

-- ============================================================================
-- CONTROLLED VOCABULARY: CATEGORIES
-- Hierarchical category system
-- ============================================================================

CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,        -- canonical name: "physical_activity"
    display_name VARCHAR(100) NOT NULL,       -- "Physical Activity"
    parent_id INT REFERENCES categories(id),  -- hierarchy
    description TEXT,
    icon VARCHAR(50),                         -- for UI
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert base categories
INSERT INTO categories (name, display_name, parent_id, description) VALUES
-- Top level
('wellness', 'Wellness', NULL, 'Overall health and wellness metrics'),
('activities', 'Activities', NULL, 'Things you do'),
('consumption', 'Consumption', NULL, 'Food, drinks, substances'),
('social', 'Social', NULL, 'Interactions with people'),
('productivity', 'Productivity', NULL, 'Work and goals'),
('reflection', 'Reflection', NULL, 'Thoughts and gratitude'),

-- Wellness subcategories
('sleep', 'Sleep', 1, 'Sleep tracking'),
('mood', 'Mood', 1, 'Emotional state'),
('energy', 'Energy', 1, 'Energy levels'),
('stress', 'Stress', 1, 'Stress levels'),
('health', 'Health', 1, 'Physical health'),

-- Activity subcategories
('physical', 'Physical Activity', 2, 'Exercise, sports, movement'),
('mental', 'Mental Activity', 2, 'Learning, reading, puzzles'),
('creative', 'Creative', 2, 'Art, music, writing'),
('leisure', 'Leisure', 2, 'Entertainment, relaxation'),
('chores', 'Chores', 2, 'Household tasks'),

-- Consumption subcategories
('meals', 'Meals', 3, 'Food intake'),
('hydration', 'Hydration', 3, 'Water and beverages'),
('substances', 'Substances', 3, 'Medications, supplements, alcohol, caffeine');

CREATE INDEX idx_categories_parent ON categories(parent_id);
CREATE INDEX idx_categories_name ON categories(name);

-- ============================================================================
-- CONTROLLED VOCABULARY: ACTIVITY TYPES
-- Master list of known activities with canonical names
-- ============================================================================

CREATE TABLE activity_types (
    id SERIAL PRIMARY KEY,
    canonical_name VARCHAR(100) NOT NULL UNIQUE,  -- "badminton", "running", "yoga"
    display_name VARCHAR(100) NOT NULL,
    category_id INT NOT NULL REFERENCES categories(id),
    
    -- Metadata
    is_physical BOOLEAN DEFAULT FALSE,
    is_screen_time BOOLEAN DEFAULT FALSE,
    avg_calories_per_hour INT,                    -- for estimation
    typical_duration_minutes INT,                 -- default duration
    
    -- Search
    search_vector TSVECTOR,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert common activities
INSERT INTO activity_types (canonical_name, display_name, category_id, is_physical, is_screen_time, avg_calories_per_hour) VALUES
-- Physical (category_id = 12)
('running', 'Running', 12, TRUE, FALSE, 600),
('walking', 'Walking', 12, TRUE, FALSE, 280),
('cycling', 'Cycling', 12, TRUE, FALSE, 500),
('swimming', 'Swimming', 12, TRUE, FALSE, 550),
('gym', 'Gym Workout', 12, TRUE, FALSE, 400),
('yoga', 'Yoga', 12, TRUE, FALSE, 200),
('badminton', 'Badminton', 12, TRUE, FALSE, 450),
('cricket', 'Cricket', 12, TRUE, FALSE, 350),
('football', 'Football', 12, TRUE, FALSE, 500),
('basketball', 'Basketball', 12, TRUE, FALSE, 550),
('tennis', 'Tennis', 12, TRUE, FALSE, 450),
('dancing', 'Dancing', 12, TRUE, FALSE, 400),

-- Mental (category_id = 13)
('reading', 'Reading', 13, FALSE, FALSE, 50),
('studying', 'Studying', 13, FALSE, FALSE, 50),
('programming', 'Programming', 13, FALSE, TRUE, 80),
('learning', 'Learning', 13, FALSE, FALSE, 50),
('meditation', 'Meditation', 13, FALSE, FALSE, 50),
('puzzles', 'Puzzles', 13, FALSE, FALSE, 50),

-- Creative (category_id = 14)
('writing', 'Writing', 14, FALSE, FALSE, 50),
('drawing', 'Drawing', 14, FALSE, FALSE, 50),
('music_playing', 'Playing Music', 14, FALSE, FALSE, 100),
('photography', 'Photography', 14, FALSE, FALSE, 80),

-- Leisure (category_id = 15)
('watching_tv', 'Watching TV', 15, FALSE, TRUE, 50),
('gaming', 'Gaming', 15, FALSE, TRUE, 80),
('social_media', 'Social Media', 15, FALSE, TRUE, 50),
('netflix', 'Netflix/Streaming', 15, FALSE, TRUE, 50),
('youtube', 'YouTube', 15, FALSE, TRUE, 50),
('music_listening', 'Listening to Music', 15, FALSE, FALSE, 50),

-- Chores (category_id = 16)
('cooking', 'Cooking', 16, FALSE, FALSE, 150),
('cleaning', 'Cleaning', 16, TRUE, FALSE, 200),
('shopping', 'Shopping', 16, TRUE, FALSE, 150),
('laundry', 'Laundry', 16, FALSE, FALSE, 100),
('gardening', 'Gardening', 16, TRUE, FALSE, 250);

CREATE INDEX idx_activity_types_category ON activity_types(category_id);
CREATE INDEX idx_activity_types_search ON activity_types USING GIN(search_vector);

-- ============================================================================
-- ALIASES / SYNONYMS
-- Maps user variations to canonical names
-- "jogging" -> "running", "gymming" -> "gym", "insta" -> "social_media"
-- ============================================================================

CREATE TABLE activity_aliases (
    id SERIAL PRIMARY KEY,
    alias VARCHAR(100) NOT NULL,              -- user's term: "jogging", "gymming"
    activity_type_id INT NOT NULL REFERENCES activity_types(id),
    confidence FLOAT DEFAULT 1.0,             -- how sure we are about this mapping
    source VARCHAR(50) DEFAULT 'manual',      -- 'manual', 'learned', 'ai_suggested'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(alias)
);

-- Insert common aliases
INSERT INTO activity_aliases (alias, activity_type_id) VALUES
('jogging', (SELECT id FROM activity_types WHERE canonical_name = 'running')),
('jog', (SELECT id FROM activity_types WHERE canonical_name = 'running')),
('run', (SELECT id FROM activity_types WHERE canonical_name = 'running')),
('gymming', (SELECT id FROM activity_types WHERE canonical_name = 'gym')),
('workout', (SELECT id FROM activity_types WHERE canonical_name = 'gym')),
('working out', (SELECT id FROM activity_types WHERE canonical_name = 'gym')),
('exercise', (SELECT id FROM activity_types WHERE canonical_name = 'gym')),
('insta', (SELECT id FROM activity_types WHERE canonical_name = 'social_media')),
('instagram', (SELECT id FROM activity_types WHERE canonical_name = 'social_media')),
('twitter', (SELECT id FROM activity_types WHERE canonical_name = 'social_media')),
('facebook', (SELECT id FROM activity_types WHERE canonical_name = 'social_media')),
('scrolling', (SELECT id FROM activity_types WHERE canonical_name = 'social_media')),
('coding', (SELECT id FROM activity_types WHERE canonical_name = 'programming')),
('code', (SELECT id FROM activity_types WHERE canonical_name = 'programming')),
('swim', (SELECT id FROM activity_types WHERE canonical_name = 'swimming')),
('bike', (SELECT id FROM activity_types WHERE canonical_name = 'cycling')),
('biking', (SELECT id FROM activity_types WHERE canonical_name = 'cycling')),
('walk', (SELECT id FROM activity_types WHERE canonical_name = 'walking')),
('stroll', (SELECT id FROM activity_types WHERE canonical_name = 'walking')),
('meditate', (SELECT id FROM activity_types WHERE canonical_name = 'meditation')),
('meditating', (SELECT id FROM activity_types WHERE canonical_name = 'meditation'));

CREATE INDEX idx_aliases_alias ON activity_aliases(alias);
CREATE INDEX idx_aliases_trgm ON activity_aliases USING GIN(alias gin_trgm_ops);

-- ============================================================================
-- FOOD VOCABULARY
-- Common foods with nutrition data for estimation
-- ============================================================================

CREATE TABLE food_items (
    id SERIAL PRIMARY KEY,
    canonical_name VARCHAR(100) NOT NULL UNIQUE,
    display_name VARCHAR(100) NOT NULL,
    category VARCHAR(50),  -- 'grain', 'protein', 'vegetable', 'fruit', 'dairy', 'junk'
    
    -- Nutrition per 100g or per serving
    serving_size_g INT DEFAULT 100,
    calories_per_serving INT,
    protein_g FLOAT,
    carbs_g FLOAT,
    fat_g FLOAT,
    fiber_g FLOAT,
    
    is_healthy BOOLEAN,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert common foods (Indian + Western)
INSERT INTO food_items (canonical_name, display_name, category, calories_per_serving, protein_g, carbs_g, fat_g, is_healthy) VALUES
-- Indian staples
('rice', 'Rice', 'grain', 130, 2.7, 28, 0.3, TRUE),
('roti', 'Roti/Chapati', 'grain', 120, 3.5, 20, 3.5, TRUE),
('dal', 'Dal', 'protein', 120, 9, 20, 1, TRUE),
('sabzi', 'Vegetable Curry', 'vegetable', 100, 3, 10, 5, TRUE),
('paratha', 'Paratha', 'grain', 200, 4, 25, 10, FALSE),
('biryani', 'Biryani', 'grain', 250, 8, 35, 10, FALSE),
('dosa', 'Dosa', 'grain', 120, 3, 18, 4, TRUE),
('idli', 'Idli', 'grain', 80, 2, 15, 0.5, TRUE),
('samosa', 'Samosa', 'junk', 250, 4, 25, 15, FALSE),
('paneer', 'Paneer', 'protein', 265, 18, 1, 21, TRUE),
('curd', 'Curd/Yogurt', 'dairy', 60, 3, 5, 3, TRUE),

-- Western
('chicken_breast', 'Chicken Breast', 'protein', 165, 31, 0, 3.6, TRUE),
('egg', 'Egg', 'protein', 78, 6, 0.6, 5, TRUE),
('oats', 'Oats', 'grain', 150, 5, 27, 3, TRUE),
('bread', 'Bread', 'grain', 80, 3, 15, 1, TRUE),
('pasta', 'Pasta', 'grain', 200, 7, 40, 1, TRUE),
('pizza', 'Pizza', 'junk', 285, 12, 36, 10, FALSE),
('burger', 'Burger', 'junk', 354, 20, 29, 17, FALSE),
('salad', 'Salad', 'vegetable', 50, 2, 8, 1, TRUE),
('fruits', 'Fruits', 'fruit', 60, 1, 15, 0, TRUE),
('milk', 'Milk', 'dairy', 60, 3, 5, 3, TRUE),

-- Beverages
('coffee', 'Coffee', 'beverage', 5, 0, 0, 0, TRUE),
('tea', 'Tea', 'beverage', 5, 0, 1, 0, TRUE),
('juice', 'Fruit Juice', 'beverage', 110, 1, 26, 0, FALSE),
('soda', 'Soda', 'beverage', 140, 0, 39, 0, FALSE),
('water', 'Water', 'beverage', 0, 0, 0, 0, TRUE);

CREATE INDEX idx_food_items_category ON food_items(category);

-- Food aliases
CREATE TABLE food_aliases (
    id SERIAL PRIMARY KEY,
    alias VARCHAR(100) NOT NULL UNIQUE,
    food_item_id INT NOT NULL REFERENCES food_items(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO food_aliases (alias, food_item_id) VALUES
('chapati', (SELECT id FROM food_items WHERE canonical_name = 'roti')),
('chapatti', (SELECT id FROM food_items WHERE canonical_name = 'roti')),
('naan', (SELECT id FROM food_items WHERE canonical_name = 'roti')),
('white rice', (SELECT id FROM food_items WHERE canonical_name = 'rice')),
('brown rice', (SELECT id FROM food_items WHERE canonical_name = 'rice')),
('lentils', (SELECT id FROM food_items WHERE canonical_name = 'dal')),
('daal', (SELECT id FROM food_items WHERE canonical_name = 'dal')),
('veggies', (SELECT id FROM food_items WHERE canonical_name = 'sabzi')),
('vegetables', (SELECT id FROM food_items WHERE canonical_name = 'sabzi')),
('cottage cheese', (SELECT id FROM food_items WHERE canonical_name = 'paneer')),
('yogurt', (SELECT id FROM food_items WHERE canonical_name = 'curd')),
('chai', (SELECT id FROM food_items WHERE canonical_name = 'tea'));

-- ============================================================================
-- CORE EXTRACTION TABLE
-- One per journal entry
-- ============================================================================

CREATE TABLE journal_extractions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    entry_date DATE NOT NULL,
    
    -- Raw input
    raw_entry TEXT NOT NULL,
    preprocessed_entry TEXT,
    
    -- Quality
    overall_quality extraction_quality,
    extraction_time_ms INT,
    gemini_model VARCHAR(50),
    
    -- Gaps
    has_gaps BOOLEAN DEFAULT FALSE,
    gaps_resolved BOOLEAN DEFAULT FALSE,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(user_id, entry_date)
);

CREATE INDEX idx_extractions_user_date ON journal_extractions(user_id, entry_date);

-- ============================================================================
-- DATA GAPS / CLARIFICATION QUESTIONS
-- Questions LLM needs to ask user
-- ============================================================================

CREATE TABLE extraction_gaps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    extraction_id UUID NOT NULL REFERENCES journal_extractions(id) ON DELETE CASCADE,
    
    -- The gap
    field_category VARCHAR(50) NOT NULL,      -- 'activity', 'meal', 'sleep'
    question TEXT NOT NULL,                    -- "What sport did you play?"
    context TEXT,                              -- "You mentioned 'played well'"
    original_mention TEXT,                     -- The exact text that's ambiguous
    
    -- Priority
    priority INT DEFAULT 1,                    -- 1 = high, 2 = medium, 3 = low
    
    -- Resolution
    status data_gap_status DEFAULT 'pending',
    user_response TEXT,
    resolved_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_gaps_extraction ON extraction_gaps(extraction_id);
CREATE INDEX idx_gaps_status ON extraction_gaps(status);

-- ============================================================================
-- METRIC EXTRACTIONS (numeric scores)
-- Sleep, mood, energy, stress, etc.
-- Generic key-value with controlled metric types
-- ============================================================================

CREATE TABLE metric_types (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,         -- 'sleep_duration', 'mood_score'
    display_name VARCHAR(100) NOT NULL,
    category_id INT REFERENCES categories(id),
    unit VARCHAR(20),                          -- 'hours', 'score_1_10', 'level_1_10'
    min_value FLOAT,
    max_value FLOAT,
    description TEXT
);

INSERT INTO metric_types (name, display_name, category_id, unit, min_value, max_value) VALUES
('sleep_duration', 'Sleep Duration', 7, 'hours', 0, 24),
('sleep_quality', 'Sleep Quality', 7, 'score_1_10', 1, 10),
('mood_score', 'Mood Score', 8, 'score_1_10', 1, 10),
('energy_level', 'Energy Level', 9, 'score_1_10', 1, 10),
('stress_level', 'Stress Level', 10, 'score_1_10', 1, 10),
('productivity_score', 'Productivity', 5, 'score_1_10', 1, 10),
('focus_level', 'Focus Level', 5, 'score_1_10', 1, 10),
('water_intake', 'Water Intake', 18, 'liters', 0, 10),
('coffee_cups', 'Coffee Cups', 18, 'count', 0, 20),
('work_hours', 'Work Hours', 5, 'hours', 0, 24),
('screen_time', 'Screen Time', 2, 'hours', 0, 24);

CREATE TABLE extraction_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    extraction_id UUID NOT NULL REFERENCES journal_extractions(id) ON DELETE CASCADE,
    metric_type_id INT NOT NULL REFERENCES metric_types(id),
    
    value FLOAT NOT NULL,
    confidence FLOAT DEFAULT 0.5,
    time_of_day time_of_day,                  -- when was this measured
    raw_mention TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(extraction_id, metric_type_id, time_of_day)
);

CREATE INDEX idx_metrics_extraction ON extraction_metrics(extraction_id);
CREATE INDEX idx_metrics_type ON extraction_metrics(metric_type_id);

-- ============================================================================
-- ACTIVITY EXTRACTIONS
-- Generic activity tracking with controlled vocabulary
-- ============================================================================

CREATE TABLE extraction_activities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    extraction_id UUID NOT NULL REFERENCES journal_extractions(id) ON DELETE CASCADE,
    
    -- Activity reference (can be NULL if unknown)
    activity_type_id INT REFERENCES activity_types(id),
    activity_raw VARCHAR(100),                -- original text if not matched
    
    -- Timing
    start_time TIME,
    end_time TIME,
    duration_minutes INT,
    time_of_day time_of_day,
    
    -- Metrics
    intensity VARCHAR(10) CHECK (intensity IN ('low', 'medium', 'high')),
    satisfaction INT CHECK (satisfaction >= 1 AND satisfaction <= 10),
    calories_burned INT,
    
    -- Extraction metadata
    confidence FLOAT DEFAULT 0.5,
    raw_mention TEXT,
    needs_clarification BOOLEAN DEFAULT FALSE,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_activities_extraction ON extraction_activities(extraction_id);
CREATE INDEX idx_activities_type ON extraction_activities(activity_type_id);
CREATE INDEX idx_activities_time ON extraction_activities(time_of_day);

-- ============================================================================
-- CONSUMPTION EXTRACTIONS (food, drinks, meds)
-- ============================================================================

CREATE TABLE extraction_consumptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    extraction_id UUID NOT NULL REFERENCES journal_extractions(id) ON DELETE CASCADE,
    
    -- Type
    consumption_type VARCHAR(20) NOT NULL CHECK (consumption_type IN ('meal', 'snack', 'drink', 'medication', 'supplement')),
    meal_type VARCHAR(20) CHECK (meal_type IN ('breakfast', 'lunch', 'dinner', 'snack')),
    
    -- Item reference (can be NULL if unknown)
    food_item_id INT REFERENCES food_items(id),
    item_raw VARCHAR(200),                    -- original text
    
    -- Timing
    consumption_time TIME,
    time_of_day time_of_day,
    
    -- Quantity
    quantity FLOAT DEFAULT 1,
    unit VARCHAR(20) DEFAULT 'serving',       -- 'serving', 'cup', 'piece', 'ml', 'g'
    
    -- Nutrition (estimated or extracted)
    calories INT,
    protein_g FLOAT,
    carbs_g FLOAT,
    fat_g FLOAT,
    
    -- Quality
    is_healthy BOOLEAN,
    is_home_cooked BOOLEAN,
    
    -- Metadata
    confidence FLOAT DEFAULT 0.5,
    raw_mention TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_consumptions_extraction ON extraction_consumptions(extraction_id);
CREATE INDEX idx_consumptions_type ON extraction_consumptions(consumption_type);
CREATE INDEX idx_consumptions_time ON extraction_consumptions(time_of_day);

-- ============================================================================
-- SOCIAL INTERACTIONS
-- ============================================================================

CREATE TABLE extraction_social (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    extraction_id UUID NOT NULL REFERENCES journal_extractions(id) ON DELETE CASCADE,
    
    -- Who
    person_name VARCHAR(100),
    relationship VARCHAR(50),                 -- 'friend', 'family', 'colleague', 'partner'
    
    -- What
    interaction_type VARCHAR(50),             -- 'in_person', 'call', 'video', 'message'
    sentiment VARCHAR(20) CHECK (sentiment IN ('positive', 'negative', 'neutral', 'conflict')),
    
    -- When
    interaction_time TIME,
    time_of_day time_of_day,
    duration_minutes INT,
    
    -- Details
    notes TEXT,
    confidence FLOAT DEFAULT 0.5,
    raw_mention TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_social_extraction ON extraction_social(extraction_id);
CREATE INDEX idx_social_person ON extraction_social(person_name);

-- ============================================================================
-- NOTES / FREE-FORM (goals, gratitude, symptoms, etc.)
-- ============================================================================

CREATE TABLE extraction_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    extraction_id UUID NOT NULL REFERENCES journal_extractions(id) ON DELETE CASCADE,
    
    note_type VARCHAR(50) NOT NULL,           -- 'goal', 'achievement', 'gratitude', 'symptom', 'thought'
    content TEXT NOT NULL,
    
    sentiment VARCHAR(20),
    confidence FLOAT DEFAULT 0.5,
    raw_mention TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_notes_extraction ON extraction_notes(extraction_id);
CREATE INDEX idx_notes_type ON extraction_notes(note_type);

-- ============================================================================
-- SLEEP DETAILS (special case - needs more structure)
-- ============================================================================

CREATE TABLE extraction_sleep (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    extraction_id UUID NOT NULL REFERENCES journal_extractions(id) ON DELETE CASCADE,
    
    duration_hours FLOAT,
    quality INT CHECK (quality >= 1 AND quality <= 10),
    
    bedtime TIME,
    waketime TIME,
    
    -- Sleep issues
    disruptions INT DEFAULT 0,
    trouble_falling_asleep BOOLEAN,
    woke_up_tired BOOLEAN,
    
    -- Naps
    nap_duration_minutes INT DEFAULT 0,
    nap_time time_of_day,
    
    confidence FLOAT DEFAULT 0.5,
    raw_mention TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(extraction_id)
);

-- ============================================================================
-- VIEWS FOR COMMON QUERIES
-- ============================================================================

-- Activity summary with canonical names
CREATE VIEW v_activity_summary AS
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

-- Daily nutrition summary
CREATE VIEW v_daily_nutrition AS
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

-- Pending gaps for user
CREATE VIEW v_pending_gaps AS
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

-- ============================================================================
-- FUNCTIONS
-- ============================================================================

-- Resolve activity name to canonical
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
    WHERE at.canonical_name % LOWER(p_name)  -- trigram similarity
    ORDER BY similarity(at.canonical_name, LOWER(p_name)) DESC
    LIMIT 1;
    
    RETURN v_type_id;  -- May be NULL
END;
$$ LANGUAGE plpgsql;

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

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE activity_types IS 'Controlled vocabulary for activities. New activities are added here with canonical names.';
COMMENT ON TABLE activity_aliases IS 'Maps user variations to canonical activity names. Grows over time as we learn new terms.';
COMMENT ON TABLE extraction_gaps IS 'Questions that need user clarification. LLM generates these when data is ambiguous.';
COMMENT ON FUNCTION resolve_activity_name IS 'Resolves user activity text to canonical activity_type_id using exact match, alias, then fuzzy match.';
