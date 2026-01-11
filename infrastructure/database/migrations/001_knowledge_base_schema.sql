-- ============================================================================
-- PLOS Knowledge Base - Database Schema Migration
-- Phase 1: Core Tables for Knowledge Management System
-- Last Updated: 2025-01-04
-- ============================================================================

-- Enable required extensions (if not already enabled from init.sql)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ============================================================================
-- 1. KNOWLEDGE BUCKETS (User Collections)
-- ============================================================================
CREATE TABLE IF NOT EXISTS knowledge_buckets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    icon VARCHAR(50) DEFAULT 'folder',
    color VARCHAR(7) DEFAULT '#6366f1',
    parent_id UUID REFERENCES knowledge_buckets(id) ON DELETE SET NULL,
    item_count INTEGER DEFAULT 0,
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, name)
);

-- Indexes for buckets
CREATE INDEX IF NOT EXISTS idx_buckets_user_id ON knowledge_buckets(user_id);
CREATE INDEX IF NOT EXISTS idx_buckets_parent_id ON knowledge_buckets(parent_id);

-- ============================================================================
-- 2. KNOWLEDGE ITEMS (Main Content)
-- ============================================================================
CREATE TABLE IF NOT EXISTS knowledge_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    bucket_id UUID REFERENCES knowledge_buckets(id) ON DELETE SET NULL,
    title VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,
    content_preview VARCHAR(500),
    source_url TEXT,
    source_type VARCHAR(50) DEFAULT 'text',  -- text, url, pdf, image
    item_type VARCHAR(50) DEFAULT 'note',    -- note, article, research, learning
    
    -- Metadata flags (bit field for efficiency)
    flags INTEGER DEFAULT 0,  -- IS_INDEXED=1, IS_VECTOR_STORED=2, IS_ARCHIVED=4, etc.
    
    -- Full-text search vector
    search_vector TSVECTOR,
    
    -- Metrics
    view_count INTEGER DEFAULT 0,
    rating INTEGER DEFAULT 0 CHECK (rating >= 0 AND rating <= 5),
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    indexed_at TIMESTAMPTZ
);

-- Full-text search index (GIN)
CREATE INDEX IF NOT EXISTS idx_items_search_vector ON knowledge_items USING GIN(search_vector);

-- Other indexes
CREATE INDEX IF NOT EXISTS idx_items_user_id ON knowledge_items(user_id);
CREATE INDEX IF NOT EXISTS idx_items_bucket_id ON knowledge_items(bucket_id);
CREATE INDEX IF NOT EXISTS idx_items_source_type ON knowledge_items(source_type);
CREATE INDEX IF NOT EXISTS idx_items_item_type ON knowledge_items(item_type);
CREATE INDEX IF NOT EXISTS idx_items_created_at ON knowledge_items(created_at DESC);

-- Trigger for auto-updating search_vector
CREATE OR REPLACE FUNCTION update_knowledge_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector := 
        setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(NEW.content_preview, '')), 'B') ||
        setweight(to_tsvector('english', COALESCE(NEW.content, '')), 'C');
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_update_knowledge_search_vector ON knowledge_items;
CREATE TRIGGER trg_update_knowledge_search_vector
    BEFORE INSERT OR UPDATE ON knowledge_items
    FOR EACH ROW
    EXECUTE FUNCTION update_knowledge_search_vector();

-- ============================================================================
-- 3. KNOWLEDGE CHUNKS (For Long Documents)
-- ============================================================================
CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    item_id UUID NOT NULL REFERENCES knowledge_items(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    content_hash VARCHAR(64),  -- For deduplication
    embedding_id VARCHAR(64),  -- Reference to Qdrant point ID
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(item_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_chunks_item_id ON knowledge_chunks(item_id);
CREATE INDEX IF NOT EXISTS idx_chunks_content_hash ON knowledge_chunks(content_hash);

-- ============================================================================
-- 4. KNOWLEDGE TAGS
-- ============================================================================
CREATE TABLE IF NOT EXISTS knowledge_tags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(50) NOT NULL,
    color VARCHAR(7) DEFAULT '#10b981',
    usage_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, name)
);

CREATE TABLE IF NOT EXISTS knowledge_item_tags (
    item_id UUID NOT NULL REFERENCES knowledge_items(id) ON DELETE CASCADE,
    tag_id UUID NOT NULL REFERENCES knowledge_tags(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (item_id, tag_id)
);

CREATE INDEX IF NOT EXISTS idx_item_tags_item_id ON knowledge_item_tags(item_id);
CREATE INDEX IF NOT EXISTS idx_item_tags_tag_id ON knowledge_item_tags(tag_id);

-- ============================================================================
-- 5. KNOWLEDGE ENTITIES (Extracted Named Entities)
-- ============================================================================
CREATE TABLE IF NOT EXISTS knowledge_entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    canonical_name VARCHAR(255),  -- Normalized form
    entity_type VARCHAR(50) NOT NULL,  -- person, organization, concept, topic, location
    description TEXT,
    aliases TEXT[],  -- Alternative names
    mention_count INTEGER DEFAULT 1,
    first_seen_at TIMESTAMPTZ DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, canonical_name, entity_type)
);

CREATE INDEX IF NOT EXISTS idx_entities_user_id ON knowledge_entities(user_id);
CREATE INDEX IF NOT EXISTS idx_entities_type ON knowledge_entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_entities_name ON knowledge_entities USING GIN(name gin_trgm_ops);

