-- ============================================================================
-- PLOS Database Seed Data
-- Run after init.sql to populate controlled vocabulary tables
-- ============================================================================

-- ============================================================================
-- CATEGORIES (Hierarchical)
-- ============================================================================

INSERT INTO categories (name, display_name, parent_id, description) VALUES
-- Top level categories
('wellness', 'Wellness', NULL, 'Overall health and wellness metrics'),
('activities', 'Activities', NULL, 'Things you do'),
('consumption', 'Consumption', NULL, 'Food, drinks, substances'),
('social', 'Social', NULL, 'Interactions with people'),
('productivity', 'Productivity', NULL, 'Work and goals'),
('reflection', 'Reflection', NULL, 'Thoughts and gratitude')
ON CONFLICT (name) DO NOTHING;

-- Get parent IDs for subcategories
INSERT INTO categories (name, display_name, parent_id, description)
SELECT 'sleep', 'Sleep', id, 'Sleep tracking' FROM categories WHERE name = 'wellness'
ON CONFLICT (name) DO NOTHING;

INSERT INTO categories (name, display_name, parent_id, description)
SELECT 'mood', 'Mood', id, 'Emotional state' FROM categories WHERE name = 'wellness'
ON CONFLICT (name) DO NOTHING;

INSERT INTO categories (name, display_name, parent_id, description)
SELECT 'energy', 'Energy', id, 'Energy levels' FROM categories WHERE name = 'wellness'
ON CONFLICT (name) DO NOTHING;

INSERT INTO categories (name, display_name, parent_id, description)
SELECT 'stress', 'Stress', id, 'Stress levels' FROM categories WHERE name = 'wellness'
ON CONFLICT (name) DO NOTHING;

INSERT INTO categories (name, display_name, parent_id, description)
SELECT 'health', 'Health', id, 'Physical health' FROM categories WHERE name = 'wellness'
ON CONFLICT (name) DO NOTHING;

INSERT INTO categories (name, display_name, parent_id, description)
SELECT 'physical', 'Physical Activity', id, 'Exercise, sports, movement' FROM categories WHERE name = 'activities'
ON CONFLICT (name) DO NOTHING;

INSERT INTO categories (name, display_name, parent_id, description)
SELECT 'mental', 'Mental Activity', id, 'Learning, reading, puzzles' FROM categories WHERE name = 'activities'
ON CONFLICT (name) DO NOTHING;

INSERT INTO categories (name, display_name, parent_id, description)
SELECT 'creative', 'Creative', id, 'Art, music, writing' FROM categories WHERE name = 'activities'
ON CONFLICT (name) DO NOTHING;

INSERT INTO categories (name, display_name, parent_id, description)
SELECT 'leisure', 'Leisure', id, 'Entertainment, relaxation' FROM categories WHERE name = 'activities'
ON CONFLICT (name) DO NOTHING;

INSERT INTO categories (name, display_name, parent_id, description)
SELECT 'chores', 'Chores', id, 'Household tasks' FROM categories WHERE name = 'activities'
ON CONFLICT (name) DO NOTHING;

INSERT INTO categories (name, display_name, parent_id, description)
SELECT 'meals', 'Meals', id, 'Food intake' FROM categories WHERE name = 'consumption'
ON CONFLICT (name) DO NOTHING;

INSERT INTO categories (name, display_name, parent_id, description)
SELECT 'hydration', 'Hydration', id, 'Water and beverages' FROM categories WHERE name = 'consumption'
ON CONFLICT (name) DO NOTHING;

INSERT INTO categories (name, display_name, parent_id, description)
SELECT 'substances', 'Substances', id, 'Medications, supplements, alcohol, caffeine' FROM categories WHERE name = 'consumption'
ON CONFLICT (name) DO NOTHING;

-- ============================================================================
-- METRIC TYPES
-- ============================================================================

INSERT INTO metric_types (name, display_name, category_id, unit, min_value, max_value, description)
SELECT 'sleep_duration', 'Sleep Duration', id, 'hours', 0, 24, 'Hours of sleep'
FROM categories WHERE name = 'sleep'
ON CONFLICT (name) DO NOTHING;

INSERT INTO metric_types (name, display_name, category_id, unit, min_value, max_value, description)
SELECT 'sleep_quality', 'Sleep Quality', id, 'score_1_10', 1, 10, 'Quality of sleep rating'
FROM categories WHERE name = 'sleep'
ON CONFLICT (name) DO NOTHING;

