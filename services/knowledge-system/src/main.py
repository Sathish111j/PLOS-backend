"""
PLOS Knowledge System Service - Phase 2 Enhanced
FastAPI application with unified ingestion for all content types
"""

import os
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel, Field

from shared.gemini import ResilientGeminiClient
from shared.utils.logger import get_logger
from shared.utils.logging_config import setup_logging

# Setup structured logging
setup_logging("knowledge-system", log_level="INFO", json_logs=True)
logger = get_logger(__name__)

# Prometheus metrics
KNOWLEDGE_ITEMS_ADDED = Counter(
    "knowledge_system_items_added_total",
    "Total number of knowledge items added",
    ["type"],
)
SEARCH_COUNT = Counter(
    "knowledge_system_searches_total", "Total number of searches performed"
)
SEARCH_LATENCY = Histogram(
    "knowledge_system_search_latency_seconds", "Search latency in seconds"
)


# ============================================================================
# GLOBAL STATE
# ============================================================================

gemini_client: Optional[ResilientGeminiClient] = None


# ============================================================================
# LIFESPAN CONTEXT MANAGER
# ============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager"""
    global gemini_client

    logger.info("Knowledge system starting - Phase 2 Enhanced")

    # Initialize Database
    try:
        from src.database import Database
        await Database.connect()
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        # We continue even if DB fails, as some features like raw extraction might work? 
        # Actually better to fail fast or handle gracefully.
        # For now, we log and continue.

    # Initialize Gemini client with API key rotation
    try:
        gemini_client = ResilientGeminiClient()
        logger.info(
            f"Gemini client initialized - rotation_enabled={gemini_client.rotation_enabled}"
        )
    except Exception as e:
        logger.error(f"Gemini client initialization failed: {e}")
        raise

    logger.info("Knowledge system ready")

    yield

    logger.info("knowledge_system_shutdown")
    from src.database import Database
    await Database.disconnect()


# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(
    title="PLOS Knowledge System",
    description="Unified ingestion system for PDFs, images, text, and URLs",
    version="2.0.0",
    lifespan=lifespan,
)


# ============================================================================
# PYDANTIC MODELS
# ============================================================================


class URLExtractionRequest(BaseModel):
    """Request model for URL extraction"""

    url: str = Field(..., description="URL to extract content from")
    user_id: str = Field(..., description="User ID")
    tags: Optional[List[str]] = Field(None, description="Optional tags")
    auto_create_bucket: Optional[bool] = Field(False, description="Auto-create bucket if needed")


class TextKnowledgeRequest(BaseModel):
    """Request model for text knowledge"""

    text: str = Field(..., description="Raw text content")
    title: Optional[str] = Field(None, description="Optional title")
    user_id: str = Field(..., description="User ID")
    tags: Optional[List[str]] = Field(None, description="Optional tags")
    auto_create_bucket: Optional[bool] = Field(False, description="Auto-create bucket if needed")


# ============================================================================
# API ENDPOINTS
# ============================================================================


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        return {
            "status": "healthy",
            "service": "knowledge-system",
            "version": "2.0.0",
            "features": [
                "pdf_extraction",
                "image_ocr",
                "web_scraping",
                "combined_ingestion",
                "batch_processing",
            ],
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}


@app.get("/metrics")
async def metrics_endpoint():
    """Prometheus metrics endpoint"""
    return PlainTextResponse(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/knowledge/extract/url")
async def extract_from_url(request: URLExtractionRequest):
    """
    Extract content from a URL using enhanced web scraper
    Extract content from a URL using enhanced web scraper
    Fallback chain: Trafilatura → DrissionPage → Readability
    """
    try:
        from src.ingestion_service import UnifiedIngestionService

        ingestion_service = UnifiedIngestionService(gemini_client=gemini_client)
        result = await ingestion_service.ingest_url(
            user_id=request.user_id, url=request.url, tags=request.tags
        )

        KNOWLEDGE_ITEMS_ADDED.labels(type="url").inc()

        return {
            "success": True,
            "message": "URL content extracted successfully",
            **result,
        }

    except Exception as e:
        logger.error(f"URL extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/knowledge/extract/pdf")
async def extract_from_pdf(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    title: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    auto_create_bucket: bool = Form(False),
):
    """
    Extract content from PDF using multi-pass extraction
    Fallback chain: pdfplumber → RapidOCR (ONNX)
    """
    try:
        from src.ingestion_service import UnifiedIngestionService
        from src.bucket_service import BucketService
        from src.persistence_service import PersistenceService

        # Save temporarily
        temp_path = f"/tmp/{file.filename}"
        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)

        tag_list = tags.split(",") if tags else None

        ingestion_service = UnifiedIngestionService(gemini_client=gemini_client)
        result = await ingestion_service.ingest_pdf(
            user_id=user_id, pdf_path=temp_path, title=title, tags=tag_list
        )

        # Cleanup
        import os as os_module

        if os_module.path.exists(temp_path):
            os_module.remove(temp_path)

        # Persist
        bucket_service = BucketService(gemini_client=gemini_client)
        persistence = PersistenceService(bucket_service)
        saved = await persistence.persist_ingestion_result(user_id, result, auto_create_bucket)

        KNOWLEDGE_ITEMS_ADDED.labels(type="pdf").inc()

        return {"success": True, "message": "PDF extracted & saved", "data": saved}

    except Exception as e:
        logger.error(f"PDF extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/knowledge/extract/image")
