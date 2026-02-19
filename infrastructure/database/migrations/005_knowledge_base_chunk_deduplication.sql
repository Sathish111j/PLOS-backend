-- ============================================================================
-- PLOS Knowledge Base - Chunk-Level Deduplication Migration
-- Adds chunk signatures table for exact/near/semantic dedup gate before indexing.
-- ============================================================================

SET search_path TO public;

CREATE TABLE IF NOT EXISTS chunk_dedup_signatures (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    normalized_sha256 VARCHAR(64) NOT NULL UNIQUE,
    simhash BIGINT NOT NULL,
    simhash_band_hashes BIGINT[] NOT NULL DEFAULT '{}'::bigint[],
    minhash_signature BIGINT[] NOT NULL DEFAULT '{}'::bigint[],
    minhash_band_hashes BIGINT[] NOT NULL DEFAULT '{}'::bigint[],
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chunk_dedup_chunk_index_non_negative CHECK (chunk_index >= 0)
);

CREATE INDEX IF NOT EXISTS idx_chunk_dedup_document_chunk
    ON chunk_dedup_signatures(document_id, chunk_index);

CREATE INDEX IF NOT EXISTS idx_chunk_dedup_sha256
    ON chunk_dedup_signatures(normalized_sha256);

CREATE INDEX IF NOT EXISTS idx_chunk_dedup_simhash
    ON chunk_dedup_signatures(simhash);

CREATE INDEX IF NOT EXISTS idx_chunk_dedup_simhash_bands
    ON chunk_dedup_signatures USING GIN(simhash_band_hashes);

CREATE INDEX IF NOT EXISTS idx_chunk_dedup_minhash_bands
    ON chunk_dedup_signatures USING GIN(minhash_band_hashes);

DROP TRIGGER IF EXISTS trg_chunk_dedup_signatures_updated_at ON chunk_dedup_signatures;
CREATE TRIGGER trg_chunk_dedup_signatures_updated_at
BEFORE UPDATE ON chunk_dedup_signatures
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

DO $$
BEGIN
    RAISE NOTICE 'Knowledge base chunk deduplication migration completed successfully!';
END $$;
