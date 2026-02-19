SET search_path TO public;

ALTER TABLE buckets
    ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id),
    ADD COLUMN IF NOT EXISTS parent_bucket_id UUID REFERENCES buckets(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS depth INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS path TEXT,
    ADD COLUMN IF NOT EXISTS icon_emoji VARCHAR(32),
    ADD COLUMN IF NOT EXISTS color_hex VARCHAR(7),
    ADD COLUMN IF NOT EXISTS document_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS is_default BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;

UPDATE buckets
SET user_id = created_by
WHERE user_id IS NULL;

UPDATE buckets
SET path = '/root/' || lower(regexp_replace(name, '[^a-zA-Z0-9]+', '-', 'g'))
WHERE path IS NULL;

ALTER TABLE buckets
    ALTER COLUMN path SET NOT NULL;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'buckets_name_key'
          AND conrelid = 'buckets'::regclass
    ) THEN
        ALTER TABLE buckets DROP CONSTRAINT buckets_name_key;
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS idx_buckets_user_parent_name_unique
    ON buckets (user_id, parent_bucket_id, lower(name))
    WHERE is_deleted = FALSE;

CREATE INDEX IF NOT EXISTS idx_buckets_user_active
    ON buckets (user_id, is_deleted);

CREATE INDEX IF NOT EXISTS idx_buckets_parent
    ON buckets (user_id, parent_bucket_id)
    WHERE is_deleted = FALSE;

CREATE INDEX IF NOT EXISTS idx_buckets_path
    ON buckets (user_id, path);

CREATE INDEX IF NOT EXISTS idx_buckets_default
    ON buckets (user_id, is_default)
    WHERE is_deleted = FALSE;

ALTER TABLE buckets
    ADD CONSTRAINT buckets_depth_non_negative CHECK (depth >= 0),
    ADD CONSTRAINT buckets_color_hex_format CHECK (
        color_hex IS NULL OR color_hex ~ '^#[0-9A-Fa-f]{6}$'
    );

DO $$
BEGIN
    RAISE NOTICE 'Bucket hierarchy and AI routing migration completed successfully!';
END $$;