async def extract_from_image(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    title: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    auto_create_bucket: bool = Form(False),
):
    """
    Extract text from image using RapidOCR (ONNX)
    With automatic preprocessing for better results
    """
    try:
        from src.ingestion_service import UnifiedIngestionService
        from src.bucket_service import BucketService
        from src.persistence_service import PersistenceService

        # Save temporarily
        temp_path = f"/tmp/{file.filename}"
        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)

        tag_list = tags.split(",") if tags else None

        ingestion_service = UnifiedIngestionService(gemini_client=gemini_client)
        result = await ingestion_service.ingest_images(
            user_id=user_id, image_paths=[temp_path], title=title, tags=tag_list
        )

        # Cleanup
        import os as os_module

        if os_module.path.exists(temp_path):
            os_module.remove(temp_path)

        # Persist
        bucket_service = BucketService(gemini_client=gemini_client)
        persistence = PersistenceService(bucket_service)
        saved = await persistence.persist_ingestion_result(
            user_id, result, auto_create_bucket=auto_create_bucket
        )

        KNOWLEDGE_ITEMS_ADDED.labels(type="image").inc()

        return {"success": True, "message": "Image analyzed & saved", "data": saved}

    except Exception as e:
        logger.error(f"Image extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/knowledge/extract/images")
async def extract_from_images(
    files: List[UploadFile] = File(...),
    user_id: str = Form(...),
    title: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
):
    """
    Extract text from multiple images in batch (RapidOCR)
    Perfect for scanned documents, screenshots, infographics
    """
    try:
        from src.ingestion_service import UnifiedIngestionService

        # Save all files
        temp_paths = []
        for file in files:
            temp_path = f"/tmp/{file.filename}"
            with open(temp_path, "wb") as f:
                content = await file.read()
                f.write(content)
            temp_paths.append(temp_path)

        tag_list = tags.split(",") if tags else None

        ingestion_service = UnifiedIngestionService(gemini_client=gemini_client)
        result = await ingestion_service.ingest_images(
            user_id=user_id, image_paths=temp_paths, title=title, tags=tag_list
        )

        # Cleanup
        import os as os_module

        for temp_path in temp_paths:
            if os_module.path.exists(temp_path):
                os_module.remove(temp_path)

        KNOWLEDGE_ITEMS_ADDED.labels(type="images_batch").inc()

        return {
            "success": True,
            "message": f"Extracted text from {len(files)} images",
            **result,
        }

    except Exception as e:
        logger.error(f"Images extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/knowledge/extract/text")
async def extract_from_text(request: TextKnowledgeRequest):
    """
    Add raw text content to knowledge base
    For notes, highlights, or any plain text
    """
    try:
        from src.ingestion_service import UnifiedIngestionService
        from src.bucket_service import BucketService
        from src.persistence_service import PersistenceService
        
        ingestion_service = UnifiedIngestionService(gemini_client=gemini_client)
        result = await ingestion_service.ingest_text(
            user_id=request.user_id,
            text=request.text,
            title=request.title,
            tags=request.tags,
        )

        # Persist
        bucket_service = BucketService(gemini_client=gemini_client)
        persistence = PersistenceService(bucket_service)
        saved = await persistence.persist_ingestion_result(
            request.user_id, result, auto_create_bucket=request.auto_create_bucket
        )

        KNOWLEDGE_ITEMS_ADDED.labels(type="text").inc()

        return {"success": True, "message": "Text saved", "data": saved}

    except Exception as e:
        logger.error(f"Text processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/knowledge/extract/combined")