INSERT INTO metric_types (name, display_name, category_id, unit, min_value, max_value, description)
SELECT 'mood_score', 'Mood Score', id, 'score_1_10', 1, 10, 'Overall mood rating'
FROM categories WHERE name = 'mood'
ON CONFLICT (name) DO NOTHING;

INSERT INTO metric_types (name, display_name, category_id, unit, min_value, max_value, description)
SELECT 'energy_level', 'Energy Level', id, 'score_1_10', 1, 10, 'Energy level rating'
FROM categories WHERE name = 'energy'
ON CONFLICT (name) DO NOTHING;

INSERT INTO metric_types (name, display_name, category_id, unit, min_value, max_value, description)
SELECT 'stress_level', 'Stress Level', id, 'score_1_10', 1, 10, 'Stress level rating'
FROM categories WHERE name = 'stress'
ON CONFLICT (name) DO NOTHING;

INSERT INTO metric_types (name, display_name, category_id, unit, min_value, max_value, description)
SELECT 'productivity_score', 'Productivity', id, 'score_1_10', 1, 10, 'Productivity rating'
FROM categories WHERE name = 'productivity'
ON CONFLICT (name) DO NOTHING;

INSERT INTO metric_types (name, display_name, category_id, unit, min_value, max_value, description)
SELECT 'focus_level', 'Focus Level', id, 'score_1_10', 1, 10, 'Focus level rating'
FROM categories WHERE name = 'productivity'
ON CONFLICT (name) DO NOTHING;

INSERT INTO metric_types (name, display_name, category_id, unit, min_value, max_value, description)
SELECT 'water_intake', 'Water Intake', id, 'liters', 0, 10, 'Water consumed in liters'
FROM categories WHERE name = 'hydration'
ON CONFLICT (name) DO NOTHING;

INSERT INTO metric_types (name, display_name, category_id, unit, min_value, max_value, description)
SELECT 'coffee_cups', 'Coffee Cups', id, 'count', 0, 20, 'Number of coffee cups'
FROM categories WHERE name = 'hydration'
ON CONFLICT (name) DO NOTHING;

INSERT INTO metric_types (name, display_name, category_id, unit, min_value, max_value, description)
SELECT 'work_hours', 'Work Hours', id, 'hours', 0, 24, 'Hours worked'
FROM categories WHERE name = 'productivity'
ON CONFLICT (name) DO NOTHING;

INSERT INTO metric_types (name, display_name, category_id, unit, min_value, max_value, description)
SELECT 'screen_time', 'Screen Time', id, 'hours', 0, 24, 'Total screen time hours'
FROM categories WHERE name = 'activities'
ON CONFLICT (name) DO NOTHING;

-- Additional metrics for extraction compatibility
INSERT INTO metric_types (name, display_name, unit, min_value, max_value)
VALUES 
    ('water_intake_liters', 'Water Intake Liters', 'liters', 0, 10),
    ('screen_time_hours', 'Screen Time Hours', 'hours', 0, 24)
ON CONFLICT (name) DO NOTHING;

-- ============================================================================
-- ACTIVITY TYPES (Common Activities)
-- ============================================================================

-- Physical activities
INSERT INTO activity_types (canonical_name, display_name, category_id, is_physical, avg_calories_per_hour)
SELECT 'running', 'Running', id, TRUE, 600 FROM categories WHERE name = 'physical'
ON CONFLICT (canonical_name) DO NOTHING;

INSERT INTO activity_types (canonical_name, display_name, category_id, is_physical, avg_calories_per_hour)
SELECT 'walking', 'Walking', id, TRUE, 280 FROM categories WHERE name = 'physical'
ON CONFLICT (canonical_name) DO NOTHING;

INSERT INTO activity_types (canonical_name, display_name, category_id, is_physical, avg_calories_per_hour)
SELECT 'yoga', 'Yoga', id, TRUE, 250 FROM categories WHERE name = 'physical'
ON CONFLICT (canonical_name) DO NOTHING;

INSERT INTO activity_types (canonical_name, display_name, category_id, is_physical, avg_calories_per_hour)
SELECT 'gym', 'Gym Workout', id, TRUE, 400 FROM categories WHERE name = 'physical'
ON CONFLICT (canonical_name) DO NOTHING;

