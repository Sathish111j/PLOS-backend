-- 003_knowledge_graph.sql
SET search_path TO public;


-- Entities
CREATE TABLE IF NOT EXISTS knowledge_entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    type VARCHAR(50) NOT NULL, -- PERSON, ORG, CONCEPT, LOCATION, ARTIFACT
    definition TEXT,
    confidence FLOAT DEFAULT 1.0,
    mention_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Entity Aliases
CREATE TABLE IF NOT EXISTS entity_aliases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id UUID REFERENCES knowledge_entities(id) ON DELETE CASCADE,
    alias TEXT NOT NULL,
    is_canonical BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Relationships
CREATE TABLE IF NOT EXISTS knowledge_relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_entity_id UUID REFERENCES knowledge_entities(id) ON DELETE CASCADE,
    target_entity_id UUID REFERENCES knowledge_entities(id) ON DELETE CASCADE,
    relation_type VARCHAR(50) NOT NULL,
    confidence FLOAT DEFAULT 1.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Link Documents to Entities
CREATE TABLE IF NOT EXISTS document_entity_links (
    document_id UUID REFERENCES knowledge_items(id) ON DELETE CASCADE,
    entity_id UUID REFERENCES knowledge_entities(id) ON DELETE CASCADE,
    confidence FLOAT DEFAULT 1.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (document_id, entity_id)
);

-- Add processing status to items
DO $$ 
BEGIN 
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='knowledge_items' AND column_name='graph_processed') THEN 
        ALTER TABLE knowledge_items ADD COLUMN graph_processed BOOLEAN DEFAULT FALSE; 
    END IF; 
END $$;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_entities_name ON knowledge_entities(name);
CREATE INDEX IF NOT EXISTS idx_entities_type ON knowledge_entities(type);
CREATE INDEX IF NOT EXISTS idx_aliases_alias ON entity_aliases(alias);
CREATE INDEX IF NOT EXISTS idx_relationships_source ON knowledge_relationships(source_entity_id);
CREATE INDEX IF NOT EXISTS idx_relationships_target ON knowledge_relationships(target_entity_id);