async def extract_combined(
    pdfs: Optional[List[UploadFile]] = File(None),
    images: Optional[List[UploadFile]] = File(None),
    user_id: str = Form(...),
    text_content: Optional[str] = Form(None),
    url: Optional[str] = Form(None),
    title: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    auto_create_bucket: bool = Form(False),
):
    """
    🚀 POWERFUL: Combine multiple sources into one knowledge item

    Upload any combination of:
    - Multiple PDFs
    - Multiple images
    - Raw text
    - A URL to scrape

    Perfect for:
    - Research: Paper PDFs + screenshots + your notes + source URL
    - Learning: Article URL + slide images + summary text
    - Documentation: Multiple sources consolidated into one searchable item
    """
    try:
        from src.ingestion_service import UnifiedIngestionService

        # Save PDF files
        pdf_paths = []
        if pdfs:
            for pdf in pdfs:
                temp_path = f"/tmp/{pdf.filename}"
                with open(temp_path, "wb") as f:
                    content = await pdf.read()
                    f.write(content)
                pdf_paths.append(temp_path)

        # Save image files
        image_paths = []
        if images:
            for image in images:
                temp_path = f"/tmp/{image.filename}"
                with open(temp_path, "wb") as f:
                    content = await image.read()
                    f.write(content)
                image_paths.append(temp_path)

        tag_list = tags.split(",") if tags else None

        ingestion_service = UnifiedIngestionService(gemini_client=gemini_client)
        result = await ingestion_service.ingest_combined(
            user_id=user_id,
            pdf_files=pdf_paths if pdf_paths else None,
            image_files=image_paths if image_paths else None,
            text_content=text_content,
            url=url,
            title=title,
            tags=tag_list,
        )

        # Cleanup
        import os as os_module

        for temp_path in pdf_paths + image_paths:
            if os_module.path.exists(temp_path):
                os_module.remove(temp_path)

        # Persist Result (Phase 3 Integration)
        from src.bucket_service import BucketService
        from src.persistence_service import PersistenceService
        
        bucket_service = BucketService(gemini_client=gemini_client)
        persistence_service = PersistenceService(bucket_service=bucket_service)
        
        saved_item = await persistence_service.persist_ingestion_result(
            user_id=user_id,
            ingestion_result=result,
            auto_create_bucket=auto_create_bucket
        )

        KNOWLEDGE_ITEMS_ADDED.labels(type="combined").inc()

        return {
            "success": True, 
            "message": "Combined ingestion complete & saved", 
            "data": saved_item,
            "raw_extraction_summary": {
                "tags": result.get("tags"),
                "file_count": len(pdf_paths + image_paths)
            }
        }

    except Exception as e:
        logger.error(f"Combined extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/knowledge/buckets/tree")
async def get_bucket_tree(user_id: str):
    """Get the full folder structure as a nested JSON tree."""
    try:
        from src.bucket_service import BucketService
        service = BucketService(gemini_client=gemini_client)
        # Ensure system buckets first
        await service.ensure_system_buckets(user_id)
        return await service.get_bucket_tree(user_id)
    except Exception as e:
        logger.error(f"Bucket tree fetch failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class BucketAssignRequest(BaseModel):
    user_id: str
    text: str
    title: str
    auto_create: bool = False


@app.post("/knowledge/buckets/assign")
async def assign_bucket_endpoint(request: BucketAssignRequest):
    """
    🤖 Smart Bucket Assignment
    Uses Gemini to analyze content and assign to best bucket (or suggest new).
    """
    try:
        from src.bucket_service import BucketService
        service = BucketService(gemini_client=gemini_client)
        return await service.smart_assign_bucket(
            user_id=request.user_id,
            document_text=request.text,
            document_title=request.title,
            auto_create=request.auto_create
        )
    except Exception as e:
        logger.error(f"Bucket assignment failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "service": "PLOS Knowledge System",
        "version": "2.0.0",
        "description": "Unified ingestion for PDFs, images, text, and URLs",
        "phase": "Phase 2 Complete",
        "endpoints": {
            "health": "/health",
            "extract_url": "/knowledge/extract/url",
            "extract_pdf": "/knowledge/extract/pdf",
            "extract_image": "/knowledge/extract/image",
            "extract_images_batch": "/knowledge/extract/images",
            "extract_text": "/knowledge/extract/text",
            "extract_combined": "/knowledge/extract/combined",
        },
        "features": {
            "pdf_extraction": "Multi-pass: pdfplumber → RapidOCR (ONNX)",
            "web_scraping": "Trafilatura → DrissionPage → Readability",
            "image_ocr": "RapidOCR (ONNX Runtime, 96-98% accuracy)",
            "combined_ingestion": "Mix PDFs + images + text + URL",
            "file_storage": "MinIO (integrated for raw files)",
            "deduplication": "Hash-based + semantic similarity",
            "chunking": "Smart sentence-aware splitting",
            "organization": "3-Tier Bucket System With Smart AI Assignment",
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
