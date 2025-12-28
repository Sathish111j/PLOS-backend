"""
Knowledge Extraction Engine for PLOS
Extracts content from URLs, PDFs, and images using Gemini AI
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
import structlog
from bs4 import BeautifulSoup
from google import genai
from google.genai import types

from src.vector_store import VectorStore

logger = structlog.get_logger(__name__)


class KnowledgeExtractor:
    """Extracts and processes knowledge from various sources"""

    def __init__(
        self,
        vector_store: VectorStore,
        gemini_api_key: str,
        model: str = "gemini-2.0-flash-exp",
    ):
        """
        Initialize Knowledge Extractor

        Args:
            vector_store: VectorStore instance for storing embeddings
            gemini_api_key: Google Gemini API key
            model: Gemini model to use for extraction
        """
        self.vector_store = vector_store
        self.gemini_client = genai.Client(api_key=gemini_api_key)
        self.model = model
        self.http_client = httpx.AsyncClient(timeout=30.0)

        logger.info("knowledge_extractor_initialized", model=model)

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

Extract:
1. Title - The main title or headline
2. Summary - A concise summary (2-3 sentences)
3. Key Points - Main takeaways (bullet points)
4. Category - Primary category (e.g., technology, health, productivity)
5. Tags - Relevant tags/keywords (max 5)

Return as JSON.
"""

            response = self.gemini_client.models.generate_content(
                model=self.model,
                contents=[extraction_prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema={
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "summary": {"type": "string"},
                            "key_points": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "category": {"type": "string"},
                            "tags": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["title", "summary"],
                    },
                ),
            )

            extracted_data = json.loads(response.text)

            # Generate unique knowledge ID
            knowledge_id = f"url_{hash(url)}_{user_id}"

            # Combine summary and key points for content
            content_parts = [extracted_data["summary"]]
            if "key_points" in extracted_data:
                content_parts.extend(extracted_data["key_points"])
            full_content = "\n\n".join(content_parts)

            # Merge user tags with extracted tags
            all_tags = list(set((tags or []) + extracted_data.get("tags", [])))

            # Store in vector database
            self.vector_store.add_knowledge_item(
                knowledge_id=knowledge_id,
                title=extracted_data["title"],
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
                title=extracted_data["title"],
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

            # Upload PDF to Gemini Files API
            pdf_file = self.gemini_client.files.upload(
                file=file_path,
                config=types.UploadFileConfig(mime_type="application/pdf"),
            )

            # Wait for file to be processed
            import time

            while pdf_file.state == "PROCESSING":
                time.sleep(2)
                pdf_file = self.gemini_client.files.get(pdf_file.name)

            if pdf_file.state == "FAILED":
                raise Exception("PDF processing failed")

            # Extract content using Gemini
            extraction_prompt = """
Analyze this PDF document and extract:
1. Title - Document title or main subject
2. Summary - Comprehensive summary (3-5 sentences)
3. Key Concepts - Main concepts and topics covered
4. Key Points - Important takeaways (bullet points)
5. Category - Primary category
6. Tags - Relevant keywords (max 5)

Return as JSON.
"""

            response = self.gemini_client.models.generate_content(
                model=self.model,
                contents=[pdf_file, extraction_prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema={
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "summary": {"type": "string"},
                            "key_concepts": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "key_points": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "category": {"type": "string"},
                            "tags": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["title", "summary"],
                    },
                ),
            )

            extracted_data = json.loads(response.text)

            # Generate unique knowledge ID
            filename = original_filename or file_path.split("/")[-1]
            knowledge_id = f"pdf_{hash(filename)}_{user_id}"

            # Combine all extracted content
            content_parts = [
                extracted_data["summary"],
                "\n\nKey Concepts:\n"
                + "\n".join(extracted_data.get("key_concepts", [])),
                "\n\nKey Points:\n" + "\n".join(extracted_data.get("key_points", [])),
            ]
            full_content = "\n".join(content_parts)

            # Merge tags
            all_tags = list(set((tags or []) + extracted_data.get("tags", [])))

            # Store in vector database
            self.vector_store.add_knowledge_item(
                knowledge_id=knowledge_id,
                title=extracted_data["title"],
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
            self.gemini_client.files.delete(pdf_file.name)

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

            # Upload image to Gemini Files API
            image_file = self.gemini_client.files.upload(
                file=file_path,
                config=types.UploadFileConfig(
                    mime_type="image/jpeg"  # Adjust based on actual file type
                ),
            )

            # Extract content using Gemini Vision
            extraction_prompt = """
Analyze this image and extract any useful knowledge:
1. Title - What is this image about?
2. Description - Detailed description
3. Text Content - Any text visible in the image
4. Key Points - Main information or insights
5. Tags - Relevant keywords

Return as JSON.
"""

            response = self.gemini_client.models.generate_content(
                model=self.model,
                contents=[image_file, extraction_prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema={
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "description": {"type": "string"},
                            "text_content": {"type": "string"},
                            "key_points": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "tags": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["title", "description"],
                    },
                ),
            )

            extracted_data = json.loads(response.text)

            # Generate unique knowledge ID
            filename = original_filename or file_path.split("/")[-1]
            knowledge_id = f"image_{hash(filename)}_{user_id}"

            # Combine extracted content
            content_parts = [
                extracted_data["description"],
                f"\n\nExtracted Text:\n{extracted_data.get('text_content', '')}",
                "\n\nKey Points:\n" + "\n".join(extracted_data.get("key_points", [])),
            ]
            full_content = "\n".join(content_parts)

            # Merge tags
            all_tags = list(set((tags or []) + extracted_data.get("tags", [])))

            # Store in vector database
            self.vector_store.add_knowledge_item(
                knowledge_id=knowledge_id,
                title=extracted_data["title"],
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
            self.gemini_client.files.delete(image_file.name)

            logger.info(
                "image_extraction_completed",
                knowledge_id=knowledge_id,
                title=extracted_data["title"],
                filename=filename,
            )

            return {
                "success": True,
                "knowledge_id": knowledge_id,
                "title": extracted_data["title"],
                "description": extracted_data["description"],
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
                title_response = self.gemini_client.models.generate_content(
                    model=self.model,
                    contents=[
                        f"Generate a concise title (max 10 words) for this text:\n\n{text[:500]}"
                    ],
                )
                title = title_response.text.strip()

            # Generate knowledge ID
            knowledge_id = f"text_{hash(text[:100])}_{user_id}"

            # Store in vector database
            self.vector_store.add_knowledge_item(
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
