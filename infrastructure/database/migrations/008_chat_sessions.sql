-- Migration 008: Chat sessions and messages for RAG conversation memory
-- Provides persistent multi-turn conversation storage for the /chat endpoint.

BEGIN;

-- Chat sessions: one row per conversation thread
CREATE TABLE IF NOT EXISTS chat_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title           VARCHAR(500),  -- auto-generated from first user message
    model           VARCHAR(100) NOT NULL DEFAULT 'gemini-3-flash-preview',
    is_archived     BOOLEAN NOT NULL DEFAULT FALSE,
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Fast session listing: most-recently-updated first
CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_updated
    ON chat_sessions (user_id, updated_at DESC);

-- Chat messages: individual turns within a session
CREATE TABLE IF NOT EXISTS chat_messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role            VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content         TEXT NOT NULL,
    sources         JSONB NOT NULL DEFAULT '[]'::jsonb,
    token_count     INTEGER NOT NULL DEFAULT 0,
    latency_ms      INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Fast conversation retrieval: messages in chronological order per session
CREATE INDEX IF NOT EXISTS idx_chat_messages_session_created
    ON chat_messages (session_id, created_at ASC);

COMMIT;
