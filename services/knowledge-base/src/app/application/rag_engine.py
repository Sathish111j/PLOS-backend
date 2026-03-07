"""
RAG Engine -- Advanced Retrieval-Augmented Generation pipeline.

Orchestrates the full query -> retrieval -> generation -> post-processing flow:

  Step A: Query understanding and rewriting
  Step B: Multi-signal chunk retrieval (Qdrant semantic + optional graph)
  Step C: Context assembly with token budgeting
  Step D: Prompt construction (system + context + conversation history)
  Step E: Generation (streaming or non-streaming)
  Step F: Post-processing (citation extraction, session persistence)
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID

import httpx
from app.application.graph.queries import GraphQueryService
from app.application.search_utils import normalize_query, query_hash
from app.core.config import KnowledgeBaseConfig
from app.infrastructure.persistence import KnowledgePersistence

from shared.gemini.client import ResilientGeminiClient
from shared.gemini.config import TaskType, get_task_config
from shared.utils.logger import get_logger

logger = get_logger(__name__)

# Rough chars-per-token ratio for context budgeting
_CHARS_PER_TOKEN = 4

# Cache key prefixes
_CACHE_RAG_CHUNKS = "kb:rag:chunks:"
_CACHE_RAG_GRAPH = "kb:rag:graph:"
_CACHE_RAG_CONTEXT = "kb:rag:ctx:"

# Default limits
_DEFAULT_MAX_CHUNKS = 15
_DEFAULT_MAX_CONTEXT_TOKENS = 100_000
_DEFAULT_CONVERSATION_MAX_MESSAGES = 20
_DEFAULT_SESSION_TTL_HOURS = 168  # 1 week


class RAGEngine:
    """Graph-augmented RAG pipeline for the /chat endpoint."""

    def __init__(
        self,
        persistence: KnowledgePersistence,
        gemini_client: ResilientGeminiClient,
        graph_query_service: GraphQueryService | None,
        config: KnowledgeBaseConfig,
    ):
        self._persistence = persistence
        self._gemini = gemini_client
        self._graph = graph_query_service
        self._config = config

        # Configurable limits (with safe defaults)
        self.max_chunks: int = getattr(config, "rag_max_chunks", _DEFAULT_MAX_CHUNKS)
        self.max_context_tokens: int = getattr(
            config, "rag_max_context_tokens", _DEFAULT_MAX_CONTEXT_TOKENS
        )
        self.conversation_max_messages: int = getattr(
            config,
            "rag_conversation_max_messages",
            _DEFAULT_CONVERSATION_MAX_MESSAGES,
        )
        self.context_broker_url: str = getattr(
            config, "context_broker_url", "http://context-broker:8001"
        )

    # ------------------------------------------------------------------
    #  Public API -- non-streaming
    # ------------------------------------------------------------------

    async def answer(
        self,
        *,
        owner_id: str,
        message: str,
        session_id: str | None = None,
        bucket_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Full RAG pipeline returning the complete answer in a single dict.

        Returns:
            dict with keys: answer, sources, session_id, model,
            token_count, latency_ms, confidence
        """
        t0 = time.perf_counter()

        # Resolve model name early so the session record stores the real model.
        task_config = get_task_config(TaskType.RAG_GENERATION)

        # Step 0 -- session management
        session = await self._ensure_session(
            owner_id,
            session_id,
            model=task_config.model,
        )
        sid = session["session_id"] if session else None

        # Persist user message
        if sid:
            await self._persistence.append_chat_message(
                session_id=sid,
                role="user",
                content=message,
            )

        # Step A -- query rewriting
        rewritten_query = await self._rewrite_query(message)

        # Step B -- multi-signal retrieval
        chunks = await self._retrieve_chunks(
            owner_id=owner_id,
            query=rewritten_query,
            original_query=message,
            bucket_id=bucket_id,
        )

        # Step B.5 -- optional graph context
        graph_context = await self._graph_enrich(owner_id, rewritten_query)

        # Step B.6 -- optional user context from context-broker
        user_context = await self._fetch_user_context(owner_id)

        # Step C -- context assembly
        context_block = self._assemble_context(chunks, graph_context, user_context)

        # Step D -- conversation history
        history = []
        if sid:
            history = await self._persistence.get_session_messages(
                session_id=sid,
                limit=self.conversation_max_messages,
            )

        # Step E -- generation
        prompt = self._build_prompt(context_block, history, message)
        answer_text = await self._gemini.generate_content(
            prompt=prompt,
            model=task_config.model,
            system_instruction=task_config.system_instruction,
            temperature=task_config.temperature,
            max_output_tokens=task_config.max_output_tokens,
        )

        # Step F -- post-processing
        sources = self._extract_citations(answer_text, chunks)
        latency_ms = int((time.perf_counter() - t0) * 1000)

        # Persist assistant message
        if sid:
            await self._persistence.append_chat_message(
                session_id=sid,
                role="assistant",
                content=answer_text,
                sources=sources,
                token_count=len(answer_text) // _CHARS_PER_TOKEN,
                latency_ms=latency_ms,
            )

        return {
            "answer": answer_text,
            "sources": sources,
            "session_id": sid,
            "model": task_config.model,
            "token_count": len(answer_text) // _CHARS_PER_TOKEN,
            "latency_ms": latency_ms,
            "confidence": self._compute_confidence(chunks),
        }

    # ------------------------------------------------------------------
    #  Public API -- streaming (SSE)
    # ------------------------------------------------------------------

    async def answer_stream(
        self,
        *,
        owner_id: str,
        message: str,
        session_id: str | None = None,
        bucket_id: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        SSE streaming RAG. Yields JSON-encoded Server-Sent Event payloads.

        Event types:
          - token:    {"type":"token","text":"..."}
          - sources:  {"type":"sources","sources":[...]}
          - done:     {"type":"done","session_id":"...","latency_ms":...,"confidence":...}
          - error:    {"type":"error","message":"..."}
        """
        t0 = time.perf_counter()

        try:
            # Resolve model name early so session stores the real model.
            task_config = get_task_config(TaskType.RAG_GENERATION)

            # Session + user message
            session = await self._ensure_session(
                owner_id,
                session_id,
                model=task_config.model,
            )
            sid = session["session_id"] if session else None
            if sid:
                await self._persistence.append_chat_message(
                    session_id=sid, role="user", content=message
                )

            # Retrieval (parallelise query rewrite + user context)
            rewritten_query, user_context = await asyncio.gather(
                self._rewrite_query(message),
                self._fetch_user_context(owner_id),
            )
            chunks = await self._retrieve_chunks(
                owner_id=owner_id,
                query=rewritten_query,
                original_query=message,
                bucket_id=bucket_id,
            )
            graph_context = await self._graph_enrich(owner_id, rewritten_query)
            context_block = self._assemble_context(chunks, graph_context, user_context)
            history = []
            if sid:
                history = await self._persistence.get_session_messages(
                    session_id=sid, limit=self.conversation_max_messages
                )

            # Build prompt and stream
            prompt = self._build_prompt(context_block, history, message)

            full_answer_parts: list[str] = []
            async for text_chunk in self._gemini.generate_content_stream(
                prompt=prompt,
                model=task_config.model,
                system_instruction=task_config.system_instruction,
                temperature=task_config.temperature,
                max_output_tokens=task_config.max_output_tokens,
            ):
                full_answer_parts.append(text_chunk)
                yield _sse({"type": "token", "text": text_chunk})

            full_answer = "".join(full_answer_parts)
            sources = self._extract_citations(full_answer, chunks)
            latency_ms = int((time.perf_counter() - t0) * 1000)

            # Persist assistant message
            if sid:
                await self._persistence.append_chat_message(
                    session_id=sid,
                    role="assistant",
                    content=full_answer,
                    sources=sources,
                    token_count=len(full_answer) // _CHARS_PER_TOKEN,
                    latency_ms=latency_ms,
                )

            yield _sse({"type": "sources", "sources": sources})
            yield _sse(
                {
                    "type": "done",
                    "session_id": sid,
                    "model": task_config.model,
                    "latency_ms": latency_ms,
                    "confidence": self._compute_confidence(chunks),
                }
            )

        except Exception as exc:
            logger.error("RAG streaming error", exc_info=True)
            yield _sse({"type": "error", "message": str(exc)})

    # ------------------------------------------------------------------
    #  Public session management
    # ------------------------------------------------------------------

    async def list_sessions(
        self,
        owner_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
        include_archived: bool = False,
    ) -> list[dict[str, Any]]:
        """Return chat sessions for *owner_id*."""
        return await self._persistence.list_user_sessions(
            owner_id,
            limit=limit,
            offset=offset,
            include_archived=include_archived,
        )

    async def get_session_detail(
        self,
        owner_id: str,
        session_id: str,
        *,
        message_limit: int = 50,
    ) -> dict[str, Any] | None:
        """Return session metadata + messages, or *None* if not found."""
        session = await self._persistence.get_session_by_id(session_id, owner_id)
        if session is None:
            return None
        messages = await self._persistence.get_session_messages(
            session_id, limit=message_limit
        )
        return {"session": session, "messages": messages}

    async def delete_session(self, session_id: str, owner_id: str) -> bool:
        """Soft-delete a chat session. Returns *True* on success."""
        return await self._persistence.delete_chat_session(session_id, owner_id)

    # ------------------------------------------------------------------
    #  Internal steps
    # ------------------------------------------------------------------

    async def _ensure_session(
        self,
        owner_id: str,
        session_id: str | None,
        model: str = "gemini-3-flash-preview",
    ) -> dict[str, Any] | None:
        """Return existing session dict, create a new one, or None for anonymous."""
        # Validate owner_id is a real UUID (registered user).
        # Anonymous / invalid user IDs cannot have persistent sessions.
        try:
            UUID(owner_id)
        except (ValueError, AttributeError):
            return None

        if session_id:
            session = await self._persistence.get_session_by_id(session_id, owner_id)
            if session:
                return session
            # Session ID was provided but not found; fall through to create

        try:
            return await self._persistence.create_chat_session(
                user_id=owner_id,
                model=model,
            )
        except Exception:
            logger.warning("Failed to create chat session", exc_info=True)
            return None

    async def _rewrite_query(self, message: str) -> str:
        """Use the flash model to rewrite the user query for better retrieval."""
        if len(message.split()) <= 4:
            # Short queries don't benefit from rewriting
            return normalize_query(message)
        try:
            rewrite_prompt = (
                "Rewrite the following user question into a concise search query "
                "optimised for semantic retrieval over a personal knowledge base. "
                "Return ONLY the rewritten query, nothing else.\n\n"
                f"User question: {message}"
            )
            task_config = get_task_config(TaskType.RAG_QUERY_REWRITE)
            rewritten = await self._gemini.generate_content(
                prompt=rewrite_prompt,
                model=task_config.model,
                temperature=task_config.temperature,
                max_output_tokens=task_config.max_output_tokens,
            )
            return rewritten.strip() or normalize_query(message)
        except Exception:
            logger.warning("Query rewrite failed, using original", exc_info=True)
            return normalize_query(message)

    async def _retrieve_chunks(
        self,
        *,
        owner_id: str,
        query: str,
        original_query: str,
        bucket_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve and enrich top-K chunks from Qdrant."""
        # Check Redis cache
        cache_key = (
            f"{_CACHE_RAG_CHUNKS}{owner_id}:{query_hash(query + (bucket_id or ''))}"
        )
        cached = await self._persistence.get_cached_json(cache_key)
        if cached and isinstance(cached, dict) and "chunks" in cached:
            return cached["chunks"]

        chunks = await self._persistence.search_chunks_for_rag(
            owner_id=owner_id,
            query=query,
            top_k=self.max_chunks * 2,  # over-fetch for reranking headroom
            bucket_id=bucket_id,
        )

        if not chunks:
            return []

        # Enrich with document metadata
        chunks = await self._persistence.enrich_chunks_with_document_info(chunks)

        # Sort by score descending and take top-K
        chunks.sort(key=lambda c: c.get("score", 0.0), reverse=True)
        chunks = chunks[: self.max_chunks]

        # Cache for 5 min
        await self._persistence.set_cached_json(
            cache_key, {"chunks": chunks}, ttl_seconds=300
        )
        return chunks

    async def _graph_enrich(self, owner_id: str, query: str) -> list[dict[str, Any]]:
        """Pull related entities / documents from the knowledge graph."""
        if not self._graph:
            return []

        cache_key = f"{_CACHE_RAG_GRAPH}{owner_id}:{query_hash(query)}"
        cached = await self._persistence.get_cached_json(cache_key)
        if cached and isinstance(cached, dict) and "entities" in cached:
            return cached["entities"]

        try:
            entities = self._graph.entity_search(query, owner_id, limit=10)
            if entities:
                await self._persistence.set_cached_json(
                    cache_key, {"entities": entities}, ttl_seconds=300
                )
            return entities
        except Exception:
            logger.warning("Graph enrichment failed", exc_info=True)
            return []

    async def _fetch_user_context(self, owner_id: str) -> dict[str, Any]:
        """Fetch user context summary from the context-broker service."""
        cache_key = f"{_CACHE_RAG_CONTEXT}{owner_id}"
        cached = await self._persistence.get_cached_json(cache_key)
        if cached:
            return cached

        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(
                    f"{self.context_broker_url}/context/{owner_id}/summary"
                )
                if resp.status_code == 200:
                    data = resp.json()
                    await self._persistence.set_cached_json(
                        cache_key, data, ttl_seconds=120
                    )
                    return data
        except Exception:
            logger.debug("Context broker unavailable", exc_info=True)
        return {}

    # ------------------------------------------------------------------
    #  Context assembly
    # ------------------------------------------------------------------

    def _assemble_context(
        self,
        chunks: list[dict[str, Any]],
        graph_entities: list[dict[str, Any]],
        user_context: dict[str, Any],
    ) -> str:
        """Build the context block injected into the prompt, respecting the token budget."""
        parts: list[str] = []
        budget = self.max_context_tokens * _CHARS_PER_TOKEN  # character budget

        # 1 -- User context (small, always fits)
        if user_context:
            uc_lines = ["<user_context>"]
            for key, value in user_context.items():
                uc_lines.append(f"  {key}: {value}")
            uc_lines.append("</user_context>")
            uc_block = "\n".join(uc_lines)
            parts.append(uc_block)
            budget -= len(uc_block)

        # 2 -- Graph entities (compact)
        if graph_entities:
            ge_lines = ["<knowledge_graph_entities>"]
            for ent in graph_entities[:10]:
                ge_lines.append(
                    f"  - {ent.get('canonical_name', '')} "
                    f"(type={ent.get('type', 'unknown')}, "
                    f"mentions={ent.get('mention_count', 0)})"
                )
            ge_lines.append("</knowledge_graph_entities>")
            ge_block = "\n".join(ge_lines)
            if len(ge_block) < budget:
                parts.append(ge_block)
                budget -= len(ge_block)

        # 3 -- Retrieved chunks (bulk of the budget)
        if chunks:
            parts.append("<retrieved_chunks>")
            for idx, chunk in enumerate(chunks, 1):
                header = f"[{idx}] "
                doc_title = chunk.get("document_title") or chunk.get("document_id", "")
                if doc_title:
                    header += f"(source: {doc_title}) "
                section = chunk.get("section_heading")
                if section:
                    header += f"[section: {section}] "

                text = chunk.get("text", "")
                entry = f"{header}\n{text}\n"
                if len(entry) > budget:
                    # Truncate to remaining budget
                    entry = entry[: max(budget - 20, 0)] + "\n...(truncated)"
                    parts.append(entry)
                    break
                parts.append(entry)
                budget -= len(entry)
                if budget <= 0:
                    break
            parts.append("</retrieved_chunks>")

        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    #  Prompt construction
    # ------------------------------------------------------------------

    @staticmethod
    def _build_prompt(
        context_block: str,
        history: list[dict[str, Any]],
        current_message: str,
    ) -> str:
        """Assemble the final prompt sent to the generation model."""
        sections: list[str] = []

        # Context
        if context_block:
            sections.append(context_block)

        # Conversation history (trimmed)
        if history:
            hist_lines = ["<conversation_history>"]
            # Skip the last user message (it's the current one)
            for msg in history[:-1]:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                # Truncate long messages in history
                if len(content) > 2000:
                    content = content[:2000] + "...(truncated)"
                hist_lines.append(f"<{role}>{content}</{role}>")
            hist_lines.append("</conversation_history>")
            if len(hist_lines) > 2:  # more than just the wrappers
                sections.append("\n".join(hist_lines))

        # Current question
        sections.append(f"<user_question>{current_message}</user_question>")

        return "\n\n".join(sections)

    # ------------------------------------------------------------------
    #  Post-processing
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_citations(
        answer: str, chunks: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Parse [1], [2], ... citation markers and map back to chunk metadata."""
        cited_indices: set[int] = set()
        for match in re.finditer(r"\[(\d+)\]", answer):
            cited_indices.add(int(match.group(1)))

        sources: list[dict[str, Any]] = []
        for idx in sorted(cited_indices):
            if 1 <= idx <= len(chunks):
                chunk = chunks[idx - 1]
                sources.append(
                    {
                        "index": idx,
                        "document_id": chunk.get("document_id", ""),
                        "document_title": chunk.get("document_title", ""),
                        "section_heading": chunk.get("section_heading"),
                        "source_url": chunk.get("source_url"),
                        "bucket_name": chunk.get("bucket_name"),
                        "score": round(chunk.get("score", 0.0), 4),
                        "text_preview": (chunk.get("text") or "")[:200],
                    }
                )
        return sources

    @staticmethod
    def _compute_confidence(chunks: list[dict[str, Any]]) -> float:
        """Compute a simple retrieval confidence score (0.0 - 1.0)."""
        if not chunks:
            return 0.0
        top_score = chunks[0].get("score", 0.0) if chunks else 0.0
        avg_score = sum(c.get("score", 0.0) for c in chunks[:5]) / min(len(chunks), 5)
        # Weighted blend: top chunk matters most
        return round(min(0.7 * top_score + 0.3 * avg_score, 1.0), 4)


# ------------------------------------------------------------------
#  Helpers
# ------------------------------------------------------------------


def _sse(payload: dict[str, Any]) -> str:
    """Format a dict as an SSE data line."""
    return f"data: {json.dumps(payload)}\n\n"