INSERT INTO activity_types (canonical_name, display_name, category_id, is_physical, avg_calories_per_hour)
SELECT 'badminton', 'Badminton', id, TRUE, 450 FROM categories WHERE name = 'physical'
ON CONFLICT (canonical_name) DO NOTHING;

INSERT INTO activity_types (canonical_name, display_name, category_id, is_physical, avg_calories_per_hour)
SELECT 'cycling', 'Cycling', id, TRUE, 500 FROM categories WHERE name = 'physical'
ON CONFLICT (canonical_name) DO NOTHING;

INSERT INTO activity_types (canonical_name, display_name, category_id, is_physical, avg_calories_per_hour)
SELECT 'swimming', 'Swimming', id, TRUE, 550 FROM categories WHERE name = 'physical'
ON CONFLICT (canonical_name) DO NOTHING;

INSERT INTO activity_types (canonical_name, display_name, category_id, is_physical, avg_calories_per_hour)
SELECT 'stretching', 'Stretching', id, TRUE, 150 FROM categories WHERE name = 'physical'
ON CONFLICT (canonical_name) DO NOTHING;

INSERT INTO activity_types (canonical_name, display_name, category_id, is_physical, avg_calories_per_hour)
SELECT 'meditation', 'Meditation', id, FALSE, 50 FROM categories WHERE name = 'mental'
ON CONFLICT (canonical_name) DO NOTHING;

-- Mental activities
INSERT INTO activity_types (canonical_name, display_name, category_id, is_physical, is_screen_time)
SELECT 'reading', 'Reading', id, FALSE, FALSE FROM categories WHERE name = 'mental'
ON CONFLICT (canonical_name) DO NOTHING;

INSERT INTO activity_types (canonical_name, display_name, category_id, is_physical, is_screen_time)
SELECT 'coding', 'Coding', id, FALSE, TRUE FROM categories WHERE name = 'mental'
ON CONFLICT (canonical_name) DO NOTHING;

INSERT INTO activity_types (canonical_name, display_name, category_id, is_physical, is_screen_time)
SELECT 'studying', 'Studying', id, FALSE, FALSE FROM categories WHERE name = 'mental'
ON CONFLICT (canonical_name) DO NOTHING;

INSERT INTO activity_types (canonical_name, display_name, category_id, is_physical, is_screen_time)
SELECT 'leetcode', 'LeetCode', id, FALSE, TRUE FROM categories WHERE name = 'mental'
ON CONFLICT (canonical_name) DO NOTHING;

-- Leisure activities
INSERT INTO activity_types (canonical_name, display_name, category_id, is_physical, is_screen_time)
SELECT 'gaming', 'Gaming', id, FALSE, TRUE FROM categories WHERE name = 'leisure'
ON CONFLICT (canonical_name) DO NOTHING;

INSERT INTO activity_types (canonical_name, display_name, category_id, is_physical, is_screen_time)
SELECT 'watching_tv', 'Watching TV', id, FALSE, TRUE FROM categories WHERE name = 'leisure'
ON CONFLICT (canonical_name) DO NOTHING;

INSERT INTO activity_types (canonical_name, display_name, category_id, is_physical, is_screen_time)
SELECT 'netflix', 'Netflix', id, FALSE, TRUE FROM categories WHERE name = 'leisure'
ON CONFLICT (canonical_name) DO NOTHING;

INSERT INTO activity_types (canonical_name, display_name, category_id, is_physical, is_screen_time)
SELECT 'youtube', 'YouTube', id, FALSE, TRUE FROM categories WHERE name = 'leisure'
ON CONFLICT (canonical_name) DO NOTHING;

INSERT INTO activity_types (canonical_name, display_name, category_id, is_physical, is_screen_time)
SELECT 'social_media', 'Social Media', id, FALSE, TRUE FROM categories WHERE name = 'leisure'
ON CONFLICT (canonical_name) DO NOTHING;

-- Creative activities
INSERT INTO activity_types (canonical_name, display_name, category_id, is_physical, is_screen_time)
SELECT 'writing', 'Writing', id, FALSE, FALSE FROM categories WHERE name = 'creative'
ON CONFLICT (canonical_name) DO NOTHING;

INSERT INTO activity_types (canonical_name, display_name, category_id, is_physical, is_screen_time)
SELECT 'drawing', 'Drawing', id, FALSE, FALSE FROM categories WHERE name = 'creative'
ON CONFLICT (canonical_name) DO NOTHING;

