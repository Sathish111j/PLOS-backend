SET search_path TO public;

CREATE TABLE IF NOT EXISTS bucket_routing_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    document_id UUID REFERENCES documents(id) ON DELETE SET NULL,
    source_bucket_id UUID REFERENCES buckets(id) ON DELETE SET NULL,
    target_bucket_id UUID NOT NULL REFERENCES buckets(id) ON DELETE CASCADE,
    content_fingerprint VARCHAR(64) NOT NULL,
    correction_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bucket_routing_feedback_user_fingerprint
    ON bucket_routing_feedback(user_id, content_fingerprint);

CREATE INDEX IF NOT EXISTS idx_bucket_routing_feedback_target
    ON bucket_routing_feedback(user_id, target_bucket_id);

DO $$
BEGIN
    RAISE NOTICE 'Bucket routing feedback migration completed successfully!';
END $$;
