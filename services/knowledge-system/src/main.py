"""
PLOS Knowledge System Service
FastAPI application for semantic knowledge management with vector search
"""

import os
from contextlib import asynccontextmanager
from typing import List, Optional

import structlog
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from src.extraction_engine import KnowledgeExtractor
from src.vector_store import VectorStore

from shared.gemini import ResilientGeminiClient

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
)
logger = structlog.get_logger(__name__)


# ============================================================================
# GLOBAL STATE
# ============================================================================

vector_store: Optional[VectorStore] = None
extractor: Optional[KnowledgeExtractor] = None
gemini_client: Optional[ResilientGeminiClient] = None


# ============================================================================
# LIFESPAN CONTEXT MANAGER
# ============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager"""
    global vector_store, extractor, gemini_client

    logger.info("knowledge_system_starting")

    # Initialize centralized Gemini client with API key rotation
    try:
        gemini_client = ResilientGeminiClient()
        logger.info(
            "gemini_client_initialized",
            client_type="ResilientGeminiClient",
            rotation_enabled=gemini_client.rotation_enabled,
        )
    except Exception as e:
        logger.error("gemini_client_init_failed", error=str(e))
        raise

    # Initialize Vector Store with shared Gemini client
    try:
        vector_store = VectorStore(
            qdrant_url=os.getenv("QDRANT_URL", "http://qdrant:6333"),
            qdrant_api_key=os.getenv("QDRANT_API_KEY", ""),
            gemini_client=gemini_client,
        )
        logger.info("vector_store_initialized")
    except Exception as e:
        logger.error("vector_store_init_failed", error=str(e))
        raise

    # Initialize Knowledge Extractor with shared Gemini client
    try:
        extractor = KnowledgeExtractor(
            vector_store=vector_store,
            gemini_client=gemini_client,
            model=os.getenv("GEMINI_DEFAULT_MODEL"),  # Uses config default if None
        )
        logger.info("knowledge_extractor_initialized")
    except Exception as e:
        logger.error("extractor_init_failed", error=str(e))
        raise

    logger.info("knowledge_system_ready")

    yield

    # Cleanup
    if extractor:
        await extractor.close()

    logger.info("knowledge_system_shutdown")


# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(
    title="PLOS Knowledge System",
    description="Semantic knowledge management with vector search powered by Qdrant and Gemini",
    version="1.0.0",
    lifespan=lifespan,
)


# ============================================================================
# PYDANTIC MODELS
# ============================================================================


class KnowledgeItemCreate(BaseModel):
    """Request model for creating a knowledge item"""

    title: str = Field(..., description="Title of the knowledge item")
    content: str = Field(..., description="Main content text")
    source_url: Optional[str] = Field(None, description="Source URL if applicable")
    item_type: str = Field(
        "article", description="Type of item (article, note, pdf, etc.)"
    )
    tags: Optional[List[str]] = Field(None, description="Tags for categorization")
    user_id: str = Field(..., description="User ID who owns this item")


class URLExtractionRequest(BaseModel):
    """Request model for URL extraction"""

    url: str = Field(..., description="URL to extract content from")
    user_id: str = Field(..., description="User ID")
    tags: Optional[List[str]] = Field(None, description="Optional tags")


class TextKnowledgeRequest(BaseModel):
    """Request model for text knowledge"""

    text: str = Field(..., description="Raw text content")
    title: Optional[str] = Field(None, description="Optional title")
    user_id: str = Field(..., description="User ID")
    tags: Optional[List[str]] = Field(None, description="Optional tags")


class SearchRequest(BaseModel):
    """Request model for semantic search"""

    query: str = Field(..., description="Search query")
    user_id: str = Field(..., description="User ID to filter results")
    top_k: int = Field(5, ge=1, le=50, description="Number of results to return")
    item_type: Optional[str] = Field(None, description="Filter by item type")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")
    score_threshold: float = Field(
        0.5, ge=0.0, le=1.0, description="Minimum similarity score"
    )


class KnowledgeItemResponse(BaseModel):
    """Response model for knowledge items"""

    knowledge_id: str
    title: str
    content_preview: str
    similarity_score: Optional[float] = None
    source_url: Optional[str] = None
    item_type: str
    tags: List[str]
    created_at: str


class SearchResponse(BaseModel):
    """Response model for search results"""

    query: str
    results_count: int
    results: List[KnowledgeItemResponse]


# ============================================================================
# API ENDPOINTS
# ============================================================================


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check vector store connection
        stats = vector_store.get_collection_stats()

        return {
            "status": "healthy",
            "service": "knowledge-system",
            "vector_db": "connected",
            "total_knowledge_items": stats.get("total_items", 0),
        }
    except Exception as e:
        logger.error("health_check_failed", error=str(e))
        return {"status": "unhealthy", "error": str(e)}


@app.post("/knowledge/add")
async def add_knowledge_item(item: KnowledgeItemCreate):
    """
    Add a new knowledge item directly

    Use this for adding pre-processed content.
    For URL/PDF extraction, use dedicated endpoints.
    """
    try:
        knowledge_id = await vector_store.add_knowledge_item(
            knowledge_id=f"manual_{hash(item.title)}_{item.user_id}",
            title=item.title,
            content=item.content,
            source_url=item.source_url,
            item_type=item.item_type,
            user_id=item.user_id,
            tags=item.tags or [],
        )

        return {
            "success": True,
            "message": "Knowledge item added successfully",
            "knowledge_id": knowledge_id,
        }

    except Exception as e:
        logger.error("add_knowledge_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/knowledge/extract/url")
