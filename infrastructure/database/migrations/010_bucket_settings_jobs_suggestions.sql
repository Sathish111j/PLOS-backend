-- Migration 010: Bucket settings, ingest jobs, and AI suggestions
-- Adds global per-user KB settings, per-bucket depth + auto-classify controls,
-- async ingest job tracking, and the AI bucket suggestion approval queue.

BEGIN;

-- -------------------------------------------------------------------------
-- 1. Per-user global KB settings
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS kb_settings (
    user_id                 UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    auto_classify           BOOLEAN NOT NULL DEFAULT TRUE,
    auto_create             BOOLEAN NOT NULL DEFAULT TRUE,
    default_max_depth       INTEGER NOT NULL DEFAULT -1,
    confidence_threshold    NUMERIC(4,3) NOT NULL DEFAULT 0.65
        CHECK (confidence_threshold >= 0 AND confidence_threshold <= 1),
    low_confidence_action   VARCHAR(30) NOT NULL DEFAULT 'send_to_unassigned'
        CHECK (low_confidence_action IN ('suggest_bucket', 'send_to_unassigned', 'force_classify')),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -------------------------------------------------------------------------
-- 2. Per-bucket depth limit and auto-classify toggle
-- -------------------------------------------------------------------------
ALTER TABLE buckets
    ADD COLUMN IF NOT EXISTS max_depth       INTEGER NOT NULL DEFAULT -1,
    ADD COLUMN IF NOT EXISTS auto_classify   BOOLEAN NOT NULL DEFAULT TRUE;

COMMENT ON COLUMN buckets.max_depth IS
    'Max nesting depth for AI-created children under this bucket. -1 = unlimited, 0 = flat (no children).';
COMMENT ON COLUMN buckets.auto_classify IS
    'When FALSE, the AI will not route documents into this bucket automatically.';

-- -------------------------------------------------------------------------
-- 3. Async ingest job tracking
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ingest_jobs (
    job_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status              VARCHAR(30) NOT NULL DEFAULT 'processing'
        CHECK (status IN ('processing', 'classified', 'pending_approval', 'unassigned', 'failed')),
    item_id             UUID REFERENCES documents(id) ON DELETE SET NULL,
    bucket_id           UUID REFERENCES buckets(id) ON DELETE SET NULL,
    bucket_path         TEXT,
    confidence          NUMERIC(5,4),
    ai_reasoning        TEXT,
    error_message       TEXT,
    suggestion_id       UUID,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ingest_jobs_user_status
    ON ingest_jobs (user_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ingest_jobs_item
    ON ingest_jobs (item_id);

-- -------------------------------------------------------------------------
-- 4. AI bucket suggestion approval queue
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bucket_suggestions (
    suggestion_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    proposed_name           VARCHAR(100) NOT NULL,
    proposed_parent_id      UUID REFERENCES buckets(id) ON DELETE SET NULL,
    proposed_description    TEXT,
    triggered_by_item_id    UUID REFERENCES documents(id) ON DELETE SET NULL,
    triggered_by_job_id     UUID REFERENCES ingest_jobs(job_id) ON DELETE SET NULL,
    ai_reasoning            TEXT,
    status                  VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected')),
    approved_name           VARCHAR(100),
    approved_description    TEXT,
    created_bucket_id       UUID REFERENCES buckets(id) ON DELETE SET NULL,
    resolved_at             TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bucket_suggestions_user_status
    ON bucket_suggestions (user_id, status, created_at DESC);

-- -------------------------------------------------------------------------
-- 5. Wire ingest_jobs.suggestion_id FK now that bucket_suggestions exists
-- -------------------------------------------------------------------------
ALTER TABLE ingest_jobs
    ADD CONSTRAINT fk_ingest_jobs_suggestion
        FOREIGN KEY (suggestion_id)
        REFERENCES bucket_suggestions(suggestion_id)
        ON DELETE SET NULL;

-- -------------------------------------------------------------------------
-- 6. Track classified_by and confidence on documents
-- -------------------------------------------------------------------------
ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS classified_by        VARCHAR(20) DEFAULT 'ai'
        CHECK (classified_by IN ('ai', 'user', 'system')),
    ADD COLUMN IF NOT EXISTS classification_confidence  NUMERIC(5,4),
    ADD COLUMN IF NOT EXISTS classification_reasoning   TEXT;

COMMENT ON COLUMN documents.classified_by IS
    'Who assigned the bucket: ai, user (manual move), or system (default/unassigned).';

DO $$
BEGIN
    RAISE NOTICE 'Migration 010 completed: kb_settings, ingest_jobs, bucket_suggestions, bucket enhancements.';
END $$;

COMMIT;
