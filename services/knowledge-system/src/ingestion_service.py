"""
Unified Ingestion Service for PLOS Knowledge System
Handles all content types: PDFs, images, text, URLs, and combinations
"""

import asyncio
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from minio import Minio
from minio.error import S3Error

from shared.gemini import ResilientGeminiClient
from shared.utils.logger import get_logger

from .auto_tagging_service import AutoTaggingService
from .dedup_service import DeduplicationService, chunk_text
from .extractors.image_extractor import ImageExtractor
from .extractors.pdf_extractor import PDFExtractor
from .extractors.web_scraper import WebScraper

logger = get_logger(__name__)


class UnifiedIngestionService:
    """
    Unified service for ingesting all content types.

    Supported inputs:
    - Single file: PDF, image, or text
    - Multiple files: batch of PDFs, images, or mixed
    - URL: web page
    - Combined: PDF + text + images together

    Features:
    - Automatic content type detection
    - MinIO file storage
    - CPU-optimized extraction (escalation strategy)
    - Deduplication (Hash → MinHash → Semantic)
    - Chunking for long content
    - Metadata extraction
    - Gemini summarization
    - Auto-tagging (keyword extraction + optional AI)
    """

    def __init__(
        self,
        minio_client: Optional[Minio] = None,
        gemini_client: Optional[ResilientGeminiClient] = None,
    ):
        """
        Initialize unified ingestion service.

        Args:
            minio_client: MinIO client for file storage
            gemini_client: Gemini client for summarization and tagging
        """
        # CPU-Optimized Extractors
        self.pdf_extractor = PDFExtractor()
        self.image_extractor = ImageExtractor()
        self.web_scraper = WebScraper()
        self.dedup_service = DeduplicationService()

        self.minio_client = minio_client or self._init_minio()
        self.gemini_client = gemini_client or ResilientGeminiClient()

        # Auto-tagging service (keyword extraction by default, AI optional)
        self.auto_tagger = AutoTaggingService(
            gemini_client=self.gemini_client,
            use_ai=False,  # Use fast keyword extraction by default
        )

        self._ensure_minio_bucket()

    def _init_minio(self) -> Minio:
        """Initialize MinIO client from environment."""
        return Minio(
            os.getenv("MINIO_ENDPOINT", "localhost:9000"),
            access_key=os.getenv("MINIO_ROOT_USER", "plos_minio_admin"),
            secret_key=os.getenv("MINIO_ROOT_PASSWORD", "plos_minio_secure_2025"),
            secure=False,  # Use HTTP for local development
        )

    def _ensure_minio_bucket(self):
        """Ensure MinIO bucket exists."""
        bucket_name = "knowledge-files"
        try:
            if not self.minio_client.bucket_exists(bucket_name):
                self.minio_client.make_bucket(bucket_name)
                logger.info(f"Created MinIO bucket: {bucket_name}")
        except S3Error as e:
            logger.warning(f"MinIO bucket check failed: {e}")
        except Exception as e:
            logger.warning(
                f"MinIO bucket check failed: {type(e).__name__}: {e}"
            )

    async def ingest_combined(
        self,
        user_id: str,
        pdf_files: Optional[List[str]] = None,
        image_files: Optional[List[str]] = None,
        text_content: Optional[str] = None,
        url: Optional[str] = None,
        title: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Ingest combined content (PDF + images + text + URL).

        Args:
            user_id: User ID
            pdf_files: List of PDF file paths
            image_files: List of image file paths
            text_content: Raw text content
            url: URL to scrape
            title: Optional title (auto-generated if not provided)
            tags: Optional tags

        Returns:
            Ingestion result with all extracted content
        """
        logger.info(
            f"Combined ingestion: pdfs={len(pdf_files or [])}, "
            f"images={len(image_files or [])}, text={bool(text_content)}, url={bool(url)}"
        )

        all_content = []
        all_metadata = []
        all_files = []

        # Extract from PDFs
        if pdf_files:
            for pdf_path in pdf_files:
                text, metadata = self.pdf_extractor.extract(pdf_path)
                all_content.append(text)
                all_metadata.append(metadata)
                all_files.append(pdf_path)

        # Extract from images
        if image_files:
            batch_results = self.image_extractor.extract_batch(image_files)
            for text, metadata in batch_results:
                if text:  # Only add if extraction was successful
                    all_content.append(text)
                    all_metadata.append(metadata)
            all_files.extend(image_files)

        # Add raw text
        if text_content:
            all_content.append(text_content)
            all_metadata.append(
                {
                    "extraction_method": "raw_text",
                    "char_count": len(text_content),
                    "word_count": len(text_content.split()),
                }
            )

        # Scrape URL
        if url:
            text, metadata = await self.web_scraper.extract(url)
            all_content.append(text)
            all_metadata.append(metadata)

        # Combine all content
        combined_text = "\n\n---\n\n".join(all_content)

        # Generate title if not provided
        if not title:
            if url:
                title = all_metadata[-1].get("title", "Untitled")
            elif pdf_files:
                title = all_metadata[0].get("title") or Path(pdf_files[0]).stem
            else:
                title = f"Document {datetime.now().strftime('%Y-%m-%d %H:%M')}"

        # Deduplication check
        content_hash = self.dedup_service.compute_hash(combined_text)

        # Upload files to MinIO
        minio_paths = []
        for file_path in all_files:
            minio_path = await self._upload_to_minio(user_id, file_path)
            if minio_path:
                minio_paths.append(minio_path)

        # Chunk content if needed
        chunks = chunk_text(combined_text, chunk_size=500, overlap=100)

        # Generate summary using Gemini
        summary = await self._generate_summary(
            combined_text[:5000]
        )  # Limit to first 5000 chars

        # Auto-generate tags if not provided
        if not tags:
            tags = self.auto_tagger.generate_tags(
                title=title,
                content=combined_text[:2000],  # Use first 2000 chars for speed
                max_tags=5,
            )
            logger.info(f"Auto-generated {len(tags)} tags: {tags}")

        # Prepare result
        result = {
            "title": title,
            "content": combined_text,
            "content_preview": combined_text[:500],
            "summary": summary,
            "content_hash": content_hash,
            "source_type": "combined",
            "item_type": "document",
            "chunks": chunks,
            "chunk_count": len(chunks),
            "metadata": {
                "sources": all_metadata,
                "files_uploaded": minio_paths,
                "total_chars": len(combined_text),
                "total_words": len(combined_text.split()),
            },
            "tags": tags or [],
            "auto_tagged": not bool(tags),  # Flag if tags were auto-generated
            "ingestion_timestamp": datetime.utcnow().isoformat(),
        }

        logger.info(
            f"Combined ingestion complete: {len(chunks)} chunks, "
            f"{len(minio_paths)} files uploaded, {len(tags)} tags"
        )

        return result

    async def ingest_text(
        self,
        user_id: str,
        text: str,
        title: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Ingest plain text content.

        Args:
            user_id: User ID
            text: Text content
            title: Optional title
            tags: Optional tags

        Returns:
            Ingestion result
        """
        return await self.ingest_combined(
            user_id=user_id, text_content=text, title=title, tags=tags
        )

    async def ingest_url(
        self,
        user_id: str,
        url: str,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Ingest content from URL.

        Args:
            user_id: User ID
            url: URL to scrape
            tags: Optional tags

        Returns:
            Ingestion result
        """
        return await self.ingest_combined(user_id=user_id, url=url, tags=tags)

    async def ingest_pdf(
        self,
        user_id: str,
        pdf_path: str,
        title: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Ingest PDF file.

        Args:
            user_id: User ID
            pdf_path: Path to PDF file
            title: Optional title
            tags: Optional tags

        Returns:
            Ingestion result
        """
        return await self.ingest_combined(
            user_id=user_id, pdf_files=[pdf_path], title=title, tags=tags
        )

    async def ingest_images(
        self,
        user_id: str,
        image_paths: List[str],
        title: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Ingest one or more images.

        Args:
            user_id: User ID
            image_paths: List of image file paths
            title: Optional title
            tags: Optional tags

        Returns:
            Ingestion result
        """
        return await self.ingest_combined(
            user_id=user_id, image_files=image_paths, title=title, tags=tags
        )

    async def _upload_to_minio(self, user_id: str, file_path: str) -> Optional[str]:
        """
        Upload file to MinIO.

        Args:
            user_id: User ID
            file_path: Path to file

        Returns:
            MinIO object path or None if failed
        """
        try:
            bucket = "knowledge-files"
            file_name = Path(file_path).name
            object_name = f"{user_id}/{uuid.uuid4()}/{file_name}"

            # Upload file
            self.minio_client.fput_object(
                bucket,
                object_name,
                file_path,
            )

            logger.info(f"Uploaded to MinIO: {object_name}")
            return f"{bucket}/{object_name}"

        except Exception as e:
            logger.error(f"MinIO upload failed: {e}")
            return None

    async def _generate_summary(self, content: str) -> str:
        """
        Generate summary using Gemini.

        Args:
            content: Content to summarize

        Returns:
            Summary text
        """
        if not content or len(content) < 100:
            return content

        try:
            prompt = f"""Provide a concise 2-3 sentence summary of the following content:

{content}

Summary:"""

            summary_text = await self.gemini_client.generate_content(
                prompt=prompt,
                max_output_tokens=150,
            )

            return summary_text.strip()

        except Exception as e:
            logger.warning(f"Summary generation failed: {e}")
            # Fallback: first 200 chars
            return content[:200] + "..."
