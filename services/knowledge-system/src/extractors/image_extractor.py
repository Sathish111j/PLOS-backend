"""
Enhanced Image Extractor - ONNX Runtime CPU Gold Standard
Uses RapidOCR for best CPU accuracy/latency trade-off
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

import cv2
import numpy as np
from PIL import Image

from shared.utils.logger import get_logger

logger = get_logger(__name__)


class ImageExtractor:
    """
    CPU-optimized image extractor using RapidOCR (ONNX Runtime).

    Flow:
    1. Preprocessing - Resize / Denoise (cheap, improves accuracy)
    2. RapidOCR - ONNX Runtime (best CPU accuracy/latency trade)
    3. Language Detect - Text heuristic (avoid wrong OCR paths)
    4. Confidence Gate - Low confidence → optional retry / flag
    5. Normalize - Text cleanup for stable chunking

    Sweet-spot: ONNX Runtime + PP-OCR models is the current CPU gold standard
    """

    def __init__(self):
        """Initialize image extractor with RapidOCR."""
        self._rapid_ocr = None

    @property
    def rapid_ocr(self):
        """Lazy load RapidOCR."""
        if self._rapid_ocr is None:
            try:
                from rapidocr_onnxruntime import RapidOCR

                self._rapid_ocr = RapidOCR()
                logger.info("RapidOCR initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize RapidOCR: {e}")
                raise RuntimeError(f"RapidOCR initialization failed: {e}")
        return self._rapid_ocr

    def extract(self, image_path: str) -> Tuple[str, Dict[str, Any]]:
        """
        Extract text from image using RapidOCR.

        Args:
            image_path: Path to image file

        Returns:
            Tuple of (extracted_text, metadata)
        """
        if not os.path.exists(image_path):
            raise ValueError(f"Image not found: {image_path}")

        # Validate format
        valid_extensions = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".webp"}
        if Path(image_path).suffix.lower() not in valid_extensions:
            raise ValueError(f"Invalid image format: {image_path}")

        logger.info(f"Extracting text from image: {image_path}")

        try:
            # Step 1: Preprocess image
            img_array = self._load_and_preprocess(image_path)

            # Step 2: RapidOCR (ONNX Runtime)
            result, elapse = self.rapid_ocr(img_array)

            # Extract text and confidence
            text_parts = []
            confidences = []

            if result:
                for line in result:
                    # line format: [bbox, text, confidence]
                    if len(line) >= 3:
                        text_parts.append(line[1])
                        confidences.append(line[2])

            extracted_text = "\n".join(text_parts)
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

            # Step 3: Language Detection (simple heuristic)
            language = self._detect_language(extracted_text)

            # Step 4: Confidence Gate
            if avg_confidence < 0.5:
                logger.warning(f"Low OCR confidence: {avg_confidence:.2f}")

            # Step 5: Normalize text
            extracted_text = self._normalize_text(extracted_text)

            # Metadata
            metadata = {
                "extraction_method": "rapidocr_onnx",
                "file_name": Path(image_path).name,
                "file_size": os.path.getsize(image_path),
                "line_count": len(text_parts),
                "char_count": len(extracted_text),
                "word_count": len(extracted_text.split()),
                "avg_confidence": round(avg_confidence, 3),
                "language": language,
                "processing_time_ms": round(elapse * 1000, 2),
            }

            logger.info(
                f"OCR complete: lines={metadata['line_count']}, "
                f"confidence={metadata['avg_confidence']:.2f}, "
                f"time={metadata['processing_time_ms']}ms"
            )

            return extracted_text, metadata

        except Exception as e:
            logger.error(f"Image extraction failed: {e}")
            raise RuntimeError(f"Failed to extract text from image: {e}")

    def extract_batch(self, image_paths: List[str]) -> List[Tuple[str, Dict]]:
        """
        Extract text from multiple images in batch.

        Args:
            image_paths: List of image file paths

        Returns:
            List of (extracted_text, metadata) tuples
        """
        logger.info(f"Batch extracting from {len(image_paths)} images")

        results = []
        for i, path in enumerate(image_paths):
            try:
                text, metadata = self.extract(path)
                metadata["batch_index"] = i
                results.append((text, metadata))
            except Exception as e:
                logger.warning(f"Failed to extract from image {i} ({path}): {e}")
                # Add placeholder for failed extraction
                results.append(
                    (
                        "",
                        {
                            "batch_index": i,
                            "file_name": Path(path).name,
                            "extraction_error": str(e),
                        },
                    )
                )

        logger.info(
            f"Batch extraction complete: {len(results)}/{len(image_paths)} successful"
        )
        return results

    def _load_and_preprocess(self, image_path: str) -> np.ndarray:
        """
        Step 1: Load and preprocess image for better OCR accuracy.

        Preprocessing:
        - Resize if too large (save computation)
        - Convert to grayscale
        - Denoise
        - Adaptive thresholding
        """
        try:
            # Load image
            img = cv2.imread(image_path)

            if img is None:
                # Try with PIL as fallback
                pil_img = Image.open(image_path)
                img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

            # Resize if too large (max 2048px on longest side)
            height, width = img.shape[:2]
            max_dim = 2048
            if max(height, width) > max_dim:
                scale = max_dim / max(height, width)
                img = cv2.resize(
                    img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA
                )
                logger.debug(
                    f"Resized image: {width}x{height} -> {img.shape[1]}x{img.shape[0]}"
                )

            # Convert to grayscale
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img

            # Denoise
            denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)

            # Adaptive thresholding
            binary = cv2.adaptiveThreshold(
                denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
            )

            return binary

        except Exception as e:
            logger.warning(f"Image preprocessing failed, using original: {e}")
            img = cv2.imread(image_path)
            return img if img is not None else np.array(Image.open(image_path))

    def _detect_language(self, text: str) -> str:
        """
        Step 3: Simple language detection heuristic.

        Avoids wrong OCR paths (e.g., using English model on Chinese text).
        """
        if not text:
            return "unknown"

        # Check for common English words
        english_words = {"the", "a", "an", "is", "are", "was", "were", "have", "has"}
        words = set(text.lower().split())

        if any(word in english_words for word in words):
            return "english"

        # Check for non-Latin characters
        latin_count = sum(1 for c in text if c.isascii() and c.isalpha())
        non_latin_count = sum(1 for c in text if not c.isascii() and c.isalpha())

        if non_latin_count > latin_count:
            return "non_english"

        return "english"

    def _normalize_text(self, text: str) -> str:
        """
        Step 5: Text normalization for stable chunking.
        """
        if not text:
            return ""

        import re

        # Remove excessive whitespace
        text = re.sub(r"\n\s*\n", "\n\n", text)
        text = re.sub(r" +", " ", text)

        # Remove control characters
        text = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f]", "", text)

        return text.strip()