-- ============================================================================
-- 6. KNOWLEDGE RELATIONSHIPS (Entity Connections)
-- ============================================================================
CREATE TABLE IF NOT EXISTS knowledge_relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source_entity_id UUID NOT NULL REFERENCES knowledge_entities(id) ON DELETE CASCADE,
    target_entity_id UUID NOT NULL REFERENCES knowledge_entities(id) ON DELETE CASCADE,
    relationship_type VARCHAR(50) NOT NULL,  -- co_occurs, mentions, related_to
    strength FLOAT DEFAULT 1.0,  -- Relationship strength/weight
    context TEXT,  -- Sample text showing relationship
    occurrence_count INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, source_entity_id, target_entity_id, relationship_type)
);

CREATE INDEX IF NOT EXISTS idx_relationships_source ON knowledge_relationships(source_entity_id);
CREATE INDEX IF NOT EXISTS idx_relationships_target ON knowledge_relationships(target_entity_id);

-- ============================================================================
-- 7. DOCUMENT-ENTITY LINKS
-- ============================================================================
CREATE TABLE IF NOT EXISTS document_entity_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    item_id UUID NOT NULL REFERENCES knowledge_items(id) ON DELETE CASCADE,
    entity_id UUID NOT NULL REFERENCES knowledge_entities(id) ON DELETE CASCADE,
    mention_count INTEGER DEFAULT 1,
    confidence FLOAT DEFAULT 0.9,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(item_id, entity_id)
);

CREATE INDEX IF NOT EXISTS idx_doc_entity_item ON document_entity_links(item_id);
CREATE INDEX IF NOT EXISTS idx_doc_entity_entity ON document_entity_links(entity_id);

-- ============================================================================
-- 8. KB CONVERSATIONS (Chat History)
-- ============================================================================
CREATE TABLE IF NOT EXISTS kb_conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255),
    summary TEXT,
    message_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON kb_conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_updated ON kb_conversations(updated_at DESC);

-- ============================================================================
-- 9. KB CHAT MESSAGES
-- ============================================================================
CREATE TABLE IF NOT EXISTS kb_chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES kb_conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    sources JSONB,  -- Array of source item IDs with relevance scores
    token_count INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation ON kb_chat_messages(conversation_id, created_at);

-- ============================================================================
-- 10. FILE STORAGE REFERENCES (MinIO)
-- ============================================================================
CREATE TABLE IF NOT EXISTS knowledge_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    item_id UUID NOT NULL REFERENCES knowledge_items(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    file_name VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,  -- MinIO path
    file_size BIGINT,
    mime_type VARCHAR(100),
    checksum VARCHAR(64),  -- SHA-256 for deduplication
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_files_item ON knowledge_files(item_id);
CREATE INDEX IF NOT EXISTS idx_files_checksum ON knowledge_files(checksum);

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Function to update bucket item count
CREATE OR REPLACE FUNCTION update_bucket_item_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE knowledge_buckets SET item_count = item_count + 1, updated_at = NOW()
        WHERE id = NEW.bucket_id;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE knowledge_buckets SET item_count = item_count - 1, updated_at = NOW()
        WHERE id = OLD.bucket_id;
    ELSIF TG_OP = 'UPDATE' AND OLD.bucket_id IS DISTINCT FROM NEW.bucket_id THEN
        IF OLD.bucket_id IS NOT NULL THEN
            UPDATE knowledge_buckets SET item_count = item_count - 1, updated_at = NOW()
            WHERE id = OLD.bucket_id;
        END IF;
        IF NEW.bucket_id IS NOT NULL THEN
            UPDATE knowledge_buckets SET item_count = item_count + 1, updated_at = NOW()
            WHERE id = NEW.bucket_id;
        END IF;
    END IF;
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_update_bucket_count ON knowledge_items;
CREATE TRIGGER trg_update_bucket_count
    AFTER INSERT OR DELETE OR UPDATE ON knowledge_items
    FOR EACH ROW
    EXECUTE FUNCTION update_bucket_item_count();

-- Function to update tag usage count
CREATE OR REPLACE FUNCTION update_tag_usage_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE knowledge_tags SET usage_count = usage_count + 1 WHERE id = NEW.tag_id;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE knowledge_tags SET usage_count = usage_count - 1 WHERE id = OLD.tag_id;
    END IF;
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_update_tag_count ON knowledge_item_tags;
CREATE TRIGGER trg_update_tag_count
    AFTER INSERT OR DELETE ON knowledge_item_tags
    FOR EACH ROW
    EXECUTE FUNCTION update_tag_usage_count();

-- ============================================================================
-- DEFAULT BUCKET TEMPLATES (Run after user creation)
-- ============================================================================
CREATE OR REPLACE FUNCTION create_default_buckets(p_user_id UUID)
RETURNS void AS $$
BEGIN
    INSERT INTO knowledge_buckets (user_id, name, description, icon, is_default) VALUES
        (p_user_id, 'Personal Notes', 'Quick thoughts and ideas', 'note', TRUE),
        (p_user_id, 'Articles & Reads', 'Web articles and blog posts', 'article', TRUE),
        (p_user_id, 'Research', 'Papers and documentation', 'book', TRUE),
        (p_user_id, 'Learning', 'Courses and tutorials', 'graduation', TRUE),
        (p_user_id, 'Projects', 'Project-specific materials', 'folder', TRUE)
    ON CONFLICT (user_id, name) DO NOTHING;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- GRANT PERMISSIONS
-- ============================================================================
GRANT ALL ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO postgres;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO postgres;

-- Log completion
DO $$
BEGIN
    RAISE NOTICE 'Knowledge Base schema migration completed successfully!';
END $$;
