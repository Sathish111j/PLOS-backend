-- ============================================================================
-- PLOS Knowledge Base - Deduplication & Content Integrity Migration
-- Adds multi-stage dedup signatures and checksum chain audit storage.
-- ============================================================================

SET search_path TO public;

CREATE TABLE IF NOT EXISTS document_dedup_signatures (
    document_id UUID PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
    normalized_sha256 VARCHAR(64) NOT NULL UNIQUE,
    simhash BIGINT NOT NULL,
    simhash_band_hashes BIGINT[] NOT NULL DEFAULT '{}'::bigint[],
    minhash_signature BIGINT[] NOT NULL DEFAULT '{}'::bigint[],
    minhash_band_hashes BIGINT[] NOT NULL DEFAULT '{}'::bigint[],
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_document_dedup_sha256
    ON document_dedup_signatures(normalized_sha256);

CREATE INDEX IF NOT EXISTS idx_document_dedup_simhash
    ON document_dedup_signatures(simhash);

CREATE INDEX IF NOT EXISTS idx_document_dedup_simhash_bands
    ON document_dedup_signatures USING GIN(simhash_band_hashes);

CREATE INDEX IF NOT EXISTS idx_document_dedup_minhash_bands
    ON document_dedup_signatures USING GIN(minhash_band_hashes);

CREATE TABLE IF NOT EXISTS document_integrity_checks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    stage_name VARCHAR(50) NOT NULL,
    checksum_md5 VARCHAR(32) NOT NULL,
    previous_checksum_md5 VARCHAR(32),
    chain_hash_sha256 VARCHAR(64) NOT NULL,
    is_verified BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_document_integrity_document_stage
    ON document_integrity_checks(document_id, stage_name, created_at DESC);

ALTER TABLE document_versions
    ADD COLUMN IF NOT EXISTS parent_version_id UUID REFERENCES document_versions(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS delta_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS is_delta BOOLEAN NOT NULL DEFAULT FALSE;

DROP TRIGGER IF EXISTS trg_document_dedup_signatures_updated_at ON document_dedup_signatures;
CREATE TRIGGER trg_document_dedup_signatures_updated_at
BEFORE UPDATE ON document_dedup_signatures
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

DO $$
BEGIN
    RAISE NOTICE 'Knowledge base deduplication and integrity migration completed successfully!';
END $$;
