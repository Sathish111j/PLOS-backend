-- ============================================================================
-- PLOS Knowledge Base - Vector Search, Hybrid Retrieval, and Entity System
-- Adds entity storage, engagement tracking, and hybrid-search indexes.
-- ============================================================================

SET search_path TO public;

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS document_entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    entity_text TEXT NOT NULL,
    canonical_name TEXT NOT NULL,
    entity_type VARCHAR(64) NOT NULL,
    confidence NUMERIC(5,4) NOT NULL DEFAULT 0.0,
    aliases JSONB NOT NULL DEFAULT '[]'::jsonb,
    entity_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT document_entities_confidence_range CHECK (confidence >= 0 AND confidence <= 1),
    UNIQUE (document_id, canonical_name, entity_type)
);

CREATE INDEX IF NOT EXISTS idx_document_entities_document
    ON document_entities(document_id);

CREATE INDEX IF NOT EXISTS idx_document_entities_canonical
    ON document_entities(canonical_name);

CREATE INDEX IF NOT EXISTS idx_document_entities_type
    ON document_entities(entity_type);

CREATE INDEX IF NOT EXISTS idx_document_entities_aliases
    ON document_entities USING GIN(aliases);

CREATE TABLE IF NOT EXISTS document_engagement (
    document_id UUID PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
    impressions BIGINT NOT NULL DEFAULT 0,
    clicks BIGINT NOT NULL DEFAULT 0,
    last_impression_at TIMESTAMPTZ,
    last_click_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT document_engagement_impressions_non_negative CHECK (impressions >= 0),
    CONSTRAINT document_engagement_clicks_non_negative CHECK (clicks >= 0)
);

CREATE INDEX IF NOT EXISTS idx_document_engagement_impressions
    ON document_engagement(impressions DESC);

CREATE INDEX IF NOT EXISTS idx_documents_owner_created_at
    ON documents(created_by, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_documents_owner_content_type
    ON documents(created_by, content_type);

CREATE INDEX IF NOT EXISTS idx_document_chunks_content_trgm
    ON document_chunks USING GIN(content gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_documents_title_trgm
    ON documents USING GIN(title gin_trgm_ops);

DROP TRIGGER IF EXISTS trg_document_entities_updated_at ON document_entities;
CREATE TRIGGER trg_document_entities_updated_at
BEFORE UPDATE ON document_entities
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trg_document_engagement_updated_at ON document_engagement;
CREATE TRIGGER trg_document_engagement_updated_at
BEFORE UPDATE ON document_engagement
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

DO $$
BEGIN
    RAISE NOTICE 'Knowledge base vector search and entity migration completed successfully!';
END $$;
