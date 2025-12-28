"""
Vector Store Manager for PLOS Knowledge System
Handles vector embeddings storage and semantic search using Qdrant
"""

import hashlib
import json
from datetime import datetime
from typing import List, Dict, Optional, Any
import structlog

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    MatchAny
)
from google import genai
from google.genai import types


logger = structlog.get_logger(__name__)


class VectorStore:
    """Manages vector embeddings in Qdrant for semantic search"""

    def __init__(
        self,
        qdrant_url: str,
        qdrant_api_key: str,
        gemini_api_key: str,
        collection_name: str = "knowledge_items"
    ):
        """
        Initialize Vector Store
        
        Args:
            qdrant_url: Qdrant server URL (e.g., http://localhost:6333)
            qdrant_api_key: API key for Qdrant authentication
            gemini_api_key: Google Gemini API key for embeddings
            collection_name: Name of the Qdrant collection
        """
        self.qdrant_url = qdrant_url
        self.collection_name = collection_name
        self.vector_size = 768  # Gemini embedding dimension
        self.embedding_model = "text-embedding-004"
        
        # Initialize Qdrant client
        try:
            self.client = QdrantClient(
                url=qdrant_url,
                api_key=qdrant_api_key,
                timeout=30
            )
            logger.info("qdrant_client_initialized", url=qdrant_url)
        except Exception as e:
            logger.error("qdrant_client_init_failed", error=str(e))
            raise
        
        # Initialize Gemini client
        try:
            self.gemini_client = genai.Client(api_key=gemini_api_key)
            logger.info("gemini_client_initialized")
        except Exception as e:
            logger.error("gemini_client_init_failed", error=str(e))
            raise
        
        # Ensure collection exists
        self._ensure_collection_exists()

    def _ensure_collection_exists(self):
        """Create Qdrant collection if it doesn't exist"""
        try:
            # Check if collection exists
            collections = self.client.get_collections().collections
            collection_exists = any(
                c.name == self.collection_name for c in collections
            )
            
            if not collection_exists:
                # Create collection with cosine distance for semantic similarity
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.vector_size,
                        distance=Distance.COSINE  # Best for semantic search
                    )
                )
                logger.info(
                    "qdrant_collection_created",
                    collection=self.collection_name,
                    vector_size=self.vector_size
                )
            else:
                logger.info(
                    "qdrant_collection_exists",
                    collection=self.collection_name
                )
        except Exception as e:
            logger.error(
                "collection_creation_failed",
                collection=self.collection_name,
                error=str(e)
            )
            raise

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding vector using Gemini
        
        Args:
            text: Text to embed
            
        Returns:
            List of floats representing the embedding vector
        """
        try:
            response = self.gemini_client.models.embed_content(
                model=self.embedding_model,
                contents=text,
                config={
                    "output_dimensionality": self.vector_size
                }
            )
            
            embedding = response.embeddings[0].values
            logger.debug(
                "embedding_generated",
                text_length=len(text),
                embedding_size=len(embedding)
            )
            return embedding
            
        except Exception as e:
            logger.error(
                "embedding_generation_failed",
                error=str(e),
                text_preview=text[:100]
            )
            raise

    def add_knowledge_item(
        self,
        knowledge_id: str,
        title: str,
        content: str,
        source_url: Optional[str] = None,
        item_type: str = "article",
        user_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Add a knowledge item with embedding to vector database
        
        Args:
            knowledge_id: Unique identifier for the knowledge item
            title: Title of the knowledge item
            content: Main content text
            source_url: Optional source URL
            item_type: Type of item (article, pdf, video, etc.)
            user_id: User who added this item
            tags: List of tags for categorization
            metadata: Additional metadata dictionary
            
        Returns:
            knowledge_id of the added item
        """
        try:
            # Generate embedding from content
            embedding = self.generate_embedding(content)
            
            # Prepare payload (metadata stored with vector)
            payload = {
                "knowledge_id": knowledge_id,
                "title": title,
                "content": content,
                "source_url": source_url,
                "item_type": item_type,
                "user_id": user_id,
                "tags": tags or [],
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }
            
            # Add custom metadata if provided
            if metadata:
                payload.update(metadata)
            
            # Create point (vector + payload)
            point = PointStruct(
                id=self._hash_to_id(knowledge_id),
                vector=embedding,
                payload=payload
            )
            
            # Upsert to Qdrant (insert or update)
            self.client.upsert(
                collection_name=self.collection_name,
                points=[point]
            )
            
            logger.info(
                "knowledge_item_added",
                knowledge_id=knowledge_id,
                title=title,
                user_id=user_id
            )
            
            return knowledge_id
            
        except Exception as e:
            logger.error(
                "add_knowledge_item_failed",
                knowledge_id=knowledge_id,
                error=str(e)
            )
            raise

    def batch_add_knowledge_items(
        self,
        items: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Add multiple knowledge items in batch for efficiency
        
        Args:
            items: List of item dictionaries with fields:
                   knowledge_id, title, content, source_url, item_type, user_id, tags
        
        Returns:
            List of knowledge_ids added
        """
        try:
            points = []
            knowledge_ids = []
            
            for item in items:
                # Generate embedding
                embedding = self.generate_embedding(item["content"])
                
                # Prepare payload
                payload = {
                    "knowledge_id": item["knowledge_id"],
                    "title": item["title"],
                    "content": item["content"],
                    "source_url": item.get("source_url"),
                    "item_type": item.get("item_type", "article"),
                    "user_id": item.get("user_id"),
                    "tags": item.get("tags", []),
                    "created_at": datetime.utcnow().isoformat(),
                }
                
                # Create point
                point = PointStruct(
                    id=self._hash_to_id(item["knowledge_id"]),
                    vector=embedding,
                    payload=payload
                )
                
                points.append(point)
                knowledge_ids.append(item["knowledge_id"])
            
            # Batch upsert
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
            
            logger.info(
                "batch_knowledge_items_added",
                count=len(knowledge_ids)
            )
            
            return knowledge_ids
            
        except Exception as e:
            logger.error("batch_add_failed", error=str(e))
            raise

    def semantic_search(
        self,
        query: str,
        top_k: int = 5,
        user_id: Optional[str] = None,
        item_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        score_threshold: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Perform semantic search for similar knowledge items
        
        Args:
            query: Search query text
            top_k: Number of results to return
            user_id: Filter by user_id (optional)
            item_type: Filter by item type (optional)
            tags: Filter by tags (optional)
            score_threshold: Minimum similarity score (0-1)
            
        Returns:
            List of search results with similarity scores
        """
        try:
            # Generate query embedding
            query_embedding = self.generate_embedding(query)
            
            # Build filter conditions
            filter_conditions = []
            
            if user_id:
                filter_conditions.append(
                    FieldCondition(
                        key="user_id",
                        match=MatchValue(value=user_id)
                    )
                )
            
            if item_type:
                filter_conditions.append(
                    FieldCondition(
                        key="item_type",
                        match=MatchValue(value=item_type)
                    )
                )
            
            if tags:
                filter_conditions.append(
                    FieldCondition(
                        key="tags",
                        match=MatchAny(any=tags)
                    )
                )
            
            # Create filter object
            query_filter = None
            if filter_conditions:
                query_filter = Filter(must=filter_conditions)
            
            # Perform search using query_points (new API)
            from qdrant_client.models import SearchRequest
            
            search_results = self.client.query_points(
                collection_name=self.collection_name,
                query=query_embedding,
                query_filter=query_filter,
                limit=top_k,
                score_threshold=score_threshold,
                with_payload=True
            ).points
            
            # Format results
            results = []
            for result in search_results:
                results.append({
                    "knowledge_id": result.payload.get("knowledge_id"),
                    "title": result.payload.get("title"),
                    "content_preview": result.payload.get("content", "")[:200],
                    "similarity_score": round(result.score, 4),
                    "source_url": result.payload.get("source_url"),
                    "item_type": result.payload.get("item_type"),
                    "tags": result.payload.get("tags", []),
                    "created_at": result.payload.get("created_at")
                })
            
            logger.info(
                "semantic_search_completed",
                query=query[:50],
                results_count=len(results),
                user_id=user_id
            )
            
            return results
            
        except Exception as e:
            logger.error(
                "semantic_search_failed",
                query=query[:50],
                error=str(e)
            )
            raise

    def delete_knowledge_item(self, knowledge_id: str) -> bool:
        """
        Delete a knowledge item from vector database
        
        Args:
            knowledge_id: ID of item to delete
            
        Returns:
            True if deleted successfully
        """
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=[self._hash_to_id(knowledge_id)]
            )
            
            logger.info("knowledge_item_deleted", knowledge_id=knowledge_id)
            return True
            
        except Exception as e:
            logger.error(
                "delete_knowledge_item_failed",
                knowledge_id=knowledge_id,
                error=str(e)
            )
            raise

    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the knowledge collection
        
        Returns:
            Dictionary with collection statistics
        """
        try:
            collection_info = self.client.get_collection(self.collection_name)
            
            stats = {
                "collection_name": self.collection_name,
                "total_items": collection_info.points_count,
                "vector_size": collection_info.config.params.vectors.size,
                "distance_metric": collection_info.config.params.vectors.distance,
                "status": collection_info.status
            }
            
            logger.info("collection_stats_retrieved", stats=stats)
            return stats
            
        except Exception as e:
            logger.error("get_collection_stats_failed", error=str(e))
            raise

    def _hash_to_id(self, string_id: str) -> int:
        """
        Convert string ID to integer ID for Qdrant
        
        Args:
            string_id: String identifier
            
        Returns:
            Integer hash suitable for Qdrant
        """
        hash_obj = hashlib.md5(string_id.encode())
        return int(hash_obj.hexdigest(), 16) % (2**63 - 1)


# Utility function for text chunking
def chunk_text(
    text: str,
    chunk_size: int = 500,
    overlap: int = 100
) -> List[str]:
    """
    Split text into overlapping chunks for better search
    
    Args:
        text: Text to chunk
        chunk_size: Maximum size of each chunk
        overlap: Number of characters to overlap between chunks
        
    Returns:
        List of text chunks
    """
    chunks = []
    start = 0
    
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end]
        chunks.append(chunk)
        
        # Move to next chunk with overlap
        start += chunk_size - overlap
        
        # Stop if we're at the end
        if end == len(text):
            break
    
    logger.debug(
        "text_chunked",
        original_length=len(text),
        chunks_count=len(chunks),
        chunk_size=chunk_size
    )
    
    return chunks
