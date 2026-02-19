-- ============================================================================
-- PLOS Knowledge Base - Document Management Migration
-- Adds buckets, documents, and document_versions tables for KB ingestion flows.
-- ============================================================================

SET search_path TO public;

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS buckets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    storage_backend VARCHAR(50) NOT NULL DEFAULT 'minio',
    storage_bucket VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by UUID REFERENCES users(id),
    updated_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (name)
);

CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bucket_id UUID REFERENCES buckets(id) ON DELETE SET NULL,
    title VARCHAR(500),
    content_type VARCHAR(50) NOT NULL,
    mime_type VARCHAR(100),
    source_type VARCHAR(50) NOT NULL,
    source_url TEXT,
    source_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    storage_backend VARCHAR(50) NOT NULL DEFAULT 'minio',
    storage_bucket VARCHAR(255),
    storage_key TEXT,
    storage_version_id VARCHAR(100),
    file_size BIGINT,
    checksum VARCHAR(64),
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    processing_stage VARCHAR(100),
    processing_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    language VARCHAR(10) NOT NULL DEFAULT 'en',
    page_count INTEGER,
    word_count INTEGER,
    char_count INTEGER,
    extracted_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by UUID REFERENCES users(id),
    updated_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ,
    search_vector TSVECTOR,
    CONSTRAINT documents_retry_count_non_negative CHECK (retry_count >= 0),
    CONSTRAINT documents_file_size_non_negative CHECK (file_size IS NULL OR file_size >= 0),
    CONSTRAINT documents_page_count_non_negative CHECK (page_count IS NULL OR page_count >= 0),
    CONSTRAINT documents_word_count_non_negative CHECK (word_count IS NULL OR word_count >= 0),
    CONSTRAINT documents_char_count_non_negative CHECK (char_count IS NULL OR char_count >= 0)
);

CREATE TABLE IF NOT EXISTS document_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    storage_key TEXT NOT NULL,
    checksum VARCHAR(64),
    file_size BIGINT,
    change_summary TEXT,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT document_versions_version_positive CHECK (version_number > 0),
    CONSTRAINT document_versions_file_size_non_negative CHECK (file_size IS NULL OR file_size >= 0),
    UNIQUE (document_id, version_number)
);

CREATE INDEX IF NOT EXISTS idx_documents_bucket ON documents(bucket_id);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_content_type ON documents(content_type);
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_documents_search ON documents USING GIN (search_vector);
CREATE INDEX IF NOT EXISTS idx_documents_source_url ON documents(source_url) WHERE source_url IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_document_versions_document_id ON document_versions(document_id);
CREATE INDEX IF NOT EXISTS idx_buckets_storage_backend ON buckets(storage_backend);

CREATE OR REPLACE FUNCTION kb_update_documents_search_vector() RETURNS trigger AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('simple', COALESCE(NEW.title, '')), 'A') ||
        setweight(to_tsvector('simple', COALESCE(NEW.source_url, '')), 'B') ||
        setweight(to_tsvector('simple', COALESCE(NEW.source_metadata::text, '')), 'C') ||
        setweight(to_tsvector('simple', COALESCE(NEW.extracted_metadata::text, '')), 'C');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_documents_search_vector ON documents;
CREATE TRIGGER trg_documents_search_vector
BEFORE INSERT OR UPDATE ON documents
FOR EACH ROW
EXECUTE FUNCTION kb_update_documents_search_vector();

DROP TRIGGER IF EXISTS trg_documents_updated_at ON documents;
CREATE TRIGGER trg_documents_updated_at
BEFORE UPDATE ON documents
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trg_buckets_updated_at ON buckets;
CREATE TRIGGER trg_buckets_updated_at
BEFORE UPDATE ON buckets
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

DO $$
BEGIN
    RAISE NOTICE 'Knowledge base document management migration completed successfully!';
END $$;