INSERT INTO activity_types (canonical_name, display_name, category_id, is_physical, is_screen_time)
SELECT 'music', 'Playing Music', id, FALSE, FALSE FROM categories WHERE name = 'creative'
ON CONFLICT (canonical_name) DO NOTHING;

-- ============================================================================
-- ACTIVITY ALIASES (Common Variations)
-- ============================================================================

-- Running aliases
INSERT INTO activity_aliases (alias, activity_type_id)
SELECT 'jogging', id FROM activity_types WHERE canonical_name = 'running'
ON CONFLICT (alias) DO NOTHING;

INSERT INTO activity_aliases (alias, activity_type_id)
SELECT 'run', id FROM activity_types WHERE canonical_name = 'running'
ON CONFLICT (alias) DO NOTHING;

INSERT INTO activity_aliases (alias, activity_type_id)
SELECT 'jog', id FROM activity_types WHERE canonical_name = 'running'
ON CONFLICT (alias) DO NOTHING;

INSERT INTO activity_aliases (alias, activity_type_id)
SELECT 'morning run', id FROM activity_types WHERE canonical_name = 'running'
ON CONFLICT (alias) DO NOTHING;

-- Walking aliases
INSERT INTO activity_aliases (alias, activity_type_id)
SELECT 'walk', id FROM activity_types WHERE canonical_name = 'walking'
ON CONFLICT (alias) DO NOTHING;

INSERT INTO activity_aliases (alias, activity_type_id)
SELECT 'stroll', id FROM activity_types WHERE canonical_name = 'walking'
ON CONFLICT (alias) DO NOTHING;

-- Gym aliases
INSERT INTO activity_aliases (alias, activity_type_id)
SELECT 'workout', id FROM activity_types WHERE canonical_name = 'gym'
ON CONFLICT (alias) DO NOTHING;

INSERT INTO activity_aliases (alias, activity_type_id)
SELECT 'weight training', id FROM activity_types WHERE canonical_name = 'gym'
ON CONFLICT (alias) DO NOTHING;

INSERT INTO activity_aliases (alias, activity_type_id)
SELECT 'lifting', id FROM activity_types WHERE canonical_name = 'gym'
ON CONFLICT (alias) DO NOTHING;

-- ============================================================================
-- COMMON FOOD ITEMS
-- ============================================================================

INSERT INTO food_items (canonical_name, display_name, category, calories_per_serving, protein_g, carbs_g, fat_g, is_healthy)
VALUES 
    ('rice', 'Rice', 'grain', 200, 4, 45, 0.5, TRUE),
    ('roti', 'Roti', 'grain', 120, 3, 25, 1, TRUE),
    ('dal', 'Dal', 'legume', 150, 9, 20, 3, TRUE),
    ('chicken', 'Chicken', 'protein', 200, 30, 0, 8, TRUE),
    ('eggs', 'Eggs', 'protein', 155, 13, 1, 11, TRUE),
    ('coffee', 'Coffee', 'beverage', 5, 0, 0, 0, TRUE),
    ('tea', 'Tea', 'beverage', 2, 0, 0, 0, TRUE),
    ('water', 'Water', 'beverage', 0, 0, 0, 0, TRUE),
    ('milk', 'Milk', 'dairy', 150, 8, 12, 8, TRUE),
    ('bread', 'Bread', 'grain', 80, 3, 15, 1, TRUE),
    ('banana', 'Banana', 'fruit', 105, 1, 27, 0, TRUE),
    ('apple', 'Apple', 'fruit', 95, 0, 25, 0, TRUE),
    ('salad', 'Salad', 'vegetable', 50, 2, 10, 0, TRUE),
    ('biryani', 'Biryani', 'mixed', 400, 15, 50, 15, FALSE),
    ('pizza', 'Pizza', 'mixed', 300, 12, 35, 12, FALSE),
    ('burger', 'Burger', 'mixed', 350, 15, 30, 18, FALSE),
    ('dosa', 'Dosa', 'grain', 150, 4, 25, 4, TRUE),
    ('idli', 'Idli', 'grain', 80, 2, 15, 0.5, TRUE),
    ('samosa', 'Samosa', 'snack', 250, 4, 25, 15, FALSE),
    ('paneer', 'Paneer', 'dairy', 265, 18, 3, 20, TRUE)
ON CONFLICT (canonical_name) DO NOTHING;

-- ============================================================================
-- END OF SEED DATA
-- ============================================================================
