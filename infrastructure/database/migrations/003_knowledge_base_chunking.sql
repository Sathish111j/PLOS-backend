-- ============================================================================
-- PLOS Knowledge Base - Intelligent Chunking Migration
-- Adds document_chunks table for semantic-aware retrieval units.
-- ============================================================================

SET search_path TO public;

CREATE TABLE IF NOT EXISTS document_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    total_chunks INTEGER NOT NULL,
    content TEXT NOT NULL,
    token_count INTEGER NOT NULL,
    char_count INTEGER NOT NULL,
    page_start INTEGER,
    page_end INTEGER,
    section_heading VARCHAR(500),
    parent_chunk_id UUID REFERENCES document_chunks(id) ON DELETE SET NULL,
    content_type VARCHAR(50) NOT NULL DEFAULT 'text',
    embedding_model VARCHAR(100),
    chunk_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    has_image BOOLEAN NOT NULL DEFAULT FALSE,
    image_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT document_chunks_index_non_negative CHECK (chunk_index >= 0),
    CONSTRAINT document_chunks_total_positive CHECK (total_chunks > 0),
    CONSTRAINT document_chunks_token_positive CHECK (token_count > 0),
    CONSTRAINT document_chunks_char_positive CHECK (char_count > 0),
    CONSTRAINT document_chunks_page_valid CHECK (
        (page_start IS NULL AND page_end IS NULL) OR
        (page_start IS NOT NULL AND page_end IS NOT NULL AND page_start > 0 AND page_end >= page_start)
    ),
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_document_chunks_document ON document_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_document_chunks_content_type ON document_chunks(content_type);
CREATE INDEX IF NOT EXISTS idx_document_chunks_tokens ON document_chunks(token_count);
CREATE INDEX IF NOT EXISTS idx_document_chunks_section_heading ON document_chunks(section_heading);
CREATE INDEX IF NOT EXISTS idx_document_chunks_metadata ON document_chunks USING GIN(chunk_metadata);
CREATE INDEX IF NOT EXISTS idx_document_chunks_image_ids ON document_chunks USING GIN(image_ids);

DO $$
BEGIN
    RAISE NOTICE 'Knowledge base chunking migration completed successfully!';
END $$;
