from datetime import datetime, timezone
from typing import Any, Dict, List
import base64

from app.application.ingestion.chunking import SemanticChunkingEngine
from app.application.ingestion.unified_processor import UnifiedDocumentProcessor
from app.infrastructure.persistence import KnowledgePersistence


class KnowledgeService:
    def __init__(self, persistence: KnowledgePersistence):
        self._documents: Dict[str, Dict[str, Any]] = {}
        self._processor = UnifiedDocumentProcessor()
        self._chunker = SemanticChunkingEngine()
        self._persistence = persistence

    async def upload_document(
        self,
        owner_id: str,
        filename: str,
        content_base64: str | None = None,
        mime_type: str | None = None,
        source_url: str | None = None,
    ) -> Dict[str, Any]:
        content_bytes = base64.b64decode(content_base64) if content_base64 else None
        structured = await self._processor.process(
            filename=filename,
            content_bytes=content_bytes,
            mime_type=mime_type,
            source_url=source_url,
        )
        chunks = self._chunker.chunk_document(
            source_document_id="pending",
            filename=filename,
            structured=structured,
        )
        structured.chunks = chunks
        structured.metadata["chunk_count"] = len(chunks)

        persisted = await self._persistence.persist_processed_document(
            owner_id=owner_id,
            filename=filename,
            source_url=source_url,
            mime_type=mime_type,
            content_bytes=content_bytes,
            structured=structured,
        )

        document = {
            "document_id": persisted["document_id"],
            "owner_id": owner_id,
            "filename": filename,
            "status": "completed",
            "content_type": structured.format.value,
            "strategy": structured.strategy_used.value,
            "word_count": structured.metadata.get("word_count", len(structured.text.split())),
            "char_count": structured.metadata.get("char_count", len(structured.text)),
            "text_preview": structured.text[:300],
            "metadata": structured.metadata,
            "confidence_scores": structured.confidence_scores,
            "chunk_count": len(chunks),
            "created_at": persisted["created_at"],
        }
        self._documents[persisted["document_id"]] = document
        return document

    async def list_documents(self, owner_id: str) -> List[Dict[str, Any]]:
        persisted_documents = await self._persistence.list_documents_for_owner(owner_id)
        if persisted_documents:
            return persisted_documents
        return [
            doc for doc in self._documents.values() if doc.get("owner_id") == owner_id
        ]

    async def list_buckets(self) -> List[Dict[str, str]]:
        return [{"name": "knowledge-base-documents", "provider": "minio"}]

    async def search(self, owner_id: str, query: str, top_k: int) -> Dict[str, Any]:
        return {
            "query": query,
            "top_k": top_k,
            "results": [],
            "owner_id": owner_id,
            "message": "Search pipeline skeleton is ready for vector + keyword wiring.",
        }

    async def chat(self, owner_id: str, message: str) -> Dict[str, Any]:
        return {
            "owner_id": owner_id,
            "answer": "Knowledge-base chat skeleton is online. RAG orchestration will be added in the next phase.",
            "sources": [],
            "input": message,
        }
