"""
Enhanced PDF Extractor - Page-Level OCR Decisions
Reuses ImageExtractor for OCR to avoid code duplication
"""

import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Tuple

import pdfplumber
from pdf2image import convert_from_path

from shared.utils.logger import get_logger

logger = get_logger(__name__)


class PDFExtractor:
    """
    CPU-optimized PDF extractor with page-level OCR decisions.

    Flow:
    1. pdfplumber - Zero ML, fastest path (always try first)
    2. Text Quality Check - Heuristic (low char density / broken layout)
    3. Page Filter - OCR is per-page, not per-doc
    4. ImageExtractor - Reuse existing OCR logic
    5. Confidence Scoring - Avoid over-processing
    6. Merge Text - Preserves reading order

    Sweet-spot: OCR should feel like a surgical tool, not a conveyor belt
    """

    def __init__(self, char_density_threshold: float = 10.0):
        """
        Initialize PDF extractor.

        Args:
            char_density_threshold: Chars per page to consider "good text"
        """
        self.char_density_threshold = char_density_threshold
        self._image_extractor = None  # Lazy load to avoid circular imports

    @property
    def image_extractor(self):
        """Lazy load ImageExtractor for PDF page OCR."""
        if self._image_extractor is None:
            from .image_extractor import ImageExtractor

            self._image_extractor = ImageExtractor()
            logger.info("ImageExtractor initialized for PDF OCR")
        return self._image_extractor

    def extract(self, pdf_path: str) -> Tuple[str, Dict[str, Any]]:
        """
        Extract text from PDF with page-level OCR decisions.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Tuple of (extracted_text, metadata)
        """
        if not os.path.exists(pdf_path):
            raise ValueError(f"PDF not found: {pdf_path}")

        logger.info(f"Extracting PDF: {pdf_path}")

        all_text = []
        metadata = {
            "extraction_method": [],
            "pages_processed": 0,
            "pages_with_ocr": 0,
            "total_confidence": 0.0,
        }

        try:
            # Step 1: Try pdfplumber (zero ML)
            with pdfplumber.open(pdf_path) as pdf:
                metadata["page_count"] = len(pdf.pages)
                metadata["title"] = pdf.metadata.get("Title", Path(pdf_path).stem)
                metadata["author"] = pdf.metadata.get("Author", "")

                for page_num, page in enumerate(pdf.pages):
                    # Extract text from page
                    page_text = page.extract_text() or ""

                    # Step 2: Text Quality Check (per page)
                    char_density = len(page_text) / max(page.width * page.height, 1)

                    if self._is_good_text(page_text, char_density):
                        # Good text extraction - use pdfplumber
                        all_text.append(page_text)
                        metadata["extraction_method"].append("pdfplumber")
                        metadata["pages_processed"] += 1
                    else:
                        # Step 3: Page Filter - OCR only this page
                        logger.info(
                            f"Page {page_num + 1}: Low quality text, applying OCR..."
                        )

                        # Step 4: Use ImageExtractor for OCR (reuse existing logic)
                        ocr_text, confidence = self._ocr_page_with_image_extractor(
                            pdf_path, page_num
                        )

                        # Step 5: Confidence Scoring
                        if ocr_text:
                            all_text.append(ocr_text)
                            metadata["extraction_method"].append("image_ocr")
                            metadata["pages_with_ocr"] += 1
                            metadata["total_confidence"] += confidence
                        else:
                            logger.warning(f"Page {page_num + 1}: OCR failed, skipping")

                        metadata["pages_processed"] += 1

            # Step 6: Merge Text (preserve reading order)
            combined_text = "\n\n".join(all_text)

            # Calculate average confidence
            if metadata["pages_with_ocr"] > 0:
                metadata["avg_ocr_confidence"] = (
                    metadata["total_confidence"] / metadata["pages_with_ocr"]
                )

            metadata["char_count"] = len(combined_text)
            metadata["word_count"] = len(combined_text.split())

            logger.info(
                f"PDF extraction complete: {metadata['pages_processed']} pages, "
                f"{metadata['pages_with_ocr']} with OCR"
            )

            return combined_text, metadata

        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
            raise RuntimeError(f"Failed to extract PDF: {e}")

    def _is_good_text(self, text: str, char_density: float) -> bool:
        """
        Step 2: Heuristic text quality check.

        Good text criteria:
        - Has enough characters
        - Not heavily garbled
        - Decent char density
        """
        if not text or len(text) < 50:
            return False

        # Check for garbled text (too many special chars)
        alpha_ratio = sum(c.isalnum() or c.isspace() for c in text) / len(text)
        if alpha_ratio < 0.7:
            return False

        # Check char density
        if char_density < (self.char_density_threshold / 10000):
            return False

        return True

    def _ocr_page_with_image_extractor(
        self, pdf_path: str, page_num: int
    ) -> Tuple[str, float]:
        """
        Step 4: OCR a single PDF page using ImageExtractor.

        This reuses the ImageExtractor logic instead of duplicating RapidOCR code.
        Follows DRY principle and ensures consistent preprocessing across all images.

        Args:
            pdf_path: Path to PDF file
            page_num: Page number (0-indexed)

        Returns:
            Tuple of (extracted_text, confidence_score)
        """
        temp_image_path = None

        try:
            # Convert PDF page to image
            images = convert_from_path(
                pdf_path,
                first_page=page_num + 1,
                last_page=page_num + 1,
                dpi=200,  # Balance quality/speed
            )

            if not images:
                return "", 0.0

            # Save to temp file for ImageExtractor
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                temp_image_path = tmp.name
                images[0].save(temp_image_path, "PNG")

            # Use ImageExtractor for OCR
            # This automatically handles:
            # - Image preprocessing (resize, grayscale, denoise, threshold)
            # - RapidOCR with ONNX Runtime
            # - Language detection
            # - Confidence gating
            # - Text normalization
            text, ocr_metadata = self.image_extractor.extract(temp_image_path)

            confidence = ocr_metadata.get("avg_confidence", 0.0)

            logger.info(
                f"Page {page_num + 1} OCR: {ocr_metadata.get('line_count', 0)} lines, "
                f"confidence={confidence:.2f}, "
                f"time={ocr_metadata.get('processing_time_ms', 0)}ms"
            )

            return text, confidence

        except Exception as e:
            logger.error(f"Page {page_num + 1} OCR failed: {e}")
            return "", 0.0

        finally:
            # Cleanup temp file
            if temp_image_path and os.path.exists(temp_image_path):
                try:
                    os.unlink(temp_image_path)
                except Exception as e:
                    logger.warning(f"Failed to delete temp file {temp_image_path}: {e}")
