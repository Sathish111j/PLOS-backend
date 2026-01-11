-- ============================================================================
-- PLOS Knowledge Base - Optimized Bucket Architecture
-- Phase 3: Bucket System enhancements (Materialized Path, Stats, Flags)
-- Last Updated: 2026-01-11
-- ============================================================================

-- 1. ENHANCE KNOWLEDGE BUCKETS TABLE
-- ============================================================================

-- Add Materialized Path columns if they don't exist
ALTER TABLE knowledge_buckets
    ADD COLUMN IF NOT EXISTS path TEXT NOT NULL DEFAULT '/',
    ADD COLUMN IF NOT EXISTS path_depth SMALLINT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS category VARCHAR(50) DEFAULT 'custom',
    ADD COLUMN IF NOT EXISTS bucket_type VARCHAR(50) DEFAULT 'user',
    ADD COLUMN IF NOT EXISTS flags SMALLINT DEFAULT 0,
    ADD COLUMN IF NOT EXISTS ema_usage_score FLOAT DEFAULT 0,
    ADD COLUMN IF NOT EXISTS last_item_added_at TIMESTAMPTZ;

-- Add indexes for optimized queries
CREATE INDEX IF NOT EXISTS idx_buckets_path ON knowledge_buckets USING GIST(path gist_trgm_ops); -- Efficient prefix search
CREATE INDEX IF NOT EXISTS idx_buckets_user_category ON knowledge_buckets(user_id, category);
CREATE INDEX IF NOT EXISTS idx_buckets_updated_stats ON knowledge_buckets(user_id, updated_at DESC);

-- Update existing buckets to have a valid path (migration for root buckets)
-- Assuming all existing buckets are root level for now
UPDATE knowledge_buckets 
SET path = '/' || id || '/', path_depth = 1
WHERE parent_id IS NULL AND path = '/';

-- 2. UPDATE HELPER FUNCTIONS
-- ============================================================================

-- Function to calculate path automatically on insert/update
CREATE OR REPLACE FUNCTION update_bucket_path()
RETURNS TRIGGER AS $$
DECLARE
    parent_path TEXT;
    parent_depth INT;
BEGIN
    IF NEW.parent_id IS NULL THEN
        NEW.path := '/' || NEW.id || '/';
        NEW.path_depth := 1;
    ELSE
        SELECT path, path_depth INTO parent_path, parent_depth 
        FROM knowledge_buckets WHERE id = NEW.parent_id;
        
        NEW.path := parent_path || NEW.id || '/';
        NEW.path_depth := parent_depth + 1;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to maintain path integrity
DROP TRIGGER IF EXISTS trg_bucket_path ON knowledge_buckets;
CREATE TRIGGER trg_bucket_path
    BEFORE INSERT ON knowledge_buckets
    FOR EACH ROW
    EXECUTE FUNCTION update_bucket_path();

-- Note: Moving a bucket (UPDATE parent_id) is complex and handled by the Service layer 
-- or a more complex trigger. For now, we rely on the Service to update paths of children.

-- 3. SYSTEM BUCKETS LOGIC
-- ============================================================================
-- Add a constraint to ensure System buckets are unique per user per type
-- (This logic will be handled by the application Service, but we can add a partial index for safety)

-- Log completion
DO $$
BEGIN
    RAISE NOTICE 'Bucket architecture migration completed successfully!';
END $$;
