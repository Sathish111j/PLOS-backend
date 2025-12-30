"""
Knowledge Extraction Engine for PLOS
Extracts content from URLs, PDFs, and images using Gemini AI
"""

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
import structlog
from bs4 import BeautifulSoup
from google.genai import types
from src.vector_store import VectorStore

from shared.gemini import ResilientGeminiClient, TaskType

logger = structlog.get_logger(__name__)


class KnowledgeExtractor:
    """Extracts and processes knowledge from various sources"""

    def __init__(
        self,
        vector_store: VectorStore,
        model: Optional[str] = None,
        gemini_client: Optional[ResilientGeminiClient] = None,
    ):
        """
        Initialize Knowledge Extractor

        Args:
            vector_store: VectorStore instance for storing embeddings
            model: Gemini model to use for extraction (optional, uses config default)
            gemini_client: Optional pre-configured ResilientGeminiClient instance
        """
        self.vector_store = vector_store
        self.gemini_client = gemini_client or ResilientGeminiClient()
        self.model = model or self.gemini_client.get_model_for_task(
            TaskType.KNOWLEDGE_EXTRACTION
        )
        self.http_client = httpx.AsyncClient(timeout=30.0)

        logger.info(
            "knowledge_extractor_initialized",
            model=self.model,
            client_type="ResilientGeminiClient",
        )

    async def extract_from_url(
        self, url: str, user_id: str, tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Extract content from a URL and store in vector database

        Args:
            url: URL to extract content from
            user_id: User who added this URL
            tags: Optional tags for categorization

        Returns:
            Dictionary with extraction results
        """
        try:
            logger.info("extracting_from_url", url=url, user_id=user_id)

            # Fetch webpage content
            response = await self.http_client.get(url, follow_redirects=True)
            response.raise_for_status()
            html_content = response.text

            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(html_content, "lxml")

            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()

            # Get text content
            raw_text = soup.get_text(separator="\n", strip=True)

            # Clean up whitespace
            lines = (line.strip() for line in raw_text.splitlines())
            text_content = "\n".join(line for line in lines if line)

            # Use Gemini to extract structured information
            extraction_prompt = f"""
Extract structured information from this webpage content:

URL: {url}

Content:
{text_content[:4000]}

Extract and return as valid JSON:
1. "title" - The main title or headline
2. "summary" - A concise summary (2-3 sentences)
3. "key_points" - Main takeaways as array of strings
4. "category" - Primary category (e.g., technology, health, productivity)
5. "tags" - Relevant tags/keywords as array (max 5)
"""

            # Use centralized client for content generation
            response_text = await self.gemini_client.generate_for_task(
                task=TaskType.KNOWLEDGE_EXTRACTION,
                prompt=extraction_prompt,
                model=self.model,
            )

            # Parse JSON from response
            try:
                # Clean response if needed (remove markdown code blocks)
                clean_response = response_text.strip()
                if clean_response.startswith("```"):
                    lines = clean_response.split("\n")
                    clean_response = "\n".join(lines[1:-1])
                extracted_data = json.loads(clean_response)
            except json.JSONDecodeError:
                logger.warning("json_parse_failed, using fallback extraction")
                extracted_data = {
                    "title": url.split("/")[-1] or "Untitled",
                    "summary": text_content[:200],
                    "key_points": [],
                    "category": "uncategorized",
                    "tags": [],
                }

            # Generate unique knowledge ID
            knowledge_id = f"url_{hash(url)}_{user_id}"

            # Combine summary and key points for content
            content_parts = [extracted_data.get("summary", "")]
            if "key_points" in extracted_data:
                content_parts.extend(extracted_data["key_points"])
            full_content = "\n\n".join(content_parts)

            # Merge user tags with extracted tags
            all_tags = list(set((tags or []) + extracted_data.get("tags", [])))

            # Store in vector database (now async)
            await self.vector_store.add_knowledge_item(
                knowledge_id=knowledge_id,
                title=extracted_data.get("title", "Untitled"),
                content=full_content,
                source_url=url,
                item_type="article",
                user_id=user_id,
                tags=all_tags,
                metadata={
                    "category": extracted_data.get("category"),
                    "extraction_date": datetime.utcnow().isoformat(),
                },
            )

            logger.info(
                "url_extraction_completed",
                knowledge_id=knowledge_id,
                title=extracted_data.get("title"),
                url=url,
            )

            return {
                "success": True,
                "knowledge_id": knowledge_id,
                "title": extracted_data["title"],
                "summary": extracted_data["summary"],
                "url": url,
                "tags": all_tags,
                "category": extracted_data.get("category"),
            }

        except Exception as e:
            logger.error("url_extraction_failed", url=url, error=str(e))
            return {"success": False, "error": str(e), "url": url}

    async def extract_from_pdf(
        self,
        file_path: str,
        user_id: str,
        original_filename: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Extract content from a PDF file and store in vector database

        Args:
            file_path: Path to the PDF file
            user_id: User who uploaded this PDF
            original_filename: Original filename
            tags: Optional tags for categorization

        Returns:
            Dictionary with extraction results
        """
        try:
            logger.info("extracting_from_pdf", file_path=file_path, user_id=user_id)

            # Get raw client for file operations
            raw_client = await self.gemini_client.raw_client

            # Upload PDF to Gemini Files API
            pdf_file = raw_client.files.upload(
                file=file_path,
                config=types.UploadFileConfig(mime_type="application/pdf"),
            )

            # Wait for file to be processed
            while pdf_file.state == "PROCESSING":
                await asyncio.sleep(2)
                pdf_file = raw_client.files.get(pdf_file.name)

            if pdf_file.state == "FAILED":
                raise Exception("PDF processing failed")

            # Extract content using Gemini (need to use raw client for multimodal)
            extraction_prompt = """
Analyze this PDF document and extract as valid JSON:
1. "title" - Document title or main subject
2. "summary" - Comprehensive summary (3-5 sentences)
3. "key_concepts" - Main concepts and topics covered (array of strings)
4. "key_points" - Important takeaways (array of strings)
5. "category" - Primary category
6. "tags" - Relevant keywords (max 5, array of strings)
"""

            response = raw_client.models.generate_content(
                model=self.model,
                contents=[pdf_file, extraction_prompt],
            )

            # Parse JSON from response
            try:
                clean_response = response.text.strip()
                if clean_response.startswith("```"):
                    lines = clean_response.split("\n")
                    clean_response = "\n".join(lines[1:-1])
                extracted_data = json.loads(clean_response)
            except json.JSONDecodeError:
                logger.warning("json_parse_failed_pdf, using fallback extraction")
                extracted_data = {
                    "title": original_filename or file_path.split("/")[-1],
                    "summary": "PDF content extraction failed",
                    "key_concepts": [],
                    "key_points": [],
                    "category": "uncategorized",
                    "tags": [],
                }

            # Generate unique knowledge ID
            filename = original_filename or file_path.split("/")[-1]
            knowledge_id = f"pdf_{hash(filename)}_{user_id}"

            # Combine all extracted content
            content_parts = [
                extracted_data.get("summary", ""),
                "\n\nKey Concepts:\n"
                + "\n".join(extracted_data.get("key_concepts", [])),
                "\n\nKey Points:\n" + "\n".join(extracted_data.get("key_points", [])),
            ]
            full_content = "\n".join(content_parts)

            # Merge tags
            all_tags = list(set((tags or []) + extracted_data.get("tags", [])))

            # Store in vector database (now async)
            await self.vector_store.add_knowledge_item(
                knowledge_id=knowledge_id,
                title=extracted_data.get("title", filename),
                content=full_content,
                source_url=f"file://{filename}",
                item_type="pdf",
                user_id=user_id,
                tags=all_tags,
                metadata={
                    "category": extracted_data.get("category"),
                    "filename": filename,
                    "extraction_date": datetime.utcnow().isoformat(),
                },
            )

            # Clean up uploaded file
            raw_client.files.delete(pdf_file.name)

            logger.info(
                "pdf_extraction_completed",
                knowledge_id=knowledge_id,
                title=extracted_data["title"],
                filename=filename,
            )

            return {
                "success": True,
                "knowledge_id": knowledge_id,
                "title": extracted_data["title"],
                "summary": extracted_data["summary"],
                "filename": filename,
                "tags": all_tags,
                "category": extracted_data.get("category"),
            }

        except Exception as e:
            logger.error("pdf_extraction_failed", file_path=file_path, error=str(e))
            return {"success": False, "error": str(e), "file_path": file_path}

    async def extract_from_image(
        self,
        file_path: str,
        user_id: str,
        original_filename: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Extract content from an image (infographic, screenshot, etc.)

        Args:
            file_path: Path to the image file
            user_id: User who uploaded this image
            original_filename: Original filename
            tags: Optional tags for categorization

        Returns:
            Dictionary with extraction results
        """
        try:
            logger.info("extracting_from_image", file_path=file_path, user_id=user_id)

            # Get raw client for file operations
            raw_client = await self.gemini_client.raw_client

            # Upload image to Gemini Files API
            image_file = raw_client.files.upload(
                file=file_path,
                config=types.UploadFileConfig(
                    mime_type="image/jpeg"  # Adjust based on actual file type
                ),
            )

            # Extract content using Gemini Vision
            extraction_prompt = """
Analyze this image and extract any useful knowledge as valid JSON:
1. "title" - What is this image about?
2. "description" - Detailed description
3. "text_content" - Any text visible in the image
4. "key_points" - Main information or insights (array of strings)
5. "tags" - Relevant keywords (array of strings)
"""

            response = raw_client.models.generate_content(
                model=self.model,
                contents=[image_file, extraction_prompt],
            )

            # Parse JSON from response
            try:
                clean_response = response.text.strip()
                if clean_response.startswith("```"):
                    lines = clean_response.split("\n")
                    clean_response = "\n".join(lines[1:-1])
                extracted_data = json.loads(clean_response)
            except json.JSONDecodeError:
                logger.warning("json_parse_failed_image, using fallback extraction")
                extracted_data = {
                    "title": original_filename or "Image",
                    "description": "Image content extraction failed",
                    "text_content": "",
                    "key_points": [],
                    "tags": [],
                }

            # Generate unique knowledge ID
            filename = original_filename or file_path.split("/")[-1]
            knowledge_id = f"image_{hash(filename)}_{user_id}"

            # Combine extracted content
            content_parts = [
                extracted_data.get("description", ""),
                f"\n\nExtracted Text:\n{extracted_data.get('text_content', '')}",
                "\n\nKey Points:\n" + "\n".join(extracted_data.get("key_points", [])),
            ]
            full_content = "\n".join(content_parts)

            # Merge tags
            all_tags = list(set((tags or []) + extracted_data.get("tags", [])))

            # Store in vector database (now async)
            await self.vector_store.add_knowledge_item(
                knowledge_id=knowledge_id,
                title=extracted_data.get("title", filename),
                content=full_content,
                source_url=f"file://{filename}",
                item_type="image",
                user_id=user_id,
                tags=all_tags,
                metadata={
                    "filename": filename,
                    "extraction_date": datetime.utcnow().isoformat(),
                },
            )

            # Clean up uploaded file
            raw_client.files.delete(image_file.name)

            logger.info(
                "image_extraction_completed",
                knowledge_id=knowledge_id,
                title=extracted_data.get("title"),
                filename=filename,
            )

            return {
                "success": True,
                "knowledge_id": knowledge_id,
                "title": extracted_data.get("title"),
                "description": extracted_data.get("description"),
                "filename": filename,
                "tags": all_tags,
            }

        except Exception as e:
            logger.error("image_extraction_failed", file_path=file_path, error=str(e))
            return {"success": False, "error": str(e), "file_path": file_path}

    async def extract_from_text(
        self,
        text: str,
        user_id: str,
        title: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Process and store raw text content

        Args:
            text: Raw text content
            user_id: User who added this text
            title: Optional title
            tags: Optional tags for categorization

        Returns:
            Dictionary with storage results
        """
        try:
            logger.info("processing_text", user_id=user_id)

            # If no title provided, use Gemini to generate one
            if not title:
                title = await self.gemini_client.generate_for_task(
                    task=TaskType.KNOWLEDGE_EXTRACTION,
                    prompt=f"Generate a concise title (max 10 words) for this text:\n\n{text[:500]}",
                )
                title = title.strip()

            # Generate knowledge ID
            knowledge_id = f"text_{hash(text[:100])}_{user_id}"

            # Store in vector database (now async)
            await self.vector_store.add_knowledge_item(
                knowledge_id=knowledge_id,
                title=title,
                content=text,
                item_type="note",
                user_id=user_id,
                tags=tags or [],
                metadata={"extraction_date": datetime.utcnow().isoformat()},
            )

            logger.info(
                "text_processing_completed", knowledge_id=knowledge_id, title=title
            )

            return {"success": True, "knowledge_id": knowledge_id, "title": title}

        except Exception as e:
            logger.error("text_processing_failed", error=str(e))
            return {"success": False, "error": str(e)}

    async def close(self):
        """Clean up resources"""
        await self.http_client.aclose()
        logger.info("knowledge_extractor_closed")