async def extract_from_url(request: URLExtractionRequest):
    """
    Extract content from a URL and add to knowledge base

    This endpoint fetches the webpage, extracts key information using AI,
    and stores it in the vector database for semantic search.
    """
    try:
        result = await extractor.extract_from_url(
            url=request.url, user_id=request.user_id, tags=request.tags
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=400, detail=result.get("error", "Extraction failed")
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("url_extraction_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/knowledge/extract/pdf")
async def extract_from_pdf(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    tags: Optional[str] = Form(None),
):
    """
    Extract content from an uploaded PDF file

    Upload a PDF file and this endpoint will extract its content
    using AI and store it in the knowledge base.
    """
    try:
        # Save uploaded file temporarily
        temp_file_path = f"/tmp/{file.filename}"
        with open(temp_file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # Parse tags if provided
        tag_list = tags.split(",") if tags else None

        # Extract content
        result = await extractor.extract_from_pdf(
            file_path=temp_file_path,
            user_id=user_id,
            original_filename=file.filename,
            tags=tag_list,
        )

        # Clean up temp file
        import os as os_module

        if os_module.path.exists(temp_file_path):
            os_module.remove(temp_file_path)

        if not result.get("success"):
            raise HTTPException(
                status_code=400, detail=result.get("error", "Extraction failed")
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("pdf_extraction_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/knowledge/extract/image")
async def extract_from_image(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    tags: Optional[str] = Form(None),
):
    """
    Extract content from an uploaded image

    Upload an image (infographic, screenshot, etc.) and this endpoint
    will extract its content using AI vision.
    """
    try:
        # Save uploaded file temporarily
        temp_file_path = f"/tmp/{file.filename}"
        with open(temp_file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # Parse tags if provided
        tag_list = tags.split(",") if tags else None

        # Extract content
        result = await extractor.extract_from_image(
            file_path=temp_file_path,
            user_id=user_id,
            original_filename=file.filename,
            tags=tag_list,
        )

        # Clean up temp file
        import os as os_module

        if os_module.path.exists(temp_file_path):
            os_module.remove(temp_file_path)

        if not result.get("success"):
            raise HTTPException(
                status_code=400, detail=result.get("error", "Extraction failed")
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("image_extraction_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/knowledge/extract/text")
async def extract_from_text(request: TextKnowledgeRequest):
    """
    Add raw text content to knowledge base

    Use this for notes, highlights, or any plain text you want to save.
    """
    try:
        result = await extractor.extract_from_text(
            text=request.text,
            user_id=request.user_id,
            title=request.title,
            tags=request.tags,
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=400, detail=result.get("error", "Processing failed")
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("text_extraction_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/knowledge/search", response_model=SearchResponse)
async def search_knowledge(request: SearchRequest):
    """
    Semantic search across knowledge base

    Search for knowledge items using natural language.
    Results are ranked by semantic similarity.

    Example queries:
    - "How to improve sleep quality"
    - "Machine learning tutorials"
    - "Productivity tips"
    """
    try:
        results = await vector_store.semantic_search(
            query=request.query,
            top_k=request.top_k,
            user_id=request.user_id,
            item_type=request.item_type,
            tags=request.tags,
            score_threshold=request.score_threshold,
        )

        # Convert to response model
        knowledge_items = [
            KnowledgeItemResponse(
                knowledge_id=r["knowledge_id"],
                title=r["title"],
                content_preview=r["content_preview"],
                similarity_score=r["similarity_score"],
                source_url=r.get("source_url"),
                item_type=r["item_type"],
                tags=r.get("tags", []),
                created_at=r.get("created_at", ""),
            )
            for r in results
        ]

        return SearchResponse(
            query=request.query,
            results_count=len(knowledge_items),
            results=knowledge_items,
        )

    except Exception as e:
        logger.error("search_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/knowledge/{knowledge_id}")
async def delete_knowledge_item(knowledge_id: str):
    """Delete a knowledge item from the database"""
    try:
        success = vector_store.delete_knowledge_item(knowledge_id)

        return {"success": success, "message": "Knowledge item deleted successfully"}

    except Exception as e:
        logger.error("delete_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/knowledge/stats")
async def get_knowledge_stats():
    """Get statistics about the knowledge base"""
    try:
        stats = vector_store.get_collection_stats()

        return {"success": True, "stats": stats}

    except Exception as e:
        logger.error("stats_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "service": "PLOS Knowledge System",
        "version": "1.0.0",
        "description": "Semantic knowledge management with vector search",
        "endpoints": {
            "health": "/health",
            "add_knowledge": "/knowledge/add",
            "extract_url": "/knowledge/extract/url",
            "extract_pdf": "/knowledge/extract/pdf",
            "extract_image": "/knowledge/extract/image",
            "extract_text": "/knowledge/extract/text",
            "search": "/knowledge/search",
            "delete": "/knowledge/{knowledge_id}",
            "stats": "/knowledge/stats",
        },
        "documentation": "/docs",
    }


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("SERVICE_PORT", "8003")),
        reload=True,
        log_level="info",
    )
